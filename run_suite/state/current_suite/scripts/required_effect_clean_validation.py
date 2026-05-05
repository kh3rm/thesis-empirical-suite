from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

from batch_utils import dump_json, thesis_supporting_dir, write_csv


CONFIGURATIONS = ("transient_immediate", "retained_immediate", "retained_deferred")
HANDLING_GAP_SEVERITIES = ("standard", "extreme")
DUPLICATE_SEVERITIES = ("standard", "extreme")
SOURCE_OMISSION_SEVERITIES = ("standard",)

MIN_REPLAYABLE_GAP_DELTA = 20.0
MAX_RETAINED_GAP_DELTA = 10.0
FAIL_REPLAYABLE_GAP_DELTA = 5.0

MIN_DUPLICATE_RELIEF_RATIO = 0.70
FAIL_DUPLICATE_RELIEF_RATIO = 0.20

MAX_SOURCE_OMISSION_SPREAD = 5.0
FAIL_SOURCE_OMISSION_SPREAD = 20.0
MIN_SOURCE_OMISSION_SIGNAL = 20.0

MIN_DEFERRED_LAG_DELTA_SECONDS = 0.15
MIN_DEFERRED_RECON_PASSES = 1.0
MIN_DEFERRED_RECON_DELTA = 3.0
MIN_DEFERRED_COST_PASS_ROWS = 2


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def as_float(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key, 0.0))
    except Exception:
        return 0.0


def row_for(
    rows: list[dict[str, str]],
    *,
    family: str,
    severity: str,
    configuration: str,
) -> dict[str, str] | None:
    for row in rows:
        if (
            row.get("family") == family
            and row.get("severity") == severity
            and row.get("configuration") == configuration
        ):
            return row
    return None


def status_for(checks: list[bool], fail_guards: list[bool], missing: bool) -> str:
    if missing:
        return "unclear"
    if checks and all(checks):
        return "pass"
    if fail_guards and any(fail_guards):
        return "fail"
    return "unclear"


def scoped_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    allowed_families = {"baseline", "duplicate_pressure", "handling_gap_replayable", "source_omission"}
    allowed_severities = {"standard", "extreme"}
    for row in rows:
        family = str(row.get("family", ""))
        severity = str(row.get("severity", ""))
        config = str(row.get("configuration", ""))
        if family not in allowed_families:
            continue
        if severity not in allowed_severities and not (family == "baseline" and severity == "standard"):
            continue
        if config not in CONFIGURATIONS:
            continue
        out.append(
            {
                "family": family,
                "severity": severity,
                "configuration": config,
                "attainment_rate_mean": round(as_float(row, "attainment_rate_mean"), 6),
                "unattained_case_count_mean": round(as_float(row, "unattained_case_count_mean"), 6),
                "duplicate_side_effect_execution_count_mean": round(
                    as_float(row, "duplicate_side_effect_execution_count_mean"), 6
                ),
                "correction_rewrite_count_mean": round(as_float(row, "correction_rewrite_count_mean"), 6),
                "producer_complete_to_last_attainment_seconds_mean": round(
                    as_float(row, "producer_complete_to_last_attainment_seconds_mean"), 6
                ),
                "reconciliation_pass_count_mean": round(as_float(row, "reconciliation_pass_count_mean"), 6),
                "run_duration_seconds_mean": round(as_float(row, "run_duration_seconds_mean"), 6),
            }
        )
    out.sort(key=lambda r: (r["family"], r["severity"], r["configuration"]))
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("Usage: required_effect_clean_validation.py <batch_dir>")

    batch_dir = Path(argv[1]).resolve()
    agg_dir = batch_dir / "aggregates"
    thesis_dir = thesis_supporting_dir(batch_dir)
    family_csv = agg_dir / "family_comparison_summary.csv"
    if not family_csv.exists():
        raise SystemExit(f"Missing family summary: {family_csv}")

    rows = load_rows(family_csv)
    clean_rows = scoped_rows(rows)

    # C1: Replay recovers handling-gap omissions (emitted but missed in transient).
    handling_rows: list[dict[str, Any]] = []
    handling_missing = False
    for severity in HANDLING_GAP_SEVERITIES:
        ti = row_for(rows, family="handling_gap_replayable", severity=severity, configuration="transient_immediate")
        ri = row_for(rows, family="handling_gap_replayable", severity=severity, configuration="retained_immediate")
        rd = row_for(rows, family="handling_gap_replayable", severity=severity, configuration="retained_deferred")
        if ti is None or ri is None or rd is None:
            handling_missing = True
            handling_rows.append(
                {
                    "severity": severity,
                    "missing_rows": {
                        "transient_immediate": ti is None,
                        "retained_immediate": ri is None,
                        "retained_deferred": rd is None,
                    },
                }
            )
            continue
        ti_unattained = as_float(ti, "unattained_case_count_mean")
        ri_unattained = as_float(ri, "unattained_case_count_mean")
        rd_unattained = as_float(rd, "unattained_case_count_mean")
        handling_rows.append(
            {
                "severity": severity,
                "transient_unattained": round(ti_unattained, 6),
                "retained_immediate_unattained": round(ri_unattained, 6),
                "retained_deferred_unattained": round(rd_unattained, 6),
                "transient_minus_retained_immediate": round(ti_unattained - ri_unattained, 6),
                "transient_minus_retained_deferred": round(ti_unattained - rd_unattained, 6),
                "retained_gap_abs": round(abs(ri_unattained - rd_unattained), 6),
            }
        )

    handling_valid = [row for row in handling_rows if "missing_rows" not in row]
    c1_checks = [
        row["transient_minus_retained_immediate"] >= MIN_REPLAYABLE_GAP_DELTA
        and row["transient_minus_retained_deferred"] >= MIN_REPLAYABLE_GAP_DELTA
        and row["retained_gap_abs"] <= MAX_RETAINED_GAP_DELTA
        for row in handling_valid
    ]
    c1_fail = [
        row["transient_minus_retained_immediate"] <= FAIL_REPLAYABLE_GAP_DELTA
        and row["transient_minus_retained_deferred"] <= FAIL_REPLAYABLE_GAP_DELTA
        for row in handling_valid
    ]
    c1_status = status_for(c1_checks, c1_fail, handling_missing or not handling_valid)

    # C2: Deferred retained consolidates duplicate side effects.
    duplicate_rows: list[dict[str, Any]] = []
    duplicate_missing = False
    for severity in DUPLICATE_SEVERITIES:
        ti = row_for(rows, family="duplicate_pressure", severity=severity, configuration="transient_immediate")
        ri = row_for(rows, family="duplicate_pressure", severity=severity, configuration="retained_immediate")
        rd = row_for(rows, family="duplicate_pressure", severity=severity, configuration="retained_deferred")
        if ti is None or ri is None or rd is None:
            duplicate_missing = True
            duplicate_rows.append(
                {
                    "severity": severity,
                    "missing_rows": {
                        "transient_immediate": ti is None,
                        "retained_immediate": ri is None,
                        "retained_deferred": rd is None,
                    },
                }
            )
            continue
        ti_side = as_float(ti, "duplicate_side_effect_execution_count_mean")
        ri_side = as_float(ri, "duplicate_side_effect_execution_count_mean")
        rd_side = as_float(rd, "duplicate_side_effect_execution_count_mean")
        best_immediate = min(ti_side, ri_side)
        relief = best_immediate - rd_side
        relief_ratio = 0.0 if best_immediate <= 0 else relief / best_immediate
        duplicate_rows.append(
            {
                "severity": severity,
                "best_immediate_duplicate_side_effect_execution_count": round(best_immediate, 6),
                "deferred_duplicate_side_effect_execution_count": round(rd_side, 6),
                "deferred_correction_rewrite_count": round(as_float(rd, "correction_rewrite_count_mean"), 6),
                "relief_absolute": round(relief, 6),
                "relief_ratio": round(relief_ratio, 6),
            }
        )

    duplicate_valid = [row for row in duplicate_rows if "missing_rows" not in row]
    c2_checks = [
        row["relief_ratio"] >= MIN_DUPLICATE_RELIEF_RATIO and row["deferred_correction_rewrite_count"] > 0
        for row in duplicate_valid
    ]
    c2_fail = [row["relief_ratio"] <= FAIL_DUPLICATE_RELIEF_RATIO for row in duplicate_valid]
    c2_status = status_for(c2_checks, c2_fail, duplicate_missing or not duplicate_valid)

    # C3: Source omission is outside replay scope (spread near zero across configurations).
    source_rows: list[dict[str, Any]] = []
    source_missing = False
    for severity in SOURCE_OMISSION_SEVERITIES:
        values: dict[str, float] = {}
        missing = False
        for configuration in CONFIGURATIONS:
            row = row_for(rows, family="source_omission", severity=severity, configuration=configuration)
            if row is None:
                missing = True
                continue
            values[configuration] = as_float(row, "unattained_case_count_mean")
        if missing or len(values) != len(CONFIGURATIONS):
            source_missing = True
            source_rows.append(
                {
                    "severity": severity,
                    "missing_rows": {
                        config: config not in values for config in CONFIGURATIONS
                    },
                }
            )
            continue
        spread = max(values.values()) - min(values.values())
        signal = max(values.values())
        source_rows.append(
            {
                "severity": severity,
                "transient_unattained": round(values["transient_immediate"], 6),
                "retained_immediate_unattained": round(values["retained_immediate"], 6),
                "retained_deferred_unattained": round(values["retained_deferred"], 6),
                "spread_unattained": round(spread, 6),
                "signal_unattained": round(signal, 6),
            }
        )

    source_valid = [row for row in source_rows if "missing_rows" not in row]
    c3_checks = [
        row["spread_unattained"] <= MAX_SOURCE_OMISSION_SPREAD and row["signal_unattained"] >= MIN_SOURCE_OMISSION_SIGNAL
        for row in source_valid
    ]
    c3_fail = [row["spread_unattained"] >= FAIL_SOURCE_OMISSION_SPREAD for row in source_valid]
    c3_status = status_for(c3_checks, c3_fail, source_missing or not source_valid)

    # C4: Deferred retained adds settlement cost (lag and reconciliation).
    cost_rows: list[dict[str, Any]] = []
    for family, severities in (
        ("duplicate_pressure", DUPLICATE_SEVERITIES),
        ("handling_gap_replayable", HANDLING_GAP_SEVERITIES),
    ):
        for severity in severities:
            ri = row_for(rows, family=family, severity=severity, configuration="retained_immediate")
            rd = row_for(rows, family=family, severity=severity, configuration="retained_deferred")
            if ri is None or rd is None:
                continue
            ri_lag = as_float(ri, "producer_complete_to_last_attainment_seconds_mean")
            rd_lag = as_float(rd, "producer_complete_to_last_attainment_seconds_mean")
            ri_recon = as_float(ri, "reconciliation_pass_count_mean")
            rd_recon = as_float(rd, "reconciliation_pass_count_mean")
            cost_rows.append(
                {
                    "family": family,
                    "severity": severity,
                    "retained_immediate_lag_seconds": round(ri_lag, 6),
                    "retained_deferred_lag_seconds": round(rd_lag, 6),
                    "lag_delta_seconds": round(rd_lag - ri_lag, 6),
                    "retained_immediate_reconciliation_pass_count": round(ri_recon, 6),
                    "retained_deferred_reconciliation_pass_count": round(rd_recon, 6),
                    "reconciliation_delta": round(rd_recon - ri_recon, 6),
                }
            )

    c4_pass_rows = [
        row
        for row in cost_rows
        if (
            row["lag_delta_seconds"] >= MIN_DEFERRED_LAG_DELTA_SECONDS
            or row["reconciliation_delta"] >= MIN_DEFERRED_RECON_DELTA
        )
        and row["retained_deferred_reconciliation_pass_count"] >= MIN_DEFERRED_RECON_PASSES
    ]
    c4_checks = [len(c4_pass_rows) >= MIN_DEFERRED_COST_PASS_ROWS]
    c4_fail = [len(c4_pass_rows) == 0]
    c4_status = status_for(c4_checks, c4_fail, not cost_rows)

    statuses = [c1_status, c2_status, c3_status, c4_status]
    if "fail" in statuses:
        overall = "fail"
    elif statuses and all(status == "pass" for status in statuses):
        overall = "pass"
    else:
        overall = "unclear"

    payload = {
        "overall_status": overall,
        "thresholds": {
            "min_replayable_gap_delta": MIN_REPLAYABLE_GAP_DELTA,
            "max_retained_gap_delta": MAX_RETAINED_GAP_DELTA,
            "min_duplicate_relief_ratio": MIN_DUPLICATE_RELIEF_RATIO,
            "max_source_omission_spread": MAX_SOURCE_OMISSION_SPREAD,
            "min_source_omission_signal": MIN_SOURCE_OMISSION_SIGNAL,
            "min_deferred_lag_delta_seconds": MIN_DEFERRED_LAG_DELTA_SECONDS,
            "min_deferred_recon_passes": MIN_DEFERRED_RECON_PASSES,
            "min_deferred_recon_delta": MIN_DEFERRED_RECON_DELTA,
            "min_deferred_cost_pass_rows": MIN_DEFERRED_COST_PASS_ROWS,
        },
        "claims": {
            "C1_replay_recovers_handling_gap_omissions": {
                "status": c1_status,
                "expected_signature": "transient misses during handling gap remain unattained, while retained variants recover by replay",
            },
            "C2_deferred_consolidates_duplicate_side_effects": {
                "status": c2_status,
                "expected_signature": "retained_deferred strongly reduces duplicate side-effect execution by coalescing before settlement",
            },
            "C3_source_omission_is_outside_replay_scope": {
                "status": c3_status,
                "expected_signature": "when events are never emitted, replay-capable retention does not improve unattained outcomes",
            },
            "C4_deferred_adds_settlement_cost": {
                "status": c4_status,
                "expected_signature": "retained_deferred increases settlement lag/reconciliation work relative to retained_immediate",
            },
        },
        "handling_gap_rows": handling_rows,
        "duplicate_rows": duplicate_rows,
        "source_omission_rows": source_rows,
        "deferred_cost_rows": cost_rows,
        "deferred_cost_pass_rows": len(c4_pass_rows),
    }

    md_lines = [
        "# Required-effect clean validation",
        "",
        "This report isolates required-effect semantics into replayable handling omissions, duplicate consolidation, and non-replayable source omission control.",
        "",
        f"- overall_status: {overall}",
        "",
        "## Claim statuses",
        f"- C1 replay recovers handling-gap omissions: {c1_status}",
        f"- C2 deferred consolidates duplicate side effects: {c2_status}",
        f"- C3 source omission is outside replay scope: {c3_status}",
        f"- C4 deferred adds settlement cost: {c4_status}",
        "",
        "## C1 handling-gap rows",
    ]
    for row in handling_rows:
        if "missing_rows" in row:
            md_lines.append(f"- {row['severity']}: missing rows {row['missing_rows']}")
            continue
        md_lines.append(
            f"- {row['severity']}: transient={row['transient_unattained']:.3f}, "
            f"retained_immediate={row['retained_immediate_unattained']:.3f}, "
            f"retained_deferred={row['retained_deferred_unattained']:.3f}, "
            f"delta_ti_ri={row['transient_minus_retained_immediate']:.3f}, "
            f"delta_ti_rd={row['transient_minus_retained_deferred']:.3f}"
        )
    md_lines.extend(["", "## C2 duplicate rows"])
    for row in duplicate_rows:
        if "missing_rows" in row:
            md_lines.append(f"- {row['severity']}: missing rows {row['missing_rows']}")
            continue
        md_lines.append(
            f"- {row['severity']}: best_immediate={row['best_immediate_duplicate_side_effect_execution_count']:.3f}, "
            f"deferred={row['deferred_duplicate_side_effect_execution_count']:.3f}, "
            f"relief_ratio={row['relief_ratio']:.3f}, rewrite={row['deferred_correction_rewrite_count']:.3f}"
        )
    md_lines.extend(["", "## C3 source omission rows"])
    for row in source_rows:
        if "missing_rows" in row:
            md_lines.append(f"- {row['severity']}: missing rows {row['missing_rows']}")
            continue
        md_lines.append(
            f"- {row['severity']}: transient={row['transient_unattained']:.3f}, "
            f"retained_immediate={row['retained_immediate_unattained']:.3f}, "
            f"retained_deferred={row['retained_deferred_unattained']:.3f}, "
            f"spread={row['spread_unattained']:.3f}"
        )
    md_lines.extend(["", "## C4 deferred-cost rows"])
    for row in cost_rows:
        md_lines.append(
            f"- {row['family']} | {row['severity']}: lag_delta={row['lag_delta_seconds']:.3f}s, "
            f"reconciliation_delta={row['reconciliation_delta']:.3f}, "
            f"rd_reconciliation={row['retained_deferred_reconciliation_pass_count']:.3f}"
        )

    md_text = "\n".join(md_lines) + "\n"

    write_csv(agg_dir / "required_effect_clean_matrix.csv", clean_rows)
    dump_json(agg_dir / "required_effect_clean_matrix.json", clean_rows)
    dump_json(agg_dir / "required_effect_clean_validation.json", payload)
    (agg_dir / "required_effect_clean_validation.md").write_text(md_text, encoding="utf-8")

    write_csv(thesis_dir / "required_effect_clean_matrix.csv", clean_rows)
    dump_json(thesis_dir / "required_effect_clean_matrix.json", clean_rows)
    dump_json(thesis_dir / "required_effect_clean_validation.json", payload)
    (thesis_dir / "required_effect_clean_validation.md").write_text(md_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
