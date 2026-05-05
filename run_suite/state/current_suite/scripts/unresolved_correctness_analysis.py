from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from batch_utils import dump_json, thesis_supporting_dir, write_csv


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def trapezoid_area(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    area = 0.0
    for x0, x1, y0, y1 in zip(xs, xs[1:], ys, ys[1:]):
        area += (x1 - x0) * ((y0 + y1) / 2.0)
    return area


def first_time_leq_after(samples: list[dict[str, Any]], start_index: int, threshold: float) -> float | None:
    for row in samples[start_index:]:
        if float(row.get("unresolved_share_observed", 0.0)) <= threshold:
            return float(row.get("elapsed_seconds", 0.0))
    return None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("Usage: unresolved_correctness_analysis.py <batch_dir>")
    batch_dir = Path(argv[1]).resolve()
    raw_runs = batch_dir / "raw_runs"
    agg_dir = batch_dir / "aggregates"
    thesis_dir = thesis_supporting_dir(batch_dir)

    per_run_rows: list[dict[str, Any]] = []
    summary_groups: dict[tuple[str, str, str, float, str, str, str, str], list[dict[str, Any]]] = {}

    for run_dir in sorted(raw_runs.iterdir()):
        if not run_dir.is_dir():
            continue
        spec_path = run_dir / "artifacts" / "run_spec.json"
        trace_path = run_dir / "artifacts" / "unresolved_correctness_trace.jsonl"
        if not spec_path.exists() or not trace_path.exists():
            continue
        spec = load_json(spec_path)
        samples = read_jsonl(trace_path)
        if not samples:
            continue
        samples = sorted(samples, key=lambda r: float(r.get("elapsed_seconds", 0.0)))
        elapsed = [float(r.get("elapsed_seconds", 0.0)) for r in samples]
        unresolved_share = [float(r.get("unresolved_share_observed", 0.0)) for r in samples]
        unresolved_count = [int(r.get("unresolved_count", 0)) for r in samples]
        pending_count = [int(r.get("pending_case_count", 0)) for r in samples]

        peak_idx = max(range(len(samples)), key=lambda i: unresolved_share[i])
        peak_share = unresolved_share[peak_idx]
        peak_count = unresolved_count[peak_idx]
        peak_time = elapsed[peak_idx]
        area_share_seconds = trapezoid_area(elapsed, unresolved_share)
        mean_share = area_share_seconds / elapsed[-1] if elapsed and elapsed[-1] > 0 else 0.0
        final_share = unresolved_share[-1]
        final_count = unresolved_count[-1]

        producer_complete_time = None
        for row in samples:
            if bool(row.get("producer_complete_seen", False)):
                producer_complete_time = float(row.get("elapsed_seconds", 0.0))
                break
        peak_after_producer_complete = producer_complete_time is not None and peak_time >= producer_complete_time
        half_time = first_time_leq_after(samples, peak_idx, peak_share / 2.0) if peak_share > 0 else None
        half_repayment_seconds_after_peak = None if half_time is None else max(0.0, half_time - peak_time)
        pending_peak = max(pending_count) if pending_count else 0

        deadline_window_seconds = float(spec.get("runtime", {}).get("deadline_window_seconds", 0.0) or 0.0)
        row = {
            "run_dir": str(run_dir),
            "scenario_id": spec.get("scenario_id"),
            "base_scenario_id": spec.get("base_scenario_id"),
            "boundary": spec.get("boundary"),
            "deadline_window_seconds": round(deadline_window_seconds, 6),
            "configuration": spec.get("configuration"),
            "family": spec.get("family"),
            "severity": spec.get("severity"),
            "scenario_role": spec.get("scenario_role"),
            "scenario_role_detail": spec.get("scenario_role_detail"),
            "scenario_display_label": spec.get("scenario_display_label"),
            "peak_unresolved_count": peak_count,
            "peak_unresolved_share": round(peak_share, 6),
            "peak_unresolved_time_seconds": round(peak_time, 6),
            "peak_after_producer_complete": bool(peak_after_producer_complete),
            "producer_complete_seen_elapsed_seconds": round(producer_complete_time, 6) if producer_complete_time is not None else None,
            "unresolved_area_share_seconds": round(area_share_seconds, 6),
            "mean_unresolved_share": round(mean_share, 6),
            "half_repayment_seconds_after_peak": None if half_repayment_seconds_after_peak is None else round(half_repayment_seconds_after_peak, 6),
            "final_unresolved_count": final_count,
            "final_unresolved_share": round(final_share, 6),
            "peak_pending_case_count": pending_peak,
        }
        per_run_rows.append(row)
        key = (
            str(row["scenario_id"]),
            str(row.get("base_scenario_id") or row["scenario_id"]),
            str(row["boundary"]),
            float(row.get("deadline_window_seconds") or 0.0),
            str(row["configuration"]),
            str(row["family"]),
            str(row["severity"]),
            str(row["scenario_role_detail"]),
        )
        summary_groups.setdefault(key, []).append(row)

    summary_rows: list[dict[str, Any]] = []
    for key, rows in summary_groups.items():
        scenario_id, base_scenario_id, boundary, deadline_window_seconds, configuration, family, severity, scenario_role_detail = key
        def avg(field: str) -> float:
            vals = [float(r[field]) for r in rows if r.get(field) is not None]
            return round(sum(vals) / len(vals), 6) if vals else 0.0
        summary_rows.append({
            "scenario_id": scenario_id,
            "base_scenario_id": base_scenario_id,
            "boundary": boundary,
            "deadline_window_seconds": round(deadline_window_seconds, 6),
            "configuration": configuration,
            "family": family,
            "severity": severity,
            "scenario_role": rows[0].get("scenario_role"),
            "scenario_role_detail": scenario_role_detail,
            "scenario_display_label": rows[0].get("scenario_display_label"),
            "peak_unresolved_share_mean": avg("peak_unresolved_share"),
            "peak_unresolved_time_seconds_mean": avg("peak_unresolved_time_seconds"),
            "unresolved_area_share_seconds_mean": avg("unresolved_area_share_seconds"),
            "mean_unresolved_share_mean": avg("mean_unresolved_share"),
            "half_repayment_seconds_after_peak_mean": avg("half_repayment_seconds_after_peak"),
            "final_unresolved_share_mean": avg("final_unresolved_share"),
            "peak_pending_case_count_mean": avg("peak_pending_case_count"),
            "peak_after_producer_complete_share": round(sum(1.0 for r in rows if r.get("peak_after_producer_complete")) / len(rows), 6),
        })

    summary_rows.sort(key=lambda r: (r["boundary"], float(r.get("deadline_window_seconds") or 0.0), r["family"], r["severity"], r["configuration"]))
    write_csv(agg_dir / "unresolved_correctness_per_run.csv", per_run_rows)
    dump_json(agg_dir / "unresolved_correctness_per_run.json", per_run_rows)
    write_csv(agg_dir / "unresolved_correctness_summary.csv", summary_rows)
    dump_json(agg_dir / "unresolved_correctness_summary.json", summary_rows)
    write_csv(thesis_dir / "unresolved_correctness_summary.csv", summary_rows)
    dump_json(thesis_dir / "unresolved_correctness_summary.json", summary_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
