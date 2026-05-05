from __future__ import annotations

import argparse
import csv
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = PACKAGE_ROOT / "verification_reports"


@dataclass(frozen=True)
class CsvComparisonSpec:
    relative_path: str
    key_columns: tuple[str, ...]


@dataclass(frozen=True)
class BatchSpec:
    label: str
    suite_dir: Path
    profile_name: str
    frozen_batch_dir: Path
    comparisons: tuple[CsvComparisonSpec, ...]


BATCH_SPECS = (
    BatchSpec(
        label="deadline",
        suite_dir=PACKAGE_ROOT / "run_suite" / "deadline" / "current_suite",
        profile_name="deadline_n10",
        frozen_batch_dir=PACKAGE_ROOT / "thesis_basis" / "frozen_results" / "deadline" / "deadline_n10",
        comparisons=(
            CsvComparisonSpec("aggregates/family_comparison_summary.csv", ("scenario_id",)),
            CsvComparisonSpec("aggregates/scenario_repeat_summary.csv", ("scenario_id",)),
            CsvComparisonSpec("aggregates/deadline_runtime_semantic_summary.csv", ("scenario_id",)),
            CsvComparisonSpec("aggregates/deadline_runtime_semantic_trace.csv", ("scenario_id", "t_sec")),
        ),
    ),
    BatchSpec(
        label="required",
        suite_dir=PACKAGE_ROOT / "run_suite" / "required" / "current_suite",
        profile_name="required_n10",
        frozen_batch_dir=PACKAGE_ROOT / "thesis_basis" / "frozen_results" / "required" / "required_n10",
        comparisons=(
            CsvComparisonSpec("aggregates/required_effect_clean_matrix.csv", ("family", "severity", "configuration")),
            CsvComparisonSpec("aggregates/scenario_repeat_summary.csv", ("scenario_id",)),
        ),
    ),
    BatchSpec(
        label="state",
        suite_dir=PACKAGE_ROOT / "run_suite" / "state" / "current_suite",
        profile_name="state_n10",
        frozen_batch_dir=PACKAGE_ROOT / "thesis_basis" / "frozen_results" / "state" / "state_n10",
        comparisons=(
            CsvComparisonSpec("aggregates/state_non_regression_points.csv", ("scenario_id",)),
            CsvComparisonSpec("aggregates/state_non_regression_configuration_gaps.csv", ("scenario_display_label",)),
            CsvComparisonSpec("aggregates/scenario_repeat_summary.csv", ("scenario_id",)),
        ),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Confirm canonical reruns against frozen thesis evidence.")
    parser.add_argument(
        "--rerun",
        action="store_true",
        help="Execute the three canonical profiles before comparing the latest batches.",
    )
    parser.add_argument(
        "--report-dir",
        default=str(REPORTS_DIR),
        help="Directory for markdown confirmation reports.",
    )
    return parser.parse_args()


def run_profile(spec: BatchSpec) -> None:
    cmd = ["./run_profile.sh", spec.profile_name]
    print(f"[confirm] rerunning {spec.label}: {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=spec.suite_dir, check=True)


def find_latest_batch(spec: BatchSpec) -> Path:
    batches_dir = spec.suite_dir / "output" / "batches"
    pattern = f"{spec.profile_name}_*"
    candidates = sorted(
        (path for path in batches_dir.glob(pattern) if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"No batch found for profile {spec.profile_name} under {batches_dir}")
    return candidates[0]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def make_key(row: dict[str, str], key_columns: Iterable[str]) -> tuple[str, ...]:
    return tuple(row[column] for column in key_columns)


def try_float(value: str) -> float | None:
    text = value.strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def compare_csv(frozen_path: Path, rerun_path: Path, key_columns: tuple[str, ...]) -> dict:
    frozen_headers, frozen_rows = read_csv(frozen_path)
    rerun_headers, rerun_rows = read_csv(rerun_path)

    result: dict[str, object] = {
        "frozen_path": str(frozen_path.relative_to(PACKAGE_ROOT)),
        "rerun_path": str(rerun_path.relative_to(PACKAGE_ROOT)),
        "key_columns": list(key_columns),
        "status": "identical",
        "header_match": frozen_headers == rerun_headers,
        "frozen_row_count": len(frozen_rows),
        "rerun_row_count": len(rerun_rows),
    }

    if frozen_headers != rerun_headers:
        result["status"] = "different"
        result["missing_headers"] = [header for header in frozen_headers if header not in rerun_headers]
        result["extra_headers"] = [header for header in rerun_headers if header not in frozen_headers]
        return result

    frozen_by_key = {make_key(row, key_columns): row for row in frozen_rows}
    rerun_by_key = {make_key(row, key_columns): row for row in rerun_rows}

    frozen_keys = set(frozen_by_key)
    rerun_keys = set(rerun_by_key)
    missing_keys = sorted(frozen_keys - rerun_keys)
    extra_keys = sorted(rerun_keys - frozen_keys)

    if missing_keys or extra_keys:
        result["status"] = "different"
        result["missing_keys"] = [list(key) for key in missing_keys[:10]]
        result["extra_keys"] = [list(key) for key in extra_keys[:10]]
        result["missing_key_count"] = len(missing_keys)
        result["extra_key_count"] = len(extra_keys)
        return result

    numeric_summaries: list[dict[str, object]] = []
    text_differences: list[dict[str, object]] = []
    max_abs_diff = 0.0

    for column in frozen_headers:
        if column in key_columns:
            continue

        numeric = True
        changed_count = 0
        column_max_abs_diff = 0.0
        worst_key: tuple[str, ...] | None = None

        for key in frozen_by_key:
            frozen_raw = frozen_by_key[key][column]
            rerun_raw = rerun_by_key[key][column]
            frozen_num = try_float(frozen_raw)
            rerun_num = try_float(rerun_raw)

            if frozen_num is None or rerun_num is None:
                numeric = False
                if frozen_raw != rerun_raw:
                    changed_count += 1
                    if len(text_differences) < 20:
                        text_differences.append(
                            {
                                "column": column,
                                "key": list(key),
                                "frozen": frozen_raw,
                                "rerun": rerun_raw,
                            }
                        )
                continue

            diff = abs(frozen_num - rerun_num)
            if diff > 0:
                changed_count += 1
                if diff > column_max_abs_diff:
                    column_max_abs_diff = diff
                    worst_key = key
                    max_abs_diff = max(max_abs_diff, diff)

        if numeric:
            numeric_summaries.append(
                {
                    "column": column,
                    "changed_count": changed_count,
                    "max_abs_diff": column_max_abs_diff,
                    "worst_key": None if worst_key is None else list(worst_key),
                }
            )

    differing_numeric = [item for item in numeric_summaries if item["changed_count"]]
    if differing_numeric or text_differences:
        result["status"] = "different"

    result["max_abs_diff_overall"] = max_abs_diff
    result["differing_numeric_columns"] = sorted(
        differing_numeric,
        key=lambda item: (float(item["max_abs_diff"]), int(item["changed_count"])),
        reverse=True,
    )[:20]
    result["text_differences"] = text_differences
    result["numeric_column_count"] = len(numeric_summaries)
    result["differing_numeric_column_count"] = len(differing_numeric)
    return result


def build_report(batch_results: list[dict]) -> str:
    overall_status = "identical" if all(item["status"] == "identical" for item in batch_results) else "different"
    generated_at = datetime.now().isoformat(timespec="seconds")

    lines = [
        "# Canonical Rerun Confirmation Report",
        "",
        f"- generated_at: `{generated_at}`",
        f"- overall_status: `{overall_status}`",
        "",
    ]

    for batch in batch_results:
        lines.append(f"## {batch['label']}")
        lines.append("")
        lines.append(f"- profile: `{batch['profile_name']}`")
        lines.append(f"- rerun_batch: `{batch['rerun_batch']}`")
        lines.append(f"- frozen_batch: `{batch['frozen_batch']}`")
        lines.append(f"- status: `{batch['status']}`")
        lines.append("")
        for file_result in batch["files"]:
            lines.append(f"### {file_result['relative_path']}")
            lines.append("")
            lines.append(f"- status: `{file_result['status']}`")
            lines.append(f"- row_count: frozen=`{file_result['frozen_row_count']}` rerun=`{file_result['rerun_row_count']}`")
            lines.append(f"- header_match: `{file_result['header_match']}`")
            if "max_abs_diff_overall" in file_result:
                lines.append(f"- max_abs_diff_overall: `{file_result['max_abs_diff_overall']}`")
            if file_result.get("differing_numeric_columns"):
                lines.append("- differing_numeric_columns:")
                for item in file_result["differing_numeric_columns"][:8]:
                    lines.append(
                        "  "
                        + f"- `{item['column']}` changed_count=`{item['changed_count']}` "
                        + f"max_abs_diff=`{item['max_abs_diff']}` worst_key=`{item['worst_key']}`"
                    )
            if file_result.get("text_differences"):
                lines.append("- text_differences:")
                for item in file_result["text_differences"][:5]:
                    lines.append(
                        "  "
                        + f"- `{item['column']}` key=`{item['key']}` "
                        + f"frozen=`{item['frozen']}` rerun=`{item['rerun']}`"
                    )
            if file_result.get("missing_keys"):
                lines.append(f"- missing_keys: `{file_result['missing_keys']}`")
            if file_result.get("extra_keys"):
                lines.append(f"- extra_keys: `{file_result['extra_keys']}`")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    if args.rerun:
        for spec in BATCH_SPECS:
            run_profile(spec)

    batch_results: list[dict] = []
    for spec in BATCH_SPECS:
        rerun_batch = find_latest_batch(spec)
        file_results: list[dict] = []
        batch_status = "identical"
        for comparison in spec.comparisons:
            frozen_path = spec.frozen_batch_dir / comparison.relative_path
            rerun_path = rerun_batch / comparison.relative_path
            file_result = compare_csv(frozen_path, rerun_path, comparison.key_columns)
            file_result["relative_path"] = comparison.relative_path
            file_results.append(file_result)
            if file_result["status"] != "identical":
                batch_status = "different"

        batch_results.append(
            {
                "label": spec.label,
                "profile_name": spec.profile_name,
                "rerun_batch": str(rerun_batch.relative_to(PACKAGE_ROOT)),
                "frozen_batch": str(spec.frozen_batch_dir.relative_to(PACKAGE_ROOT)),
                "status": batch_status,
                "files": file_results,
            }
        )

    markdown = build_report(batch_results)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_md = report_dir / f"canonical_rerun_confirmation_{timestamp}.md"
    report_md.write_text(markdown, encoding="utf-8")
    print(report_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
