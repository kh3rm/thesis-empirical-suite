from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

from batch_utils import dump_json, thesis_supporting_dir


MIN_DUPLICATE_RATE_GAIN = 0.08
MAX_DUPLICATE_UNATTAINED_DELTA = 5.0
MIN_OMISSION_UNATTAINED_DELTA = 80.0
MIN_OMISSION_ATTAINMENT_DROP = 0.08
MIN_SEPARATION_UNATTAINED_GAP = 60.0
MIN_SEPARATION_DUPLICATE_GAP = 0.06

CONFIGURATIONS = ("transient_immediate", "retained_immediate", "retained_deferred")


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def as_float(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key, 0.0))
    except Exception:
        return 0.0


def row_for(rows: list[dict[str, str]], *, family: str, configuration: str) -> dict[str, str] | None:
    for row in rows:
        if row.get("family") == family and row.get("configuration") == configuration and row.get("severity") == "standard":
            return row
    return None


def pattern_status(*, checks: list[bool], fail_guards: list[bool], missing: bool) -> str:
    if missing:
        return "unclear"
    if checks and all(checks):
        return "pass"
    if fail_guards and any(fail_guards):
        return "fail"
    return "unclear"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("Usage: required_effect_focus_analysis.py <batch_dir>")
    batch_dir = Path(argv[1]).resolve()
    agg_dir = batch_dir / "aggregates"
    thesis_dir = thesis_supporting_dir(batch_dir)
    family_csv = agg_dir / "family_comparison_summary.csv"
    if not family_csv.exists():
        raise SystemExit(f"Missing family summary: {family_csv}")

    rows = load_rows(family_csv)
    config_rows: list[dict[str, Any]] = []
    missing_any = False

    for configuration in CONFIGURATIONS:
        baseline = row_for(rows, family="baseline", configuration=configuration)
        duplicate = row_for(rows, family="duplicate_pressure", configuration=configuration)
        omission = row_for(rows, family="omission_pressure", configuration=configuration)
        if baseline is None or duplicate is None or omission is None:
            missing_any = True
            config_rows.append(
                {
                    "configuration": configuration,
                    "missing_rows": {
                        "baseline": baseline is None,
                        "duplicate_pressure": duplicate is None,
                        "omission_pressure": omission is None,
                    },
                }
            )
            continue

        baseline_unattained = as_float(baseline, "unattained_case_count_mean")
        baseline_attainment = as_float(baseline, "attainment_rate_mean")
        baseline_duplicate_rate = as_float(baseline, "duplicate_delivery_rate_mean")

        duplicate_unattained = as_float(duplicate, "unattained_case_count_mean")
        duplicate_attainment = as_float(duplicate, "attainment_rate_mean")
        duplicate_rate = as_float(duplicate, "duplicate_delivery_rate_mean")

        omission_unattained = as_float(omission, "unattained_case_count_mean")
        omission_attainment = as_float(omission, "attainment_rate_mean")
        omission_duplicate_rate = as_float(omission, "duplicate_delivery_rate_mean")

        config_rows.append(
            {
                "configuration": configuration,
                "baseline_unattained": round(baseline_unattained, 6),
                "duplicate_unattained": round(duplicate_unattained, 6),
                "omission_unattained": round(omission_unattained, 6),
                "baseline_attainment_rate": round(baseline_attainment, 6),
                "duplicate_attainment_rate": round(duplicate_attainment, 6),
                "omission_attainment_rate": round(omission_attainment, 6),
                "baseline_duplicate_delivery_rate": round(baseline_duplicate_rate, 6),
                "duplicate_delivery_rate": round(duplicate_rate, 6),
                "omission_duplicate_delivery_rate": round(omission_duplicate_rate, 6),
                "duplicate_rate_gain_vs_baseline": round(duplicate_rate - baseline_duplicate_rate, 6),
                "duplicate_unattained_delta_vs_baseline": round(duplicate_unattained - baseline_unattained, 6),
                "omission_unattained_delta_vs_baseline": round(omission_unattained - baseline_unattained, 6),
                "omission_attainment_drop_vs_baseline": round(baseline_attainment - omission_attainment, 6),
                "separation_unattained_gap_omission_minus_duplicate": round(omission_unattained - duplicate_unattained, 6),
                "separation_duplicate_rate_gap_duplicate_minus_omission": round(duplicate_rate - omission_duplicate_rate, 6),
            }
        )

    valid_rows = [row for row in config_rows if "missing_rows" not in row]

    duplicate_checks = [
        row["duplicate_rate_gain_vs_baseline"] >= MIN_DUPLICATE_RATE_GAIN
        and row["duplicate_unattained_delta_vs_baseline"] <= MAX_DUPLICATE_UNATTAINED_DELTA
        for row in valid_rows
    ]
    duplicate_fail_guards = [
        row["duplicate_rate_gain_vs_baseline"] < (MIN_DUPLICATE_RATE_GAIN / 2.0)
        or row["duplicate_unattained_delta_vs_baseline"] > (MAX_DUPLICATE_UNATTAINED_DELTA * 3.0)
        for row in valid_rows
    ]

    omission_checks = [
        row["omission_unattained_delta_vs_baseline"] >= MIN_OMISSION_UNATTAINED_DELTA
        and row["omission_attainment_drop_vs_baseline"] >= MIN_OMISSION_ATTAINMENT_DROP
        for row in valid_rows
    ]
    omission_fail_guards = [
        row["omission_unattained_delta_vs_baseline"] < (MIN_OMISSION_UNATTAINED_DELTA / 2.0)
        or row["omission_attainment_drop_vs_baseline"] < (MIN_OMISSION_ATTAINMENT_DROP / 2.0)
        for row in valid_rows
    ]

    separation_checks = [
        row["separation_unattained_gap_omission_minus_duplicate"] >= MIN_SEPARATION_UNATTAINED_GAP
        and row["separation_duplicate_rate_gap_duplicate_minus_omission"] >= MIN_SEPARATION_DUPLICATE_GAP
        for row in valid_rows
    ]
    separation_fail_guards = [
        row["separation_unattained_gap_omission_minus_duplicate"] < (MIN_SEPARATION_UNATTAINED_GAP / 3.0)
        or row["separation_duplicate_rate_gap_duplicate_minus_omission"] < (MIN_SEPARATION_DUPLICATE_GAP / 3.0)
        for row in valid_rows
    ]

    pattern_a_status = pattern_status(checks=duplicate_checks, fail_guards=duplicate_fail_guards, missing=missing_any or not valid_rows)
    pattern_b_status = pattern_status(checks=omission_checks, fail_guards=omission_fail_guards, missing=missing_any or not valid_rows)
    pattern_c_status = pattern_status(checks=separation_checks, fail_guards=separation_fail_guards, missing=missing_any or not valid_rows)

    statuses = [pattern_a_status, pattern_b_status, pattern_c_status]
    if "fail" in statuses:
        overall = "fail"
    elif statuses and all(status == "pass" for status in statuses):
        overall = "pass"
    else:
        overall = "unclear"

    payload = {
        "overall_status": overall,
        "thresholds": {
            "min_duplicate_rate_gain_vs_baseline": MIN_DUPLICATE_RATE_GAIN,
            "max_duplicate_unattained_delta_vs_baseline": MAX_DUPLICATE_UNATTAINED_DELTA,
            "min_omission_unattained_delta_vs_baseline": MIN_OMISSION_UNATTAINED_DELTA,
            "min_omission_attainment_drop_vs_baseline": MIN_OMISSION_ATTAINMENT_DROP,
            "min_separation_unattained_gap_omission_minus_duplicate": MIN_SEPARATION_UNATTAINED_GAP,
            "min_separation_duplicate_rate_gap_duplicate_minus_omission": MIN_SEPARATION_DUPLICATE_GAP,
        },
        "patterns": {
            "A_duplicate_discipline": {
                "status": pattern_a_status,
                "expected_signature": "duplicate pressure raises duplicate delivery without materially increasing unattained cases",
            },
            "B_omission_discipline": {
                "status": pattern_b_status,
                "expected_signature": "omission pressure increases unattained cases and lowers attainment",
            },
            "C_duplicate_vs_omission_separation": {
                "status": pattern_c_status,
                "expected_signature": "duplicate and omission produce separable signatures, not one blurred effect",
            },
        },
        "configuration_results": config_rows,
    }

    md_lines = [
        "# Required-effect focused validation",
        "",
        f"- overall_status: {overall}",
        "",
        "## Pattern statuses",
        f"- A duplicate discipline: {pattern_a_status}",
        f"- B omission discipline: {pattern_b_status}",
        f"- C duplicate-vs-omission separation: {pattern_c_status}",
        "",
        "## Configuration values",
    ]
    for row in config_rows:
        configuration = row["configuration"]
        if "missing_rows" in row:
            md_lines.append(f"- {configuration}: missing rows {row['missing_rows']}")
            continue
        md_lines.append(
            "- "
            f"{configuration}: "
            f"dup_rate_gain={row['duplicate_rate_gain_vs_baseline']:.6f}, "
            f"dup_unattained_delta={row['duplicate_unattained_delta_vs_baseline']:.3f}, "
            f"omi_unattained_delta={row['omission_unattained_delta_vs_baseline']:.3f}, "
            f"omi_attainment_drop={row['omission_attainment_drop_vs_baseline']:.6f}, "
            f"sep_unattained_gap={row['separation_unattained_gap_omission_minus_duplicate']:.3f}, "
            f"sep_dup_rate_gap={row['separation_duplicate_rate_gap_duplicate_minus_omission']:.6f}"
        )

    md_text = "\n".join(md_lines) + "\n"
    dump_json(agg_dir / "required_effect_focus_validation.json", payload)
    (agg_dir / "required_effect_focus_validation.md").write_text(md_text, encoding="utf-8")
    dump_json(thesis_dir / "required_effect_focus_validation.json", payload)
    (thesis_dir / "required_effect_focus_validation.md").write_text(md_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
