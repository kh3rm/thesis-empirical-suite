from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from batch_utils import dump_json, load_json, mean, median, std, write_csv, parse_env_file, thesis_main_dir, thesis_supporting_dir, internal_aggregates_dir, scenario_display_label, scenario_display_severity, scenario_role_tag

METRIC_FIELDS = [
    "attainment_rate",
    "completed_in_time_count",
    "expired_count",
    "completed_in_time_rate",
    "expired_rate",
    "terminal_resolution_rate",
    "completion_lag_from_production_mean_seconds",
    "completion_lag_from_production_p50_seconds",
    "completion_lag_from_production_p90_seconds",
    "completion_lag_from_production_p95_seconds",
    "completion_lag_from_production_p99_seconds",
    "median_time_to_completion_in_time",
    "median_time_to_expiry",
    "share_resolved_by_expiry",
    "share_resolved_by_completion",
    "unattained_case_count",
    "all_cases_attained_within_window_flag",
    "observation_window_expired_flag",
    "tta_metrics_censored_flag",
    "mean_time_to_attainment_seconds",
    "p95_time_to_attainment_seconds",
    "p99_time_to_attainment_seconds",
    "p999_time_to_attainment_seconds",
    "attainment_t25_seconds",
    "attainment_t50_seconds",
    "attainment_t75_seconds",
    "attainment_t90_seconds",
    "attainment_t95_seconds",
    "attainment_t99_seconds",
    "early_bulk_window_25_to_50_seconds",
    "main_bulk_window_50_to_75_seconds",
    "bulk_window_25_to_75_seconds",
    "upper_bulk_window_75_to_90_seconds",
    "late_region_window_75_to_95_seconds",
    "tail_window_90_to_99_seconds",
    "straggler_window_95_to_99_seconds",
    "tail_to_bulk_ratio",
    "upper_bulk_to_bulk_ratio",
    "straggler_to_bulk_ratio",
    "last_attainment_seconds",
    "producer_complete_seen_elapsed_seconds",
    "producer_complete_to_last_attainment_seconds",
    "producer_complete_to_p95_seconds",
    "attained_after_producer_complete_share",
    "temporal_clustering_busiest_10pct_interval_share_100ms",
    "temporal_clustering_busiest_10pct_interval_share_250ms",
    "distinct_attainment_timestamps_1ms",
    "distinct_attainment_timestamps_10ms",
    "mean_inter_attainment_gap_ms",
    "inter_attainment_gap_cv",
    "reconciliation_pass_count",
    "retained_buffer_remaining",
    "pending_case_count_remaining",
    "run_duration_seconds",
    "received_event_count",
    "duplicate_delivery_count",
    "duplicate_delivery_rate",
    "duplicate_after_attainment_count",
    "deferred_pending_overwrite_count",
    "duplicate_side_effect_execution_count",
    "correction_rewrite_count",
    "wrong_latest_version_commit_count",
    "state_latest_version_attainment_count",
    "state_latest_version_attainment_rate",
    "state_latest_version_omission_count",
    "state_latest_version_omission_rate",
    "state_obsolete_suppression_count",
    "state_obsolete_suppression_rate",
    "state_same_version_duplicate_count",
    "state_outage_exposed_event_count",
    "state_outage_exposed_event_rate",
    "state_outage_exposed_expected_event_count",
    "state_outage_exposed_expected_event_rate",
    "state_outage_exposed_seen_fraction_of_expected",
    "state_outage_exposed_unseen_count",
    "state_outage_exposed_unseen_fraction_of_expected",
    "state_transient_outage_drop_count",
    "state_transient_outage_drop_rate",
    "state_transient_outage_drop_fraction_of_expected",
    "state_outage_exposed_loss_count",
    "state_outage_exposed_loss_fraction_of_expected",
    "state_outage_exposed_version",
    "state_latest_version_target",
    "state_forward_resumption_version",
    "state_forward_resumption_entity_count",
    "state_forward_resumption_adequacy_rate",
    "state_forward_resumption_after_loss_count",
    "state_forward_resumption_after_loss_rate",
]

FAMILY_LABELS = {
    "baseline": "baseline",
    "degradation": "degradation",
    "interrupt_mid": "body-phase interruption",
    "interrupt_late": "late-convergence interruption",
    "interruption": "interruption",
    "backlog_shock": "backlog shock",
    "backlog_forward_resume": "backlog shock + forward resume",
    "duplicate_pressure": "duplicate pressure",
    "omission_pressure": "omission pressure",
    "mixed_pressure": "mixed pressure",
    "handling_gap_replayable": "handling-gap replayable omission",
    "source_omission": "source omission control",
    "overload_burst": "overload burst",
    "skewed_tail": "skewed-tail delay",
    "retained_tail_diagnostic": "retained-tail diagnostic",
}




ROLE_ALIASES = {
    "synchronized-lateness dominant": "broadly delayed recovery",
    "concentration-dominant": "catch-up surge recovery",
    "convergence-region dominant": "late-convergence fragility",
    "tail-dominant": "straggler-stretch recovery",
    "mean-dominant": "general slowdown",
    "mixed": "mixed burden pattern",
    "mixed/weak": "weak or mixed burden pattern",
}

REGION_ALIASES = {
    "early_bulk": "early recovery body",
    "main_bulk": "main recovery body",
    "upper_bulk": "late recovery body",
    "late_convergence": "near-finish region",
    "tail": "last recovery segment",
    "straggler": "slowest cases",
    None: "n/a",
    "None": "n/a",
}


def role_alias(role: str | None) -> str:
    return ROLE_ALIASES.get(role, role or "n/a")


def region_alias(region: str | None) -> str:
    return REGION_ALIASES.get(region, region or "n/a")


def role_glossary_lines() -> list[str]:
    return [
        "- **Broadly delayed recovery** means much of the attainment curve shifts later together.",
        "- **Catch-up surge recovery** means recovery resumes in a more synchronized burst rather than spreading out smoothly.",
        "- **Late-convergence fragility** means the near-finish region moves more than the average alone would suggest.",
        "- **Straggler-stretch recovery** means the slowest cases stretch more than the rest of the curve.",
        "- **General slowdown** means average recovery time rises without a clearer regional or concentration signature.",
        "- **Mixed burden pattern** means more than one burden type matters at once and no single one dominates cleanly.",
    ]

def family_label(family: str, severity: str) -> str:
    if family == "degradation":
        return scenario_display_label(family, severity)
    label = FAMILY_LABELS.get(family, family.replace("_", " "))
    display_severity = scenario_display_severity(family, severity)
    return label if display_severity == "standard" else f"{label} ({display_severity})"


def read_outcome_payloads(path: Path) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    if not path.exists():
        return payloads
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        try:
            payload = json.loads(line)
            if isinstance(payload, dict):
                payloads.append(payload)
        except Exception:
            continue
    return payloads


def read_outcome_times(path: Path) -> list[float]:
    values: list[float] = []
    for payload in read_outcome_payloads(path):
        try:
            values.append(float(payload.get("resolved_at_seconds", payload.get("attained_at_seconds", 0.0))))
        except Exception:
            continue
    return sorted(values)


def read_completion_lags(path: Path) -> list[float]:
    values: list[float] = []
    for payload in read_outcome_payloads(path):
        raw = payload.get("completion_lag_from_production_seconds")
        if raw is None:
            continue
        try:
            values.append(float(raw))
        except Exception:
            continue
    return sorted(values)


def attainment_time_at_fraction(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    if fraction <= 0:
        return 0.0
    index = max(0, math.ceil(len(values) * fraction) - 1)
    index = min(index, len(values) - 1)
    return float(values[index])


def quantile_from_sorted(values: list[float], fraction: float) -> float:
    return attainment_time_at_fraction(values, fraction)


def collect_batch_coverage(batch_dir: Path) -> dict[str, Any]:
    raw_runs = batch_dir / "raw_runs"
    plan_path = batch_dir / "execution_plan.json"
    planned = load_json(plan_path) if plan_path.exists() else []
    planned_keys = {f"{row['scenario_id']}__rep{int(row['repeat_index']):02d}": row for row in planned if isinstance(row, dict)}
    status_counts: dict[str, int] = defaultdict(int)
    scenario_coverage: dict[str, dict[str, Any]] = defaultdict(lambda: {"planned": 0, "completed": 0, "failed": 0, "missing": 0})
    for run_dir in sorted(raw_runs.iterdir() if raw_runs.exists() else []):
        if not run_dir.is_dir():
            continue
        status = "unknown"
        status_path = run_dir / "run_status.json"
        if status_path.exists():
            try:
                status = str(load_json(status_path).get("status", "unknown"))
            except Exception:
                status = "unknown"
        elif (run_dir / "logs" / "consumer_summary.json").exists():
            status = "completed"
        status_counts[status] += 1
    for key, row in planned_keys.items():
        scenario_coverage[row['scenario_id']]['planned'] += 1
        run_dir = raw_runs / key
        status_path = run_dir / 'run_status.json'
        status = None
        if status_path.exists():
            try:
                status = str(load_json(status_path).get('status'))
            except Exception:
                status = None
        elif (run_dir / 'logs' / 'consumer_summary.json').exists():
            status = 'completed'
        if status == 'completed':
            scenario_coverage[row['scenario_id']]['completed'] += 1
        elif status == 'failed':
            scenario_coverage[row['scenario_id']]['failed'] += 1
        else:
            scenario_coverage[row['scenario_id']]['missing'] += 1
    coverage_rows = []
    for scenario_id, counts in sorted(scenario_coverage.items()):
        coverage_rows.append({"scenario_id": scenario_id, **counts, "coverage_fraction": round(0.0 if counts['planned'] == 0 else counts['completed'] / counts['planned'], 6)})
    return {
        "expected_runs": len(planned_keys) if planned_keys else None,
        "status_counts": dict(status_counts),
        "scenario_coverage_rows": coverage_rows,
    }


def safe_div(numerator: float, denominator: float, floor: float = 1.0) -> float:
    return numerator / max(abs(denominator), floor)


def positive(value: float) -> float:
    return value if value > 0 else 0.0


def window(start: float, end: float) -> float:
    return max(0.0, end - start)


def bin_counts(values: list[float], bucket_width_seconds: float) -> dict[int, int]:
    counts: dict[int, int] = defaultdict(int)
    for value in values:
        counts[int(value / bucket_width_seconds)] += 1
    return dict(counts)


def summarize_series(runs: list[list[float]], bucket_width_seconds: float) -> dict[str, Any]:
    max_bucket = 0
    count_runs = [bin_counts(run, bucket_width_seconds) for run in runs]
    for counts in count_runs:
        if counts:
            max_bucket = max(max_bucket, max(counts.keys()))
    bins = []
    for bucket in range(max_bucket + 1):
        bucket_time = round(bucket * bucket_width_seconds, 6)
        repeated_counts = [counts.get(bucket, 0) for counts in count_runs]
        cumulative = [sum(v for k, v in counts.items() if k <= bucket) for counts in count_runs]
        bins.append({
            "bucket": bucket,
            "seconds": bucket_time,
            "count_mean": round(mean(repeated_counts), 6),
            "count_min": min(repeated_counts) if repeated_counts else 0,
            "count_max": max(repeated_counts) if repeated_counts else 0,
            "count_median": round(median(repeated_counts), 6),
            "cumulative_mean": round(mean(cumulative), 6),
            "cumulative_min": min(cumulative) if cumulative else 0,
            "cumulative_max": max(cumulative) if cumulative else 0,
            "cumulative_median": round(median(cumulative), 6),
        })
    return {"bucket_width_seconds": bucket_width_seconds, "bins": bins}


def scenario_stat_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    base = rows[0]
    row: dict[str, Any] = {
        "scenario_id": base["scenario_id"],
        "base_scenario_id": base.get("base_scenario_id", base["scenario_id"]),
        "boundary_type": base["boundary_type"],
        "deadline_window_seconds": base.get("deadline_window_seconds", 0.0),
        "configuration": base["configuration"],
        "family": base["family"],
        "severity": base["severity"],
        "severity_display": base.get("severity_display", scenario_display_severity(str(base["family"]), str(base["severity"]))),
        "scenario_display_label": base.get("scenario_display_label", family_label(str(base["family"]), str(base["severity"]))),
        "scenario_role": base.get("scenario_role", "main_core"),
        "scenario_role_detail": base.get("scenario_role_detail", scenario_role_tag(str(base["family"]), str(base["severity"]), None)),
        "repeat_count": len(rows),
    }
    for field in METRIC_FIELDS:
        values = [float(r.get(field, 0.0)) for r in rows]
        row[f"{field}_mean"] = round(mean(values), 6)
        row[f"{field}_std"] = round(std(values), 6)
        row[f"{field}_median"] = round(median(values), 6)
    return row


def top_row(rows: list[dict[str, Any]], key: str, positive_only: bool = False) -> dict[str, Any] | None:
    if not rows:
        return None
    row = max(rows, key=lambda r: float(r.get(key, 0.0)))
    if positive_only and float(row.get(key, 0.0)) <= 0:
        return None
    return row


def top_scenario(rows: list[dict[str, Any]], key: str, positive_only: bool = False) -> str | None:
    row = top_row(rows, key, positive_only=positive_only)
    return None if row is None else str(row["scenario_id"])


def bottom_row(rows: list[dict[str, Any]], key: str, negative_only: bool = False) -> dict[str, Any] | None:
    if not rows:
        return None
    row = min(rows, key=lambda r: float(r.get(key, 0.0)))
    if negative_only and float(row.get(key, 0.0)) >= 0:
        return None
    return row


def format_top_line(label: str, row: dict[str, Any] | None, metric_key: str) -> str:
    if not row:
        return f"- {label}: n/a"
    return f"- {label}: {row['scenario_id']} [{family_label(str(row['family']), str(row['severity']))}] ({metric_key}={row.get(metric_key)})"


def region_rankings(delta_row: dict[str, Any]) -> tuple[str, str]:
    region_values = {
        "early_bulk": positive(float(delta_row.get("early_bulk_region_shift", 0.0))),
        "main_bulk": positive(float(delta_row.get("main_bulk_region_shift", 0.0))),
        "upper_bulk": positive(float(delta_row.get("upper_bulk_region_shift", 0.0))),
        "late_convergence": positive(float(delta_row.get("convergence_region_shift", 0.0))),
        "tail": positive(float(delta_row.get("tail_region_shift", 0.0))),
        "straggler": positive(float(delta_row.get("straggler_region_shift", 0.0))),
    }
    ordered = sorted(region_values.items(), key=lambda kv: kv[1], reverse=True)
    primary = ordered[0][0]
    secondary = ordered[1][0] if len(ordered) > 1 else primary
    return primary, secondary


def classify_roles(role_scores: dict[str, float]) -> tuple[str, str | None, str]:
    ordered = sorted(role_scores.items(), key=lambda kv: kv[1], reverse=True)
    top_label, top_value = ordered[0]
    second_label, second_value = ordered[1]
    if top_value <= 0:
        return "mixed/weak", None, "low"
    ratio = float("inf") if second_value <= 0 else top_value / max(second_value, 1e-9)
    gap = top_value - second_value
    if ratio < 1.08 or gap < 0.12:
        return "mixed", second_label if second_value > 0 else None, "low"
    confidence = "high" if (ratio >= 1.28 and gap >= 0.25) else "medium"
    return top_label, (second_label if second_value > 0 else None), confidence


def role_reason(primary_role: str, *, delta_mean: float, delta_p95: float, delta_bulk_window: float,
                delta_upper_bulk_window: float, delta_late_region_window: float, delta_tail_window: float,
                delta_straggler_window: float, delta_gap_cv: float, timestamp_compression_ratio: float,
                delta_t75: float, delta_t90: float, delta_t95: float, delta_t99: float,
                tail_to_bulk_ratio_delta: float, upper_bulk_to_bulk_ratio_delta: float,
                straggler_to_bulk_ratio_delta: float, delta_early_bulk: float, delta_main_bulk: float,
                synchronized_lateness_score: float, concentration_score: float,
                convergence_region_score: float, tail_score: float, straggler_score: float) -> str:
    if primary_role == "synchronized-lateness dominant":
        return (
            f"Broad synchronized lateness dominates: mean={delta_mean:.3f}s, early_bulk={delta_early_bulk:.3f}s, "
            f"main_bulk={delta_main_bulk:.3f}s, upper_bulk={delta_upper_bulk_window:.3f}s, late_region={delta_late_region_window:.3f}s; "
            f"tail_window={delta_tail_window:.3f}s and straggler_window={delta_straggler_window:.3f}s are secondary."
        )
    if primary_role == "concentration-dominant":
        return (
            f"Recovery concentration dominates: gap_cv={delta_gap_cv:.3f}, timestamp_compression_ratio={timestamp_compression_ratio:.3f}, "
            f"with concentration_score={concentration_score:.3f} outweighing curve-shift scores (sync={synchronized_lateness_score:.3f}, conv={convergence_region_score:.3f})."
        )
    if primary_role == "convergence-region dominant":
        return (
            f"Late-convergence region shifts more than the early/main bulk: delta_t75={delta_t75:.3f}s, delta_t90={delta_t90:.3f}s, delta_t95={delta_t95:.3f}s, "
            f"upper_bulk={delta_upper_bulk_window:.3f}s, late_region={delta_late_region_window:.3f}s, while straggler_window={delta_straggler_window:.3f}s remains secondary."
        )
    if primary_role == "tail-dominant":
        return (
            f"True straggler-tail stretch dominates: tail_window={delta_tail_window:.3f}s, straggler_window={delta_straggler_window:.3f}s, tail_to_bulk_ratio_delta={tail_to_bulk_ratio_delta:.3f}, "
            f"straggler_to_bulk_ratio_delta={straggler_to_bulk_ratio_delta:.3f}, with tail_score={tail_score:.3f} and straggler_score={straggler_score:.3f}."
        )
    if primary_role == "mean-dominant":
        return (
            f"Average timing shift dominates: mean={delta_mean:.3f}s and p95={delta_p95:.3f}s rise without a clearer concentration, convergence-region, or tail-specific dominance."
        )
    return "No single burden dimension dominates clearly; changes are mixed or weak across mean, synchronized lateness, concentration, convergence-region, and tail metrics."


def concise_takeaway(primary_role: str, family: str, severity: str) -> str:
    label = family_label(family, severity)
    mapping = {
        "synchronized-lateness dominant": f"{label} behaves mainly as broadly delayed recovery: much of the curve moves later together.",
        "concentration-dominant": f"{label} behaves mainly as catch-up surge recovery: the disturbance bunches cases into a more synchronized resumption.",
        "convergence-region dominant": f"{label} behaves mainly as late-convergence fragility: the near-finish region shifts more than the average alone suggests.",
        "tail-dominant": f"{label} behaves mainly as straggler-stretch recovery: the slowest cases stretch more than the rest of the curve.",
        "mean-dominant": f"{label} behaves mainly as general slowdown without a stronger regional signature.",
        "mixed": f"{label} shows a mixed burden pattern rather than one clearly dominant recovery burden.",
        "mixed/weak": f"{label} shows only a weak or mixed burden pattern in this batch.",
    }
    return mapping.get(primary_role, f"{label} shows a mixed burden pattern.")


def render_aggregate_report(batch_dir: Path, scenario_rows: list[dict[str, Any]], profile_summary: dict[str, Any],
                            delta_rows: list[dict[str, Any]], role_rows: list[dict[str, Any]],
                            curve_rows: list[dict[str, Any]], analysis_ready_rows: list[dict[str, Any]],
                            candidate_findings: list[dict[str, Any]], failed_runs: list[dict[str, Any]]) -> None:
    report_dir = batch_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    families = sorted({family_label(str(row["family"]), str(row["severity"])) for row in scenario_rows})

    top_mean = top_row(delta_rows, "delta_mean_tta", positive_only=True)
    top_p95 = top_row(delta_rows, "delta_p95", positive_only=True)
    top_gap = top_row(delta_rows, "delta_gap_cv", positive_only=True)
    top_shape = top_row(delta_rows, "deferred_shape_gap_vs_same_family_abs", positive_only=True)
    top_unattained = top_row(delta_rows, "delta_unattained_case_count", positive_only=True)
    top_residual = top_row(delta_rows, "residual_backlog_indicator", positive_only=True)
    top_tail_without_mean = top_row(delta_rows, "tail_without_mean_score", positive_only=True)
    top_bulk_window = top_row(delta_rows, "delta_bulk_window_25_to_75", positive_only=True)
    top_upper_bulk_window = top_row(delta_rows, "delta_upper_bulk_window_75_to_90", positive_only=True)
    top_late_region_window = top_row(delta_rows, "delta_late_region_window_75_to_95", positive_only=True)
    top_tail_window = top_row(delta_rows, "delta_tail_window_90_to_99", positive_only=True)
    top_straggler_window = top_row(delta_rows, "delta_straggler_window_95_to_99", positive_only=True)
    top_upper_bulk_region_shift = top_row(delta_rows, "upper_bulk_region_shift", positive_only=True)
    top_convergence_region_shift = top_row(delta_rows, "convergence_region_shift", positive_only=True)
    top_straggler_region_shift = top_row(delta_rows, "straggler_region_shift", positive_only=True)
    top_upper_bulk_compression = bottom_row(delta_rows, "delta_upper_bulk_window_75_to_90", negative_only=True)
    top_late_region_compression = bottom_row(delta_rows, "delta_late_region_window_75_to_95", negative_only=True)
    top_tail_window_compression = bottom_row(delta_rows, "delta_tail_window_90_to_99", negative_only=True)
    top_straggler_compression = bottom_row(delta_rows, "delta_straggler_window_95_to_99", negative_only=True)
    top_tail_bulk_shift = top_row(delta_rows, "tail_to_bulk_ratio_delta", positive_only=True)
    top_upper_bulk_shift = top_row(delta_rows, "upper_bulk_to_bulk_ratio_delta", positive_only=True)
    top_concentration = top_row(role_rows, "concentration_score", positive_only=True)
    top_tail_role = top_row(role_rows, "tail_score", positive_only=True)
    top_bulk_role = top_row(role_rows, "bulk_score", positive_only=True)
    top_sync_lateness = top_row(role_rows, "synchronized_lateness_score", positive_only=True)
    top_convergence_region = top_row(role_rows, "convergence_region_score", positive_only=True)
    top_upper_bulk_displacement = top_row(role_rows, "upper_bulk_displacement_score", positive_only=True)
    top_conv_vs_straggler = top_row(role_rows, "convergence_vs_straggler_score", positive_only=True)
    top_straggler_role = top_row(role_rows, "straggler_score", positive_only=True)

    lines = [
        "# Batch summary",
        "",
        "## Batch headlines",
        f"- total_runs_seen: {profile_summary.get('total_runs_seen', 0)}",
        f"- total_runs_aggregated: {profile_summary.get('total_runs_aggregated', 0)}",
        f"- total_runs_failed_or_incomplete: {profile_summary.get('total_runs_failed_or_incomplete', 0)}",
        f"- total_scenarios: {profile_summary.get('total_scenarios', 0)}",
        f"- highest_variance_scenario: {profile_summary.get('highest_variance_scenario')}",
        f"- highest_variance_std: {profile_summary.get('highest_variance_std')}",
        f"- highest_p99_scenario: {profile_summary.get('highest_p99_scenario')}",
        f"- highest_cluster100_scenario: {profile_summary.get('highest_cluster100_scenario')}",
        f"- highest_unattained_scenario: {profile_summary.get('highest_unattained_scenario')}",
        f"- highest_residual_backlog_scenario: {profile_summary.get('highest_residual_backlog_scenario')}",
        "",
        "## Included families",
    ]
    lines.extend(f"- {family}" for family in families)
    lines.extend([
        "",
        "## Strongest amplifiers",
        format_top_line("largest mean amplification", top_mean, "delta_mean_tta"),
        format_top_line("largest p95 amplification", top_p95, "delta_p95"),
        format_top_line("largest gap-cv amplification", top_gap, "delta_gap_cv"),
        format_top_line("strongest deferred-vs-immediate shape gap", top_shape, "deferred_shape_gap_vs_same_family_abs"),
        format_top_line("largest bulk-window amplifier", top_bulk_window, "delta_bulk_window_25_to_75"),
        format_top_line("largest upper-bulk-window amplifier", top_upper_bulk_window, "delta_upper_bulk_window_75_to_90"),
        format_top_line("largest late-region-window amplifier", top_late_region_window, "delta_late_region_window_75_to_95"),
        format_top_line("largest tail-window amplifier", top_tail_window, "delta_tail_window_90_to_99"),
        format_top_line("largest straggler-window amplifier", top_straggler_window, "delta_straggler_window_95_to_99"),
        format_top_line("largest upper-bulk region shift", top_upper_bulk_region_shift, "upper_bulk_region_shift"),
        format_top_line("largest convergence-region shift", top_convergence_region_shift, "convergence_region_shift"),
        format_top_line("largest straggler-region shift", top_straggler_region_shift, "straggler_region_shift"),
        format_top_line("strongest upper-bulk compression", top_upper_bulk_compression, "delta_upper_bulk_window_75_to_90"),
        format_top_line("strongest late-region compression", top_late_region_compression, "delta_late_region_window_75_to_95"),
        format_top_line("strongest tail-window compression", top_tail_window_compression, "delta_tail_window_90_to_99"),
        format_top_line("strongest straggler compression", top_straggler_compression, "delta_straggler_window_95_to_99"),
        format_top_line("largest tail-to-bulk shift", top_tail_bulk_shift, "tail_to_bulk_ratio_delta"),
        format_top_line("largest upper-bulk-to-bulk shift", top_upper_bulk_shift, "upper_bulk_to_bulk_ratio_delta"),
        format_top_line("strongest tail-without-mean candidate", top_tail_without_mean, "tail_without_mean_score"),
        format_top_line("largest unattained-case increase", top_unattained, "delta_unattained_case_count"),
        format_top_line("largest residual backlog indicator", top_residual, "residual_backlog_indicator"),
        "",
        "## Burden redistribution highlights",
        format_top_line("strongest synchronized-lateness candidate", top_sync_lateness, "synchronized_lateness_score"),
        format_top_line("strongest concentration-sensitive candidate", top_concentration, "concentration_score"),
        format_top_line("strongest convergence-region candidate", top_convergence_region, "convergence_region_score"),
        format_top_line("strongest upper-bulk displacement candidate", top_upper_bulk_displacement, "upper_bulk_displacement_score"),
        format_top_line("strongest convergence-over-straggler candidate", top_conv_vs_straggler, "convergence_vs_straggler_score"),
        format_top_line("strongest tail-sensitive candidate", top_tail_role, "tail_score"),
        format_top_line("strongest straggler-sensitive candidate", top_straggler_role, "straggler_score"),
        format_top_line("strongest bulk-stretch candidate", top_bulk_role, "bulk_score"),
        "",
        "## Candidate findings",
    ])
    for item in candidate_findings[:10]:
        lines.append(f"- {item['label']}: {item['scenario_id']} [{family_label(item['family'], item['severity'])}] — {item.get('explanation', item['finding'])}")
    lines.extend(["", "## How to read the roles"])
    lines.extend(role_glossary_lines())
    lines.extend(["", "## Burden redistribution map"])
    for row in sorted(role_rows, key=lambda r: (r["family"], r["severity"], r["configuration"])):
        lines.append(
            f"- {row['scenario_id']} [{family_label(str(row['family']), str(row['severity']))}] => {row.get('primary_role_label', role_alias(row['primary_role']))}"
            f" ({row['primary_role']})"
            f"; secondary={row.get('secondary_role_label', role_alias(row['secondary_role']))}"
            f" ({row['secondary_role']}); confidence={row['classification_confidence']}"
        )
        lines.append(
            f"  - burden regions: primary={row.get('primary_burden_region_label', region_alias(row.get('primary_burden_region')))}"
            f" ({row.get('primary_burden_region')}), secondary={row.get('secondary_burden_region_label', region_alias(row.get('secondary_burden_region')))}"
            f" ({row.get('secondary_burden_region')})"
        )
        lines.append(f"  - reason: {row['role_reason']}")
    lines.extend(["", "## Family-role cues"])
    for row in sorted(role_rows, key=lambda r: (r["family"], r["severity"], r["configuration"])):
        lines.append(
            f"- {row['scenario_id']} [{family_label(str(row['family']), str(row['severity']))}] => {row.get('primary_role_label', role_alias(row['primary_role']))}"
            f" ({row['primary_role']})"
            f" with {row.get('secondary_role_label', role_alias(row['secondary_role']))} ({row['secondary_role']}) as secondary; confidence={row['classification_confidence']}"
        )
        lines.append(
            f"  - scores: sync={row['synchronized_lateness_score']}, conc={row['concentration_score']}, conv={row['convergence_region_score']}, "
            f"tail={row['tail_score']}, straggler={row['straggler_score']}"
        )
        lines.append(f"  - reason: {row['role_reason']}")
    lines.extend([
        "",
        "## Curve-region cues",
        f"- scenarios_with_any_censoring: {profile_summary.get('scenarios_with_any_censoring', 0)}",
        f"- scenarios_with_any_residual_backlog: {profile_summary.get('scenarios_with_any_residual_backlog', 0)}",
        f"- max_window_expired_repeat_fraction: {profile_summary.get('max_window_expired_repeat_fraction', 0)}",
        "",
        "## Interpretive cautions",
    ])
    if top_tail_role is None or float(top_tail_role.get("tail_score", 0.0)) < 0.75:
        lines.append("- No clean strongly straggler-stretch pattern was observed in this batch; the strongest late effects should be read mainly through near-finish-region and broad lateness signals rather than a pure tail story.")
    if top_convergence_region is not None and top_upper_bulk_displacement is not None:
        lines.append("- Late-convergence scenarios should be read using both near-finish-region and late-recovery-body evidence rather than strict tail metrics alone.")
    if top_upper_bulk_window is None and top_late_region_window is None:
        lines.append("- Some of the strongest late-region effects in this batch appear as region displacement rather than simple window expansion, so region-shift metrics may be more informative than raw window deltas on their own.")
    lines.extend([
        "",
        "## Analysis-ready exports",
        "- aggregates/scenario_repeat_summary.csv",
        "- aggregates/family_comparison_summary.csv",
        "- aggregates/family_delta_summary.csv",
        "- aggregates/family_role_summary.csv",
        "- aggregates/burden_redistribution_summary.csv",
        "- aggregates/scenario_curve_summary.csv",
        "- aggregates/curve_region_summary.csv",
        "- aggregates/analysis_ready_family_summary.csv",
        "- aggregates/candidate_findings.json",
        "- aggregates/profile_summary.json",
    ])
    if failed_runs:
        lines.extend(["", "## Failed or incomplete runs"])
        for item in failed_runs[:20]:
            lines.append(f"- {item['run_id']}: {item['reason']}")
        if len(failed_runs) > 20:
            lines.append(f"- ... and {len(failed_runs)-20} more")
    lines.extend(["", "## Plotting", "- If plots were not generated yet, run plot_batch.sh on this batch later."])
    (report_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("Usage: aggregate_batch.py <batch_dir>")
    batch_dir = Path(argv[1])
    raw_runs = batch_dir / "raw_runs"
    agg_dir = batch_dir / "aggregates"
    agg_dir.mkdir(parents=True, exist_ok=True)

    run_rows: list[dict[str, Any]] = []
    failed_runs: list[dict[str, Any]] = []
    scenario_timeseries: dict[str, list[list[float]]] = defaultdict(list)
    scenario_specs: dict[str, dict[str, Any]] = {}

    for run_dir in sorted(p for p in raw_runs.iterdir() if p.is_dir()):
        try:
            metrics = load_json(run_dir / "artifacts" / "metrics_summary.json")
            shape = load_json(run_dir / "artifacts" / "recovery_shape_summary.json")
            spec = load_json(run_dir / "artifacts" / "run_spec.json")
            outcome_log = run_dir / "logs" / "outcome.log"
            outcome_times = read_outcome_times(outcome_log)
            completion_lags = read_completion_lags(outcome_log)
        except Exception as exc:
            failed_runs.append({"run_id": run_dir.name, "reason": f"artifact_read_failure: {type(exc).__name__}: {exc}"})
            continue

        t25 = attainment_time_at_fraction(outcome_times, 0.25)
        t50 = attainment_time_at_fraction(outcome_times, 0.50)
        t75 = attainment_time_at_fraction(outcome_times, 0.75)
        t90 = attainment_time_at_fraction(outcome_times, 0.90)
        t95 = attainment_time_at_fraction(outcome_times, 0.95)
        t99 = attainment_time_at_fraction(outcome_times, 0.99)
        bulk = window(t25, t75)
        tail = window(t90, t99)
        row = {
            "run_id": run_dir.name,
            "scenario_id": str(spec["scenario_id"]),
            "base_scenario_id": str(spec.get("base_scenario_id", spec["scenario_id"])),
            "boundary_type": str(spec["boundary"]),
            "deadline_window_seconds": float(spec.get("deadline_window_seconds", 0.0)),
            "configuration": str(spec["configuration"]),
            "family": str(spec["family"]),
            "severity": str(spec["severity"]),
            "scenario_role": str(spec.get("scenario_role", "main_core")),
            "scenario_role_detail": str(spec.get("scenario_role_detail", scenario_role_tag(str(spec["family"]), str(spec["severity"]), None))),
            "severity_display": str(spec.get("scenario_display_severity", scenario_display_severity(str(spec["family"]), str(spec["severity"])))),
            "scenario_display_label": str(spec.get("scenario_display_label", scenario_display_label(str(spec["family"]), str(spec["severity"])))),
            "attainment_rate": float(metrics.get("attainment_rate", 0.0)),
            "completed_in_time_count": float(metrics.get("completed_in_time_count", 0.0)),
            "expired_count": float(metrics.get("expired_count", 0.0)),
            "completed_in_time_rate": float(metrics.get("completed_in_time_rate", 0.0)),
            "expired_rate": float(metrics.get("expired_rate", 0.0)),
            "terminal_resolution_rate": float(metrics.get("terminal_resolution_rate", metrics.get("attainment_rate", 0.0))),
            "completion_lag_from_production_mean_seconds": mean(completion_lags),
            "completion_lag_from_production_p50_seconds": quantile_from_sorted(completion_lags, 0.50) if completion_lags else 0.0,
            "completion_lag_from_production_p90_seconds": quantile_from_sorted(completion_lags, 0.90) if completion_lags else 0.0,
            "completion_lag_from_production_p95_seconds": quantile_from_sorted(completion_lags, 0.95) if completion_lags else 0.0,
            "completion_lag_from_production_p99_seconds": quantile_from_sorted(completion_lags, 0.99) if completion_lags else 0.0,
            "median_time_to_completion_in_time": float(metrics.get("median_time_to_completion_in_time", 0.0)),
            "median_time_to_expiry": float(metrics.get("median_time_to_expiry", 0.0)),
            "share_resolved_by_expiry": float(metrics.get("share_resolved_by_expiry", 0.0)),
            "share_resolved_by_completion": float(metrics.get("share_resolved_by_completion", 0.0)),
            "unattained_case_count": float(metrics.get("unattained_case_count", 0.0)),
            "all_cases_attained_within_window_flag": float(metrics.get("all_cases_attained_within_window_flag", 0.0)),
            "observation_window_expired_flag": float(metrics.get("observation_window_expired_flag", 0.0)),
            "tta_metrics_censored_flag": float(metrics.get("tta_metrics_censored_flag", 0.0)),
            "mean_time_to_attainment_seconds": float(metrics.get("mean_time_to_attainment_seconds", 0.0)),
            "p95_time_to_attainment_seconds": float(metrics.get("p95_time_to_attainment_seconds", 0.0)),
            "p99_time_to_attainment_seconds": float(metrics.get("p99_time_to_attainment_seconds", 0.0)),
            "p999_time_to_attainment_seconds": float(metrics.get("p999_time_to_attainment_seconds", 0.0)),
            "attainment_t25_seconds": t25,
            "attainment_t50_seconds": float(metrics.get("attainment_t50_seconds", t50)),
            "attainment_t75_seconds": t75,
            "attainment_t90_seconds": float(metrics.get("attainment_t90_seconds", t90)),
            "attainment_t95_seconds": float(metrics.get("attainment_t95_seconds", t95)),
            "attainment_t99_seconds": t99,
            "early_bulk_window_25_to_50_seconds": window(t25, t50),
            "main_bulk_window_50_to_75_seconds": window(t50, t75),
            "bulk_window_25_to_75_seconds": bulk,
            "upper_bulk_window_75_to_90_seconds": window(t75, t90),
            "late_region_window_75_to_95_seconds": window(t75, t95),
            "tail_window_90_to_99_seconds": tail,
            "straggler_window_95_to_99_seconds": window(t95, t99),
            "tail_to_bulk_ratio": round(safe_div(tail, bulk, floor=0.1), 6),
            "upper_bulk_to_bulk_ratio": round(safe_div(window(t75, t90), bulk, floor=0.1), 6),
            "straggler_to_bulk_ratio": round(safe_div(window(t95, t99), bulk, floor=0.1), 6),
            "last_attainment_seconds": float(metrics.get("last_attainment_seconds", outcome_times[-1] if outcome_times else 0.0)),
            "producer_complete_seen_elapsed_seconds": float(metrics.get("producer_complete_seen_elapsed_seconds", 0.0)),
            "producer_complete_to_last_attainment_seconds": float(metrics.get("producer_complete_to_last_attainment_seconds", 0.0)),
            "producer_complete_to_p95_seconds": float(metrics.get("producer_complete_to_p95_seconds", 0.0)),
            "attained_after_producer_complete_share": float(metrics.get("attained_after_producer_complete_share", 0.0)),
            "temporal_clustering_busiest_10pct_interval_share_100ms": float(shape.get("temporal_clustering_busiest_10pct_interval_share_100ms", shape.get("busiest_10pct_interval_share_100ms", 0.0))),
            "temporal_clustering_busiest_10pct_interval_share_250ms": float(shape.get("temporal_clustering_busiest_10pct_interval_share_250ms", shape.get("busiest_10pct_interval_share_250ms", 0.0))),
            "distinct_attainment_timestamps_1ms": float(shape.get("distinct_attainment_timestamps_1ms", 0.0)),
            "distinct_attainment_timestamps_10ms": float(shape.get("distinct_attainment_timestamps_10ms", 0.0)),
            "mean_inter_attainment_gap_ms": float(shape.get("mean_inter_attainment_gap_ms", 0.0)),
            "inter_attainment_gap_cv": float(shape.get("inter_attainment_gap_cv", 0.0)),
            "reconciliation_pass_count": float(shape.get("reconciliation_pass_count", 0.0)),
            "retained_buffer_remaining": float(metrics.get("retained_buffer_remaining", 0.0)),
            "pending_case_count_remaining": float(metrics.get("pending_case_count_remaining", 0.0)),
            "run_duration_seconds": float(metrics.get("run_duration_seconds", 0.0)),
            "received_event_count": float(metrics.get("received_event_count", 0.0)),
            "duplicate_delivery_count": float(metrics.get("duplicate_delivery_count", 0.0)),
            "duplicate_delivery_rate": float(metrics.get("duplicate_delivery_rate", 0.0)),
            "duplicate_after_attainment_count": float(metrics.get("duplicate_after_attainment_count", 0.0)),
            "deferred_pending_overwrite_count": float(metrics.get("deferred_pending_overwrite_count", 0.0)),
            "duplicate_side_effect_execution_count": float(metrics.get("duplicate_side_effect_execution_count", 0.0)),
            "correction_rewrite_count": float(metrics.get("correction_rewrite_count", 0.0)),
            "wrong_latest_version_commit_count": float(metrics.get("wrong_latest_version_commit_count", 0.0)),
            "state_latest_version_attainment_count": float(metrics.get("state_latest_version_attainment_count", 0.0)),
            "state_latest_version_attainment_rate": float(metrics.get("state_latest_version_attainment_rate", 0.0)),
            "state_latest_version_omission_count": float(metrics.get("state_latest_version_omission_count", 0.0)),
            "state_latest_version_omission_rate": float(metrics.get("state_latest_version_omission_rate", 0.0)),
            "state_obsolete_suppression_count": float(metrics.get("state_obsolete_suppression_count", 0.0)),
            "state_obsolete_suppression_rate": float(metrics.get("state_obsolete_suppression_rate", 0.0)),
            "state_same_version_duplicate_count": float(metrics.get("state_same_version_duplicate_count", 0.0)),
            "state_outage_exposed_event_count": float(metrics.get("state_outage_exposed_event_count", 0.0)),
            "state_outage_exposed_event_rate": float(metrics.get("state_outage_exposed_event_rate", 0.0)),
            "state_outage_exposed_expected_event_count": float(metrics.get("state_outage_exposed_expected_event_count", 0.0)),
            "state_outage_exposed_expected_event_rate": float(metrics.get("state_outage_exposed_expected_event_rate", 0.0)),
            "state_outage_exposed_seen_fraction_of_expected": float(metrics.get("state_outage_exposed_seen_fraction_of_expected", 0.0)),
            "state_outage_exposed_unseen_count": float(metrics.get("state_outage_exposed_unseen_count", 0.0)),
            "state_outage_exposed_unseen_fraction_of_expected": float(metrics.get("state_outage_exposed_unseen_fraction_of_expected", 0.0)),
            "state_transient_outage_drop_count": float(metrics.get("state_transient_outage_drop_count", 0.0)),
            "state_transient_outage_drop_rate": float(metrics.get("state_transient_outage_drop_rate", 0.0)),
            "state_transient_outage_drop_fraction_of_expected": float(metrics.get("state_transient_outage_drop_fraction_of_expected", 0.0)),
            "state_outage_exposed_loss_count": float(metrics.get("state_outage_exposed_loss_count", 0.0)),
            "state_outage_exposed_loss_fraction_of_expected": float(metrics.get("state_outage_exposed_loss_fraction_of_expected", 0.0)),
            "state_outage_exposed_version": float(metrics.get("state_outage_exposed_version", 0.0)),
            "state_latest_version_target": float(metrics.get("state_latest_version_target", 0.0)),
            "state_forward_resumption_version": float(metrics.get("state_forward_resumption_version", 0.0)),
            "state_forward_resumption_entity_count": float(metrics.get("state_forward_resumption_entity_count", 0.0)),
            "state_forward_resumption_adequacy_rate": float(metrics.get("state_forward_resumption_adequacy_rate", 0.0)),
            "state_forward_resumption_after_loss_count": float(metrics.get("state_forward_resumption_after_loss_count", 0.0)),
            "state_forward_resumption_after_loss_rate": float(metrics.get("state_forward_resumption_after_loss_rate", 0.0)),
        }
        run_rows.append(row)
        scenario_timeseries[row["scenario_id"]].append(outcome_times)
        scenario_specs[row["scenario_id"]] = {
            "boundary": row["boundary_type"],
            "base_scenario_id": row["base_scenario_id"],
            "deadline_window_seconds": row["deadline_window_seconds"],
            "configuration": row["configuration"],
            "family": row["family"],
            "severity": row["severity"],
            "scenario_role": row.get("scenario_role", "main_core"),
            "scenario_role_detail": row.get("scenario_role_detail", "main_core"),
            "severity_display": row.get("severity_display", row["severity"]),
            "scenario_display_label": row.get("scenario_display_label", family_label(str(row["family"]), str(row["severity"]))),
        }

    dump_json(agg_dir / "failed_runs.json", failed_runs)
    grouped = defaultdict(list)
    for row in run_rows:
        grouped[row["scenario_id"]].append(row)
    scenario_rows = [scenario_stat_row(rows) for _, rows in sorted(grouped.items())]
    write_csv(agg_dir / "scenario_repeat_summary.csv", scenario_rows)
    dump_json(agg_dir / "scenario_repeat_summary.json", scenario_rows)

    baseline_by_config = {row["configuration"]: row for row in scenario_rows if row["family"] == "baseline"}
    scenario_by_key = {(row["family"], row["severity"], row["configuration"]): row for row in scenario_rows}

    family_rows: list[dict[str, Any]] = []
    delta_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []

    for row in scenario_rows:
        baseline_row = baseline_by_config.get(row["configuration"])
        family_row = dict(row)
        residual_backlog = round(row["retained_buffer_remaining_mean"] + row["pending_case_count_remaining_mean"], 6)
        if baseline_row:
            family_row["mean_tta_delta_vs_same_config_baseline"] = round(row["mean_time_to_attainment_seconds_mean"] - baseline_row["mean_time_to_attainment_seconds_mean"], 6)
            family_row["p95_delta_vs_same_config_baseline"] = round(row["p95_time_to_attainment_seconds_mean"] - baseline_row["p95_time_to_attainment_seconds_mean"], 6)
            family_row["p99_delta_vs_same_config_baseline"] = round(row["p99_time_to_attainment_seconds_mean"] - baseline_row["p99_time_to_attainment_seconds_mean"], 6)
            family_row["cluster100_delta_vs_same_config_baseline"] = round(row["temporal_clustering_busiest_10pct_interval_share_100ms_mean"] - baseline_row["temporal_clustering_busiest_10pct_interval_share_100ms_mean"], 6)
            family_row["gap_cv_delta_vs_same_config_baseline"] = round(row["inter_attainment_gap_cv_mean"] - baseline_row["inter_attainment_gap_cv_mean"], 6)
            family_row["attainment_rate_delta_vs_same_config_baseline"] = round(row["attainment_rate_mean"] - baseline_row["attainment_rate_mean"], 6)
            family_row["unattained_delta_vs_same_config_baseline"] = round(row["unattained_case_count_mean"] - baseline_row["unattained_case_count_mean"], 6)
        else:
            for field in [
                "mean_tta_delta_vs_same_config_baseline", "p95_delta_vs_same_config_baseline", "p99_delta_vs_same_config_baseline",
                "cluster100_delta_vs_same_config_baseline", "gap_cv_delta_vs_same_config_baseline", "attainment_rate_delta_vs_same_config_baseline",
                "unattained_delta_vs_same_config_baseline",
            ]:
                family_row[field] = 0.0
        family_row["residual_backlog_indicator"] = residual_backlog
        family_rows.append(family_row)

        if row["family"] == "baseline" or baseline_row is None:
            continue

        immediate_row = scenario_by_key.get((row["family"], row["severity"], "retained_immediate"))
        deferred_row = scenario_by_key.get((row["family"], row["severity"], "retained_deferred"))
        deferred_shape_gap = 0.0
        if immediate_row and deferred_row:
            deferred_shape_gap = round(float(deferred_row["inter_attainment_gap_cv_mean"]) - float(immediate_row["inter_attainment_gap_cv_mean"]), 6)

        delta_mean = round(row["mean_time_to_attainment_seconds_mean"] - baseline_row["mean_time_to_attainment_seconds_mean"], 6)
        delta_p95 = round(row["p95_time_to_attainment_seconds_mean"] - baseline_row["p95_time_to_attainment_seconds_mean"], 6)
        delta_p99 = round(row["p99_time_to_attainment_seconds_mean"] - baseline_row["p99_time_to_attainment_seconds_mean"], 6)
        delta_t25 = round(row["attainment_t25_seconds_mean"] - baseline_row["attainment_t25_seconds_mean"], 6)
        delta_t50 = round(row["attainment_t50_seconds_mean"] - baseline_row["attainment_t50_seconds_mean"], 6)
        delta_t75 = round(row["attainment_t75_seconds_mean"] - baseline_row["attainment_t75_seconds_mean"], 6)
        delta_t90 = round(row["attainment_t90_seconds_mean"] - baseline_row["attainment_t90_seconds_mean"], 6)
        delta_t95 = round(row["attainment_t95_seconds_mean"] - baseline_row["attainment_t95_seconds_mean"], 6)
        delta_t99 = round(row["attainment_t99_seconds_mean"] - baseline_row["attainment_t99_seconds_mean"], 6)
        delta_early_bulk = round(row["early_bulk_window_25_to_50_seconds_mean"] - baseline_row["early_bulk_window_25_to_50_seconds_mean"], 6)
        delta_main_bulk = round(row["main_bulk_window_50_to_75_seconds_mean"] - baseline_row["main_bulk_window_50_to_75_seconds_mean"], 6)
        delta_bulk_window = round(row["bulk_window_25_to_75_seconds_mean"] - baseline_row["bulk_window_25_to_75_seconds_mean"], 6)
        delta_upper_bulk_window = round(row["upper_bulk_window_75_to_90_seconds_mean"] - baseline_row["upper_bulk_window_75_to_90_seconds_mean"], 6)
        delta_late_region_window = round(row["late_region_window_75_to_95_seconds_mean"] - baseline_row["late_region_window_75_to_95_seconds_mean"], 6)
        delta_tail_window = round(row["tail_window_90_to_99_seconds_mean"] - baseline_row["tail_window_90_to_99_seconds_mean"], 6)
        delta_straggler_window = round(row["straggler_window_95_to_99_seconds_mean"] - baseline_row["straggler_window_95_to_99_seconds_mean"], 6)
        delta_cluster100 = round(row["temporal_clustering_busiest_10pct_interval_share_100ms_mean"] - baseline_row["temporal_clustering_busiest_10pct_interval_share_100ms_mean"], 6)
        delta_cluster250 = round(row["temporal_clustering_busiest_10pct_interval_share_250ms_mean"] - baseline_row["temporal_clustering_busiest_10pct_interval_share_250ms_mean"], 6)
        delta_distinct_1ms = round(row["distinct_attainment_timestamps_1ms_mean"] - baseline_row["distinct_attainment_timestamps_1ms_mean"], 6)
        delta_distinct_10ms = round(row["distinct_attainment_timestamps_10ms_mean"] - baseline_row["distinct_attainment_timestamps_10ms_mean"], 6)
        delta_gap_cv = round(row["inter_attainment_gap_cv_mean"] - baseline_row["inter_attainment_gap_cv_mean"], 6)
        delta_attainment_rate = round(row["attainment_rate_mean"] - baseline_row["attainment_rate_mean"], 6)
        delta_unattained = round(row["unattained_case_count_mean"] - baseline_row["unattained_case_count_mean"], 6)
        delta_window_expired = round(row["observation_window_expired_flag_mean"] - baseline_row["observation_window_expired_flag_mean"], 6)
        delta_last_lag = round(row["producer_complete_to_last_attainment_seconds_mean"] - baseline_row["producer_complete_to_last_attainment_seconds_mean"], 6)

        mean_ratio = round(safe_div(float(row["mean_time_to_attainment_seconds_mean"]), float(baseline_row["mean_time_to_attainment_seconds_mean"]), floor=1.0), 6)
        p95_ratio = round(safe_div(float(row["p95_time_to_attainment_seconds_mean"]), float(baseline_row["p95_time_to_attainment_seconds_mean"]), floor=1.0), 6)
        p99_ratio = round(safe_div(float(row["p99_time_to_attainment_seconds_mean"]), float(baseline_row["p99_time_to_attainment_seconds_mean"]), floor=1.0), 6)
        cluster100_ratio = round(safe_div(float(row["temporal_clustering_busiest_10pct_interval_share_100ms_mean"]), float(baseline_row["temporal_clustering_busiest_10pct_interval_share_100ms_mean"]), floor=0.1), 6)
        gap_cv_ratio = round(safe_div(float(row["inter_attainment_gap_cv_mean"]), float(baseline_row["inter_attainment_gap_cv_mean"]), floor=1.0), 6)
        timestamp_compression_ratio = round(safe_div(float(baseline_row["distinct_attainment_timestamps_1ms_mean"]), float(row["distinct_attainment_timestamps_1ms_mean"]), floor=1.0), 6)
        bulk_window_ratio = round(safe_div(float(row["bulk_window_25_to_75_seconds_mean"]), float(baseline_row["bulk_window_25_to_75_seconds_mean"]), floor=0.1), 6)
        upper_bulk_window_ratio = round(safe_div(float(row["upper_bulk_window_75_to_90_seconds_mean"]), float(baseline_row["upper_bulk_window_75_to_90_seconds_mean"]), floor=0.1), 6)
        late_region_window_ratio = round(safe_div(float(row["late_region_window_75_to_95_seconds_mean"]), float(baseline_row["late_region_window_75_to_95_seconds_mean"]), floor=0.1), 6)
        tail_window_ratio = round(safe_div(float(row["tail_window_90_to_99_seconds_mean"]), float(baseline_row["tail_window_90_to_99_seconds_mean"]), floor=0.1), 6)
        straggler_window_ratio = round(safe_div(float(row["straggler_window_95_to_99_seconds_mean"]), float(baseline_row["straggler_window_95_to_99_seconds_mean"]), floor=0.1), 6)
        tail_to_bulk_ratio_delta = round(float(row["tail_to_bulk_ratio_mean"]) - float(baseline_row["tail_to_bulk_ratio_mean"]), 6)
        tail_to_bulk_amplification_ratio = round(safe_div(float(row["tail_to_bulk_ratio_mean"]), float(baseline_row["tail_to_bulk_ratio_mean"]), floor=0.1), 6)
        upper_bulk_to_bulk_ratio_delta = round(float(row["upper_bulk_to_bulk_ratio_mean"]) - float(baseline_row["upper_bulk_to_bulk_ratio_mean"]), 6)
        upper_bulk_to_bulk_amplification_ratio = round(safe_div(float(row["upper_bulk_to_bulk_ratio_mean"]), float(baseline_row["upper_bulk_to_bulk_ratio_mean"]), floor=0.1), 6)
        straggler_to_bulk_ratio_delta = round(float(row["straggler_to_bulk_ratio_mean"]) - float(baseline_row["straggler_to_bulk_ratio_mean"]), 6)
        straggler_to_bulk_amplification_ratio = round(safe_div(float(row["straggler_to_bulk_ratio_mean"]), float(baseline_row["straggler_to_bulk_ratio_mean"]), floor=0.1), 6)

        tail_without_mean_score = round(max(0.0, delta_p95 - delta_mean) + 0.5 * max(0.0, delta_p99 - delta_p95), 6)
        early_bulk_region_shift = round((delta_t25 + delta_t50) / 2.0, 6)
        main_bulk_region_shift = round((delta_t50 + delta_t75) / 2.0, 6)
        upper_bulk_region_shift = round((delta_t75 + delta_t90) / 2.0, 6)
        convergence_region_shift = round((delta_t75 + delta_t95) / 2.0, 6)
        tail_region_shift = round((delta_t90 + delta_t99) / 2.0, 6)
        straggler_region_shift = round((delta_t95 + delta_t99) / 2.0, 6)

        concentration_base = 0.78 * math.log1p(positive(delta_gap_cv)) + 0.52 * math.log1p(positive(delta_cluster100) * 10.0) + 0.55 * math.log1p(max(0.0, timestamp_compression_ratio - 1.0))
        concentration_penalty = 0.38 * math.log1p(positive(main_bulk_region_shift) + 0.7 * positive(convergence_region_shift) + 0.4 * positive(tail_region_shift))
        concentration_score = round(max(0.0, concentration_base - concentration_penalty), 6)

        mean_score = round(math.log1p(max(0.0, positive(delta_mean) - 0.15 * positive(delta_t75) - 0.10 * positive(delta_t90))), 6)
        bulk_score = round(math.log1p(positive(delta_bulk_window) + 0.40 * positive(delta_early_bulk) + 0.40 * positive(delta_main_bulk)), 6)

        synchronized_lateness_base = math.log1p(positive(delta_mean) + 0.35 * positive(early_bulk_region_shift) + 0.45 * positive(main_bulk_region_shift) + 0.50 * positive(upper_bulk_region_shift) + 0.45 * positive(convergence_region_shift))
        synchronized_lateness_score = 0.0

        upper_bulk_displacement_score = round(math.log1p(0.55 * positive(main_bulk_region_shift) + 0.90 * positive(upper_bulk_region_shift) + 0.75 * positive(convergence_region_shift) + 0.20 * positive(delta_upper_bulk_window)), 6)
        convergence_region_base = math.log1p(0.35 * positive(main_bulk_region_shift) + 0.65 * positive(upper_bulk_region_shift) + 1.00 * positive(convergence_region_shift) + 0.25 * positive(delta_late_region_window) + 0.20 * positive(delta_p95 - delta_mean))
        convergence_region_penalty = 0.28 * math.log1p(positive(delta_gap_cv) + 2.0 * positive(straggler_region_shift) + 1.5 * positive(delta_straggler_window))
        convergence_region_score = round(max(0.0, convergence_region_base - convergence_region_penalty), 6)

        tail_base = math.log1p(0.45 * positive(tail_region_shift) + 0.95 * positive(straggler_region_shift) + 0.55 * positive(delta_tail_window) + 0.90 * positive(delta_straggler_window) + 0.70 * positive(straggler_to_bulk_ratio_delta) + 0.40 * positive(delta_t99 - delta_t95))
        tail_penalty = 0.40 * math.log1p(positive(convergence_region_shift) + positive(upper_bulk_region_shift) + positive(delta_gap_cv))
        tail_score = round(max(0.0, tail_base - tail_penalty), 6)
        straggler_score = round(math.log1p(positive(straggler_region_shift) + 0.85 * positive(delta_straggler_window) + 0.85 * positive(straggler_to_bulk_ratio_delta) + 0.55 * positive(delta_t99 - delta_t95)), 6)

        synchronized_lateness_penalty = 0.22 * math.log1p(positive(delta_gap_cv) + 1.8 * positive(tail_region_shift) + 2.0 * positive(straggler_region_shift))
        synchronized_lateness_score = round(max(0.0, synchronized_lateness_base - synchronized_lateness_penalty), 6)
        convergence_vs_straggler_score = round(max(0.0, convergence_region_score - 0.80 * straggler_score), 6)
        synchronized_vs_tail_score = round(max(0.0, synchronized_lateness_score - 0.65 * tail_score), 6)
        concentration_vs_curve_shift_score = round(max(0.0, concentration_score - 0.30 * synchronized_lateness_score - 0.35 * convergence_region_score), 6)

        role_scores = {
            "mean-dominant": mean_score,
            "synchronized-lateness dominant": synchronized_lateness_score,
            "concentration-dominant": concentration_score,
            "convergence-region dominant": convergence_region_score,
            "tail-dominant": tail_score,
        }
        primary_role, secondary_role, confidence = classify_roles(role_scores)
        reason = role_reason(primary_role,
                             delta_mean=delta_mean,
                             delta_p95=delta_p95,
                             delta_bulk_window=delta_bulk_window,
                             delta_upper_bulk_window=delta_upper_bulk_window,
                             delta_late_region_window=delta_late_region_window,
                             delta_tail_window=delta_tail_window,
                             delta_straggler_window=delta_straggler_window,
                             delta_gap_cv=delta_gap_cv,
                             timestamp_compression_ratio=timestamp_compression_ratio,
                             delta_t75=delta_t75,
                             delta_t90=delta_t90,
                             delta_t95=delta_t95,
                             delta_t99=delta_t99,
                             tail_to_bulk_ratio_delta=tail_to_bulk_ratio_delta,
                             upper_bulk_to_bulk_ratio_delta=upper_bulk_to_bulk_ratio_delta,
                             straggler_to_bulk_ratio_delta=straggler_to_bulk_ratio_delta,
                             delta_early_bulk=delta_early_bulk,
                             delta_main_bulk=delta_main_bulk,
                             synchronized_lateness_score=synchronized_lateness_score,
                             concentration_score=concentration_score,
                             convergence_region_score=convergence_region_score,
                             tail_score=tail_score,
                             straggler_score=straggler_score)

        delta_row = {
            "scenario_id": row["scenario_id"],
            "boundary_type": row["boundary_type"],
            "family": row["family"],
            "severity": row["severity"],
            "configuration": row["configuration"],
            "delta_mean_tta": delta_mean,
            "delta_p95": delta_p95,
            "delta_p99": delta_p99,
            "delta_t25": delta_t25,
            "delta_t50": delta_t50,
            "delta_t75": delta_t75,
            "delta_t90": delta_t90,
            "delta_t95": delta_t95,
            "delta_t99": delta_t99,
            "early_bulk_region_shift": early_bulk_region_shift,
            "main_bulk_region_shift": main_bulk_region_shift,
            "upper_bulk_region_shift": upper_bulk_region_shift,
            "convergence_region_shift": convergence_region_shift,
            "tail_region_shift": tail_region_shift,
            "straggler_region_shift": straggler_region_shift,
            "delta_early_bulk_window_25_to_50": delta_early_bulk,
            "delta_main_bulk_window_50_to_75": delta_main_bulk,
            "delta_bulk_window_25_to_75": delta_bulk_window,
            "delta_upper_bulk_window_75_to_90": delta_upper_bulk_window,
            "delta_late_region_window_75_to_95": delta_late_region_window,
            "delta_tail_window_90_to_99": delta_tail_window,
            "delta_straggler_window_95_to_99": delta_straggler_window,
            "delta_cluster100": delta_cluster100,
            "delta_cluster250": delta_cluster250,
            "delta_distinct_1ms": delta_distinct_1ms,
            "delta_distinct_10ms": delta_distinct_10ms,
            "delta_gap_cv": delta_gap_cv,
            "delta_attainment_rate": delta_attainment_rate,
            "delta_unattained_case_count": delta_unattained,
            "delta_window_expired_flag": delta_window_expired,
            "delta_producer_complete_to_last_attainment": delta_last_lag,
            "mean_amplification_ratio": mean_ratio,
            "p95_amplification_ratio": p95_ratio,
            "p99_amplification_ratio": p99_ratio,
            "cluster100_amplification_ratio": cluster100_ratio,
            "gap_cv_amplification_ratio": gap_cv_ratio,
            "bulk_window_amplification_ratio": bulk_window_ratio,
            "upper_bulk_window_amplification_ratio": upper_bulk_window_ratio,
            "late_region_window_amplification_ratio": late_region_window_ratio,
            "tail_window_amplification_ratio": tail_window_ratio,
            "straggler_window_amplification_ratio": straggler_window_ratio,
            "tail_to_bulk_ratio_delta": tail_to_bulk_ratio_delta,
            "tail_to_bulk_amplification_ratio": tail_to_bulk_amplification_ratio,
            "upper_bulk_to_bulk_ratio_delta": upper_bulk_to_bulk_ratio_delta,
            "upper_bulk_to_bulk_amplification_ratio": upper_bulk_to_bulk_amplification_ratio,
            "straggler_to_bulk_ratio_delta": straggler_to_bulk_ratio_delta,
            "straggler_to_bulk_amplification_ratio": straggler_to_bulk_amplification_ratio,
            "timestamp_compression_ratio": timestamp_compression_ratio,
            "upper_bulk_displacement_score": upper_bulk_displacement_score,
            "convergence_vs_straggler_score": convergence_vs_straggler_score,
            "synchronized_vs_tail_score": synchronized_vs_tail_score,
            "concentration_vs_curve_shift_score": concentration_vs_curve_shift_score,
            "residual_backlog_indicator": residual_backlog,
            "deferred_shape_gap_vs_same_family": deferred_shape_gap,
            "deferred_shape_gap_vs_same_family_abs": round(abs(deferred_shape_gap), 6),
            "tail_without_mean_score": tail_without_mean_score,
            "concentration_dominance_score": concentration_score,
            "tail_shift_without_mean_shift_candidate": tail_without_mean_score >= 1.0 and abs(delta_mean) <= 1.0,
            "bulk_shift_without_mean_shift_candidate": positive(delta_bulk_window) > 1.0 and abs(delta_mean) <= 1.0,
        }
        delta_rows.append(delta_row)
        primary_region, secondary_region = region_rankings(delta_row)
        role_rows.append({
            "scenario_id": row["scenario_id"],
            "boundary_type": row["boundary_type"],
            "family": row["family"],
            "severity": row["severity"],
            "configuration": row["configuration"],
            "mean_score": mean_score,
            "bulk_score": bulk_score,
            "synchronized_lateness_score": synchronized_lateness_score,
            "concentration_score": concentration_score,
            "convergence_region_score": convergence_region_score,
            "upper_bulk_displacement_score": upper_bulk_displacement_score,
            "tail_score": tail_score,
            "straggler_score": straggler_score,
            "convergence_vs_straggler_score": convergence_vs_straggler_score,
            "synchronized_vs_tail_score": synchronized_vs_tail_score,
            "concentration_vs_curve_shift_score": concentration_vs_curve_shift_score,
            "primary_role": primary_role,
            "primary_role_label": role_alias(primary_role),
            "secondary_role": secondary_role,
            "secondary_role_label": role_alias(secondary_role),
            "classification_confidence": confidence,
            "primary_burden_region": primary_region,
            "primary_burden_region_label": region_alias(primary_region),
            "secondary_burden_region": secondary_region,
            "secondary_burden_region_label": region_alias(secondary_region),
            "role_reason": reason,
            "note": family_label(str(row["family"]), str(row["severity"])),
        })

    family_rows = sorted(family_rows, key=lambda r: (r["family"], r["severity"], r["configuration"]))
    delta_rows = sorted(delta_rows, key=lambda r: r["scenario_id"])
    role_rows = sorted(role_rows, key=lambda r: (r["family"], r["severity"], r["configuration"]))
    write_csv(agg_dir / "family_comparison_summary.csv", family_rows)
    dump_json(agg_dir / "family_comparison_summary.json", family_rows)
    write_csv(agg_dir / "family_delta_summary.csv", delta_rows)
    dump_json(agg_dir / "family_delta_summary.json", delta_rows)
    write_csv(agg_dir / "family_role_summary.csv", role_rows)
    dump_json(agg_dir / "family_role_summary.json", role_rows)
    burden_rows = []
    for row in role_rows:
        burden_rows.append({
            "scenario_id": row["scenario_id"],
            "boundary_type": row["boundary_type"],
            "family": row["family"],
            "severity": row["severity"],
            "configuration": row["configuration"],
            "primary_role": row["primary_role"],
            "primary_role_label": row.get("primary_role_label", role_alias(row["primary_role"])),
            "secondary_role": row["secondary_role"],
            "secondary_role_label": row.get("secondary_role_label", role_alias(row["secondary_role"])),
            "classification_confidence": row["classification_confidence"],
            "primary_burden_region": row["primary_burden_region"],
            "primary_burden_region_label": row.get("primary_burden_region_label", region_alias(row["primary_burden_region"])),
            "secondary_burden_region": row["secondary_burden_region"],
            "secondary_burden_region_label": row.get("secondary_burden_region_label", region_alias(row["secondary_burden_region"])),
            "role_reason": row["role_reason"],
            "synchronized_lateness_score": row["synchronized_lateness_score"],
            "concentration_score": row["concentration_score"],
            "convergence_region_score": row["convergence_region_score"],
            "tail_score": row["tail_score"],
            "straggler_score": row["straggler_score"],
            "upper_bulk_displacement_score": row["upper_bulk_displacement_score"],
        })
    write_csv(agg_dir / "burden_redistribution_summary.csv", burden_rows)
    dump_json(agg_dir / "burden_redistribution_summary.json", burden_rows)

    curve_payload: dict[str, Any] = {}
    curve_rows: list[dict[str, Any]] = []
    for scenario_id, runs in scenario_timeseries.items():
        spec = scenario_specs[scenario_id]
        summary = {
            "attainment_t25_seconds_mean": round(mean([attainment_time_at_fraction(run, 0.25) for run in runs]), 6),
            "attainment_t50_seconds_mean": round(mean([attainment_time_at_fraction(run, 0.50) for run in runs]), 6),
            "attainment_t75_seconds_mean": round(mean([attainment_time_at_fraction(run, 0.75) for run in runs]), 6),
            "attainment_t90_seconds_mean": round(mean([attainment_time_at_fraction(run, 0.90) for run in runs]), 6),
            "attainment_t95_seconds_mean": round(mean([attainment_time_at_fraction(run, 0.95) for run in runs]), 6),
            "attainment_t99_seconds_mean": round(mean([attainment_time_at_fraction(run, 0.99) for run in runs]), 6),
        }
        summary["early_bulk_window_25_to_50_seconds_mean"] = round(mean([window(attainment_time_at_fraction(run, 0.25), attainment_time_at_fraction(run, 0.50)) for run in runs]), 6)
        summary["main_bulk_window_50_to_75_seconds_mean"] = round(mean([window(attainment_time_at_fraction(run, 0.50), attainment_time_at_fraction(run, 0.75)) for run in runs]), 6)
        summary["bulk_window_25_to_75_seconds_mean"] = round(mean([window(attainment_time_at_fraction(run, 0.25), attainment_time_at_fraction(run, 0.75)) for run in runs]), 6)
        summary["upper_bulk_window_75_to_90_seconds_mean"] = round(mean([window(attainment_time_at_fraction(run, 0.75), attainment_time_at_fraction(run, 0.90)) for run in runs]), 6)
        summary["late_region_window_75_to_95_seconds_mean"] = round(mean([window(attainment_time_at_fraction(run, 0.75), attainment_time_at_fraction(run, 0.95)) for run in runs]), 6)
        summary["tail_window_90_to_99_seconds_mean"] = round(mean([window(attainment_time_at_fraction(run, 0.90), attainment_time_at_fraction(run, 0.99)) for run in runs]), 6)
        summary["straggler_window_95_to_99_seconds_mean"] = round(mean([window(attainment_time_at_fraction(run, 0.95), attainment_time_at_fraction(run, 0.99)) for run in runs]), 6)
        summary["tail_to_bulk_ratio_mean"] = round(mean([safe_div(window(attainment_time_at_fraction(run, 0.90), attainment_time_at_fraction(run, 0.99)), window(attainment_time_at_fraction(run, 0.25), attainment_time_at_fraction(run, 0.75)), floor=0.1) for run in runs]), 6)
        summary["upper_bulk_to_bulk_ratio_mean"] = round(mean([safe_div(window(attainment_time_at_fraction(run, 0.75), attainment_time_at_fraction(run, 0.90)), window(attainment_time_at_fraction(run, 0.25), attainment_time_at_fraction(run, 0.75)), floor=0.1) for run in runs]), 6)
        summary["straggler_to_bulk_ratio_mean"] = round(mean([safe_div(window(attainment_time_at_fraction(run, 0.95), attainment_time_at_fraction(run, 0.99)), window(attainment_time_at_fraction(run, 0.25), attainment_time_at_fraction(run, 0.75)), floor=0.1) for run in runs]), 6)

        curve_payload[scenario_id] = {
            "scenario_id": scenario_id,
            "boundary_type": spec["boundary"],
            "configuration": spec["configuration"],
            "family": spec["family"],
            "severity": spec["severity"],
            "curve_100ms": summarize_series(runs, 0.10),
            "curve_250ms": summarize_series(runs, 0.25),
            "cumulative_attainment_summary": summary,
        }
        curve_rows.append({
            "scenario_id": scenario_id,
            "boundary_type": spec["boundary"],
            "configuration": spec["configuration"],
            "family": spec["family"],
            "severity": spec["severity"],
            **summary,
        })
    dump_json(agg_dir / "scenario_curve_summary.json", curve_payload)
    write_csv(agg_dir / "scenario_curve_summary.csv", curve_rows)
    curve_region_rows = []
    for row in curve_rows:
        curve_region_rows.append({
            "scenario_id": row["scenario_id"],
            "boundary_type": row["boundary_type"],
            "family": row["family"],
            "severity": row["severity"],
            "configuration": row["configuration"],
            "attainment_t50_seconds_mean": row["attainment_t50_seconds_mean"],
            "attainment_t75_seconds_mean": row["attainment_t75_seconds_mean"],
            "attainment_t90_seconds_mean": row["attainment_t90_seconds_mean"],
            "attainment_t95_seconds_mean": row["attainment_t95_seconds_mean"],
            "attainment_t99_seconds_mean": row["attainment_t99_seconds_mean"],
            "early_bulk_window_25_to_50_seconds_mean": row["early_bulk_window_25_to_50_seconds_mean"],
            "main_bulk_window_50_to_75_seconds_mean": row["main_bulk_window_50_to_75_seconds_mean"],
            "upper_bulk_window_75_to_90_seconds_mean": row["upper_bulk_window_75_to_90_seconds_mean"],
            "late_region_window_75_to_95_seconds_mean": row["late_region_window_75_to_95_seconds_mean"],
            "tail_window_90_to_99_seconds_mean": row["tail_window_90_to_99_seconds_mean"],
            "straggler_window_95_to_99_seconds_mean": row["straggler_window_95_to_99_seconds_mean"],
        })
    write_csv(agg_dir / "curve_region_summary.csv", curve_region_rows)
    dump_json(agg_dir / "curve_region_summary.json", curve_region_rows)

    role_by_id = {r["scenario_id"]: r for r in role_rows}
    delta_by_id = {r["scenario_id"]: r for r in delta_rows}
    curve_by_id = {r["scenario_id"]: r for r in curve_rows}
    analysis_ready_rows: list[dict[str, Any]] = []
    for row in scenario_rows:
        role = role_by_id.get(row["scenario_id"], {})
        delta = delta_by_id.get(row["scenario_id"], {})
        curve = curve_by_id.get(row["scenario_id"], {})
        analysis_ready_rows.append({
            "scenario_id": row["scenario_id"],
            "boundary_type": row["boundary_type"],
            "family": row["family"],
            "severity": row["severity"],
            "configuration": row["configuration"],
            "family_label": family_label(str(row["family"]), str(row["severity"])),
            "primary_role": role.get("primary_role", "baseline" if row["family"] == "baseline" else "unknown"),
            "primary_role_label": role.get("primary_role_label", role_alias(role.get("primary_role", "baseline" if row["family"] == "baseline" else "unknown"))),
            "secondary_role": role.get("secondary_role"),
            "secondary_role_label": role.get("secondary_role_label", role_alias(role.get("secondary_role"))),
            "classification_confidence": role.get("classification_confidence", "n/a"),
            "primary_burden_region": role.get("primary_burden_region"),
            "primary_burden_region_label": role.get("primary_burden_region_label", region_alias(role.get("primary_burden_region"))),
            "secondary_burden_region": role.get("secondary_burden_region"),
            "secondary_burden_region_label": role.get("secondary_burden_region_label", region_alias(role.get("secondary_burden_region"))),
            "mean_tta_mean": row["mean_time_to_attainment_seconds_mean"],
            "p95_mean": row["p95_time_to_attainment_seconds_mean"],
            "p99_mean": row["p99_time_to_attainment_seconds_mean"],
            "gap_cv_mean": row["inter_attainment_gap_cv_mean"],
            "cluster100_mean": row["temporal_clustering_busiest_10pct_interval_share_100ms_mean"],
            "bulk_window_mean": curve.get("bulk_window_25_to_75_seconds_mean", row.get("bulk_window_25_to_75_seconds_mean")),
            "upper_bulk_window_mean": curve.get("upper_bulk_window_75_to_90_seconds_mean"),
            "late_region_window_mean": curve.get("late_region_window_75_to_95_seconds_mean"),
            "tail_window_mean": curve.get("tail_window_90_to_99_seconds_mean"),
            "straggler_window_mean": curve.get("straggler_window_95_to_99_seconds_mean"),
            "delta_mean_tta": delta.get("delta_mean_tta", 0.0),
            "delta_p95": delta.get("delta_p95", 0.0),
            "delta_bulk_window": delta.get("delta_bulk_window_25_to_75", 0.0),
            "delta_upper_bulk_window": delta.get("delta_upper_bulk_window_75_to_90", 0.0),
            "delta_late_region_window": delta.get("delta_late_region_window_75_to_95", 0.0),
            "delta_tail_window": delta.get("delta_tail_window_90_to_99", 0.0),
            "delta_straggler_window": delta.get("delta_straggler_window_95_to_99", 0.0),
            "early_bulk_region_shift": delta.get("early_bulk_region_shift", 0.0),
            "main_bulk_region_shift": delta.get("main_bulk_region_shift", 0.0),
            "upper_bulk_region_shift": delta.get("upper_bulk_region_shift", 0.0),
            "convergence_region_shift": delta.get("convergence_region_shift", 0.0),
            "tail_region_shift": delta.get("tail_region_shift", 0.0),
            "straggler_region_shift": delta.get("straggler_region_shift", 0.0),
            "upper_bulk_displacement_score": role.get("upper_bulk_displacement_score", 0.0),
            "convergence_vs_straggler_score": role.get("convergence_vs_straggler_score", 0.0),
            "synchronized_vs_tail_score": role.get("synchronized_vs_tail_score", 0.0),
            "concentration_vs_curve_shift_score": role.get("concentration_vs_curve_shift_score", 0.0),
            "takeaway": concise_takeaway(str(role.get("primary_role", "mixed")), str(row["family"]), str(row["severity"])),
            "role_reason": role.get("role_reason", "")
        })
    write_csv(agg_dir / "analysis_ready_family_summary.csv", analysis_ready_rows)
    dump_json(agg_dir / "analysis_ready_family_summary.json", analysis_ready_rows)

    def cf(label: str, row: dict[str, Any] | None, finding: str) -> dict[str, Any] | None:
        if row is None:
            return None
        primary_role = row.get("primary_role")
        return {
            "label": label,
            "scenario_id": row["scenario_id"],
            "family": row["family"],
            "severity": row["severity"],
            "configuration": row["configuration"],
            "finding": finding,
            "role": primary_role,
            "role_label": role_alias(primary_role),
            "explanation": f"{family_label(str(row['family']), str(row['severity']))} currently reads mainly as {role_alias(primary_role)}. {finding}",
        }

    candidate_findings = [
        cf("Synchronized lateness leader", top_row(role_rows, "synchronized_lateness_score", positive_only=True), "This scenario most strongly shifts much of the recovery curve later together."),
        cf("Concentration leader", top_row(role_rows, "concentration_score", positive_only=True), "This scenario most strongly converts disturbance into concentrated catch-up behaviour."),
        cf("Convergence-region leader", top_row(role_rows, "convergence_region_score", positive_only=True), "This scenario most strongly displaces the late-convergence region relative to the early or main bulk."),
        cf("Upper-bulk displacement leader", top_row(role_rows, "upper_bulk_displacement_score", positive_only=True), "This scenario most strongly shifts the upper bulk / late recovery body."),
        cf("Tail-sensitive candidate", top_row(role_rows, "tail_score", positive_only=True), "This scenario is the strongest current candidate for a true tail-stretch effect, though it should be read alongside convergence-region signals."),
        cf("Straggler-sensitive candidate", top_row(role_rows, "straggler_score", positive_only=True), "This scenario most strongly affects the strict straggler window (95→99)."),
        cf("Upper-bulk shift leader", top_row(delta_rows, "upper_bulk_region_shift", positive_only=True), "This scenario most strongly shifts the upper bulk later in the recovery episode."),
        cf("Convergence-region shift leader", top_row(delta_rows, "convergence_region_shift", positive_only=True), "This scenario most strongly shifts the late-convergence region later in the recovery episode."),
        cf("Straggler-region shift leader", top_row(delta_rows, "straggler_region_shift", positive_only=True), "This scenario most strongly shifts the strict straggler region later."),
        cf("Upper-bulk compression leader", bottom_row(delta_rows, "delta_upper_bulk_window_75_to_90", negative_only=True), "This scenario most strongly compresses the upper bulk while shifting the broader curve."),
        cf("Late-region compression leader", bottom_row(delta_rows, "delta_late_region_window_75_to_95", negative_only=True), "This scenario most strongly compresses the late-convergence region while still shifting it later overall."),
    ]
    candidate_findings = [c for c in candidate_findings if c is not None]
    dump_json(agg_dir / "candidate_findings.json", candidate_findings)

    coverage = collect_batch_coverage(batch_dir)
    write_csv(agg_dir / "scenario_coverage_summary.csv", coverage.get("scenario_coverage_rows", []))
    dump_json(agg_dir / "scenario_coverage_summary.json", coverage.get("scenario_coverage_rows", []))

    profile_summary = {
        "total_runs_seen": len(run_rows) + len(failed_runs),
        "expected_run_count": coverage.get("expected_runs"),
        "run_status_counts": coverage.get("status_counts", {}),
        "total_runs_aggregated": len(run_rows),
        "total_runs_failed_or_incomplete": len(failed_runs),
        "total_scenarios": len(scenario_rows),
        "highest_variance_scenario": top_scenario(scenario_rows, "mean_time_to_attainment_seconds_std"),
        "highest_variance_std": max((r["mean_time_to_attainment_seconds_std"] for r in scenario_rows), default=0.0),
        "highest_p99_scenario": top_scenario(scenario_rows, "p99_time_to_attainment_seconds_mean"),
        "highest_cluster100_scenario": top_scenario(scenario_rows, "temporal_clustering_busiest_10pct_interval_share_100ms_mean"),
        "highest_unattained_scenario": top_scenario(scenario_rows, "unattained_case_count_mean", positive_only=True),
        "highest_residual_backlog_scenario": top_scenario([{**r, "residual_backlog_indicator": (r["retained_buffer_remaining_mean"] + r["pending_case_count_remaining_mean"])} for r in scenario_rows], "residual_backlog_indicator", positive_only=True),
        "max_window_expired_repeat_fraction": max((r["observation_window_expired_flag_mean"] for r in scenario_rows), default=0.0),
        "scenarios_with_any_censoring": sum(1 for r in scenario_rows if r["tta_metrics_censored_flag_mean"] > 0),
        "scenarios_with_any_residual_backlog": sum(1 for r in scenario_rows if (r["retained_buffer_remaining_mean"] + r["pending_case_count_remaining_mean"]) > 0),
        "family_with_largest_mean_tta_amplification": top_scenario(delta_rows, "delta_mean_tta", positive_only=True),
        "family_with_largest_p95_amplification": top_scenario(delta_rows, "delta_p95", positive_only=True),
        "family_with_largest_gap_cv_amplification": top_scenario(delta_rows, "delta_gap_cv", positive_only=True),
        "family_with_largest_bulk_window_amplification": top_scenario(delta_rows, "delta_bulk_window_25_to_75", positive_only=True),
        "family_with_largest_upper_bulk_window_amplification": top_scenario(delta_rows, "delta_upper_bulk_window_75_to_90", positive_only=True),
        "family_with_largest_late_region_window_amplification": top_scenario(delta_rows, "delta_late_region_window_75_to_95", positive_only=True),
        "family_with_largest_tail_window_amplification": top_scenario(delta_rows, "delta_tail_window_90_to_99", positive_only=True),
        "family_with_largest_straggler_window_amplification": top_scenario(delta_rows, "delta_straggler_window_95_to_99", positive_only=True),
        "family_with_largest_upper_bulk_region_shift": top_scenario(delta_rows, "upper_bulk_region_shift", positive_only=True),
        "family_with_largest_convergence_region_shift": top_scenario(delta_rows, "convergence_region_shift", positive_only=True),
        "family_with_largest_straggler_region_shift": top_scenario(delta_rows, "straggler_region_shift", positive_only=True),
        "family_with_strongest_upper_bulk_compression": None if bottom_row(delta_rows, "delta_upper_bulk_window_75_to_90", negative_only=True) is None else bottom_row(delta_rows, "delta_upper_bulk_window_75_to_90", negative_only=True)["scenario_id"],
        "family_with_strongest_late_region_compression": None if bottom_row(delta_rows, "delta_late_region_window_75_to_95", negative_only=True) is None else bottom_row(delta_rows, "delta_late_region_window_75_to_95", negative_only=True)["scenario_id"],
        "family_with_strongest_tail_window_compression": None if bottom_row(delta_rows, "delta_tail_window_90_to_99", negative_only=True) is None else bottom_row(delta_rows, "delta_tail_window_90_to_99", negative_only=True)["scenario_id"],
        "family_with_strongest_straggler_compression": None if bottom_row(delta_rows, "delta_straggler_window_95_to_99", negative_only=True) is None else bottom_row(delta_rows, "delta_straggler_window_95_to_99", negative_only=True)["scenario_id"],
        "family_with_largest_tail_to_bulk_shift": top_scenario(delta_rows, "tail_to_bulk_ratio_delta", positive_only=True),
        "family_with_largest_unattained_increase": top_scenario(delta_rows, "delta_unattained_case_count", positive_only=True),
        "family_with_largest_residual_backlog": top_scenario(delta_rows, "residual_backlog_indicator", positive_only=True),
        "family_with_smallest_mean_change_but_largest_tail_change": top_scenario(delta_rows, "tail_without_mean_score", positive_only=True),
        "family_with_largest_upper_bulk_to_bulk_shift": top_scenario(delta_rows, "upper_bulk_to_bulk_ratio_delta", positive_only=True),
        "family_with_largest_straggler_to_bulk_shift": top_scenario(delta_rows, "straggler_to_bulk_ratio_delta", positive_only=True),
        "strongest_deferred_vs_immediate_shape_gap": top_scenario(delta_rows, "deferred_shape_gap_vs_same_family_abs", positive_only=True),
        "strongest_synchronized_lateness_candidate": top_scenario(role_rows, "synchronized_lateness_score", positive_only=True),
        "strongest_concentration_sensitive_candidate": top_scenario(role_rows, "concentration_score", positive_only=True),
        "strongest_convergence_region_candidate": top_scenario(role_rows, "convergence_region_score", positive_only=True),
        "strongest_upper_bulk_displacement_candidate": top_scenario(role_rows, "upper_bulk_displacement_score", positive_only=True),
        "strongest_tail_sensitive_candidate": top_scenario(role_rows, "tail_score", positive_only=True),
        "strongest_straggler_sensitive_candidate": top_scenario(role_rows, "straggler_score", positive_only=True),
        "strongest_convergence_vs_straggler_candidate": top_scenario(role_rows, "convergence_vs_straggler_score", positive_only=True),
        "primary_role_counts": {role: sum(1 for r in role_rows if r["primary_role"] == role) for role in sorted({r["primary_role"] for r in role_rows})},
        "primary_region_counts": {region: sum(1 for r in role_rows if r.get("primary_burden_region") == region) for region in sorted({str(r.get("primary_burden_region")) for r in role_rows})},
    }

    thesis_core_rows = []
    main_core_rows = []
    supporting_rows = []
    for row in scenario_rows:
        thesis_row = {
            "scenario_id": row["scenario_id"],
            "boundary_type": row["boundary_type"],
            "configuration": row["configuration"],
            "family": row["family"],
            "severity": row["severity"],
            "scenario_role": row.get("scenario_role", "main_core"),
            "attainment_rate_mean": row["attainment_rate_mean"],
            "mean_time_to_attainment_seconds_mean": row["mean_time_to_attainment_seconds_mean"],
            "p95_time_to_attainment_seconds_mean": row["p95_time_to_attainment_seconds_mean"],
            "completed_in_time_rate_mean": row.get("completed_in_time_rate_mean", 0.0),
            "expired_rate_mean": row.get("expired_rate_mean", 0.0),
            "temporal_clustering_busiest_10pct_interval_share_100ms_mean": row["temporal_clustering_busiest_10pct_interval_share_100ms_mean"],
            "duplicate_delivery_rate_mean": row.get("duplicate_delivery_rate_mean", 0.0),
            "duplicate_delivery_count_mean": row.get("duplicate_delivery_count_mean", 0.0),
        }
        thesis_core_rows.append(thesis_row)
        if thesis_row["scenario_role"] == "main_core":
            main_core_rows.append(thesis_row)
        else:
            supporting_rows.append(thesis_row)
    thesis_main = thesis_main_dir(batch_dir)
    thesis_supporting = thesis_supporting_dir(batch_dir)
    internal_dir = internal_aggregates_dir(batch_dir)

    write_csv(agg_dir / "thesis_core_summary.csv", thesis_core_rows)
    dump_json(agg_dir / "thesis_core_summary.json", thesis_core_rows)
    write_csv(agg_dir / "thesis_main_core_summary.csv", main_core_rows)
    dump_json(agg_dir / "thesis_main_core_summary.json", main_core_rows)
    write_csv(agg_dir / "thesis_supporting_summary.csv", supporting_rows)
    dump_json(agg_dir / "thesis_supporting_summary.json", supporting_rows)

    write_csv(thesis_main / "main_core_summary.csv", main_core_rows)
    dump_json(thesis_main / "main_core_summary.json", main_core_rows)
    write_csv(thesis_main / "cross_boundary_delta_summary.csv", delta_rows)
    dump_json(thesis_main / "cross_boundary_delta_summary.json", delta_rows)
    write_csv(thesis_supporting / "supporting_scenario_summary.csv", supporting_rows)
    dump_json(thesis_supporting / "supporting_scenario_summary.json", supporting_rows)

    dump_json(agg_dir / "profile_summary.json", profile_summary)
    dump_json(internal_dir / "profile_summary.json", profile_summary)
    render_aggregate_report(batch_dir, scenario_rows, profile_summary, delta_rows, role_rows, curve_rows, analysis_ready_rows, candidate_findings, failed_runs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
