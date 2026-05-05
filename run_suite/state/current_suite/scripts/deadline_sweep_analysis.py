from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from batch_utils import dump_json, load_json, thesis_supporting_dir, write_csv, scenario_display_label, scenario_display_severity, scenario_role_tag


def threshold_pattern(expired_delta: float) -> str:
    delta = abs(expired_delta)
    if delta >= 0.20:
        return 'sharp threshold shift'
    if delta >= 0.08:
        return 'moderate threshold shift'
    return 'gradual threshold shift'


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit('Usage: deadline_sweep_analysis.py <batch_dir>')
    batch_dir = Path(argv[1])
    agg_dir = batch_dir / 'aggregates'
    thesis_dir = thesis_supporting_dir(batch_dir)
    rows = load_json(agg_dir / 'scenario_repeat_summary.json')
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row['base_scenario_id']), str(row['configuration']), str(row['family']), str(row['severity']))].append(row)

    summary_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    thesis_rows: list[dict[str, Any]] = []
    for (base_scenario_id, configuration, family, severity), variants in sorted(grouped.items()):
        variants = sorted(variants, key=lambda r: float(r.get('deadline_window_seconds', 0.0)))
        prev = None
        for row in variants:
            deadline = round(float(row.get('deadline_window_seconds', 0.0) or 0.0), 6)
            expired = round(float(row.get('expired_rate_mean', 0.0) or 0.0), 6)
            in_time = round(float(row.get('completed_in_time_rate_mean', 0.0) or 0.0), 6)
            concentration = round(float(row.get('temporal_clustering_busiest_10pct_interval_share_100ms_mean', 0.0) or 0.0), 6)
            summary_rows.append({
                'scenario_id': row['scenario_id'],
                'base_scenario_id': base_scenario_id,
                'boundary_type': row['boundary_type'],
                'configuration': configuration,
                'family': family,
                'severity': severity,
                'severity_display': row.get('severity_display', scenario_display_severity(family, severity)),
                'scenario_display_label': row.get('scenario_display_label', scenario_display_label(family, severity)),
                'scenario_role_detail': row.get('scenario_role_detail', scenario_role_tag(family, severity, None)),
                'deadline_window_seconds': deadline,
                'attainment_rate_mean': round(float(row.get('attainment_rate_mean', 0.0) or 0.0), 6),
                'completed_in_time_rate_mean': in_time,
                'expired_rate_mean': expired,
                'mean_time_to_attainment_seconds_mean': round(float(row.get('mean_time_to_attainment_seconds_mean', 0.0) or 0.0), 6),
                'p95_time_to_attainment_seconds_mean': round(float(row.get('p95_time_to_attainment_seconds_mean', 0.0) or 0.0), 6),
                'temporal_clustering_busiest_10pct_interval_share_100ms_mean': concentration,
            })
            if prev is not None:
                expired_delta = round(expired - prev['expired_rate_mean'], 6)
                row_out = {
                    'base_scenario_id': base_scenario_id,
                    'configuration': configuration,
                    'family': family,
                    'severity': severity,
                    'severity_display': row.get('severity_display', scenario_display_severity(family, severity)),
                    'scenario_display_label': row.get('scenario_display_label', scenario_display_label(family, severity)),
                    'scenario_role_detail': row.get('scenario_role_detail', scenario_role_tag(family, severity, None)),
                    'from_deadline_seconds': prev['deadline_window_seconds'],
                    'to_deadline_seconds': deadline,
                    'expired_rate_delta': expired_delta,
                    'completed_in_time_rate_delta': round(in_time - prev['completed_in_time_rate_mean'], 6),
                    'threshold_pattern': threshold_pattern(expired_delta),
                }
                threshold_rows.append(row_out)
                thesis_rows.append(row_out)
            prev = {
                'deadline_window_seconds': deadline,
                'expired_rate_mean': expired,
                'completed_in_time_rate_mean': in_time,
            }

    write_csv(agg_dir / 'deadline_sweep_summary.csv', summary_rows)
    dump_json(agg_dir / 'deadline_sweep_summary.json', summary_rows)
    write_csv(agg_dir / 'deadline_sweep_threshold_summary.csv', threshold_rows)
    dump_json(agg_dir / 'deadline_sweep_threshold_summary.json', threshold_rows)
    write_csv(thesis_dir / 'deadline_sweep_summary.csv', summary_rows)
    dump_json(thesis_dir / 'deadline_sweep_summary.json', summary_rows)
    write_csv(thesis_dir / 'deadline_sweep_threshold_summary.csv', thesis_rows)
    dump_json(thesis_dir / 'deadline_sweep_threshold_summary.json', thesis_rows)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
