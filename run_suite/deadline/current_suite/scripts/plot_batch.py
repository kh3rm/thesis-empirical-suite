from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
import csv
import statistics

from batch_utils import dump_json, load_json, parse_env_file

FAMILY_LABELS = {
    "baseline": "baseline",
    "degradation": "degradation",
    "interrupt_mid": "body-phase interruption",
    "interrupt_late": "late-convergence interruption",
    "interruption": "interruption",
    "overload_burst": "overload burst",
    "backlog_shock": "backlog shock",
    "skewed_tail": "skewed-tail delay",
    "retained_tail_diagnostic": "retained-tail diagnostic",
}


def family_label(family: str, severity: str) -> str:
    label = FAMILY_LABELS.get(family, family.replace("_", " "))
    return label if severity == "standard" else f"{label} ({severity})"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    import csv
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def try_import_matplotlib():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def plot_recovery_curves(plt, curve_payload: dict, out_dir: Path) -> list[str]:
    ensure_dir(out_dir)
    saved: list[str] = []
    grouped = defaultdict(list)
    for payload in curve_payload.values():
        grouped[(payload["family"], payload["severity"])].append(payload)
    for (family, severity), items in grouped.items():
        fig, ax = plt.subplots(figsize=(9, 5))
        for item in sorted(items, key=lambda x: x["configuration"]):
            bins = item["curve_250ms"]["bins"]
            xs = [b["seconds"] for b in bins]
            ys = [b["cumulative_median"] for b in bins]
            ax.plot(xs, ys, label=item["configuration"])
        ax.set_title(f"Recovery curves: {family_label(family, severity)}")
        ax.set_xlabel("Seconds")
        ax.set_ylabel("Median cumulative attainments")
        ax.legend()
        path = out_dir / f"{family}__{severity}.png"
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        saved.append(str(path.relative_to(out_dir.parent.parent)))
    return saved


def plot_binned_attainment(plt, curve_payload: dict, out_dir: Path) -> list[str]:
    ensure_dir(out_dir)
    saved: list[str] = []
    grouped = defaultdict(list)
    for payload in curve_payload.values():
        grouped[(payload["family"], payload["severity"])].append(payload)
    for (family, severity), items in grouped.items():
        fig, ax = plt.subplots(figsize=(9, 5))
        for item in sorted(items, key=lambda x: x["configuration"]):
            bins = item["curve_100ms"]["bins"]
            xs = [b["seconds"] for b in bins]
            ys = [b["count_median"] for b in bins]
            ax.plot(xs, ys, label=item["configuration"])
        ax.set_title(f"Binned attainment (100ms): {family_label(family, severity)}")
        ax.set_xlabel("Seconds")
        ax.set_ylabel("Median attainments per 100ms bin")
        ax.legend()
        path = out_dir / f"{family}__{severity}.png"
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        saved.append(str(path.relative_to(out_dir.parent.parent)))
    return saved


def plot_tail_comparisons(plt, rows: list[dict[str, str]], out_dir: Path) -> list[str]:
    ensure_dir(out_dir)
    saved: list[str] = []
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["family"], row["severity"])].append(row)
    for (family, severity), items in grouped.items():
        labels = [item["configuration"] for item in items]
        p95 = [float(item["p95_time_to_attainment_seconds_mean"]) for item in items]
        p99 = [float(item["p99_time_to_attainment_seconds_mean"]) for item in items]
        x = range(len(labels))
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(list(x), p95, marker="o", label="p95")
        ax.plot(list(x), p99, marker="o", label="p99")
        ax.set_xticks(list(x), labels, rotation=15)
        ax.set_title(f"Tail comparison: {family_label(family, severity)}")
        ax.set_ylabel("Seconds")
        ax.legend()
        path = out_dir / f"{family}__{severity}.png"
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        saved.append(str(path.relative_to(out_dir.parent.parent)))
    return saved


def plot_shape_metrics(plt, rows: list[dict[str, str]], out_dir: Path) -> list[str]:
    ensure_dir(out_dir)
    saved: list[str] = []
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["family"], row["severity"])].append(row)
    for (family, severity), items in grouped.items():
        labels = [item["configuration"] for item in items]
        cluster = [float(item["temporal_clustering_busiest_10pct_interval_share_100ms_mean"]) for item in items]
        gap = [float(item["inter_attainment_gap_cv_mean"]) for item in items]
        x = range(len(labels))
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.plot(list(x), cluster, marker="o", label="cluster100")
        ax.plot(list(x), gap, marker="o", label="gap_cv")
        ax.set_xticks(list(x), labels, rotation=15)
        ax.set_title(f"Shape metrics: {family_label(family, severity)}")
        ax.legend()
        path = out_dir / f"{family}__{severity}.png"
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        saved.append(str(path.relative_to(out_dir.parent.parent)))
    return saved


def plot_curve_regions(plt, rows: list[dict[str, str]], out_dir: Path) -> list[str]:
    ensure_dir(out_dir)
    saved: list[str] = []
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["family"], row["severity"])].append(row)
    for (family, severity), items in grouped.items():
        labels = [item["configuration"] for item in items]
        bulk = [float(item["bulk_window_25_to_75_seconds_mean"]) for item in items]
        upper = [float(item["upper_bulk_window_75_to_90_seconds_mean"]) for item in items]
        late = [float(item["late_region_window_75_to_95_seconds_mean"]) for item in items]
        straggler = [float(item["straggler_window_95_to_99_seconds_mean"]) for item in items]
        x = range(len(labels))
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(list(x), bulk, marker="o", label="bulk 25-75")
        ax.plot(list(x), upper, marker="o", label="upper bulk 75-90")
        ax.plot(list(x), late, marker="o", label="late region 75-95")
        ax.plot(list(x), straggler, marker="o", label="straggler 95-99")
        ax.set_xticks(list(x), labels, rotation=15)
        ax.set_title(f"Curve-region windows: {family_label(family, severity)}")
        ax.set_ylabel("Seconds")
        ax.legend()
        path = out_dir / f"{family}__{severity}.png"
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        saved.append(str(path.relative_to(out_dir.parent.parent)))
    return saved


def plot_role_scores(plt, rows: list[dict[str, str]], out_dir: Path) -> list[str]:
    ensure_dir(out_dir)
    saved: list[str] = []
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["family"], row["severity"])].append(row)
    for (family, severity), items in grouped.items():
        labels = [item["configuration"] for item in items]
        sync = [float(item["synchronized_lateness_score"]) for item in items]
        conc = [float(item["concentration_score"]) for item in items]
        conv = [float(item["convergence_region_score"]) for item in items]
        tail = [float(item["tail_score"]) for item in items]
        x = range(len(labels))
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(list(x), sync, marker="o", label="sync lateness")
        ax.plot(list(x), conc, marker="o", label="concentration")
        ax.plot(list(x), conv, marker="o", label="convergence region")
        ax.plot(list(x), tail, marker="o", label="tail")
        ax.set_xticks(list(x), labels, rotation=15)
        ax.set_title(f"Role scores: {family_label(family, severity)}")
        ax.legend()
        path = out_dir / f"{family}__{severity}.png"
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        saved.append(str(path.relative_to(out_dir.parent.parent)))
    return saved


def plot_cross_family(plt, rows: list[dict[str, str]], out_dir: Path) -> list[str]:
    ensure_dir(out_dir)
    saved: list[str] = []
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["configuration"]].append(row)
    for configuration, items in grouped.items():
        labels = [f"{item['family']}:{item['severity']}" for item in items]
        values = [float(item["p95_delta_vs_same_config_baseline"]) for item in items]
        late_values = [float(item.get("delta_late_region_window_75_to_95", 0.0)) for item in items]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(range(len(labels)), values, marker="o", label="p95 delta")
        ax.plot(range(len(labels)), late_values, marker="o", label="late-region delta")
        ax.set_xticks(range(len(labels)), labels, rotation=35, ha="right")
        ax.set_title(f"Cross-family deltas vs baseline: {configuration}")
        ax.set_ylabel("Seconds")
        ax.legend()
        path = out_dir / f"{configuration}.png"
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
        saved.append(str(path.relative_to(out_dir.parent.parent)))
    return saved




def load_runtime_trace(path: Path) -> list[dict[str, float]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        rows = []
        for raw in csv.DictReader(fh):
            row: dict[str, float] = {}
            for key, value in raw.items():
                if value is None or value == "":
                    row[key] = 0.0
                else:
                    row[key] = float(value)
            rows.append(row)
        return rows


def median_runtime_series(rows_by_run: list[list[dict[str, float]]], field: str, step_seconds: float = 0.25) -> tuple[list[float], list[float]]:
    if not rows_by_run:
        return [], []
    max_t = max((run[-1].get("t_sec", 0.0) for run in rows_by_run if run), default=0.0)
    if max_t <= 0:
        return [], []
    xs: list[float] = []
    ys: list[float] = []
    sample_t = 0.0
    while sample_t <= max_t + 1e-9:
        vals: list[float] = []
        for run in rows_by_run:
            if not run:
                continue
            chosen = run[-1].get(field, 0.0)
            for row in run:
                if row["t_sec"] >= sample_t:
                    chosen = row.get(field, 0.0)
                    break
                chosen = row.get(field, 0.0)
            vals.append(chosen)
        xs.append(round(sample_t, 6))
        ys.append(statistics.median(vals) if vals else 0.0)
        sample_t += step_seconds
    return xs, ys


def load_runtime_groups(batch_dir: Path) -> dict[tuple[str, str, str, str], list[list[dict[str, float]]]]:
    raw_runs = batch_dir / "raw_runs"
    grouped: dict[tuple[str, str, str, str], list[list[dict[str, float]]]] = defaultdict(list)
    if not raw_runs.exists():
        return grouped
    for run_dir in sorted([p for p in raw_runs.iterdir() if p.is_dir()]):
        env_path = run_dir / "scenario.env"
        trace_path = run_dir / "artifacts" / "runtime_trace.csv"
        if not env_path.exists() or not trace_path.exists():
            continue
        env = parse_env_file(env_path)
        key = (env.get("BOUNDARY", ""), env.get("CONFIGURATION", ""), env.get("FAMILY", ""), env.get("SEVERITY", ""))
        rows = load_runtime_trace(trace_path)
        if rows:
            grouped[key].append(rows)
    return grouped


def current_deadline_family_candidates(grouped: dict[tuple[str, str, str, str], list[list[dict[str, float]]]]) -> list[tuple[str, str, str]]:
    preferred = [
        ("baseline", "standard", "Baseline"),
        ("degradation", "moderate", "Moderate drag"),
        ("degradation", "high", "High drag"),
        ("backlog_shock", "standard", "Backlog shock"),
    ]
    available = {(family, severity) for (boundary, _configuration, family, severity) in grouped.keys() if boundary == "deadline_constrained"}
    rows = [item for item in preferred if (item[0], item[1]) in available]
    if rows:
        return rows
    legacy = [
        ("baseline", "standard", "Baseline"),
        ("degradation", "moderate", "Moderate drag"),
        ("degradation", "moderate", "High drag"),
        ("interrupt_mid", "moderate", "Interrupt mid"),
        ("interrupt_late", "moderate", "Interrupt late"),
    ]
    return [item for item in legacy if (item[0], item[1]) in available]


def plot_runtime_burden_states_small_multiples(plt, batch_dir: Path, out_dir: Path) -> list[str]:
    ensure_dir(out_dir)
    grouped = load_runtime_groups(batch_dir)
    family_candidates = current_deadline_family_candidates(grouped)
    rows = []
    for family, severity, label in family_candidates:
        key = ("deadline_constrained", "retained_immediate", family, severity)
        series = grouped.get(key, [])
        if not series:
            continue
        xs, completed = median_runtime_series(series, "completed_in_time_total")
        _, salvageable = median_runtime_series(series, "salvageable_unsettled_cases")
        _, doomed = median_runtime_series(series, "doomed_unsettled_cases")
        _, expired = median_runtime_series(series, "expired_total")
        if not xs:
            continue
        rows.append((label, xs, completed, salvageable, doomed, expired))
    if not rows:
        return []
    fig, axes = plt.subplots(1, len(rows), figsize=(4.6 * len(rows), 4.4), sharey=True)
    if len(rows) == 1:
        axes = [axes]
    for ax, (label, xs, completed, salvageable, doomed, expired) in zip(axes, rows):
        ax.stackplot(xs, completed, salvageable, doomed, expired, alpha=0.72, labels=["completed in time", "still salvageable", "already doomed", "expired"])
        ax.set_title(label)
        ax.set_xlabel("Seconds")
        ax.grid(True, alpha=0.22)
    axes[0].set_ylabel("Median case count")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles[:4], labels[:4], loc="upper center", ncol=4)
    fig.suptitle("Deadline states over time in the main core\nRetained/immediate: what is already safe, what can still be saved, and what is already lost", y=1.05)
    path = out_dir / "deadline_constrained__retained_immediate__semantic_state_gallery.png"
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return [str(path.relative_to(out_dir.parent.parent))]


def plot_runtime_pending_compare(plt, batch_dir: Path, out_dir: Path) -> list[str]:
    ensure_dir(out_dir)
    grouped = load_runtime_groups(batch_dir)
    retained_variants = [
        ("retained_immediate", "Retained / immediate"),
        ("retained_deferred", "Retained / deferred"),
    ]
    moderate_key_suffix = ("degradation", "moderate")
    fig, ax = plt.subplots(figsize=(9, 5))
    plotted = False
    for configuration, label in retained_variants:
        key = ("deadline_constrained", configuration, moderate_key_suffix[0], moderate_key_suffix[1])
        series = grouped.get(key, [])
        if not series:
            continue
        xs, ys = median_runtime_series(series, "pending_cases")
        ax.plot(xs, ys, label=label)
        plotted = True
    if not plotted:
        plt.close(fig)
        return []
    ax.set_title("Pending settlement under degradation moderate")
    ax.set_xlabel("Seconds")
    ax.set_ylabel("Pending cases")
    ax.legend()
    path = out_dir / "deadline_constrained__degradation__moderate__pending_compare.png"
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return [str(path.relative_to(out_dir.parent.parent))]


def plot_runtime_unresolved_share_gallery(plt, batch_dir: Path, out_dir: Path) -> list[str]:
    ensure_dir(out_dir)
    grouped = load_runtime_groups(batch_dir)
    family_candidates = [
        ("baseline", "standard", "Baseline"),
        ("degradation", "moderate", "Degradation moderate"),
        ("degradation", "moderate", "Degradation high"),
        ("interrupt_mid", "moderate", "Interrupt mid"),
        ("interrupt_late", "moderate", "Interrupt late"),
    ]
    fig, ax = plt.subplots(figsize=(10, 5.2))
    plotted = False
    for family, severity, label in family_candidates:
        key = ("deadline_constrained", "transient_immediate", family, severity)
        series = grouped.get(key, [])
        if not series:
            continue
        xs, ys = median_runtime_series(series, "unresolved_share")
        if not xs:
            continue
        ax.plot(xs, ys, label=label)
        plotted = True
    if not plotted:
        plt.close(fig)
        return []
    ax.set_title("Deadline-constrained runtime burden in the stable core")
    ax.set_xlabel("Seconds since run start")
    ax.set_ylabel("Unresolved share")
    ax.legend()
    path = out_dir / "deadline_constrained__transient_immediate__unresolved_share_gallery.png"
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return [str(path.relative_to(out_dir.parent.parent))]

def plot_deadline_pressure_compare(plt, batch_dir: Path, out_dir: Path) -> list[str]:
    ensure_dir(out_dir)
    grouped = load_runtime_groups(batch_dir)
    pairs = [
        (("deadline_constrained", "retained_immediate", "degradation", "moderate"), "Moderate drag"),
        (("deadline_constrained", "retained_immediate", "backlog_shock", "standard"), "Backlog shock"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    plotted = False
    for ax, (key, label) in zip(axes, pairs):
        series = grouped.get(key, [])
        if not series:
            continue
        xs, salvageable = median_runtime_series(series, "salvageable_unsettled_share")
        _, critical = median_runtime_series(series, "critical_slack_share")
        _, doomed = median_runtime_series(series, "doomed_unsettled_share")
        _, expired = median_runtime_series(series, "expired_total")
        if not xs:
            continue
        ax.plot(xs, salvageable, label="still salvageable")
        ax.plot(xs, critical, label="near deadline")
        ax.plot(xs, doomed, label="already doomed")
        final_produced = max((run[-1].get("produced_total", 0.0) for run in series if run), default=0.0)
        expired_share = [0.0 if final_produced <= 0 else value / final_produced for value in expired]
        ax.plot(xs, expired_share, label="expired so far")
        ax.set_title(label)
        ax.set_xlabel("Seconds")
        ax.grid(True, alpha=0.25)
        plotted = True
    if not plotted:
        plt.close(fig)
        return []
    axes[0].set_ylabel("Share of produced cases")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4)
    fig.suptitle("Why broad drag can beat a sharper shock\nThe key difference is not only backlog size, but how much unresolved work slides toward the deadline", y=1.05)
    path = out_dir / "deadline_constrained__retained_immediate__pressure_compare.png"
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return [str(path.relative_to(out_dir.parent.parent))]


def plot_deferred_bill_compare(plt, batch_dir: Path, out_dir: Path) -> list[str]:
    ensure_dir(out_dir)
    grouped = load_runtime_groups(batch_dir)
    variants = [
        (("deadline_constrained", "retained_immediate", "degradation", "moderate"), "Retained / immediate"),
        (("deadline_constrained", "retained_deferred", "degradation", "moderate"), "Retained / deferred"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    plotted = False
    for ax, (key, label) in zip(axes, variants):
        series = grouped.get(key, [])
        if not series:
            continue
        xs, pending = median_runtime_series(series, "pending_cases")
        _, backlog = median_runtime_series(series, "retained_backlog_cases")
        _, critical = median_runtime_series(series, "critical_slack_cases")
        _, doomed = median_runtime_series(series, "doomed_unsettled_cases")
        if not xs:
            continue
        ax.plot(xs, backlog, label="retained backlog")
        ax.plot(xs, pending, label="pending settlement")
        ax.plot(xs, critical, label="near deadline")
        ax.plot(xs, doomed, label="already doomed")
        ax.set_title(label)
        ax.set_xlabel("Seconds")
        ax.grid(True, alpha=0.25)
        plotted = True
    if not plotted:
        plt.close(fig)
        return []
    axes[0].set_ylabel("Median case count")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4)
    fig.suptitle("Immediate versus deferred settlement under moderate drag\nDeferred handling makes the later bill visible instead of hiding it inside one total burden line", y=1.05)
    path = out_dir / "deadline_constrained__degradation__moderate__deferred_bill_compare.png"
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return [str(path.relative_to(out_dir.parent.parent))]




def plot_retained_timing_overview(plt, batch_dir: Path, out_dir: Path) -> list[str]:
    ensure_dir(out_dir)
    summary_path = batch_dir / "aggregates" / "deadline_retained_timing_summary.csv"
    if not summary_path.exists():
        return []
    rows = load_csv_rows(summary_path)
    rows = [r for r in rows if r.get("configuration") in {"retained_immediate", "retained_deferred"}]
    if not rows:
        return []
    family_order = current_deadline_family_candidates({("deadline_constrained", r["configuration"], r["family"], r["severity"]): [] for r in rows})
    configs = [("retained_immediate", "Retained / immediate"), ("retained_deferred", "Retained / deferred")]
    fig, axes = plt.subplots(len(family_order), 2, figsize=(9.5, 2.2 * max(1, len(family_order))), sharex=True, sharey=True)
    if len(family_order) == 1:
        axes = [axes]
    for i, (family, severity, label) in enumerate(family_order):
        for j, (config, config_label) in enumerate(configs):
            ax = axes[i][j] if len(family_order) > 1 else axes[0][j]
            match = next((r for r in rows if r.get("family") == family and r.get("severity") == severity and r.get("configuration") == config), None)
            if match is None:
                ax.axis("off")
                continue
            backlog = float(match.get("backlog_dwell_fraction", 0.0) or 0.0)
            active = float(match.get("active_payment_fraction", 0.0) or 0.0)
            expired = float(match.get("expiry_share_proxy", 0.0) or 0.0)
            ax.bar([0], [backlog], label="retained backlog")
            ax.bar([0], [active], bottom=[backlog], label="active settlement")
            ax.bar([0], [expired], bottom=[backlog + active], label="expired")
            ax.set_ylim(0, 1.0)
            ax.set_xticks([])
            if i == 0:
                ax.set_title(config_label)
            if j == 0:
                ax.set_ylabel(label)
            ax.grid(True, axis="y", alpha=0.2)
    handles, labels = axes[0][0].get_legend_handles_labels() if len(family_order) > 1 else axes[0][0].get_legend_handles_labels()
    fig.legend(handles[:3], labels[:3], loc="upper center", ncol=3)
    fig.suptitle("Retained timing across the full deadline spine\nRetention keeps work available; timing determines whether it sits preserved or is actively being paid", y=1.03)
    path = out_dir / "deadline_constrained__retained_timing__overview.png"
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return [str(path.relative_to(out_dir.parent.parent))]


def plot_retained_timing_detail(plt, batch_dir: Path, out_dir: Path) -> list[str]:
    ensure_dir(out_dir)
    grouped = load_runtime_groups(batch_dir)
    variants = [
        (("deadline_constrained", "retained_immediate", "degradation", "moderate"), "Retained / immediate"),
        (("deadline_constrained", "retained_deferred", "degradation", "moderate"), "Retained / deferred"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    plotted = False
    for ax, (key, label) in zip(axes, variants):
        series = grouped.get(key, [])
        if not series:
            continue
        xs, settled = median_runtime_series(series, "completed_in_time_total")
        _, active = median_runtime_series(series, "active_settlement_cases")
        _, backlog = median_runtime_series(series, "retained_backlog_cases")
        _, expired = median_runtime_series(series, "expired_total")
        if not xs:
            continue
        ax.stackplot(xs, settled, active, backlog, expired, alpha=0.75, labels=["settled in time", "active settlement", "retained backlog", "expired"])
        ax.set_title(label)
        ax.set_xlabel("Seconds")
        ax.grid(True, alpha=0.22)
        plotted = True
    if not plotted:
        plt.close(fig)
        return []
    axes[0].set_ylabel("Median case count")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles[:4], labels[:4], loc="upper center", ncol=4)
    fig.suptitle("Timing within retained recovery under moderate drag\nThe key difference is not whether work still exists, but when that preserved work becomes active settlement", y=1.05)
    path = out_dir / "deadline_constrained__degradation__moderate__retained_timing_detail.png"
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return [str(path.relative_to(out_dir.parent.parent))]


def render_summary_report(batch_dir: Path, saved: dict[str, list[str]], plotting_status: dict[str, str]) -> None:
    report_dir = batch_dir / "reports"
    ensure_dir(report_dir)
    summary_path = report_dir / "summary.md"
    existing = summary_path.read_text(encoding="utf-8") if summary_path.exists() else "# Batch summary\n"
    plotting_lines = ["", "## Plotting status", f"- plotting_enabled: {plotting_status.get('plotting_enabled')}", f"- plotting_error: {plotting_status.get('plotting_error')}", "", "## Plot folders"]
    for name, paths in saved.items():
        plotting_lines.append(f"- {name}: {len(paths)} plot(s)")
    summary_path.write_text(existing.rstrip() + "\n" + "\n".join(plotting_lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("Usage: plot_batch.py <batch_dir>")
    batch_dir = Path(argv[1])
    agg_dir = batch_dir / "aggregates"
    plots_dir = batch_dir / "plots"
    ensure_dir(plots_dir)

    curve_payload = load_json(agg_dir / "scenario_curve_summary.json")
    family_rows = load_csv_rows(agg_dir / "family_comparison_summary.csv")
    role_rows = load_csv_rows(agg_dir / "family_role_summary.csv")

    plt, import_error = try_import_matplotlib()
    plotting_status = {"plotting_enabled": str(plt is not None).lower(), "plotting_error": import_error or ""}

    if plt is None:
        saved = {name: [] for name in ["recovery_curves", "binned_attainment", "tails", "shape_metrics", "curve_regions", "role_scores", "cross_family", "runtime_burden_states", "runtime_pending_compare", "runtime_unresolved_share", "deadline_pressure_compare", "deferred_bill_compare", "retained_timing_overview", "retained_timing_detail"]}
    else:
        saved = {
            "recovery_curves": plot_recovery_curves(plt, curve_payload, plots_dir / "recovery_curves"),
            "binned_attainment": plot_binned_attainment(plt, curve_payload, plots_dir / "binned_attainment"),
            "tails": plot_tail_comparisons(plt, family_rows, plots_dir / "tails"),
            "shape_metrics": plot_shape_metrics(plt, family_rows, plots_dir / "shape_metrics"),
            "curve_regions": plot_curve_regions(plt, load_csv_rows(agg_dir / "scenario_curve_summary.csv"), plots_dir / "curve_regions"),
            "role_scores": plot_role_scores(plt, role_rows, plots_dir / "role_scores"),
            "cross_family": plot_cross_family(plt, family_rows, plots_dir / "cross_family"),
            "runtime_burden_states": plot_runtime_burden_states_small_multiples(plt, batch_dir, plots_dir / "runtime_burden_states"),
            "runtime_pending_compare": plot_runtime_pending_compare(plt, batch_dir, plots_dir / "runtime_pending_compare"),
            "runtime_unresolved_share": plot_runtime_unresolved_share_gallery(plt, batch_dir, plots_dir / "runtime_unresolved_share"),
            "deadline_pressure_compare": plot_deadline_pressure_compare(plt, batch_dir, plots_dir / "deadline_pressure_compare"),
            "deferred_bill_compare": plot_deferred_bill_compare(plt, batch_dir, plots_dir / "deferred_bill_compare"),
            "retained_timing_overview": plot_retained_timing_overview(plt, batch_dir, plots_dir / "retained_timing_overview"),
            "retained_timing_detail": plot_retained_timing_detail(plt, batch_dir, plots_dir / "retained_timing_detail"),
        }
    dump_json(batch_dir / "plots" / "plot_manifest.json", {**saved, "plotting_status": plotting_status})
    render_summary_report(batch_dir, saved, plotting_status)
    if plt is None:
        print(f"[plot_batch] plotting skipped: {import_error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
