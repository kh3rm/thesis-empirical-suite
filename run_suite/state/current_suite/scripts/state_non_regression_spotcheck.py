from __future__ import annotations

import json
import math
import sys
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from statistics import mean


def _to_float(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except Exception:
        return default


def _first_exposed_index(event_count: int, fraction: float) -> int:
    if event_count <= 0:
        return 0
    normalized = max(0.0, min(1.0, fraction))
    threshold = (Decimal(str(normalized)) * Decimal(event_count)).to_integral_value(rounding=ROUND_CEILING)
    first = int(threshold)
    return max(0, min(event_count, first))


def _expected_from_rendered(run_dir: Path) -> float:
    rendered = run_dir / "scenario.rendered.json"
    if not rendered.exists():
        return 0.0
    try:
        scenario = json.loads(rendered.read_text(encoding="utf-8"))
    except Exception:
        return 0.0
    if scenario.get("boundary_type", scenario.get("boundary")) != "state_non_regression":
        return 0.0
    event_count = int(scenario.get("event_count", 0) or 0)
    disturbance = scenario.get("disturbance") if isinstance(scenario.get("disturbance"), dict) else {}
    fraction = float(scenario.get("state_outage_exposed_start_fraction", disturbance.get("state_outage_exposed_start_fraction", 0.34)) or 0.0)
    if event_count <= 0:
        return 0.0
    first_exposed = _first_exposed_index(event_count, fraction)
    return float(max(0, event_count - first_exposed))


def _load_metrics(batch_dir: Path, family: str, configuration: str) -> list[dict]:
    raw_runs = batch_dir / "raw_runs"
    rows: list[dict] = []
    if not raw_runs.exists():
        return rows
    for run_dir in sorted(raw_runs.iterdir()):
        if not run_dir.is_dir() or family not in run_dir.name or configuration not in run_dir.name:
            continue
        metrics_path = run_dir / "artifacts" / "metrics_summary.json"
        if not metrics_path.exists():
            continue
        row = json.loads(metrics_path.read_text(encoding="utf-8"))
        if _to_float(row.get("state_outage_exposed_expected_event_count")) <= 0.0:
            row["state_outage_exposed_expected_event_count"] = _expected_from_rendered(run_dir)
        expected = _to_float(row.get("state_outage_exposed_expected_event_count"))
        seen = _to_float(row.get("state_outage_exposed_event_count"))
        drop = _to_float(row.get("state_transient_outage_drop_count"))
        if _to_float(row.get("state_outage_exposed_seen_fraction_of_expected")) <= 0.0 and expected > 0:
            row["state_outage_exposed_seen_fraction_of_expected"] = seen / expected
        if _to_float(row.get("state_outage_exposed_unseen_count")) <= 0.0 and expected > 0:
            row["state_outage_exposed_unseen_count"] = max(0.0, expected - seen)
        if _to_float(row.get("state_outage_exposed_unseen_fraction_of_expected")) <= 0.0 and expected > 0:
            row["state_outage_exposed_unseen_fraction_of_expected"] = max(0.0, expected - seen) / expected
        if _to_float(row.get("state_transient_outage_drop_fraction_of_expected")) <= 0.0 and expected > 0:
            row["state_transient_outage_drop_fraction_of_expected"] = drop / expected
        if _to_float(row.get("state_outage_exposed_loss_count")) <= 0.0 and expected > 0:
            row["state_outage_exposed_loss_count"] = max(0.0, expected - seen) + drop
        if _to_float(row.get("state_outage_exposed_loss_fraction_of_expected")) <= 0.0 and expected > 0:
            row["state_outage_exposed_loss_fraction_of_expected"] = (max(0.0, expected - seen) + drop) / expected
        rows.append(row)
    return rows


def _m(rows: list[dict], key: str) -> float:
    return mean(_to_float(r.get(key)) for r in rows) if rows else 0.0


def _append_section(lines: list[str], title: str, transient_rows: list[dict], retained_rows: list[dict]) -> tuple[bool, dict[str, float]]:
    ok = True
    lines.append(f"## {title}\n\n")
    summary: dict[str, float] = {}
    if not transient_rows or not retained_rows:
        lines.append("Missing raw-run metrics for transient and/or retained configuration.\n\n")
        return False, summary

    keys = {
        "t_expected": "state_outage_exposed_expected_event_count",
        "t_seen": "state_outage_exposed_event_count",
        "t_seen_frac": "state_outage_exposed_seen_fraction_of_expected",
        "t_unseen": "state_outage_exposed_unseen_count",
        "t_drop": "state_transient_outage_drop_count",
        "t_loss": "state_outage_exposed_loss_count",
        "t_loss_frac": "state_outage_exposed_loss_fraction_of_expected",
        "t_omit": "state_latest_version_omission_rate",
        "t_forward": "state_forward_resumption_adequacy_rate",
        "t_forward_after_loss": "state_forward_resumption_after_loss_rate",
    }
    for short, key in keys.items():
        summary[short] = _m(transient_rows, key)
    summary["r_expected"] = _m(retained_rows, "state_outage_exposed_expected_event_count")
    summary["r_seen"] = _m(retained_rows, "state_outage_exposed_event_count")
    summary["r_seen_frac"] = _m(retained_rows, "state_outage_exposed_seen_fraction_of_expected")
    summary["r_unseen"] = _m(retained_rows, "state_outage_exposed_unseen_count")
    summary["r_drop"] = _m(retained_rows, "state_transient_outage_drop_count")
    summary["r_loss"] = _m(retained_rows, "state_outage_exposed_loss_count")
    summary["r_loss_frac"] = _m(retained_rows, "state_outage_exposed_loss_fraction_of_expected")
    summary["r_omit"] = _m(retained_rows, "state_latest_version_omission_rate")
    summary["r_forward"] = _m(retained_rows, "state_forward_resumption_adequacy_rate")
    summary["r_forward_after_loss"] = _m(retained_rows, "state_forward_resumption_after_loss_rate")

    lines.extend([
        f"- transient expected-exposed count: {summary['t_expected']:.3f}\n",
        f"- retained expected-exposed count: {summary['r_expected']:.3f}\n",
        f"- transient seen-exposed count: {summary['t_seen']:.3f}\n",
        f"- retained seen-exposed count: {summary['r_seen']:.3f}\n",
        f"- transient seen fraction: {summary['t_seen_frac']:.6f}\n",
        f"- retained seen fraction: {summary['r_seen_frac']:.6f}\n",
        f"- transient unseen count: {summary['t_unseen']:.3f}\n",
        f"- retained unseen count: {summary['r_unseen']:.3f}\n",
        f"- transient explicit-drop count: {summary['t_drop']:.3f}\n",
        f"- retained explicit-drop count: {summary['r_drop']:.3f}\n",
        f"- transient total-loss count: {summary['t_loss']:.3f}\n",
        f"- retained total-loss count: {summary['r_loss']:.3f}\n",
        f"- transient total-loss fraction: {summary['t_loss_frac']:.6f}\n",
        f"- retained total-loss fraction: {summary['r_loss_frac']:.6f}\n",
        f"- transient omission rate: {summary['t_omit']:.6f}\n",
        f"- retained omission rate: {summary['r_omit']:.6f}\n",
        f"- transient forward-resumption adequacy: {summary['t_forward']:.6f}\n",
        f"- retained forward-resumption adequacy: {summary['r_forward']:.6f}\n",
        f"- transient forward-resumption after loss: {summary['t_forward_after_loss']:.6f}\n",
        f"- retained forward-resumption after loss: {summary['r_forward_after_loss']:.6f}\n",
    ])

    if summary['t_expected'] <= 0.0:
        ok = False
        lines.append("- FAIL: transient run has no expected exposed slice.\n")
    if abs(summary['t_expected'] - summary['r_expected']) > 1e-6:
        ok = False
        lines.append("- FAIL: transient and retained expected exposed slices differ.\n")
    lines.append("\n")
    return ok, summary


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SystemExit("Usage: state_non_regression_spotcheck.py <batch_dir>")
    batch_dir = Path(argv[1])
    report = batch_dir / "reports" / "state_non_regression_spotcheck.md"
    lines = ["# State non-regression spot-check\n\n"]
    overall_ok = True

    t_rows = _load_metrics(batch_dir, "backlog_shock", "transient_immediate")
    r_rows = _load_metrics(batch_dir, "backlog_shock", "retained_immediate")
    section_ok, s = _append_section(lines, "Recoverability-sensitive backlog shock", t_rows, r_rows)
    overall_ok &= section_ok
    if t_rows and r_rows:
        if s['t_loss'] <= 0.0:
            overall_ok = False
            lines.append("- FAIL: transient backlog shock did not lose any of the expected exposed latest slice.\n")
        if s['t_omit'] <= s['r_omit']:
            overall_ok = False
            lines.append("- FAIL: transient omission did not exceed retained omission under backlog shock.\n")
        lines.append("\n")

    fr_t = _load_metrics(batch_dir, "backlog_forward_resume", "transient_immediate")
    fr_r = _load_metrics(batch_dir, "backlog_forward_resume", "retained_immediate")
    if fr_t or fr_r:
        section_ok, s = _append_section(lines, "Forward-resumption backlog scenario", fr_t, fr_r)
        overall_ok &= section_ok
        if fr_t and fr_r:
            if s['t_loss'] <= 0.0:
                overall_ok = False
                lines.append("- FAIL: transient forward-resumption scenario did not lose the exposed target slice.\n")
            if s['t_forward'] <= 0.0:
                overall_ok = False
                lines.append("- FAIL: transient forward-resumption adequacy did not recover after target-slice loss.\n")
            if s['t_forward_after_loss'] <= 0.0:
                overall_ok = False
                lines.append("- FAIL: no lost target slice was later superseded by forward progress.\n")
            if _m(fr_t, 'state_latest_version_attainment_rate') <= 0.0 or _m(fr_r, 'state_latest_version_attainment_rate') <= 0.0:
                overall_ok = False
                lines.append("- FAIL: forward-resumption scenario did not preserve final latest-state attainment.\n")
            lines.append("\n")

    lines.append(f"Result: {'PASS' if overall_ok else 'CHECK FAILED'}\n")
    report.write_text(''.join(lines), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
