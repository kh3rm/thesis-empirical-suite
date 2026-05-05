from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from statistics import mean

from batch_utils import thesis_supporting_dir


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _to_float(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value).strip()
    if text == "":
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def _metric_mean(group_rows: list[dict[str, str]], key: str) -> float:
    return mean(_to_float(r.get(key)) for r in group_rows)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("Usage: state_non_regression_analysis.py <batch_dir>")

    batch_dir = Path(argv[1])
    summary_csv = batch_dir / "aggregates" / "scenario_repeat_summary.csv"
    if not summary_csv.exists():
        raise SystemExit(f"Missing aggregate summary: {summary_csv}")

    rows = _read_csv_rows(summary_csv)
    state = [r for r in rows if r.get("boundary_type") == "state_non_regression"]

    report = batch_dir / "reports" / "state_non_regression_analysis.md"
    report.parent.mkdir(parents=True, exist_ok=True)

    if not state:
        report.write_text("# State non-regression analysis\n\nNo state_non_regression rows were found in this batch.\n", encoding="utf-8")
        return 0

    point_cols = [
        "scenario_id",
        "configuration",
        "family",
        "severity",
        "scenario_display_label",
        "repeat_count",
        "state_latest_version_attainment_rate_mean",
        "state_latest_version_omission_rate_mean",
        "state_obsolete_suppression_rate_mean",
        "state_obsolete_suppression_count_mean",
        "state_outage_exposed_expected_event_count_mean",
        "state_outage_exposed_expected_event_rate_mean",
        "state_outage_exposed_event_count_mean",
        "state_outage_exposed_seen_fraction_of_expected_mean",
        "state_outage_exposed_unseen_count_mean",
        "state_outage_exposed_unseen_fraction_of_expected_mean",
        "state_transient_outage_drop_count_mean",
        "state_transient_outage_drop_fraction_of_expected_mean",
        "state_outage_exposed_loss_count_mean",
        "state_outage_exposed_loss_fraction_of_expected_mean",
        "state_outage_exposed_version_mean",
        "state_forward_resumption_version_mean",
        "state_forward_resumption_entity_count_mean",
        "state_forward_resumption_adequacy_rate_mean",
        "state_forward_resumption_after_loss_count_mean",
        "state_forward_resumption_after_loss_rate_mean",
        "mean_time_to_attainment_seconds_mean",
        "p95_time_to_attainment_seconds_mean",
        "attained_after_producer_complete_share_mean",
    ]
    available_point_cols = [c for c in point_cols if c in state[0]]
    state_points = [{col: row.get(col, "") for col in available_point_cols} for row in sorted(state, key=lambda r: (r.get("family", ""), r.get("configuration", ""), r.get("scenario_id", "")))]
    _write_csv(batch_dir / "aggregates" / "state_non_regression_points.csv", state_points, available_point_cols)
    _write_json(batch_dir / "aggregates" / "state_non_regression_points.json", state_points)

    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in state:
        grouped.setdefault((row.get("family", ""), row.get("scenario_display_label", "")), []).append(row)

    family_summary: list[dict[str, object]] = []
    for (family, label), group_rows in sorted(grouped.items()):
        family_summary.append(
            {
                "family": family,
                "scenario_display_label": label,
                "attainment_rate_mean": _metric_mean(group_rows, "state_latest_version_attainment_rate_mean"),
                "omission_rate_mean": _metric_mean(group_rows, "state_latest_version_omission_rate_mean"),
                "obsolete_suppression_rate_mean": _metric_mean(group_rows, "state_obsolete_suppression_rate_mean"),
                "outage_exposed_expected_event_count_mean": _metric_mean(group_rows, "state_outage_exposed_expected_event_count_mean"),
                "outage_exposed_expected_event_rate_mean": _metric_mean(group_rows, "state_outage_exposed_expected_event_rate_mean"),
                "outage_exposed_seen_event_count_mean": _metric_mean(group_rows, "state_outage_exposed_event_count_mean"),
                "outage_exposed_seen_fraction_of_expected_mean": _metric_mean(group_rows, "state_outage_exposed_seen_fraction_of_expected_mean"),
                "outage_exposed_unseen_count_mean": _metric_mean(group_rows, "state_outage_exposed_unseen_count_mean"),
                "outage_exposed_unseen_fraction_of_expected_mean": _metric_mean(group_rows, "state_outage_exposed_unseen_fraction_of_expected_mean"),
                "transient_outage_drop_count_mean": _metric_mean(group_rows, "state_transient_outage_drop_count_mean"),
                "transient_outage_drop_fraction_of_expected_mean": _metric_mean(group_rows, "state_transient_outage_drop_fraction_of_expected_mean"),
                "outage_exposed_loss_count_mean": _metric_mean(group_rows, "state_outage_exposed_loss_count_mean"),
                "outage_exposed_loss_fraction_of_expected_mean": _metric_mean(group_rows, "state_outage_exposed_loss_fraction_of_expected_mean"),
                "outage_exposed_version_mean": _metric_mean(group_rows, "state_outage_exposed_version_mean"),
                "forward_resumption_version_mean": _metric_mean(group_rows, "state_forward_resumption_version_mean"),
                "forward_resumption_entity_count_mean": _metric_mean(group_rows, "state_forward_resumption_entity_count_mean"),
                "forward_resumption_adequacy_rate_mean": _metric_mean(group_rows, "state_forward_resumption_adequacy_rate_mean"),
                "forward_resumption_after_loss_count_mean": _metric_mean(group_rows, "state_forward_resumption_after_loss_count_mean"),
                "forward_resumption_after_loss_rate_mean": _metric_mean(group_rows, "state_forward_resumption_after_loss_rate_mean"),
                "mean_tta_mean": _metric_mean(group_rows, "mean_time_to_attainment_seconds_mean"),
                "p95_tta_mean": _metric_mean(group_rows, "p95_time_to_attainment_seconds_mean"),
            }
        )

    config_gaps: list[dict[str, object]] = []
    by_scenario: dict[str, dict[str, dict[str, str]]] = {}
    for row in state:
        by_scenario.setdefault(row.get("scenario_display_label", ""), {})[row.get("configuration", "")] = row
    for label, cfg_rows in sorted(by_scenario.items()):
        transient = cfg_rows.get("transient_immediate")
        retained = cfg_rows.get("retained_immediate")
        if not transient or not retained:
            continue
        config_gaps.append(
            {
                "scenario_display_label": label,
                "transient_attainment_rate": _to_float(transient.get("state_latest_version_attainment_rate_mean")),
                "retained_attainment_rate": _to_float(retained.get("state_latest_version_attainment_rate_mean")),
                "attainment_gap_retained_minus_transient": _to_float(retained.get("state_latest_version_attainment_rate_mean")) - _to_float(transient.get("state_latest_version_attainment_rate_mean")),
                "transient_omission_rate": _to_float(transient.get("state_latest_version_omission_rate_mean")),
                "retained_omission_rate": _to_float(retained.get("state_latest_version_omission_rate_mean")),
                "omission_gap_transient_minus_retained": _to_float(transient.get("state_latest_version_omission_rate_mean")) - _to_float(retained.get("state_latest_version_omission_rate_mean")),
                "transient_mean_tta": _to_float(transient.get("mean_time_to_attainment_seconds_mean")),
                "retained_mean_tta": _to_float(retained.get("mean_time_to_attainment_seconds_mean")),
                "transient_outage_exposed_expected_count": _to_float(transient.get("state_outage_exposed_expected_event_count_mean")),
                "retained_outage_exposed_expected_count": _to_float(retained.get("state_outage_exposed_expected_event_count_mean")),
                "transient_outage_exposed_seen_count": _to_float(transient.get("state_outage_exposed_event_count_mean")),
                "retained_outage_exposed_seen_count": _to_float(retained.get("state_outage_exposed_event_count_mean")),
                "transient_outage_exposed_seen_fraction": _to_float(transient.get("state_outage_exposed_seen_fraction_of_expected_mean")),
                "retained_outage_exposed_seen_fraction": _to_float(retained.get("state_outage_exposed_seen_fraction_of_expected_mean")),
                "transient_outage_unseen_count": _to_float(transient.get("state_outage_exposed_unseen_count_mean")),
                "retained_outage_unseen_count": _to_float(retained.get("state_outage_exposed_unseen_count_mean")),
                "transient_outage_drop_count": _to_float(transient.get("state_transient_outage_drop_count_mean")),
                "retained_outage_drop_count": _to_float(retained.get("state_transient_outage_drop_count_mean")),
                "transient_outage_drop_fraction": _to_float(transient.get("state_transient_outage_drop_fraction_of_expected_mean")),
                "retained_outage_drop_fraction": _to_float(retained.get("state_transient_outage_drop_fraction_of_expected_mean")),
                "transient_outage_loss_count": _to_float(transient.get("state_outage_exposed_loss_count_mean")),
                "retained_outage_loss_count": _to_float(retained.get("state_outage_exposed_loss_count_mean")),
                "transient_outage_loss_fraction": _to_float(transient.get("state_outage_exposed_loss_fraction_of_expected_mean")),
                "retained_outage_loss_fraction": _to_float(retained.get("state_outage_exposed_loss_fraction_of_expected_mean")),
                "transient_forward_resumption_count": _to_float(transient.get("state_forward_resumption_entity_count_mean")),
                "retained_forward_resumption_count": _to_float(retained.get("state_forward_resumption_entity_count_mean")),
                "transient_forward_resumption_adequacy": _to_float(transient.get("state_forward_resumption_adequacy_rate_mean")),
                "retained_forward_resumption_adequacy": _to_float(retained.get("state_forward_resumption_adequacy_rate_mean")),
                "transient_forward_resumption_after_loss_rate": _to_float(transient.get("state_forward_resumption_after_loss_rate_mean")),
                "retained_forward_resumption_after_loss_rate": _to_float(retained.get("state_forward_resumption_after_loss_rate_mean")),
            }
        )

    family_fields = list(family_summary[0].keys()) if family_summary else []
    _write_csv(batch_dir / "aggregates" / "state_non_regression_family_summary.csv", family_summary, family_fields)
    _write_json(batch_dir / "aggregates" / "state_non_regression_family_summary.json", family_summary)
    thesis_supporting_dir(batch_dir)
    _write_csv(batch_dir / "aggregates" / "thesis_supporting" / "state_non_regression_family_summary.csv", family_summary, family_fields)

    gap_fields = list(config_gaps[0].keys()) if config_gaps else ["scenario_display_label"]
    _write_csv(batch_dir / "aggregates" / "state_non_regression_configuration_gaps.csv", config_gaps, gap_fields)
    _write_json(batch_dir / "aggregates" / "state_non_regression_configuration_gaps.json", config_gaps)

    def pick_best(metric: str, reverse: bool) -> dict[str, str]:
        return sorted(state, key=lambda r: _to_float(r.get(metric)), reverse=reverse)[0]

    best = pick_best("state_latest_version_attainment_rate_mean", True)
    worst = pick_best("state_latest_version_attainment_rate_mean", False)
    most_obsolete = pick_best("state_obsolete_suppression_rate_mean", True)
    slowest = pick_best("p95_time_to_attainment_seconds_mean", True)
    strongest_gap = sorted(config_gaps, key=lambda r: r.get("omission_gap_transient_minus_retained", 0.0), reverse=True)[0] if config_gaps else None

    lines = [
        "# State non-regression analysis",
        "",
        f"- scenario points: {len(state_points)}",
        f"- configurations: {', '.join(sorted({r.get('configuration', '') for r in state}))}",
        f"- families: {', '.join(sorted({r.get('family', '') for r in state}))}",
        "",
        "## Headlines",
        f"- highest latest-state attainment: {best.get('scenario_id', '')} ({_to_float(best.get('state_latest_version_attainment_rate_mean')):.6f})",
        f"- lowest latest-state attainment: {worst.get('scenario_id', '')} ({_to_float(worst.get('state_latest_version_attainment_rate_mean')):.6f})",
        f"- strongest obsolete-suppression load: {most_obsolete.get('scenario_id', '')} ({_to_float(most_obsolete.get('state_obsolete_suppression_rate_mean')):.6f})",
        f"- slowest p95 attainment: {slowest.get('scenario_id', '')} ({_to_float(slowest.get('p95_time_to_attainment_seconds_mean')):.6f}s)",
        f"- largest retained-vs-transient omission gap: {strongest_gap['scenario_display_label']} ({strongest_gap['omission_gap_transient_minus_retained']:.6f})" if strongest_gap else "- largest retained-vs-transient omission gap: n/a",
        "",
        "## Notes",
        "- expected_exposed is the producer-defined latest-version slice inside the configured outage window.",
        "- seen_exposed is the portion of that slice actually observed by the consumer.",
        "- loss_count = unseen_exposed + explicit_drop_count. This is the stable cross-configuration measure of outage-slice loss.",
        "",
        "## Family summary",
    ]
    for row in family_summary:
        lines.append(
            f"- {row['scenario_display_label']}: attainment={row['attainment_rate_mean']:.6f}, omission={row['omission_rate_mean']:.6f}, obsolete_suppression={row['obsolete_suppression_rate_mean']:.6f}, expected_exposed={row['outage_exposed_expected_event_count_mean']:.3f}, seen_exposed={row['outage_exposed_seen_event_count_mean']:.3f}, seen_fraction={row['outage_exposed_seen_fraction_of_expected_mean']:.6f}, unseen={row['outage_exposed_unseen_count_mean']:.3f}, drop_count={row['transient_outage_drop_count_mean']:.3f}, drop_fraction={row['transient_outage_drop_fraction_of_expected_mean']:.6f}, loss_count={row['outage_exposed_loss_count_mean']:.3f}, loss_fraction={row['outage_exposed_loss_fraction_of_expected_mean']:.6f}, forward_version={row['forward_resumption_version_mean']:.3f}, forward_resumption_count={row['forward_resumption_entity_count_mean']:.3f}, forward_adequacy={row['forward_resumption_adequacy_rate_mean']:.6f}, forward_after_loss_rate={row['forward_resumption_after_loss_rate_mean']:.6f}, mean_tta={row['mean_tta_mean']:.6f}s, p95_tta={row['p95_tta_mean']:.6f}s"
        )
    if config_gaps:
        lines.extend(["", "## Retained vs transient configuration gaps"])
        for row in config_gaps:
            lines.append(
                f"- {row['scenario_display_label']}: transient_omission={row['transient_omission_rate']:.6f}, retained_omission={row['retained_omission_rate']:.6f}, omission_gap={row['omission_gap_transient_minus_retained']:.6f}, transient_expected={row['transient_outage_exposed_expected_count']:.3f}, retained_expected={row['retained_outage_exposed_expected_count']:.3f}, transient_seen={row['transient_outage_exposed_seen_count']:.3f}, retained_seen={row['retained_outage_exposed_seen_count']:.3f}, transient_unseen={row['transient_outage_unseen_count']:.3f}, retained_unseen={row['retained_outage_unseen_count']:.3f}, transient_drop_count={row['transient_outage_drop_count']:.3f}, retained_drop_count={row['retained_outage_drop_count']:.3f}, transient_loss_count={row['transient_outage_loss_count']:.3f}, retained_loss_count={row['retained_outage_loss_count']:.3f}, transient_loss_fraction={row['transient_outage_loss_fraction']:.6f}, retained_loss_fraction={row['retained_outage_loss_fraction']:.6f}, transient_forward_resumption={row['transient_forward_resumption_adequacy']:.6f}, retained_forward_resumption={row['retained_forward_resumption_adequacy']:.6f}, transient_after_loss_forward={row['transient_forward_resumption_after_loss_rate']:.6f}, retained_after_loss_forward={row['retained_forward_resumption_after_loss_rate']:.6f}, transient_attainment={row['transient_attainment_rate']:.6f}, retained_attainment={row['retained_attainment_rate']:.6f}"
            )

    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
