from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from batch_utils import dump_json, load_json, thesis_supporting_dir, internal_aggregates_dir, write_csv, scenario_display_label, scenario_display_severity, scenario_role_tag


def expired_regime(expired: float) -> str:
    if expired >= 0.90:
        return 'collapse-end'
    if expired >= 0.65:
        return 'heavily pressured'
    if expired >= 0.35:
        return 'meaningfully pressured'
    if expired >= 0.10:
        return 'lightly pressured'
    return 'safe'


def response_shape(deadlines: list[float], expireds: list[float]) -> str:
    if not expireds:
        return 'unknown'
    lo, hi = expireds[0], expireds[-1]
    span = max(expireds) - min(expireds)
    if max(expireds) <= 0.10:
        return 'resilient throughout'
    if min(expireds) >= 0.90:
        return 'collapse-end throughout'
    if span < 0.10:
        return 'weak deadline sensitivity'
    deltas = [abs(expireds[i+1] - expireds[i]) for i in range(len(expireds)-1)]
    max_delta = max(deltas) if deltas else 0.0
    if span >= 0.30 and max_delta >= 0.18:
        return 'threshold-like response'
    if expireds[-1] < expireds[0]:
        return 'gradual release with looser deadline'
    return 'mixed response'


def first_deadline_below(expireds: list[float], deadlines: list[float], cutoff: float) -> float | None:
    for d, e in zip(deadlines, expireds):
        if e <= cutoff:
            return d
    return None


def base_display(row: dict[str, Any]) -> dict[str, Any]:
    fam = str(row['family'])
    sev = str(row['severity'])
    return {
        'severity_display': row.get('severity_display', scenario_display_severity(fam, sev)),
        'scenario_display_label': row.get('scenario_display_label', scenario_display_label(fam, sev)),
        'scenario_role_detail': row.get('scenario_role_detail', scenario_role_tag(fam, sev, None)),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit('Usage: deadline_response_analysis.py <batch_dir>')
    batch_dir = Path(argv[1])
    agg_dir = batch_dir / 'aggregates'
    thesis_dir = thesis_supporting_dir(batch_dir)
    internal_dir = internal_aggregates_dir(batch_dir)
    rows = load_json(agg_dir / 'scenario_repeat_summary.json')

    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    deadline_grouped: dict[tuple[float, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        if str(row.get('boundary_type')) != 'deadline_constrained':
            continue
        key = (str(row['base_scenario_id']), str(row['configuration']), str(row['family']), str(row['severity']))
        grouped[key].append(row)
        deadline = round(float(row.get('deadline_window_seconds', 0.0) or 0.0), 6)
        deadline_grouped[(deadline, str(row['configuration']))][str(row['base_scenario_id'])] = row

    point_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    transition_rows: list[dict[str, Any]] = []
    contrast_rows: list[dict[str, Any]] = []

    for (base_scenario_id, configuration, family, severity), variants in sorted(grouped.items()):
        variants = sorted(variants, key=lambda r: float(r.get('deadline_window_seconds', 0.0)))
        deadlines: list[float] = []
        expireds: list[float] = []
        in_times: list[float] = []
        prev = None
        for row in variants:
            deadline = round(float(row.get('deadline_window_seconds', 0.0) or 0.0), 6)
            expired = round(float(row.get('expired_rate_mean', 0.0) or 0.0), 6)
            in_time = round(float(row.get('completed_in_time_rate_mean', 0.0) or 0.0), 6)
            deadlines.append(deadline)
            expireds.append(expired)
            in_times.append(in_time)
            pr = {
                'scenario_id': row['scenario_id'],
                'base_scenario_id': base_scenario_id,
                'configuration': configuration,
                'family': family,
                'severity': severity,
                **base_display(row),
                'deadline_window_seconds': deadline,
                'expired_rate_mean': expired,
                'completed_in_time_rate_mean': in_time,
                'mean_time_to_attainment_seconds_mean': round(float(row.get('mean_time_to_attainment_seconds_mean', 0.0) or 0.0), 6),
                'p95_time_to_attainment_seconds_mean': round(float(row.get('p95_time_to_attainment_seconds_mean', 0.0) or 0.0), 6),
                'concentration_mean': round(float(row.get('temporal_clustering_busiest_10pct_interval_share_100ms_mean', 0.0) or 0.0), 6),
                'response_regime': expired_regime(expired),
            }
            point_rows.append(pr)
            if prev is not None:
                transition_rows.append({
                    'base_scenario_id': base_scenario_id,
                    'configuration': configuration,
                    'family': family,
                    'severity': severity,
                    **base_display(row),
                    'from_deadline_seconds': prev['deadline'],
                    'to_deadline_seconds': deadline,
                    'expired_rate_delta': round(expired - prev['expired'], 6),
                    'completed_in_time_rate_delta': round(in_time - prev['in_time'], 6),
                    'transition_magnitude': round(abs(expired - prev['expired']), 6),
                    'from_regime': expired_regime(prev['expired']),
                    'to_regime': expired_regime(expired),
                })
            prev = {'deadline': deadline, 'expired': expired, 'in_time': in_time}

        span = round(max(expireds) - min(expireds), 6) if expireds else 0.0
        curve_rows.append({
            'base_scenario_id': base_scenario_id,
            'configuration': configuration,
            'family': family,
            'severity': severity,
            **base_display(variants[0]),
            'strictest_deadline_seconds': deadlines[0] if deadlines else 0.0,
            'loosest_deadline_seconds': deadlines[-1] if deadlines else 0.0,
            'expired_rate_at_strictest': expireds[0] if expireds else 0.0,
            'expired_rate_at_loosest': expireds[-1] if expireds else 0.0,
            'expired_rate_span': span,
            'completed_in_time_span': round(max(in_times) - min(in_times), 6) if in_times else 0.0,
            'response_shape': response_shape(deadlines, expireds),
            'deadline_at_or_below_0p50_expired': first_deadline_below(expireds, deadlines, 0.50),
            'deadline_at_or_below_0p25_expired': first_deadline_below(expireds, deadlines, 0.25),
            'regime_at_strictest': expired_regime(expireds[0]) if expireds else 'unknown',
            'regime_at_loosest': expired_regime(expireds[-1]) if expireds else 'unknown',
        })

    # Burden-family contrasts at each deadline/configuration.
    moderate_suffix = 'degradation__moderate'
    high_suffix = 'degradation__high'
    backlog_suffix = 'backlog_shock__standard'
    for (deadline, configuration), mapping in sorted(deadline_grouped.items()):
        moderate = next((v for k, v in mapping.items() if moderate_suffix in k), None)
        high = next((v for k, v in mapping.items() if high_suffix in k), None)
        backlog = next((v for k, v in mapping.items() if backlog_suffix in k), None)
        if moderate and backlog:
            moderate_exp = float(moderate.get('expired_rate_mean', 0.0) or 0.0)
            backlog_exp = float(backlog.get('expired_rate_mean', 0.0) or 0.0)
            contrast_rows.append({
                'deadline_window_seconds': deadline,
                'configuration': configuration,
                'contrast_pair': 'degradation_moderate_vs_backlog_shock',
                'expired_rate_gap': round(moderate_exp - backlog_exp, 6),
                'more_deadline_destructive': 'degradation_moderate' if moderate_exp > backlog_exp else 'backlog_shock',
                'contrast_strength': 'strong' if abs(moderate_exp - backlog_exp) >= 0.20 else 'moderate' if abs(moderate_exp - backlog_exp) >= 0.08 else 'weak',
            })
        if moderate and high:
            moderate_exp = float(moderate.get('expired_rate_mean', 0.0) or 0.0)
            high_exp = float(high.get('expired_rate_mean', 0.0) or 0.0)
            contrast_rows.append({
                'deadline_window_seconds': deadline,
                'configuration': configuration,
                'contrast_pair': 'degradation_high_vs_moderate',
                'expired_rate_gap': round(high_exp - moderate_exp, 6),
                'more_deadline_destructive': 'degradation_high' if high_exp > moderate_exp else 'degradation_moderate',
                'contrast_strength': 'strong' if abs(high_exp - moderate_exp) >= 0.20 else 'moderate' if abs(high_exp - moderate_exp) >= 0.08 else 'weak',
            })

    # Write outputs.
    for base in [agg_dir, thesis_dir, internal_dir]:
        write_csv(base / 'deadline_response_points.csv', point_rows)
        dump_json(base / 'deadline_response_points.json', point_rows)
        write_csv(base / 'deadline_response_curve_summary.csv', curve_rows)
        dump_json(base / 'deadline_response_curve_summary.json', curve_rows)
        write_csv(base / 'deadline_response_transition_summary.csv', transition_rows)
        dump_json(base / 'deadline_response_transition_summary.json', transition_rows)
        write_csv(base / 'deadline_family_contrast_summary.csv', contrast_rows)
        dump_json(base / 'deadline_family_contrast_summary.json', contrast_rows)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
