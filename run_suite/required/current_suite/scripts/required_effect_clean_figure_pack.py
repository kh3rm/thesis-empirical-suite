from __future__ import annotations

import csv
import json
import os
import sys
import warnings
from pathlib import Path
from typing import Any

if "MPLCONFIGDIR" not in os.environ:
    os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib"

warnings.filterwarnings(
    "ignore",
    message="Unable to import Axes3D.*",
    category=UserWarning,
    module="matplotlib.projections",
)

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


CONFIGS = ("transient_immediate", "retained_immediate", "retained_deferred")
CONFIG_LABELS = {
    "transient_immediate": "transient/immediate",
    "retained_immediate": "retained/immediate",
    "retained_deferred": "retained/deferred",
}
CONFIG_COLORS = {
    "transient_immediate": "#c23b22",
    "retained_immediate": "#2b8cbe",
    "retained_deferred": "#2ca25f",
}
SEVERITY_ORDER = {"low": 0, "medium": 1, "standard": 2, "high": 2, "extreme": 3}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def as_float(row: dict[str, str] | None, key: str) -> float:
    if row is None:
        return 0.0
    try:
        return float(row.get(key, 0.0))
    except Exception:
        return 0.0


def row_for(rows: list[dict[str, str]], family: str, severity: str, configuration: str) -> dict[str, str] | None:
    for row in rows:
        if (
            row.get("family") == family
            and row.get("severity") == severity
            and row.get("configuration") == configuration
        ):
            return row
    return None


def present_severities(rows: list[dict[str, str]], family: str) -> list[str]:
    values = {str(row.get("severity", "")) for row in rows if row.get("family") == family}
    return sorted(values, key=lambda v: (SEVERITY_ORDER.get(v, 99), v))


def grouped_bars(ax: plt.Axes, x_labels: list[str], series: dict[str, list[float]], ylabel: str) -> None:
    width = 0.22
    x = list(range(len(x_labels)))
    offsets = {
        "transient_immediate": -width,
        "retained_immediate": 0.0,
        "retained_deferred": width,
    }
    for config in CONFIGS:
        values = series.get(config, [0.0] * len(x_labels))
        xs = [xi + offsets[config] for xi in x]
        ax.bar(xs, values, width=width, color=CONFIG_COLORS[config], label=CONFIG_LABELS[config])
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.3)


def add_caption(fig: plt.Figure, text: str) -> None:
    fig.text(0.02, 0.02, text, fontsize=9, va="bottom", ha="left", wrap=True)


def policy_for(rows: list[dict[str, str]], family: str, severity: str) -> str:
    if family == "duplicate_pressure":
        return "retained_deferred"
    if family == "source_omission":
        return "transient_immediate"
    # handling_gap_replayable: prioritize unattained recovery, then lower lag among retained
    vals = []
    for config in CONFIGS:
        row = row_for(rows, family, severity, config)
        if row is None:
            continue
        vals.append(
            (
                config,
                as_float(row, "unattained_case_count_mean"),
                as_float(row, "producer_complete_to_last_attainment_seconds_mean"),
            )
        )
    if not vals:
        return "unclear"
    vals.sort(key=lambda item: (item[1], item[2]))
    return vals[0][0]


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3):
        raise SystemExit("Usage: required_effect_clean_figure_pack.py <batch_dir> [output_pdf]")

    batch_dir = Path(argv[1]).resolve()
    agg_dir = batch_dir / "aggregates"
    family_csv = agg_dir / "family_comparison_summary.csv"
    validation_json = agg_dir / "required_effect_clean_validation.json"
    if not family_csv.exists():
        raise SystemExit(f"Missing family summary: {family_csv}")
    if not validation_json.exists():
        raise SystemExit(f"Missing clean validation report: {validation_json}")

    rows = load_csv(family_csv)
    validation = load_json(validation_json)

    if len(argv) == 3:
        out_pdf = Path(argv[2]).resolve()
    else:
        out_pdf = Path.cwd() / "required_effect_clean_10_graph_pack.pdf"
    out_md = out_pdf.with_suffix(".md")

    duplicate_severities = [s for s in present_severities(rows, "duplicate_pressure") if s in ("standard", "extreme")]
    handling_severities = [s for s in present_severities(rows, "handling_gap_replayable") if s in ("standard", "extreme")]
    source_severities = [s for s in present_severities(rows, "source_omission") if s in ("standard",)]

    notes: list[str] = [
        "# Required-effect clean figure notes",
        "",
        f"- Batch: `{batch_dir}`",
        f"- Validation overall status: `{validation.get('overall_status', 'unknown')}`",
        "",
    ]

    with PdfPages(out_pdf) as pdf:
        # Figure 1: claim status dashboard
        fig, ax = plt.subplots(figsize=(11, 6))
        claims = validation.get("claims", {})
        claim_names = list(claims.keys())
        claim_status = [str(claims[name].get("status", "unclear")) for name in claim_names]
        score_map = {"fail": 0, "unclear": 1, "pass": 2}
        scores = [score_map.get(status, 1) for status in claim_status]
        colors = ["#d73027" if s == 0 else "#fdae61" if s == 1 else "#1a9850" for s in scores]
        y = list(range(len(claim_names)))
        ax.barh(y, scores, color=colors)
        ax.set_yticks(y)
        ax.set_yticklabels([name.replace("_", " ") for name in claim_names], fontsize=9)
        ax.set_xlim(0, 2.2)
        ax.set_xticks([0, 1, 2])
        ax.set_xticklabels(["fail", "unclear", "pass"])
        ax.set_title("Figure 1. Claim status dashboard (clean required-effect)")
        ax.grid(axis="x", alpha=0.3)
        for idx, status in enumerate(claim_status):
            ax.text(scores[idx] + 0.03, idx, status, va="center", fontsize=9)
        cap = (
            "Why this is useful: it states upfront whether each intended mechanism-level claim is supported. "
            "The rest of the figures explain why those statuses are justified."
        )
        add_caption(fig, cap)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        notes.extend(["## Figure 1", cap, ""])

        # Figure 2: handling-gap unattained outcomes
        fig, ax = plt.subplots(figsize=(11, 6))
        series = {
            config: [
                as_float(row_for(rows, "handling_gap_replayable", sev, config), "unattained_case_count_mean")
                for sev in handling_severities
            ]
            for config in CONFIGS
        }
        grouped_bars(ax, handling_severities, series, "unattained cases (mean)")
        ax.set_title("Figure 2. Replayable handling-gap omissions: unattained outcomes")
        ax.legend(loc="upper left")
        cap = (
            "Why this is useful: transient should carry omission residue when handling is interrupted; "
            "retained paths should recover emitted work through replay."
        )
        add_caption(fig, cap)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        notes.extend(["## Figure 2", cap, ""])

        # Figure 3: handling-gap settlement lag
        fig, ax = plt.subplots(figsize=(11, 6))
        series = {
            config: [
                as_float(
                    row_for(rows, "handling_gap_replayable", sev, config),
                    "producer_complete_to_last_attainment_seconds_mean",
                )
                for sev in handling_severities
            ]
            for config in CONFIGS
        }
        grouped_bars(ax, handling_severities, series, "producer-complete to last-attainment (s)")
        ax.set_title("Figure 3. Replay recovery cost: settlement lag")
        ax.legend(loc="upper left")
        cap = (
            "Why this is useful: recovery can be successful but still slower. This shows the time cost "
            "of replay/settlement under each mechanism."
        )
        add_caption(fig, cap)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        notes.extend(["## Figure 3", cap, ""])

        # Figure 4: duplicate side-effect execution
        fig, ax = plt.subplots(figsize=(11, 6))
        series = {
            config: [
                as_float(row_for(rows, "duplicate_pressure", sev, config), "duplicate_side_effect_execution_count_mean")
                for sev in duplicate_severities
            ]
            for config in CONFIGS
        }
        grouped_bars(ax, duplicate_severities, series, "duplicate side-effect executions (mean)")
        ax.set_title("Figure 4. Duplicate pressure: direct integrity exposure by mechanism")
        ax.legend(loc="upper left")
        cap = (
            "Why this is useful: required-effect integrity is not only about eventual attainment; "
            "it is also about avoiding repeated side-effect execution."
        )
        add_caption(fig, cap)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        notes.extend(["## Figure 4", cap, ""])

        # Figure 5: deferred conversion (immediate side effects -> deferred rewrites)
        fig, ax = plt.subplots(figsize=(11, 6))
        x = list(range(len(duplicate_severities)))
        width = 0.25
        immediate_best = []
        deferred_side = []
        deferred_rewrite = []
        for sev in duplicate_severities:
            ti = as_float(row_for(rows, "duplicate_pressure", sev, "transient_immediate"), "duplicate_side_effect_execution_count_mean")
            ri = as_float(row_for(rows, "duplicate_pressure", sev, "retained_immediate"), "duplicate_side_effect_execution_count_mean")
            rd_side = as_float(row_for(rows, "duplicate_pressure", sev, "retained_deferred"), "duplicate_side_effect_execution_count_mean")
            rd_rw = as_float(row_for(rows, "duplicate_pressure", sev, "retained_deferred"), "correction_rewrite_count_mean")
            immediate_best.append(min(ti, ri))
            deferred_side.append(rd_side)
            deferred_rewrite.append(rd_rw)
        ax.bar([i - width for i in x], immediate_best, width=width, label="best immediate side effects", color="#c23b22")
        ax.bar(x, deferred_side, width=width, label="deferred side effects", color="#2ca25f")
        ax.bar([i + width for i in x], deferred_rewrite, width=width, label="deferred rewrites", color="#807dba")
        ax.set_xticks(x)
        ax.set_xticklabels(duplicate_severities)
        ax.set_ylabel("count (mean)")
        ax.set_title("Figure 5. Duplicate consolidation mechanism under deferred retained handling")
        ax.grid(axis="y", alpha=0.3)
        ax.legend(loc="upper left")
        cap = (
            "Why this is useful: it shows the mechanism shift directly: repeated immediate side effects "
            "are converted into overwrite/rewrite activity before final settlement."
        )
        add_caption(fig, cap)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        notes.extend(["## Figure 5", cap, ""])

        # Figure 6: duplicate relief ratio
        fig, ax = plt.subplots(figsize=(11, 6))
        ratios = []
        for sev in duplicate_severities:
            ti = as_float(row_for(rows, "duplicate_pressure", sev, "transient_immediate"), "duplicate_side_effect_execution_count_mean")
            ri = as_float(row_for(rows, "duplicate_pressure", sev, "retained_immediate"), "duplicate_side_effect_execution_count_mean")
            rd = as_float(row_for(rows, "duplicate_pressure", sev, "retained_deferred"), "duplicate_side_effect_execution_count_mean")
            best = min(ti, ri)
            ratio = 0.0 if best <= 0 else (best - rd) / best
            ratios.append(ratio)
        ax.plot(duplicate_severities, ratios, marker="o", linewidth=2.0, color="#2ca25f")
        ax.axhline(0.70, linestyle="--", color="#555555", linewidth=1.0, label="validation threshold (0.70)")
        ax.set_ylim(0.0, 1.05)
        ax.set_ylabel("relief ratio vs best immediate")
        ax.set_title("Figure 6. Duplicate relief ratio by severity")
        ax.grid(axis="y", alpha=0.3)
        ax.legend(loc="lower right")
        cap = (
            "Why this is useful: this normalizes absolute counts into a ratio, making the consolidation "
            "effect comparable across stress levels."
        )
        add_caption(fig, cap)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        notes.extend(["## Figure 6", cap, ""])

        # Figure 7: source omission control invariance
        fig, ax = plt.subplots(figsize=(11, 6))
        source_series = {
            config: [
                as_float(row_for(rows, "source_omission", sev, config), "unattained_case_count_mean")
                for sev in source_severities
            ]
            for config in CONFIGS
        }
        grouped_bars(ax, source_severities, source_series, "unattained cases (mean)")
        ax.set_title("Figure 7. Source omission control: replay scope boundary")
        ax.legend(loc="upper left")
        cap = (
            "Why this is useful: when work is never emitted, replay-capable retention has no extra material "
            "to recover. Similar bars are expected here."
        )
        add_caption(fig, cap)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        notes.extend(["## Figure 7", cap, ""])

        # Figure 8: transient disadvantage by family/severity
        fig, ax = plt.subplots(figsize=(11, 6))
        labels = []
        values = []
        colors = []
        for family in ("handling_gap_replayable", "source_omission", "duplicate_pressure"):
            for severity in present_severities(rows, family):
                ti = as_float(row_for(rows, family, severity, "transient_immediate"), "unattained_case_count_mean")
                ri = as_float(row_for(rows, family, severity, "retained_immediate"), "unattained_case_count_mean")
                rd = as_float(row_for(rows, family, severity, "retained_deferred"), "unattained_case_count_mean")
                best_retained = min(ri, rd) if (ri or rd) else 0.0
                labels.append(f"{family}:{severity}")
                values.append(ti - best_retained)
                colors.append("#c23b22" if family == "handling_gap_replayable" else "#636363")
        ax.bar(labels, values, color=colors)
        ax.axhline(0.0, color="#444444", linewidth=1.0)
        ax.set_ylabel("transient unattained - best retained unattained")
        ax.set_title("Figure 8. Where retention/replay helps (and where it does not)")
        ax.tick_params(axis="x", rotation=35)
        ax.grid(axis="y", alpha=0.3)
        cap = (
            "Why this is useful: positive values indicate retained replay advantage. "
            "Handling-gap should be positive; source omission should remain near zero."
        )
        add_caption(fig, cap)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        notes.extend(["## Figure 8", cap, ""])

        # Figure 9: deferred cost deltas (retained_deferred - retained_immediate)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6))
        labels = []
        lag_values = []
        recon_values = []
        for family in ("duplicate_pressure", "handling_gap_replayable"):
            for severity in present_severities(rows, family):
                ri = row_for(rows, family, severity, "retained_immediate")
                rd = row_for(rows, family, severity, "retained_deferred")
                if ri is None or rd is None:
                    continue
                labels.append(f"{family}:{severity}")
                lag_values.append(
                    as_float(rd, "producer_complete_to_last_attainment_seconds_mean")
                    - as_float(ri, "producer_complete_to_last_attainment_seconds_mean")
                )
                recon_values.append(
                    as_float(rd, "reconciliation_pass_count_mean")
                    - as_float(ri, "reconciliation_pass_count_mean")
                )
        ax1.bar(labels, lag_values, color="#2ca25f")
        ax1.axhline(0.0, color="#444444", linewidth=1.0)
        ax1.set_title("Lag delta (deferred - immediate)")
        ax1.set_ylabel("seconds")
        ax1.tick_params(axis="x", rotation=35)
        ax1.grid(axis="y", alpha=0.3)
        ax2.bar(labels, recon_values, color="#2ca25f")
        ax2.axhline(0.0, color="#444444", linewidth=1.0)
        ax2.set_title("Reconciliation pass delta (deferred - immediate)")
        ax2.set_ylabel("count")
        ax2.tick_params(axis="x", rotation=35)
        ax2.grid(axis="y", alpha=0.3)
        fig.suptitle("Figure 9. Deferred settlement cost signals")
        cap = (
            "Why this is useful: it quantifies the cost side of deferred handling, which is needed "
            "to keep the thesis claim balanced (benefit and cost together)."
        )
        add_caption(fig, cap)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        notes.extend(["## Figure 9", cap, ""])

        # Figure 10: unattained vs settlement lag scatter (trade-off map)
        fig, ax = plt.subplots(figsize=(11, 7))
        family_markers = {
            "duplicate_pressure": "o",
            "handling_gap_replayable": "s",
            "source_omission": "^",
        }
        for family in ("duplicate_pressure", "handling_gap_replayable", "source_omission"):
            for severity in present_severities(rows, family):
                for config in CONFIGS:
                    row = row_for(rows, family, severity, config)
                    if row is None:
                        continue
                    x = as_float(row, "producer_complete_to_last_attainment_seconds_mean")
                    y = as_float(row, "unattained_case_count_mean")
                    ax.scatter(
                        x,
                        y,
                        color=CONFIG_COLORS[config],
                        marker=family_markers[family],
                        s=70,
                        alpha=0.9,
                    )
                    ax.text(x + 0.02, y + 1.0, f"{family}:{severity}:{config.split('_')[0]}", fontsize=7)
        ax.set_xlabel("producer-complete to last-attainment (s)")
        ax.set_ylabel("unattained cases")
        ax.set_title("Figure 10. Required-effect trade-off map by mechanism")
        ax.grid(alpha=0.3)
        cap = (
            "Why this is useful: this puts effectiveness (lower unattained) and cost (higher settlement lag) "
            "on one map, showing there is no single dominant mechanism for all disturbance classes."
        )
        add_caption(fig, cap)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)
        notes.extend(["## Figure 10", cap, ""])

    # Add concise policy summary to notes.
    notes.extend(["## Policy summary from this batch"])
    for family in ("duplicate_pressure", "handling_gap_replayable", "source_omission"):
        for severity in present_severities(rows, family):
            policy = policy_for(rows, family, severity)
            notes.append(f"- {family} | {severity}: {policy}")
    notes.append("")
    out_md.write_text("\n".join(notes), encoding="utf-8")
    print(out_pdf)
    print(out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
