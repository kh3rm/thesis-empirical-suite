from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

from batch_utils import dump_json, thesis_supporting_dir, write_csv


CONFIGURATIONS = ("transient_immediate", "retained_immediate", "retained_deferred")
FAMILIES = ("duplicate_pressure", "omission_pressure", "mixed_pressure")
SEVERITY_RANK = {"low": 0, "medium": 1, "standard": 2, "high": 2, "extreme": 3}
SEVERITY_LABEL = {"low": "low", "medium": "medium", "standard": "high", "high": "high", "extreme": "extreme"}


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def as_float(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key, 0.0))
    except Exception:
        return 0.0


def baseline_runtime_by_configuration(rows: list[dict[str, str]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for config in CONFIGURATIONS:
        baseline_row = None
        for row in rows:
            if row.get("family") == "baseline" and row.get("configuration") == config and row.get("severity") == "standard":
                baseline_row = row
                break
        if baseline_row is None:
            for row in rows:
                if row.get("family") == "baseline" and row.get("configuration") == config:
                    baseline_row = row
                    break
        out[config] = as_float(baseline_row or {}, "run_duration_seconds_mean")
    return out


def severity_key(value: str) -> tuple[int, str]:
    return (SEVERITY_RANK.get(value, 99), value)


def build_guideline_matrix(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    baseline_runtime = baseline_runtime_by_configuration(rows)
    matrix: list[dict[str, Any]] = []
    for row in rows:
        family = row.get("family", "")
        severity = row.get("severity", "")
        config = row.get("configuration", "")
        if family not in FAMILIES or config not in CONFIGURATIONS or severity not in SEVERITY_RANK:
            continue
        duplicate_delivery_count = as_float(row, "duplicate_delivery_count_mean")
        duplicate_after_attainment = as_float(row, "duplicate_after_attainment_count_mean")
        deferred_overwrite = as_float(row, "deferred_pending_overwrite_count_mean")
        duplicate_side_effect_execution = as_float(row, "duplicate_side_effect_execution_count_mean")
        correction_rewrite_count = as_float(row, "correction_rewrite_count_mean")
        wrong_latest_version_commit_count = as_float(row, "wrong_latest_version_commit_count_mean")
        run_duration = as_float(row, "run_duration_seconds_mean")
        reconciliation = as_float(row, "reconciliation_pass_count_mean")
        attainment_rate = as_float(row, "attainment_rate_mean")
        unattained = as_float(row, "unattained_case_count_mean")

        post_attainment_share = 0.0
        pre_settlement_share = 0.0
        if duplicate_delivery_count > 0:
            post_attainment_share = duplicate_after_attainment / duplicate_delivery_count
            pre_settlement_share = deferred_overwrite / duplicate_delivery_count

        runtime_over_baseline = max(0.0, run_duration - baseline_runtime.get(config, 0.0))
        coordination_cost_index = reconciliation + runtime_over_baseline
        correctness_loss_index = unattained + max(0.0, 1.0 - attainment_rate) * 1000.0

        matrix.append(
            {
                "family": family,
                "severity": severity,
                "severity_display": SEVERITY_LABEL.get(severity, severity),
                "severity_rank": SEVERITY_RANK.get(severity, 99),
                "configuration": config,
                "attainment_rate_mean": round(attainment_rate, 6),
                "unattained_case_count_mean": round(unattained, 6),
                "duplicate_delivery_count_mean": round(duplicate_delivery_count, 6),
                "duplicate_after_attainment_count_mean": round(duplicate_after_attainment, 6),
                "deferred_pending_overwrite_count_mean": round(deferred_overwrite, 6),
                "duplicate_side_effect_execution_count_mean": round(duplicate_side_effect_execution, 6),
                "correction_rewrite_count_mean": round(correction_rewrite_count, 6),
                "wrong_latest_version_commit_count_mean": round(wrong_latest_version_commit_count, 6),
                "duplicate_after_attainment_share": round(post_attainment_share, 6),
                "deferred_pending_overwrite_share": round(pre_settlement_share, 6),
                "reconciliation_pass_count_mean": round(reconciliation, 6),
                "run_duration_seconds_mean": round(run_duration, 6),
                "runtime_over_baseline_seconds": round(runtime_over_baseline, 6),
                "coordination_cost_index": round(coordination_cost_index, 6),
                "correctness_loss_index": round(correctness_loss_index, 6),
            }
        )
    matrix.sort(key=lambda row: (row["family"], row["severity_rank"], row["configuration"]))
    return matrix


def recommend_for_duplicate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    immediate_rows = [row for row in rows if row["configuration"] in ("transient_immediate", "retained_immediate")]
    deferred = next((row for row in rows if row["configuration"] == "retained_deferred"), None)
    best_immediate = min(immediate_rows, key=lambda row: (row["duplicate_after_attainment_share"], row["coordination_cost_index"]))
    if deferred is None:
        return {
            "recommended_configuration": best_immediate["configuration"],
            "recommendation_strength": "unclear",
            "reason": "retained_deferred row missing",
            "deferred_improvement_vs_best_immediate": 0.0,
            "deferred_coordination_penalty_vs_best_immediate": 0.0,
            "attainment_spread": 0.0,
        }

    improvement = best_immediate["duplicate_after_attainment_share"] - deferred["duplicate_after_attainment_share"]
    coordination_penalty = deferred["coordination_cost_index"] - best_immediate["coordination_cost_index"]
    correctness_penalty = deferred["correctness_loss_index"] - best_immediate["correctness_loss_index"]

    if improvement >= 0.20 and correctness_penalty <= 1.0:
        recommendation = "retained_deferred"
    else:
        recommendation = best_immediate["configuration"]

    strength = "strong" if abs(improvement) >= 0.20 else "moderate" if abs(improvement) >= 0.10 else "weak"
    reason = (
        f"deferred duplicate-after-attainment share improvement={improvement:.3f}, "
        f"coordination penalty={coordination_penalty:.3f}, correctness penalty={correctness_penalty:.3f}"
    )
    return {
        "recommended_configuration": recommendation,
        "recommendation_strength": strength,
        "reason": reason,
        "deferred_improvement_vs_best_immediate": round(improvement, 6),
        "deferred_coordination_penalty_vs_best_immediate": round(coordination_penalty, 6),
        "attainment_spread": 0.0,
    }


def recommend_for_omission(rows: list[dict[str, Any]]) -> dict[str, Any]:
    immediate_rows = [row for row in rows if row["configuration"] in ("transient_immediate", "retained_immediate")]
    immediate_by_config = {row["configuration"]: row for row in immediate_rows}
    best_immediate = min(immediate_rows, key=lambda row: (row["correctness_loss_index"], row["coordination_cost_index"]))
    best_overall = min(rows, key=lambda row: (row["correctness_loss_index"], row["coordination_cost_index"]))
    deferred = next((row for row in rows if row["configuration"] == "retained_deferred"), None)
    attainment_values = [row["attainment_rate_mean"] for row in rows]
    attainment_spread = max(attainment_values) - min(attainment_values) if attainment_values else 0.0

    # Guard against tiny numerical tie noise: prefer transient/immediate as omission default
    # when immediate variants are practically equal.
    ti_row = immediate_by_config.get("transient_immediate")
    ri_row = immediate_by_config.get("retained_immediate")
    if ti_row is not None and ri_row is not None:
        loss_gap = abs(ti_row["correctness_loss_index"] - ri_row["correctness_loss_index"])
        coordination_gap = abs(ti_row["coordination_cost_index"] - ri_row["coordination_cost_index"])
        if loss_gap <= 1.0 and coordination_gap <= 0.5:
            best_immediate = ti_row

    if deferred is not None and attainment_spread <= 0.005 and deferred["coordination_cost_index"] > (best_immediate["coordination_cost_index"] + 3.0):
        recommendation = best_immediate["configuration"]
    else:
        recommendation = best_overall["configuration"]

    strength = "strong" if attainment_spread <= 0.005 else "moderate"
    reason = (
        f"attainment spread={attainment_spread:.6f}; "
        f"best immediate coordination index={best_immediate['coordination_cost_index']:.3f}; "
        f"best overall correctness-loss index={best_overall['correctness_loss_index']:.3f}"
    )
    return {
        "recommended_configuration": recommendation,
        "recommendation_strength": strength,
        "reason": reason,
        "attainment_spread": round(attainment_spread, 6),
        "deferred_improvement_vs_best_immediate": 0.0,
        "deferred_coordination_penalty_vs_best_immediate": 0.0,
    }


def recommend_for_mixed(rows: list[dict[str, Any]]) -> dict[str, Any]:
    immediate_rows = [row for row in rows if row["configuration"] in ("transient_immediate", "retained_immediate")]
    best_immediate = min(immediate_rows, key=lambda row: (row["correctness_loss_index"], row["coordination_cost_index"]))
    deferred = next((row for row in rows if row["configuration"] == "retained_deferred"), None)
    if deferred is None:
        return {
            "recommended_configuration": best_immediate["configuration"],
            "recommendation_strength": "unclear",
            "reason": "retained_deferred row missing",
            "attainment_spread": 0.0,
            "deferred_improvement_vs_best_immediate": 0.0,
            "deferred_coordination_penalty_vs_best_immediate": 0.0,
        }

    duplicate_relief = best_immediate["duplicate_side_effect_execution_count_mean"] - deferred["duplicate_side_effect_execution_count_mean"]
    immediate_correctness = best_immediate["correctness_loss_index"]
    deferred_correctness = deferred["correctness_loss_index"]
    correctness_gap = abs(immediate_correctness - deferred_correctness)
    deferred_penalty = deferred["coordination_cost_index"] - best_immediate["coordination_cost_index"]

    # Mixed regime policy:
    # - if duplicate side-effect pressure is still small, keep immediate to avoid needless overhead
    # - otherwise switch to retained/deferred when duplicate relief is substantial and correctness is not worse
    if best_immediate["duplicate_side_effect_execution_count_mean"] <= 120:
        recommendation = best_immediate["configuration"]
        strength = "moderate"
        reason = (
            "mixed duplicate side-effect pressure remains low; keep immediate to minimize coordination overhead "
            f"(immediate_dup_side_effect={best_immediate['duplicate_side_effect_execution_count_mean']:.3f})"
        )
    elif duplicate_relief >= 150.0 and deferred_correctness <= (immediate_correctness + 1.0):
        recommendation = "retained_deferred"
        strength = "strong"
        reason = (
            "mixed pressure favors retained/deferred due strong duplicate-side-effect relief "
            f"(relief={duplicate_relief:.3f}, deferred_penalty={deferred_penalty:.3f}, correctness_gap={correctness_gap:.3f})"
        )
    else:
        recommendation = best_immediate["configuration"]
        strength = "unclear"
        reason = (
            "mixed pressure shows no strong deferred advantage under current thresholds "
            f"(relief={duplicate_relief:.3f}, deferred_penalty={deferred_penalty:.3f}, correctness_gap={correctness_gap:.3f})"
        )

    return {
        "recommended_configuration": recommendation,
        "recommendation_strength": strength,
        "reason": reason,
        "attainment_spread": 0.0,
        "deferred_improvement_vs_best_immediate": round(duplicate_relief, 6),
        "deferred_coordination_penalty_vs_best_immediate": round(deferred_penalty, 6),
    }


def build_recommendations(matrix_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in matrix_rows:
        key = (row["family"], row["severity"])
        grouped.setdefault(key, []).append(row)

    recs: list[dict[str, Any]] = []
    for family in FAMILIES:
        for severity in sorted({row["severity"] for row in matrix_rows if row["family"] == family}, key=severity_key):
            key = (family, severity)
            rows = grouped.get(key, [])
            if len(rows) < 2:
                recs.append(
                    {
                        "family": family,
                        "severity": severity,
                        "severity_display": SEVERITY_LABEL.get(severity, severity),
                        "severity_rank": SEVERITY_RANK.get(severity, 99),
                        "recommended_configuration": "unclear",
                        "recommendation_strength": "unclear",
                        "reason": "insufficient rows for recommendation",
                    }
                )
                continue

            if family == "duplicate_pressure":
                payload = recommend_for_duplicate(rows)
            elif family == "omission_pressure":
                payload = recommend_for_omission(rows)
            else:
                payload = recommend_for_mixed(rows)
            recs.append(
                {
                    "family": family,
                    "severity": severity,
                    "severity_display": SEVERITY_LABEL.get(severity, severity),
                    "severity_rank": SEVERITY_RANK.get(severity, 99),
                    **payload,
                }
            )
    recs.sort(key=lambda row: (row["family"], row["severity_rank"]))
    return recs


def duplicate_breakpoint(recommendations: list[dict[str, Any]]) -> str:
    duplicate_rows = [row for row in recommendations if row["family"] == "duplicate_pressure"]
    duplicate_rows.sort(key=lambda row: row["severity_rank"])
    for row in duplicate_rows:
        if row["recommended_configuration"] == "retained_deferred":
            return row["severity_display"]
    return "none"


def render_report(recommendations: list[dict[str, Any]]) -> str:
    lines = [
        "# Required-effect guideline report",
        "",
        "This report focuses on placement guidance by stress severity rather than only class separability.",
        "",
        f"- duplicate breakpoint to retained/deferred: {duplicate_breakpoint(recommendations)}",
        "",
        "## Recommendations by family and severity",
    ]
    for row in recommendations:
        lines.append(
            f"- {row['family']} | {row['severity_display']}: "
            f"recommend={row['recommended_configuration']} "
            f"({row['recommendation_strength']})"
        )
        lines.append(f"  reason: {row['reason']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("Usage: required_effect_guideline_analysis.py <batch_dir>")

    batch_dir = Path(argv[1]).resolve()
    agg_dir = batch_dir / "aggregates"
    thesis_dir = thesis_supporting_dir(batch_dir)
    family_csv = agg_dir / "family_comparison_summary.csv"
    if not family_csv.exists():
        raise SystemExit(f"Missing family summary: {family_csv}")

    rows = load_rows(family_csv)
    matrix = build_guideline_matrix(rows)
    recommendations = build_recommendations(matrix)
    report_md = render_report(recommendations)

    write_csv(agg_dir / "required_effect_guideline_matrix.csv", matrix)
    dump_json(agg_dir / "required_effect_guideline_matrix.json", matrix)
    write_csv(agg_dir / "required_effect_guideline_recommendations.csv", recommendations)
    dump_json(agg_dir / "required_effect_guideline_recommendations.json", recommendations)
    (agg_dir / "required_effect_guideline_report.md").write_text(report_md, encoding="utf-8")

    write_csv(thesis_dir / "required_effect_guideline_matrix.csv", matrix)
    dump_json(thesis_dir / "required_effect_guideline_matrix.json", matrix)
    write_csv(thesis_dir / "required_effect_guideline_recommendations.csv", recommendations)
    dump_json(thesis_dir / "required_effect_guideline_recommendations.json", recommendations)
    (thesis_dir / "required_effect_guideline_report.md").write_text(report_md, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
