from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


CONFIGS = ("transient_immediate", "retained_immediate", "retained_deferred")


def row(df: pd.DataFrame, configuration: str, family: str) -> pd.Series:
    rows = df[(df["configuration"] == configuration) & (df["family"] == family)]
    if rows.empty:
        raise RuntimeError(f"missing row for configuration={configuration} family={family}")
    return rows.iloc[0]


def roundf(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def status_from_checks(checks: dict[str, bool]) -> str:
    directional = checks["directional_tradeoff_present"]
    if not directional:
        return "fail"
    if all(checks.values()):
        return "pass"
    return "warn"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("batch_dir")
    parser.add_argument("--severity", default="stage_a")
    parser.add_argument("--report-stem", default="composition_probe_stage_a_validation")
    parser.add_argument("--min-deadline-gap", type=float, default=0.05)
    parser.add_argument("--min-duplicate-relief-ratio", type=float, default=0.60)
    parser.add_argument("--max-baseline-dup-side", type=float, default=1.0)
    parser.add_argument("--min-immediate-dup-side", type=float, default=30.0)
    args = parser.parse_args()

    batch_dir = Path(args.batch_dir).resolve()
    agg_path = batch_dir / "aggregates" / "scenario_repeat_summary.csv"
    if not agg_path.exists():
        raise SystemExit(f"missing aggregate file: {agg_path}")

    df = pd.read_csv(agg_path)
    df = df[df["severity"] == args.severity].copy()
    if df.empty:
        raise SystemExit(
            f"no rows found for severity={args.severity} in scenario_repeat_summary.csv"
        )

    rows: list[dict[str, Any]] = []
    for configuration in CONFIGS:
        baseline = row(df, configuration, "baseline")
        tension = row(df, configuration, "backlog_shock")
        rows.append(
            {
                "configuration": configuration,
                "baseline_expired_rate_mean": roundf(baseline["expired_rate_mean"]),
                "tension_expired_rate_mean": roundf(tension["expired_rate_mean"]),
                "expired_rate_delta_tension_minus_baseline": roundf(
                    tension["expired_rate_mean"] - baseline["expired_rate_mean"]
                ),
                "baseline_duplicate_side_effect_execution_count_mean": roundf(
                    baseline["duplicate_side_effect_execution_count_mean"]
                ),
                "tension_duplicate_side_effect_execution_count_mean": roundf(
                    tension["duplicate_side_effect_execution_count_mean"]
                ),
                "duplicate_side_effect_delta_tension_minus_baseline": roundf(
                    tension["duplicate_side_effect_execution_count_mean"]
                    - baseline["duplicate_side_effect_execution_count_mean"]
                ),
                "tension_correction_rewrite_count_mean": roundf(
                    tension["correction_rewrite_count_mean"]
                ),
            }
        )

    by_cfg = {r["configuration"]: r for r in rows}
    ti = by_cfg["transient_immediate"]
    ri = by_cfg["retained_immediate"]
    rd = by_cfg["retained_deferred"]

    deadline_gap_rd_vs_ri = (
        rd["tension_expired_rate_mean"] - ri["tension_expired_rate_mean"]
    )
    duplicate_relief_rd_vs_ri = (
        ri["tension_duplicate_side_effect_execution_count_mean"]
        - rd["tension_duplicate_side_effect_execution_count_mean"]
    )
    immediate_duplicate_reference = max(
        ri["tension_duplicate_side_effect_execution_count_mean"], 1.0
    )
    duplicate_relief_ratio_rd_vs_ri = (
        duplicate_relief_rd_vs_ri / immediate_duplicate_reference
    )

    checks = {
        "directional_tradeoff_present": (
            deadline_gap_rd_vs_ri > 0.0 and duplicate_relief_rd_vs_ri > 0.0
        ),
        "deadline_gap_material": deadline_gap_rd_vs_ri >= args.min_deadline_gap,
        "duplicate_relief_material": duplicate_relief_ratio_rd_vs_ri
        >= args.min_duplicate_relief_ratio,
        "baseline_duplicate_near_zero": max(
            ti["baseline_duplicate_side_effect_execution_count_mean"],
            ri["baseline_duplicate_side_effect_execution_count_mean"],
            rd["baseline_duplicate_side_effect_execution_count_mean"],
        )
        <= args.max_baseline_dup_side,
        # Signal should be present in immediate modes; deferred is expected to
        # collapse duplicate side effects via coalescing/rewrite.
        "tension_duplicate_signal_present": min(
            ti["tension_duplicate_side_effect_execution_count_mean"],
            ri["tension_duplicate_side_effect_execution_count_mean"],
        )
        >= args.min_immediate_dup_side,
    }

    status = status_from_checks(checks)
    stage_name = args.severity.replace("_", " ")
    verdict = {
        "pass": f"{stage_name} supports proceeding to the next gate.",
        "warn": f"{stage_name} shows partial signal; tune scope or thresholds before promotion.",
        "fail": f"{stage_name} does not yet show credible arbitration tension; do not promote.",
    }[status]

    payload: dict[str, Any] = {
        "status": status,
        "verdict": verdict,
        "batch_dir": str(batch_dir),
        "checks": checks,
        "thresholds": {
            "min_deadline_gap": args.min_deadline_gap,
            "min_duplicate_relief_ratio": args.min_duplicate_relief_ratio,
            "max_baseline_dup_side": args.max_baseline_dup_side,
            "min_immediate_dup_side": args.min_immediate_dup_side,
        },
        "key_contrasts": {
            "deadline_gap_rd_vs_ri": roundf(deadline_gap_rd_vs_ri),
            "duplicate_relief_rd_vs_ri": roundf(duplicate_relief_rd_vs_ri),
            "duplicate_relief_ratio_rd_vs_ri": roundf(duplicate_relief_ratio_rd_vs_ri),
        },
        "scenario_rows": rows,
    }

    reports_dir = batch_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_path = reports_dir / f"{args.report_stem}.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md_lines = [
        "# Composition Probe Validation",
        "",
        f"- status: **{status.upper()}**",
        f"- verdict: {verdict}",
        f"- severity slice: `{args.severity}`",
        "",
        "## Key contrasts",
        f"- deadline gap (R/D - R/I, tension expiry rate): {deadline_gap_rd_vs_ri:.6f}",
        f"- duplicate relief (R/I - R/D, tension duplicate side effects): {duplicate_relief_rd_vs_ri:.6f}",
        f"- duplicate relief ratio (vs R/I): {duplicate_relief_ratio_rd_vs_ri:.6f}",
        "",
        "## Checks",
    ]
    for name, ok in checks.items():
        md_lines.append(f"- {name}: {'pass' if ok else 'fail'}")

    md_lines.extend(["", "## Per-configuration rows"])
    for item in rows:
        md_lines.append(
            "- {cfg}: baseline_expired={bexp:.6f}, tension_expired={texp:.6f}, "
            "baseline_dup_side={bdup:.6f}, tension_dup_side={tdup:.6f}, "
            "tension_rewrite={rw:.6f}".format(
                cfg=item["configuration"],
                bexp=item["baseline_expired_rate_mean"],
                texp=item["tension_expired_rate_mean"],
                bdup=item["baseline_duplicate_side_effect_execution_count_mean"],
                tdup=item["tension_duplicate_side_effect_execution_count_mean"],
                rw=item["tension_correction_rewrite_count_mean"],
            )
        )

    md_path = reports_dir / f"{args.report_stem}.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"status={status}")
    print(f"json={json_path}")
    print(f"md={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
