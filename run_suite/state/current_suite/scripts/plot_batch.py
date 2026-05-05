from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from batch_utils import dump_json, load_json

FAMILY_LABELS = {
    "baseline": "baseline",
    "degradation": "degradation",
    "interrupt_mid": "body-phase interruption",
    "interrupt_late": "late-convergence interruption",
    "interruption": "interruption",
    "backlog_shock": "backlog shock",
    "duplicate_pressure": "duplicate pressure",
    "omission_pressure": "omission pressure",
    "mixed_pressure": "mixed pressure",
    "overload_burst": "overload burst",
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
        saved = {name: [] for name in ["recovery_curves", "binned_attainment", "tails", "shape_metrics", "curve_regions", "role_scores", "cross_family"]}
    else:
        saved = {
            "recovery_curves": plot_recovery_curves(plt, curve_payload, plots_dir / "recovery_curves"),
            "binned_attainment": plot_binned_attainment(plt, curve_payload, plots_dir / "binned_attainment"),
            "tails": plot_tail_comparisons(plt, family_rows, plots_dir / "tails"),
            "shape_metrics": plot_shape_metrics(plt, family_rows, plots_dir / "shape_metrics"),
            "curve_regions": plot_curve_regions(plt, load_csv_rows(agg_dir / "scenario_curve_summary.csv"), plots_dir / "curve_regions"),
            "role_scores": plot_role_scores(plt, role_rows, plots_dir / "role_scores"),
            "cross_family": plot_cross_family(plt, family_rows, plots_dir / "cross_family"),
        }
    dump_json(batch_dir / "plots" / "plot_manifest.json", {**saved, "plotting_status": plotting_status})
    render_summary_report(batch_dir, saved, plotting_status)
    if plt is None:
        print(f"[plot_batch] plotting skipped: {import_error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
