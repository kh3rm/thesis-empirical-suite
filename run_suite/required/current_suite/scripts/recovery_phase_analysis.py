from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from batch_utils import dump_json, load_json, thesis_supporting_dir, write_csv, scenario_display_label, scenario_display_severity, scenario_role_tag


def load_outcome_times(path: Path) -> list[float]:
    values: list[float] = []
    if not path.exists():
        return values
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        raw = payload.get('resolved_at_seconds', payload.get('attained_at_seconds'))
        try:
            values.append(float(raw))
        except Exception:
            continue
    return sorted(values)


def ratio(count: int, total: int) -> float:
    return round(0.0 if total <= 0 else count / total, 6)


def busiest_window_share(values: list[float], bucket_width_seconds: float = 0.25) -> float:
    if not values:
        return 0.0
    counts: dict[int, int] = defaultdict(int)
    for value in values:
        counts[int(value / bucket_width_seconds)] += 1
    ordered = sorted(counts.values(), reverse=True)
    top_bucket_count = max(1, int(len(ordered) * 0.1))
    return round(sum(ordered[:top_bucket_count]) / len(values), 6)


def dominant_phase(before_share: float, early_post_share: float, late_share: float) -> str:
    if before_share >= max(early_post_share, late_share):
        return 'pre-completion attainment'
    if early_post_share >= late_share:
        return 'early post-production catch-up'
    return 'late recovery attainment'


def burden_shape(after_share: float, late_share: float, concentration_share: float) -> str:
    if concentration_share >= 0.45:
        return 'concentrated catch-up'
    if late_share >= 0.35 or after_share >= 0.35:
        return 'later-shifted recovery'
    return 'mostly pre-completion recovery'


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit('Usage: recovery_phase_analysis.py <batch_dir>')
    batch_dir = Path(argv[1])
    raw_runs = batch_dir / 'raw_runs'
    agg_dir = batch_dir / 'aggregates'
    thesis_dir = thesis_supporting_dir(batch_dir)
    batch_meta = load_json(batch_dir / 'batch_meta.json') if (batch_dir / 'batch_meta.json').exists() else {}

    per_run_rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str, str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for run_dir in sorted(raw_runs.iterdir() if raw_runs.exists() else []):
        if not run_dir.is_dir():
            continue
        env_path = run_dir / 'scenario.env'
        summary_path = run_dir / 'logs' / 'consumer_summary.json'
        outcome_path = run_dir / 'logs' / 'outcome.log'
        if not env_path.exists() or not summary_path.exists() or not outcome_path.exists():
            continue
        env = {}
        for raw in env_path.read_text(encoding='utf-8').splitlines():
            if '=' in raw:
                k, v = raw.split('=', 1)
                env[k.strip()] = v.strip()
        summary = load_json(summary_path)
        times = load_outcome_times(outcome_path)
        total = len(times)
        if total == 0:
            continue
        producer_complete = float(summary.get('producer_complete_seen_elapsed_seconds') or 0.0)
        last_attainment = float(summary.get('last_attainment_seconds') or (times[-1] if times else 0.0))
        early_post_end = producer_complete + max(0.0, last_attainment - producer_complete) / 2.0 if last_attainment > producer_complete else producer_complete
        before_pc = sum(1 for t in times if t <= producer_complete)
        early_post = sum(1 for t in times if producer_complete < t <= early_post_end)
        late_recovery = sum(1 for t in times if t > early_post_end)
        row = {
            'run_id': run_dir.name,
            'scenario_id': env.get('SCENARIO_ID'),
            'base_scenario_id': env.get('BASE_SCENARIO_ID', env.get('SCENARIO_ID')),
            'boundary_type': env.get('BOUNDARY'),
            'configuration': env.get('CONFIGURATION'),
            'family': env.get('FAMILY'),
            'severity': env.get('SEVERITY'),
            'scenario_role': env.get('SCENARIO_ROLE', 'main_core'),
            'scenario_role_detail': env.get('SCENARIO_ROLE_DETAIL', scenario_role_tag(str(env.get('FAMILY')), str(env.get('SEVERITY')), None)),
            'severity_display': env.get('SCENARIO_DISPLAY_SEVERITY', scenario_display_severity(str(env.get('FAMILY')), str(env.get('SEVERITY')))),
            'scenario_display_label': env.get('SCENARIO_DISPLAY_LABEL', scenario_display_label(str(env.get('FAMILY')), str(env.get('SEVERITY')))).replace('_', ' '),
            'run_mode': env.get('RUN_MODE', batch_meta.get('run_mode', 'evidence')),
            'producer_complete_seen_elapsed_seconds': round(producer_complete, 6),
            'last_attainment_seconds': round(last_attainment, 6),
            'early_post_recovery_cut_seconds': round(early_post_end, 6),
            'before_producer_complete_share': ratio(before_pc, total),
            'early_post_production_share': ratio(early_post, total),
            'late_recovery_share': ratio(late_recovery, total),
            'busiest_window_share_250ms': busiest_window_share(times, 0.25),
            'attained_after_producer_complete_share': round(float(summary.get('attained_after_producer_complete_share', 0.0) or 0.0), 6),
        }
        per_run_rows.append(row)
        key = (row['scenario_id'], row['base_scenario_id'], row['boundary_type'], row['configuration'], row['family'], row['severity'])
        grouped[key].append(row)

    summary_rows: list[dict[str, Any]] = []
    thesis_rows: list[dict[str, Any]] = []
    for key, rows in sorted(grouped.items()):
        scenario_id, base_scenario_id, boundary_type, configuration, family, severity = key
        def avg(field: str) -> float:
            return round(sum(float(r[field]) for r in rows) / max(len(rows), 1), 6)
        before_share = avg('before_producer_complete_share')
        early_post_share = avg('early_post_production_share')
        late_share = avg('late_recovery_share')
        after_share = avg('attained_after_producer_complete_share')
        concentration_share = avg('busiest_window_share_250ms')
        dominant = dominant_phase(before_share, early_post_share, late_share)
        burden = burden_shape(after_share, late_share, concentration_share)
        summary = {
            'scenario_id': scenario_id,
            'base_scenario_id': base_scenario_id,
            'boundary_type': boundary_type,
            'configuration': configuration,
            'family': family,
            'severity': severity,
            'severity_display': rows[0]['severity_display'],
            'scenario_display_label': rows[0]['scenario_display_label'],
            'scenario_role': rows[0]['scenario_role'],
            'scenario_role_detail': rows[0]['scenario_role_detail'],
            'run_mode': rows[0]['run_mode'],
            'repeat_count': len(rows),
            'before_producer_complete_share_mean': before_share,
            'early_post_production_share_mean': early_post_share,
            'late_recovery_share_mean': late_share,
            'attained_after_producer_complete_share_mean': after_share,
            'busiest_window_share_250ms_mean': concentration_share,
            'dominant_recovery_phase': dominant,
            'recovery_burden_shape': burden,
        }
        summary_rows.append(summary)
        thesis_rows.append({
            'scenario_id': scenario_id,
            'boundary_type': boundary_type,
            'configuration': configuration,
            'family': family,
            'severity': severity,
            'severity_display': rows[0]['severity_display'],
            'scenario_display_label': rows[0]['scenario_display_label'],
            'scenario_role': rows[0]['scenario_role'],
            'scenario_role_detail': rows[0]['scenario_role_detail'],
            'dominant_recovery_phase': dominant,
            'recovery_burden_shape': burden,
            'before_producer_complete_share_mean': before_share,
            'attained_after_producer_complete_share_mean': after_share,
            'late_recovery_share_mean': late_share,
            'busiest_window_share_250ms_mean': concentration_share,
        })

    write_csv(agg_dir / 'recovery_phase_distribution_per_run.csv', per_run_rows)
    dump_json(agg_dir / 'recovery_phase_distribution_per_run.json', per_run_rows)
    write_csv(agg_dir / 'recovery_phase_distribution.csv', summary_rows)
    dump_json(agg_dir / 'recovery_phase_distribution.json', summary_rows)
    write_csv(thesis_dir / 'recovery_phase_distribution.csv', thesis_rows)
    dump_json(thesis_dir / 'recovery_phase_distribution.json', thesis_rows)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
