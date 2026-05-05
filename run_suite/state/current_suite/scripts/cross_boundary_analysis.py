from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from batch_utils import dump_json, load_json, write_csv


def role_alias(value: str | None) -> str:
    mapping = {
        "synchronized-lateness dominant": "broadly delayed recovery",
        "concentration-dominant": "catch-up surge recovery",
        "convergence-region dominant": "late-convergence fragility",
        "tail-dominant": "straggler-stretch recovery",
        "mean-dominant": "general slowdown",
        "mixed": "mixed burden pattern",
        "mixed/weak": "weak or mixed burden pattern",
    }
    return mapping.get(value, value or "n/a")


def region_alias(value: str | None) -> str:
    mapping = {
        "early_bulk": "early recovery body",
        "main_bulk": "main recovery body",
        "upper_bulk": "late recovery body",
        "late_convergence": "near-finish region",
        "tail": "last recovery segment",
        "straggler": "slowest cases",
    }
    return mapping.get(value, value or "n/a")


def family_label(family: str, severity: str) -> str:
    labels = {
        "baseline": "baseline",
        "degradation": "degradation",
        "interrupt_mid": "body-phase interruption",
        "interrupt_late": "late-convergence interruption",
        "backlog_shock": "backlog shock",
        "duplicate_pressure": "duplicate pressure",
    }
    base = labels.get(family, family.replace("_", " "))
    return base if severity == "standard" else f"{base} ({severity})"


def shift_label(expired_rate: float, in_time_rate: float) -> str:
    if expired_rate >= 0.35:
        return "expiry-dominant"
    if expired_rate >= 0.10:
        return "deadline-sensitive"
    if expired_rate > 0.0 or in_time_rate < 0.98:
        return "temporal-with-deadline-pressure"
    return "mostly-temporal"


def gloss(required_role: str, deadline_role: str, expired_rate: float, in_time_rate: float, shift: str) -> str:
    if shift == "expiry-dominant":
        return f"Under required-effect the pattern remains mainly temporal ({required_role}), but under the deadline boundary it becomes heavily correctness-threatening: in-time={in_time_rate:.3f}, expiry={expired_rate:.3f}."
    if shift == "deadline-sensitive":
        return f"Under required-effect the pattern reads mainly as {required_role}; under the deadline boundary it still resembles {deadline_role}, but part of the burden now converts into expiry risk: in-time={in_time_rate:.3f}, expiry={expired_rate:.3f}."
    if shift == "temporal-with-deadline-pressure":
        return f"The burden remains mainly temporal, but some deadline pressure now appears: in-time={in_time_rate:.3f}, expiry={expired_rate:.3f}."
    return f"The burden remains primarily temporal across boundaries, with in-time={in_time_rate:.3f} and expiry={expired_rate:.3f}."


def append_to_summary(report_path: Path, cross_rows: list[dict[str, Any]], deadline_rows: list[dict[str, Any]]) -> None:
    if not report_path.exists():
        return
    text = report_path.read_text(encoding="utf-8")
    lines = [text.rstrip(), "", "## Cross-boundary significance shifts"]
    if cross_rows:
        for row in cross_rows:
            label = family_label(str(row["family"]), str(row["severity"]))
            lines.append(f"- {label} / {row['configuration']}: {row['significance_shift']} — {row['explanation']}")
    else:
        lines.append("- n/a")
    lines.extend(["", "## Deadline-constrained outcome map"])
    if deadline_rows:
        for row in deadline_rows:
            lines.append(
                f"- {row['scenario_id']} [{family_label(str(row['family']), str(row['severity']))}] => in-time={row['completed_in_time_rate_mean']}, "
                f"expiry={row['expired_rate_mean']}; role={row.get('primary_role_label', row.get('primary_role'))}; "
                f"burden_region={row.get('primary_burden_region_label', row.get('primary_burden_region'))}"
            )
    else:
        lines.append("- n/a")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("Usage: cross_boundary_analysis.py <batch_dir>")
    batch_dir = Path(argv[1])
    agg_dir = batch_dir / "aggregates"
    scenario_rows = load_json(agg_dir / "scenario_repeat_summary.json")
    role_rows = load_json(agg_dir / "family_role_summary.json")
    role_by_scenario = {str(r["scenario_id"]): r for r in role_rows}

    grouped: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in scenario_rows:
        key = (str(row["family"]), str(row["severity"]), str(row["configuration"]))
        grouped[key][str(row["boundary_type"])] = row

    cross_rows: list[dict[str, Any]] = []
    shift_rows: list[dict[str, Any]] = []
    deadline_rows: list[dict[str, Any]] = []

    for _, mapping in sorted(grouped.items()):
        req = mapping.get("required_effect")
        ddl = mapping.get("deadline_constrained")
        if ddl is not None:
            ddl_role = role_by_scenario.get(str(ddl["scenario_id"]), {})
            deadline_rows.append({
                "scenario_id": ddl["scenario_id"],
                "family": ddl["family"],
                "severity": ddl["severity"],
                "configuration": ddl["configuration"],
                "completed_in_time_rate_mean": ddl.get("completed_in_time_rate_mean", 0.0),
                "expired_rate_mean": ddl.get("expired_rate_mean", 0.0),
                "completed_in_time_count_mean": ddl.get("completed_in_time_count_mean", 0.0),
                "expired_count_mean": ddl.get("expired_count_mean", 0.0),
                "primary_role": ddl_role.get("primary_role"),
                "primary_role_label": ddl_role.get("primary_role_label", role_alias(ddl_role.get("primary_role"))),
                "primary_burden_region": ddl_role.get("primary_burden_region"),
                "primary_burden_region_label": ddl_role.get("primary_burden_region_label", region_alias(ddl_role.get("primary_burden_region"))),
            })
        if req is None or ddl is None:
            continue
        req_role = role_by_scenario.get(str(req["scenario_id"]), {})
        ddl_role = role_by_scenario.get(str(ddl["scenario_id"]), {})
        in_time = float(ddl.get("completed_in_time_rate_mean", 0.0))
        expiry = float(ddl.get("expired_rate_mean", 0.0))
        shift = shift_label(expiry, in_time)
        explanation = gloss(
            req_role.get("primary_role_label", role_alias(req_role.get("primary_role"))),
            ddl_role.get("primary_role_label", role_alias(ddl_role.get("primary_role"))),
            expiry,
            in_time,
            shift,
        )
        cross_rows.append({
            "family": req["family"],
            "severity": req["severity"],
            "configuration": req["configuration"],
            "required_effect_scenario_id": req["scenario_id"],
            "deadline_constrained_scenario_id": ddl["scenario_id"],
            "required_effect_primary_role": req_role.get("primary_role"),
            "required_effect_primary_role_label": req_role.get("primary_role_label", role_alias(req_role.get("primary_role"))),
            "required_effect_primary_burden_region": req_role.get("primary_burden_region"),
            "required_effect_primary_burden_region_label": req_role.get("primary_burden_region_label", region_alias(req_role.get("primary_burden_region"))),
            "deadline_constrained_primary_role": ddl_role.get("primary_role"),
            "deadline_constrained_primary_role_label": ddl_role.get("primary_role_label", role_alias(ddl_role.get("primary_role"))),
            "deadline_constrained_primary_burden_region": ddl_role.get("primary_burden_region"),
            "deadline_constrained_primary_burden_region_label": ddl_role.get("primary_burden_region_label", region_alias(ddl_role.get("primary_burden_region"))),
            "deadline_constrained_completed_in_time_rate_mean": in_time,
            "deadline_constrained_expired_rate_mean": expiry,
            "significance_shift": shift,
            "explanation": explanation,
        })
        shift_rows.append({
            "family": req["family"],
            "severity": req["severity"],
            "configuration": req["configuration"],
            "significance_shift": shift,
            "completed_in_time_rate_mean": in_time,
            "expired_rate_mean": expiry,
            "explanation": explanation,
        })

    write_csv(agg_dir / "cross_boundary_summary.csv", cross_rows)
    dump_json(agg_dir / "cross_boundary_summary.json", cross_rows)
    write_csv(agg_dir / "boundary_significance_shift_summary.csv", shift_rows)
    dump_json(agg_dir / "boundary_significance_shift_summary.json", shift_rows)
    write_csv(agg_dir / "deadline_outcome_summary.csv", deadline_rows)
    dump_json(agg_dir / "deadline_outcome_summary.json", deadline_rows)

    append_to_summary(batch_dir / "reports" / "summary.md", cross_rows, deadline_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
