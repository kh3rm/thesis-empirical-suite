from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from batch_utils import dump_json, load_json, thesis_supporting_dir, write_csv, scenario_display_label, scenario_display_severity, scenario_role_tag


def signature_gloss(configuration: str, late_share: float, concentration: float, expired: float) -> str:
    parts = []
    if expired >= 0.35:
        parts.append('heavy deadline pressure')
    elif expired >= 0.10:
        parts.append('moderate deadline pressure')
    else:
        parts.append('primarily temporal burden')
    if concentration >= 0.45:
        parts.append('strong catch-up concentration')
    elif concentration >= 0.20:
        parts.append('moderate concentration')
    if late_share >= 0.35:
        parts.append('more burden landing in late recovery')
    return f"{configuration.replace('_', ' ')}: " + ', '.join(parts)


def compact_signature(late_share: float, concentration: float, expired: float) -> str:
    if expired >= 0.35:
        return 'expiry-heavy'
    if concentration >= 0.45:
        return 'concentration-heavy'
    if late_share >= 0.35:
        return 'later-burdened'
    return 'earlier-burdened'


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit('Usage: placement_signature_analysis.py <batch_dir>')
    batch_dir = Path(argv[1])
    agg_dir = batch_dir / 'aggregates'
    thesis_dir = thesis_supporting_dir(batch_dir)
    scenario_rows = load_json(agg_dir / 'scenario_repeat_summary.json')
    phase_rows = load_json(agg_dir / 'recovery_phase_distribution.json') if (agg_dir / 'recovery_phase_distribution.json').exists() else []
    phase_by_id = {str(r['scenario_id']): r for r in phase_rows}

    rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in scenario_rows:
        phase = phase_by_id.get(str(row['scenario_id']), {})
        late_share = round(float(phase.get('late_recovery_share_mean', 0.0) or 0.0), 6)
        concentration = round(float(row.get('temporal_clustering_busiest_10pct_interval_share_100ms_mean', 0.0) or 0.0), 6)
        expired = round(float(row.get('expired_rate_mean', 0.0) or 0.0), 6)
        entry = {
            'scenario_id': row['scenario_id'],
            'boundary_type': row['boundary_type'],
            'family': row['family'],
            'severity': row['severity'],
            'severity_display': row.get('severity_display', scenario_display_severity(str(row['family']), str(row['severity']))),
            'scenario_display_label': row.get('scenario_display_label', scenario_display_label(str(row['family']), str(row['severity']))),
            'configuration': row['configuration'],
            'scenario_role': row.get('scenario_role', 'main_core'),
            'scenario_role_detail': row.get('scenario_role_detail', scenario_role_tag(str(row['family']), str(row['severity']), None)),
            'median_tta_seconds': round(float(row.get('mean_time_to_attainment_seconds_median', row.get('mean_time_to_attainment_seconds_mean', 0.0)) or 0.0), 6),
            'p95_tta_seconds': round(float(row.get('p95_time_to_attainment_seconds_mean', 0.0) or 0.0), 6),
            'concentration_share_100ms': concentration,
            'late_recovery_share': late_share,
            'expired_rate_mean': expired,
            'placement_signature': compact_signature(late_share, concentration, expired),
            'gloss': signature_gloss(str(row['configuration']), late_share, concentration, expired),
        }
        rows.append(entry)
        grouped[(entry['boundary_type'], entry['family'], entry['severity'])].append(entry)

    comparison_rows: list[dict[str, Any]] = []
    thesis_rows: list[dict[str, Any]] = []
    for (boundary, family, severity), entries in sorted(grouped.items()):
        by_concentration = sorted(entries, key=lambda r: r['concentration_share_100ms'], reverse=True)
        by_late = sorted(entries, key=lambda r: r['late_recovery_share'], reverse=True)
        by_expiry = sorted(entries, key=lambda r: r['expired_rate_mean'], reverse=True)
        row = {
            'boundary_type': boundary,
            'family': family,
            'severity': severity,
            'severity_display': by_concentration[0].get('severity_display', severity),
            'scenario_display_label': by_concentration[0].get('scenario_display_label', scenario_display_label(family, severity)),
            'scenario_role_detail': by_concentration[0].get('scenario_role_detail', scenario_role_tag(family, severity, None)),
            'highest_concentration_configuration': by_concentration[0]['configuration'],
            'highest_late_recovery_configuration': by_late[0]['configuration'],
            'highest_expired_rate_configuration': by_expiry[0]['configuration'],
            'concentration_spread': round(by_concentration[0]['concentration_share_100ms'] - by_concentration[-1]['concentration_share_100ms'], 6),
            'late_recovery_spread': round(by_late[0]['late_recovery_share'] - by_late[-1]['late_recovery_share'], 6),
            'expired_rate_spread': round(by_expiry[0]['expired_rate_mean'] - by_expiry[-1]['expired_rate_mean'], 6),
        }
        comparison_rows.append(row)
        thesis_rows.append({
            **row,
            'concentration_leader_signature': by_concentration[0]['placement_signature'],
            'late_recovery_leader_signature': by_late[0]['placement_signature'],
            'expiry_leader_signature': by_expiry[0]['placement_signature'],
        })

    write_csv(agg_dir / 'placement_signature_summary.csv', rows)
    dump_json(agg_dir / 'placement_signature_summary.json', rows)
    write_csv(agg_dir / 'placement_signature_comparison.csv', comparison_rows)
    dump_json(agg_dir / 'placement_signature_comparison.json', comparison_rows)
    write_csv(thesis_dir / 'placement_signature_summary.csv', rows)
    dump_json(thesis_dir / 'placement_signature_summary.json', rows)
    write_csv(thesis_dir / 'placement_signature_comparison.csv', thesis_rows)
    dump_json(thesis_dir / 'placement_signature_comparison.json', thesis_rows)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
