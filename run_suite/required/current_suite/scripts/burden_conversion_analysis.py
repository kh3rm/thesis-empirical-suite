from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from batch_utils import dump_json, load_json, thesis_supporting_dir, write_csv


METRICS: list[tuple[str, str]] = [
    ("peak_unresolved_share_mean", "peak_unresolved_share"),
    ("unresolved_area_share_seconds_mean", "unresolved_area_share_seconds"),
    ("half_repayment_seconds_after_peak_mean", "half_repayment_seconds_after_peak"),
    ("mean_unresolved_share_mean", "mean_unresolved_share"),
]

PAIR_SPECS: list[dict[str, str]] = [
    {
        "label": "degradation_moderate_vs_backlog_shock",
        "lhs_family": "degradation",
        "lhs_severity": "moderate",
        "rhs_family": "backlog_shock",
        "rhs_severity": "standard",
        "interpretation": "Tests whether broad persistent lateness or concentrated catch-up burden is more destructive under the same configuration.",
    },
    {
        "label": "degradation_high_vs_degradation_moderate",
        "lhs_family": "degradation",
        "lhs_severity": "high",
        "rhs_family": "degradation",
        "rhs_severity": "moderate",
        "interpretation": "Tests whether endpoint-like severe degradation stays aligned with the same burden signals as the broad-lateness moderate case.",
    },
]


def merge_rows(
    scenario_rows: list[dict[str, Any]],
    unresolved_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    unresolved_by_id = {str(row.get("scenario_id")): row for row in unresolved_rows if row.get("scenario_id")}
    merged: list[dict[str, Any]] = []
    for scenario in scenario_rows:
        if str(scenario.get("boundary_type")) != "deadline_constrained":
            continue
        scenario_id = str(scenario.get("scenario_id"))
        unresolved = unresolved_by_id.get(scenario_id)
        if unresolved is None:
            continue
        merged.append({
            "scenario_id": scenario_id,
            "base_scenario_id": scenario.get("base_scenario_id", scenario_id),
            "boundary_type": scenario.get("boundary_type"),
            "deadline_window_seconds": scenario.get("deadline_window_seconds"),
            "configuration": scenario.get("configuration"),
            "family": scenario.get("family"),
            "severity": scenario.get("severity"),
            "scenario_role": scenario.get("scenario_role"),
            "scenario_role_detail": scenario.get("scenario_role_detail"),
            "scenario_display_label": scenario.get("scenario_display_label"),
            "repeat_count": scenario.get("repeat_count"),
            "expired_rate_mean": scenario.get("expired_rate_mean"),
            "completed_in_time_rate_mean": scenario.get("completed_in_time_rate_mean"),
            "peak_unresolved_share_mean": unresolved.get("peak_unresolved_share_mean"),
            "peak_unresolved_time_seconds_mean": unresolved.get("peak_unresolved_time_seconds_mean"),
            "unresolved_area_share_seconds_mean": unresolved.get("unresolved_area_share_seconds_mean"),
            "mean_unresolved_share_mean": unresolved.get("mean_unresolved_share_mean"),
            "half_repayment_seconds_after_peak_mean": unresolved.get("half_repayment_seconds_after_peak_mean"),
            "final_unresolved_share_mean": unresolved.get("final_unresolved_share_mean"),
            "peak_pending_case_count_mean": unresolved.get("peak_pending_case_count_mean"),
            "peak_after_producer_complete_share": unresolved.get("peak_after_producer_complete_share"),
        })
    merged.sort(key=lambda row: (
        float(row.get("deadline_window_seconds") or 0.0),
        str(row.get("configuration") or ""),
        str(row.get("family") or ""),
        str(row.get("severity") or ""),
    ))
    return merged


def metric_value(row: dict[str, Any], field: str) -> float | None:
    raw = row.get(field)
    if raw is None:
        return None
    try:
        return float(raw)
    except Exception:
        return None


def expiry_order(lhs: dict[str, Any], rhs: dict[str, Any]) -> str:
    left = metric_value(lhs, "expired_rate_mean")
    right = metric_value(rhs, "expired_rate_mean")
    if left is None or right is None:
        return "unknown"
    if abs(left - right) < 1e-12:
        return "tie"
    return "lhs" if left > right else "rhs"


def compare_metric(lhs: dict[str, Any], rhs: dict[str, Any], field: str) -> str:
    left = metric_value(lhs, field)
    right = metric_value(rhs, field)
    if left is None or right is None:
        return "unknown"
    if abs(left - right) < 1e-12:
        return "tie"
    return "lhs" if left > right else "rhs"


def find_match(rows: list[dict[str, Any]], *, configuration: str, deadline_window_seconds: float | None, family: str, severity: str) -> dict[str, Any] | None:
    for row in rows:
        if str(row.get("configuration")) != configuration:
            continue
        if deadline_window_seconds is not None:
            try:
                if abs(float(row.get("deadline_window_seconds") or 0.0) - deadline_window_seconds) > 1e-9:
                    continue
            except Exception:
                continue
        if str(row.get("family")) != family or str(row.get("severity")) != severity:
            continue
        return row
    return None


def build_pairwise_rows(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    configs = sorted({str(row.get("configuration")) for row in points if row.get("configuration")})
    deadlines = sorted({float(row.get("deadline_window_seconds") or 0.0) for row in points})
    pairwise_rows: list[dict[str, Any]] = []
    for deadline in deadlines:
        for configuration in configs:
            for spec in PAIR_SPECS:
                lhs = find_match(points, configuration=configuration, deadline_window_seconds=deadline, family=spec["lhs_family"], severity=spec["lhs_severity"])
                rhs = find_match(points, configuration=configuration, deadline_window_seconds=deadline, family=spec["rhs_family"], severity=spec["rhs_severity"])
                if lhs is None or rhs is None:
                    continue
                expiry_worse = expiry_order(lhs, rhs)
                row: dict[str, Any] = {
                    "contrast_label": spec["label"],
                    "contrast_interpretation": spec["interpretation"],
                    "deadline_window_seconds": deadline,
                    "configuration": configuration,
                    "lhs_scenario_id": lhs.get("scenario_id"),
                    "lhs_display_label": lhs.get("scenario_display_label"),
                    "lhs_family": lhs.get("family"),
                    "lhs_severity": lhs.get("severity"),
                    "lhs_expired_rate_mean": lhs.get("expired_rate_mean"),
                    "rhs_scenario_id": rhs.get("scenario_id"),
                    "rhs_display_label": rhs.get("scenario_display_label"),
                    "rhs_family": rhs.get("family"),
                    "rhs_severity": rhs.get("severity"),
                    "rhs_expired_rate_mean": rhs.get("expired_rate_mean"),
                    "expiry_worse_side": expiry_worse,
                }
                for field, short_name in METRICS:
                    lhs_value = metric_value(lhs, field)
                    rhs_value = metric_value(rhs, field)
                    row[f"lhs_{short_name}"] = None if lhs_value is None else round(lhs_value, 6)
                    row[f"rhs_{short_name}"] = None if rhs_value is None else round(rhs_value, 6)
                    ordering = compare_metric(lhs, rhs, field)
                    row[f"{short_name}_worse_side"] = ordering
                    row[f"{short_name}_aligned_with_expiry"] = ordering == expiry_worse if expiry_worse not in {"tie", "unknown"} and ordering not in {"tie", "unknown"} else None
                    if lhs_value is not None and rhs_value is not None:
                        row[f"{short_name}_delta_lhs_minus_rhs"] = round(lhs_value - rhs_value, 6)
                pairwise_rows.append(row)
    pairwise_rows.sort(key=lambda row: (float(row["deadline_window_seconds"]), str(row["configuration"]), str(row["contrast_label"])))
    return pairwise_rows


def build_alignment_summary(pairwise_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary_rows: list[dict[str, Any]] = []
    for contrast_label in sorted({str(row.get("contrast_label")) for row in pairwise_rows} | {"overall"}):
        rows = pairwise_rows if contrast_label == "overall" else [row for row in pairwise_rows if str(row.get("contrast_label")) == contrast_label]
        if not rows:
            continue
        base: dict[str, Any] = {
            "contrast_label": contrast_label,
            "pair_count": len(rows),
        }
        best_metric = None
        best_rate = -1.0
        for field, short_name in METRICS:
            aligned = [row for row in rows if row.get(f"{short_name}_aligned_with_expiry") is not None]
            aligned_count = sum(1 for row in aligned if bool(row.get(f"{short_name}_aligned_with_expiry")))
            comparable_count = len(aligned)
            rate = (aligned_count / comparable_count) if comparable_count else 0.0
            base[f"{short_name}_alignment_count"] = aligned_count
            base[f"{short_name}_comparable_pair_count"] = comparable_count
            base[f"{short_name}_alignment_rate"] = round(rate, 6)
            if comparable_count and rate > best_rate:
                best_metric = short_name
                best_rate = rate
        base["best_aligned_metric"] = best_metric
        base["best_aligned_metric_rate"] = None if best_metric is None else round(best_rate, 6)
        summary_rows.append(base)
    return summary_rows


def render_report(points: list[dict[str, Any]], pairwise_rows: list[dict[str, Any]], summary_rows: list[dict[str, Any]], batch_dir: Path) -> None:
    report_lines: list[str] = [
        "# Burden-to-failure conversion analysis",
        "",
        "This report asks which burden dimensions align best with deadline expiry in the current batch.",
        "The intent is not to fit a statistical model, but to compare ordering: when one scenario is more expiry-destructive than another under the same configuration and deadline, which burden metric points in the same direction?",
        "",
        f"- deadline_constrained scenario points: {len(points)}",
        f"- pairwise contrasts evaluated: {len(pairwise_rows)}",
        "",
        "## Alignment summary",
    ]
    for row in summary_rows:
        contrast = row["contrast_label"]
        report_lines.append(f"### {contrast}")
        report_lines.append(f"- pair_count: {row['pair_count']}")
        report_lines.append(f"- best_aligned_metric: {row.get('best_aligned_metric')}")
        report_lines.append(f"- best_aligned_metric_rate: {row.get('best_aligned_metric_rate')}")
        for _field, short_name in METRICS:
            report_lines.append(
                f"- {short_name}: alignment_rate={row.get(f'{short_name}_alignment_rate')} "
                f"({row.get(f'{short_name}_alignment_count')}/{row.get(f'{short_name}_comparable_pair_count')})"
            )
        report_lines.append("")
    (batch_dir / "reports").mkdir(parents=True, exist_ok=True)
    (batch_dir / "reports" / "burden_conversion_analysis.md").write_text("\n".join(report_lines).strip() + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("Usage: burden_conversion_analysis.py <batch_dir>")
    batch_dir = Path(argv[1]).resolve()
    agg_dir = batch_dir / "aggregates"
    thesis_dir = thesis_supporting_dir(batch_dir)

    scenario_path = agg_dir / "scenario_repeat_summary.json"
    unresolved_path = agg_dir / "unresolved_correctness_summary.json"
    if not scenario_path.exists() or not unresolved_path.exists():
        raise SystemExit("Missing required aggregate inputs: scenario_repeat_summary.json and/or unresolved_correctness_summary.json")

    scenario_rows = load_json(scenario_path)
    unresolved_rows = load_json(unresolved_path)
    points = merge_rows(scenario_rows, unresolved_rows)
    pairwise_rows = build_pairwise_rows(points)
    summary_rows = build_alignment_summary(pairwise_rows)

    write_csv(agg_dir / "burden_conversion_points.csv", points)
    dump_json(agg_dir / "burden_conversion_points.json", points)
    write_csv(agg_dir / "burden_conversion_pairwise.csv", pairwise_rows)
    dump_json(agg_dir / "burden_conversion_pairwise.json", pairwise_rows)
    write_csv(agg_dir / "burden_conversion_summary.csv", summary_rows)
    dump_json(agg_dir / "burden_conversion_summary.json", summary_rows)

    write_csv(thesis_dir / "burden_conversion_points.csv", points)
    dump_json(thesis_dir / "burden_conversion_points.json", points)
    write_csv(thesis_dir / "burden_conversion_pairwise.csv", pairwise_rows)
    dump_json(thesis_dir / "burden_conversion_pairwise.json", pairwise_rows)
    write_csv(thesis_dir / "burden_conversion_summary.csv", summary_rows)
    dump_json(thesis_dir / "burden_conversion_summary.json", summary_rows)

    render_report(points, pairwise_rows, summary_rows, batch_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
