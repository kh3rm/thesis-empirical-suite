from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

from batch_utils import dump_json, thesis_supporting_dir


CONFIGURATIONS = ("transient_immediate", "retained_immediate", "retained_deferred")
SEVERITY_RANK = {"low": 0, "medium": 1, "standard": 2, "high": 2, "extreme": 3}

MIN_DUPLICATE_RATE_GAIN = 0.08
MAX_DUPLICATE_UNATTAINED_DELTA = 5.0
MIN_OMISSION_UNATTAINED_DELTA = 80.0
MIN_OMISSION_ATTAINMENT_DROP = 0.08

MIN_MIXED_DIFFERING_SEVERITIES = 1
MIN_DIRECT_RELIEF = 100.0
MIN_DIRECT_RELIEF_SEVERITIES = 2


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def as_float(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key, 0.0))
    except Exception:
        return 0.0


def row_for(rows: list[dict[str, str]], *, family: str, configuration: str, severity: str = "standard") -> dict[str, str] | None:
    for row in rows:
        if row.get("family") == family and row.get("configuration") == configuration and row.get("severity") == severity:
            return row
    return None


def pattern_status(checks: list[bool], fail_guards: list[bool], missing: bool) -> str:
    if missing:
        return "unclear"
    if checks and all(checks):
        return "pass"
    if fail_guards and any(fail_guards):
        return "fail"
    return "unclear"


def severity_key(value: str) -> tuple[int, str]:
    return (SEVERITY_RANK.get(value, 99), value)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("Usage: required_effect_pattern_validation.py <batch_dir>")

    batch_dir = Path(argv[1]).resolve()
    agg_dir = batch_dir / "aggregates"
    thesis_dir = thesis_supporting_dir(batch_dir)

    family_csv = agg_dir / "family_comparison_summary.csv"
    guideline_matrix_csv = agg_dir / "required_effect_guideline_matrix.csv"
    recommendations_csv = agg_dir / "required_effect_guideline_recommendations.csv"
    if not family_csv.exists():
        raise SystemExit(f"Missing family summary: {family_csv}")
    if not guideline_matrix_csv.exists():
        raise SystemExit(f"Missing guideline matrix: {guideline_matrix_csv}")
    if not recommendations_csv.exists():
        raise SystemExit(f"Missing recommendations: {recommendations_csv}")

    family_rows = load_rows(family_csv)
    matrix_rows = load_rows(guideline_matrix_csv)
    rec_rows = load_rows(recommendations_csv)

    # Pattern 1 and 2 (standard severity anchoring, same as focused A/B semantics)
    p1_rows: list[dict[str, Any]] = []
    missing_any = False
    for config in CONFIGURATIONS:
        baseline = row_for(family_rows, family="baseline", configuration=config, severity="standard")
        duplicate = row_for(family_rows, family="duplicate_pressure", configuration=config, severity="standard")
        omission = row_for(family_rows, family="omission_pressure", configuration=config, severity="standard")
        if baseline is None or duplicate is None or omission is None:
            missing_any = True
            p1_rows.append(
                {
                    "configuration": config,
                    "missing_rows": {
                        "baseline": baseline is None,
                        "duplicate_pressure": duplicate is None,
                        "omission_pressure": omission is None,
                    },
                }
            )
            continue

        baseline_unattained = as_float(baseline, "unattained_case_count_mean")
        baseline_attainment = as_float(baseline, "attainment_rate_mean")
        baseline_duplicate_rate = as_float(baseline, "duplicate_delivery_rate_mean")
        duplicate_unattained = as_float(duplicate, "unattained_case_count_mean")
        duplicate_rate = as_float(duplicate, "duplicate_delivery_rate_mean")
        omission_unattained = as_float(omission, "unattained_case_count_mean")
        omission_attainment = as_float(omission, "attainment_rate_mean")

        p1_rows.append(
            {
                "configuration": config,
                "duplicate_rate_gain_vs_baseline": round(duplicate_rate - baseline_duplicate_rate, 6),
                "duplicate_unattained_delta_vs_baseline": round(duplicate_unattained - baseline_unattained, 6),
                "omission_unattained_delta_vs_baseline": round(omission_unattained - baseline_unattained, 6),
                "omission_attainment_drop_vs_baseline": round(baseline_attainment - omission_attainment, 6),
            }
        )

    valid_p1_rows = [row for row in p1_rows if "missing_rows" not in row]
    p1_checks = [
        row["duplicate_rate_gain_vs_baseline"] >= MIN_DUPLICATE_RATE_GAIN
        and row["duplicate_unattained_delta_vs_baseline"] <= MAX_DUPLICATE_UNATTAINED_DELTA
        for row in valid_p1_rows
    ]
    p1_fail = [
        row["duplicate_rate_gain_vs_baseline"] < (MIN_DUPLICATE_RATE_GAIN / 2.0)
        or row["duplicate_unattained_delta_vs_baseline"] > (MAX_DUPLICATE_UNATTAINED_DELTA * 3.0)
        for row in valid_p1_rows
    ]
    pattern_p1_status = pattern_status(p1_checks, p1_fail, missing_any or not valid_p1_rows)

    p2_checks = [
        row["omission_unattained_delta_vs_baseline"] >= MIN_OMISSION_UNATTAINED_DELTA
        and row["omission_attainment_drop_vs_baseline"] >= MIN_OMISSION_ATTAINMENT_DROP
        for row in valid_p1_rows
    ]
    p2_fail = [
        row["omission_unattained_delta_vs_baseline"] < (MIN_OMISSION_UNATTAINED_DELTA / 2.0)
        or row["omission_attainment_drop_vs_baseline"] < (MIN_OMISSION_ATTAINMENT_DROP / 2.0)
        for row in valid_p1_rows
    ]
    pattern_p2_status = pattern_status(p2_checks, p2_fail, missing_any or not valid_p1_rows)

    # Pattern 3 (mixed regime boundary)
    rec_by_key = {(row.get("family", ""), row.get("severity", "")): row for row in rec_rows}
    severities = sorted(
        {
            severity
            for family, severity in rec_by_key.keys()
            if family in {"duplicate_pressure", "omission_pressure", "mixed_pressure"}
        },
        key=severity_key,
    )
    mixed_comparison_rows: list[dict[str, Any]] = []
    differing_count = 0
    identical_to_duplicate_all = True
    identical_to_omission_all = True
    missing_mixed = False
    for severity in severities:
        dup = rec_by_key.get(("duplicate_pressure", severity))
        omi = rec_by_key.get(("omission_pressure", severity))
        mix = rec_by_key.get(("mixed_pressure", severity))
        if dup is None or omi is None or mix is None:
            missing_mixed = True
            mixed_comparison_rows.append(
                {
                    "severity": severity,
                    "missing_rows": {
                        "duplicate_pressure": dup is None,
                        "omission_pressure": omi is None,
                        "mixed_pressure": mix is None,
                    },
                }
            )
            continue
        dup_cfg = str(dup.get("recommended_configuration", ""))
        omi_cfg = str(omi.get("recommended_configuration", ""))
        mix_cfg = str(mix.get("recommended_configuration", ""))
        differs_from_duplicate = mix_cfg != dup_cfg
        differs_from_omission = mix_cfg != omi_cfg
        if differs_from_duplicate or differs_from_omission:
            differing_count += 1
        if differs_from_duplicate:
            identical_to_duplicate_all = False
        if differs_from_omission:
            identical_to_omission_all = False
        mixed_comparison_rows.append(
            {
                "severity": severity,
                "duplicate_recommendation": dup_cfg,
                "omission_recommendation": omi_cfg,
                "mixed_recommendation": mix_cfg,
                "differs_from_duplicate": differs_from_duplicate,
                "differs_from_omission": differs_from_omission,
            }
        )

    p3_checks = [differing_count >= MIN_MIXED_DIFFERING_SEVERITIES, not identical_to_duplicate_all, not identical_to_omission_all]
    p3_fail = [differing_count == 0, identical_to_duplicate_all and identical_to_omission_all]
    pattern_p3_status = pattern_status(p3_checks, p3_fail, missing_mixed or not severities)

    # Pattern 4 (direct integrity metrics)
    matrix_by_key = {
        (row.get("family", ""), row.get("severity", ""), row.get("configuration", "")): row
        for row in matrix_rows
    }
    target_severities = [severity for severity in severities if severity in {"medium", "standard", "high", "extreme"}]
    relief_rows: list[dict[str, Any]] = []
    relief_passes = 0
    for family in ("duplicate_pressure", "mixed_pressure"):
        for severity in target_severities:
            ti = matrix_by_key.get((family, severity, "transient_immediate"))
            ri = matrix_by_key.get((family, severity, "retained_immediate"))
            rd = matrix_by_key.get((family, severity, "retained_deferred"))
            if ti is None or ri is None or rd is None:
                continue
            best_immediate = min(
                [ti, ri],
                key=lambda row: as_float(row, "duplicate_side_effect_execution_count_mean"),
            )
            relief = as_float(best_immediate, "duplicate_side_effect_execution_count_mean") - as_float(
                rd, "duplicate_side_effect_execution_count_mean"
            )
            rewrite = as_float(rd, "correction_rewrite_count_mean")
            if relief >= MIN_DIRECT_RELIEF and rewrite > 0:
                relief_passes += 1
            relief_rows.append(
                {
                    "family": family,
                    "severity": severity,
                    "best_immediate_duplicate_side_effect_execution_count": round(
                        as_float(best_immediate, "duplicate_side_effect_execution_count_mean"), 6
                    ),
                    "deferred_duplicate_side_effect_execution_count": round(
                        as_float(rd, "duplicate_side_effect_execution_count_mean"), 6
                    ),
                    "deferred_correction_rewrite_count": round(rewrite, 6),
                    "relief_vs_best_immediate": round(relief, 6),
                }
            )

    direct_metric_non_zero = any(
        as_float(row, "duplicate_side_effect_execution_count_mean") > 0
        or as_float(row, "correction_rewrite_count_mean") > 0
        or as_float(row, "wrong_latest_version_commit_count_mean") > 0
        for row in matrix_rows
    )
    p4_checks = [direct_metric_non_zero, relief_passes >= MIN_DIRECT_RELIEF_SEVERITIES]
    p4_fail = [not direct_metric_non_zero, relief_passes == 0]
    pattern_p4_status = pattern_status(p4_checks, p4_fail, not matrix_rows)

    statuses = [pattern_p1_status, pattern_p2_status, pattern_p3_status, pattern_p4_status]
    if "fail" in statuses:
        overall = "fail"
    elif statuses and all(status == "pass" for status in statuses):
        overall = "pass"
    else:
        overall = "unclear"

    payload = {
        "overall_status": overall,
        "thresholds": {
            "min_duplicate_rate_gain_vs_baseline": MIN_DUPLICATE_RATE_GAIN,
            "max_duplicate_unattained_delta_vs_baseline": MAX_DUPLICATE_UNATTAINED_DELTA,
            "min_omission_unattained_delta_vs_baseline": MIN_OMISSION_UNATTAINED_DELTA,
            "min_omission_attainment_drop_vs_baseline": MIN_OMISSION_ATTAINMENT_DROP,
            "min_mixed_differing_severities": MIN_MIXED_DIFFERING_SEVERITIES,
            "min_direct_relief": MIN_DIRECT_RELIEF,
            "min_direct_relief_severities": MIN_DIRECT_RELIEF_SEVERITIES,
        },
        "patterns": {
            "P1_duplicate_containment_frontier": {
                "status": pattern_p1_status,
                "expected_signature": "duplicate pressure raises duplicate load without materially increasing unattained cases",
            },
            "P2_omission_durability_dominance": {
                "status": pattern_p2_status,
                "expected_signature": "omission pressure raises unattained cases and lowers attainment",
            },
            "P3_mixed_regime_boundary": {
                "status": pattern_p3_status,
                "expected_signature": "mixed-pressure recommendation is not identical to one pure family across all severities",
            },
            "P4_direct_integrity_violations": {
                "status": pattern_p4_status,
                "expected_signature": "direct integrity metrics are non-zero and deferred relief appears in >=2 medium+ severities",
            },
        },
        "standard_anchor_rows": p1_rows,
        "mixed_regime_rows": mixed_comparison_rows,
        "direct_integrity_rows": relief_rows,
        "direct_integrity_relief_pass_count": relief_passes,
    }

    md_lines = [
        "# Required-effect pattern validation (P1-P4)",
        "",
        f"- overall_status: {overall}",
        "",
        "## Pattern statuses",
        f"- P1 duplicate containment frontier: {pattern_p1_status}",
        f"- P2 omission durability dominance: {pattern_p2_status}",
        f"- P3 mixed regime boundary: {pattern_p3_status}",
        f"- P4 direct integrity violations: {pattern_p4_status}",
        "",
        "## Standard-anchor values (P1/P2)",
    ]
    for row in p1_rows:
        if "missing_rows" in row:
            md_lines.append(f"- {row['configuration']}: missing {row['missing_rows']}")
            continue
        md_lines.append(
            f"- {row['configuration']}: "
            f"dup_rate_gain={row['duplicate_rate_gain_vs_baseline']:.6f}, "
            f"dup_unattained_delta={row['duplicate_unattained_delta_vs_baseline']:.3f}, "
            f"omi_unattained_delta={row['omission_unattained_delta_vs_baseline']:.3f}, "
            f"omi_attainment_drop={row['omission_attainment_drop_vs_baseline']:.6f}"
        )
    md_lines.extend(["", "## Mixed regime rows (P3)"])
    for row in mixed_comparison_rows:
        if "missing_rows" in row:
            md_lines.append(f"- {row['severity']}: missing {row['missing_rows']}")
            continue
        md_lines.append(
            f"- {row['severity']}: dup={row['duplicate_recommendation']}, "
            f"omi={row['omission_recommendation']}, mixed={row['mixed_recommendation']}, "
            f"diff_dup={row['differs_from_duplicate']}, diff_omi={row['differs_from_omission']}"
        )
    md_lines.extend(["", "## Direct integrity rows (P4)"])
    for row in relief_rows:
        md_lines.append(
            f"- {row['family']} | {row['severity']}: "
            f"immediate={row['best_immediate_duplicate_side_effect_execution_count']:.3f}, "
            f"deferred={row['deferred_duplicate_side_effect_execution_count']:.3f}, "
            f"rewrite={row['deferred_correction_rewrite_count']:.3f}, "
            f"relief={row['relief_vs_best_immediate']:.3f}"
        )
    md_lines.append(f"- direct_integrity_relief_pass_count: {relief_passes}")
    md_text = "\n".join(md_lines) + "\n"

    dump_json(agg_dir / "required_effect_pattern_validation.json", payload)
    (agg_dir / "required_effect_pattern_validation.md").write_text(md_text, encoding="utf-8")
    dump_json(thesis_dir / "required_effect_pattern_validation.json", payload)
    (thesis_dir / "required_effect_pattern_validation.md").write_text(md_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
