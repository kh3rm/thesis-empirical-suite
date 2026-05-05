from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from batch_utils import dump_json, load_json, write_csv


def choose_recommendation(rows: list[dict]) -> tuple[dict | None, list[dict]]:
    per_deadline: dict[float, dict[tuple[str, str, str], dict]] = defaultdict(dict)
    for row in rows:
        deadline = float(row.get("deadline_window_seconds_mean", row.get("deadline_window_seconds", 0.0)))
        key = (str(row["family"]), str(row["severity"]), str(row["configuration"]))
        per_deadline[deadline][key] = row

    summaries: list[dict] = []
    for deadline in sorted(per_deadline):
        mapping = per_deadline[deadline]

        def avg(items: list[dict], field: str) -> float:
            return sum(float(i.get(field, 0.0)) for i in items) / len(items) if items else 0.0

        baseline_rows = [v for (f, _s, _c), v in mapping.items() if f == "baseline"]
        degrade_rows = [v for (f, s, _c), v in mapping.items() if f == "degradation" and s == "moderate"]
        mid_rows = [v for (f, s, _c), v in mapping.items() if f == "interrupt_mid" and s == "moderate"]
        late_rows = [v for (f, s, _c), v in mapping.items() if f == "interrupt_late" and s == "moderate"]

        baseline_in = avg(baseline_rows, "completed_in_time_rate_mean")
        baseline_exp = avg(baseline_rows, "expired_rate_mean")
        baseline_lag_p95 = avg(baseline_rows, "completion_lag_from_production_p95_seconds_mean")
        degrade_in = avg(degrade_rows, "completed_in_time_rate_mean")
        degrade_exp = avg(degrade_rows, "expired_rate_mean")
        degrade_lag_p95 = avg(degrade_rows, "completion_lag_from_production_p95_seconds_mean")
        mid_in = avg(mid_rows, "completed_in_time_rate_mean")
        mid_exp = avg(mid_rows, "expired_rate_mean")
        mid_lag_p95 = avg(mid_rows, "completion_lag_from_production_p95_seconds_mean")
        late_in = avg(late_rows, "completed_in_time_rate_mean")
        late_exp = avg(late_rows, "expired_rate_mean")
        late_lag_p95 = avg(late_rows, "completion_lag_from_production_p95_seconds_mean")

        # Deadline should be mostly safe in baseline, but activate on degradation and late-convergence scenarios.
        pressure_score = 3.5 * min(degrade_exp, 0.30) + 3.8 * min(late_exp, 0.30) + 1.5 * min(mid_exp, 0.20)
        baseline_penalty = max(0.0, (0.985 - baseline_in) * 35.0) + baseline_exp * 40.0
        collapse_penalty = 0.0
        for value in (degrade_in, late_in, mid_in):
            if value < 0.55:
                collapse_penalty += (0.55 - value) * 12.0

        discrimination_bonus = 0.0
        if baseline_in >= 0.985 and (degrade_exp > 0.005 or late_exp > 0.005):
            discrimination_bonus += 0.40
        if degrade_exp > 0 and late_exp > 0:
            discrimination_bonus += min(abs(late_exp - degrade_exp), 0.12)
        if late_exp >= mid_exp:
            discrimination_bonus += 0.08

        # Case-relative lag cues help avoid obviously superfluous deadlines.
        lag_alignment_bonus = 0.0
        if baseline_lag_p95 < deadline:
            lag_alignment_bonus += 0.08
        if degrade_lag_p95 > deadline:
            lag_alignment_bonus += 0.12
        if late_lag_p95 > deadline:
            lag_alignment_bonus += 0.12

        score = round(pressure_score + discrimination_bonus + lag_alignment_bonus - baseline_penalty - collapse_penalty, 6)
        summaries.append({
            "deadline_window_seconds": round(deadline, 6),
            "baseline_in_time_rate_mean": round(baseline_in, 6),
            "baseline_expired_rate_mean": round(baseline_exp, 6),
            "baseline_completion_lag_p95_seconds_mean": round(baseline_lag_p95, 6),
            "degradation_moderate_in_time_rate_mean": round(degrade_in, 6),
            "degradation_moderate_expired_rate_mean": round(degrade_exp, 6),
            "degradation_moderate_completion_lag_p95_seconds_mean": round(degrade_lag_p95, 6),
            "body_phase_in_time_rate_mean": round(mid_in, 6),
            "body_phase_expired_rate_mean": round(mid_exp, 6),
            "body_phase_completion_lag_p95_seconds_mean": round(mid_lag_p95, 6),
            "late_convergence_in_time_rate_mean": round(late_in, 6),
            "late_convergence_expired_rate_mean": round(late_exp, 6),
            "late_convergence_completion_lag_p95_seconds_mean": round(late_lag_p95, 6),
            "case_relative_deadline_activation_score": score,
        })

    if not summaries:
        return None, summaries

    summaries_by_score = sorted(
        summaries,
        key=lambda r: (-float(r["case_relative_deadline_activation_score"]), -float(r["baseline_in_time_rate_mean"]), float(r["deadline_window_seconds"])),
    )
    return summaries_by_score[0], sorted(summaries, key=lambda r: float(r["deadline_window_seconds"]))


def build_gloss(row: dict) -> str:
    return (
        f"Baseline stays mostly in-time (in-time={row['baseline_in_time_rate_mean']:.3f}, p95 lag={row['baseline_completion_lag_p95_seconds_mean']:.3f}s), while moderate degradation "
        f"(expiry={row['degradation_moderate_expired_rate_mean']:.3f}, p95 lag={row['degradation_moderate_completion_lag_p95_seconds_mean']:.3f}s) and late-convergence interruption "
        f"(expiry={row['late_convergence_expired_rate_mean']:.3f}, p95 lag={row['late_convergence_completion_lag_p95_seconds_mean']:.3f}s) begin to show deadline pressure under case-relative timing."
    )


def append_report(report_path: Path, summaries: list[dict], recommended: dict | None) -> None:
    if not report_path.exists():
        return
    lines = [report_path.read_text(encoding="utf-8").rstrip(), "", "## Deadline calibration"]
    if recommended is None:
        lines.append("- No calibration recommendation available.")
    else:
        lines.append(f"- Recommended deadline window: {recommended['deadline_window_seconds']} seconds")
        lines.append(f"- Rationale: {build_gloss(recommended)}")
    lines.extend(["", "### Activation preview"])
    for row in summaries:
        lines.append(
            f"- {row['deadline_window_seconds']}s => baseline in-time={row['baseline_in_time_rate_mean']}, baseline p95 lag={row['baseline_completion_lag_p95_seconds_mean']}s, "
            f"degradation high expiry={row['degradation_moderate_expired_rate_mean']} (p95 lag={row['degradation_moderate_completion_lag_p95_seconds_mean']}s), "
            f"body-phase expiry={row['body_phase_expired_rate_mean']} (p95 lag={row['body_phase_completion_lag_p95_seconds_mean']}s), "
            f"late-convergence expiry={row['late_convergence_expired_rate_mean']} (p95 lag={row['late_convergence_completion_lag_p95_seconds_mean']}s), "
            f"score={row['case_relative_deadline_activation_score']}"
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("Usage: deadline_calibration_analysis.py <batch_dir>")
    batch_dir = Path(argv[1])
    agg_dir = batch_dir / "aggregates"
    rows = load_json(agg_dir / "scenario_repeat_summary.json")
    recommended, summaries = choose_recommendation(rows)

    write_csv(agg_dir / "deadline_calibration_summary.csv", summaries)
    dump_json(agg_dir / "deadline_calibration_summary.json", summaries)

    recommendation_payload = {
        "recommended_deadline_window_seconds": None if recommended is None else recommended["deadline_window_seconds"],
        "recommendation": recommended,
        "candidate_windows_evaluated": [row["deadline_window_seconds"] for row in summaries],
        "calibration_basis": "case_relative_completion_lag",
        "explanation": None if recommended is None else build_gloss(recommended),
    }
    dump_json(agg_dir / "deadline_selection_recommendation.json", recommendation_payload)

    lag_rows = []
    for row in summaries:
        lag_rows.append({
            "deadline_window_seconds": row["deadline_window_seconds"],
            "baseline_p95_lag_seconds": row["baseline_completion_lag_p95_seconds_mean"],
            "degradation_moderate_p95_lag_seconds": row["degradation_moderate_completion_lag_p95_seconds_mean"],
            "body_phase_p95_lag_seconds": row["body_phase_completion_lag_p95_seconds_mean"],
            "late_convergence_p95_lag_seconds": row["late_convergence_completion_lag_p95_seconds_mean"],
        })
    write_csv(agg_dir / "case_relative_lag_summary.csv", lag_rows)
    dump_json(agg_dir / "case_relative_lag_summary.json", lag_rows)

    report_dir = batch_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "deadline_calibration_report.md"
    report_lines = ["# Deadline calibration report", "", "This calibration is based on case-relative completion lag from production to terminal outcome.", ""]
    if recommended is None:
        report_lines.append("No recommendation available.")
    else:
        report_lines.append(f"Recommended deadline window: **{recommended['deadline_window_seconds']} seconds**")
        report_lines.append("")
        report_lines.append(build_gloss(recommended))
    report_lines.extend(["", "## Candidate deadlines"])
    for row in summaries:
        report_lines.append(
            f"- {row['deadline_window_seconds']}s: baseline in-time={row['baseline_in_time_rate_mean']}, baseline p95 lag={row['baseline_completion_lag_p95_seconds_mean']}s, "
            f"degradation high expiry={row['degradation_moderate_expired_rate_mean']}, body-phase expiry={row['body_phase_expired_rate_mean']}, "
            f"late-convergence expiry={row['late_convergence_expired_rate_mean']}, score={row['case_relative_deadline_activation_score']}"
        )
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    append_report(batch_dir / "reports" / "summary.md", summaries, recommended)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
