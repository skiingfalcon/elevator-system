#!/usr/bin/env python3
"""Render slide-ready comparison charts from results/scheduler_comparison.csv.

Produces two PNGs in ``results/``:

* ``results/comparison_avg_total.png`` — grouped bars of avg total_time per
  scenario x scheduler (the headline "no free lunch" chart).
* ``results/comparison_wait_vs_tail.png`` — avg wait vs p95 total_time, showing
  the fairness/tail trade-off.

Run ``python scripts/generate_results.py`` first to refresh the CSV, then:

    python scripts/plot_comparison.py
"""

import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results"
CSV_PATH = RESULTS_DIR / "scheduler_comparison.csv"

# Stable scheduler order + colorblind-friendly palette.
SCHEDULERS = ["nearest_car", "round_robin", "zone_based"]
COLORS = {"nearest_car": "#4C72B0", "round_robin": "#DD8452", "zone_based": "#55A868"}
# Shorten long scenario labels for the x-axis.
SHORT = {
    "Provided sample (15 reqs)": "Sample\n(15)",
    "Mixed traffic (200 reqs)": "Mixed\n(200)",
    "Up-peak rush (150 reqs)": "Up-peak\n(150)",
    "Down-peak rush (150 reqs)": "Down-peak\n(150)",
    "Tall building (300 reqs)": "Tall bldg\n(300)",
}


def load_rows() -> list[dict[str, str]]:
    if not CSV_PATH.exists():
        raise SystemExit(
            f"{CSV_PATH} not found — run scripts/generate_results.py first."
        )
    with open(CSV_PATH, newline="") as fh:
        return list(csv.DictReader(fh))


def _ordered_scenarios(rows: list[dict[str, str]]) -> list[str]:
    seen: list[str] = []
    for r in rows:
        if r["scenario"] not in seen:
            seen.append(r["scenario"])
    return seen


def plot_avg_total(rows: list[dict[str, str]], plt) -> Path:
    scenarios = _ordered_scenarios(rows)
    lookup = {(r["scenario"], r["scheduler"]): float(r["total_avg"]) for r in rows}

    n = len(scenarios)
    width = 0.25
    x = list(range(n))

    fig, ax = plt.subplots(figsize=(11, 5.5))
    for i, sched in enumerate(SCHEDULERS):
        offsets = [xi + (i - 1) * width for xi in x]
        vals = [lookup.get((sc, sched), 0.0) for sc in scenarios]
        bars = ax.bar(offsets, vals, width, label=sched, color=COLORS[sched])
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 1.5, f"{v:.0f}",
                    ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels([SHORT.get(sc, sc) for sc in scenarios])
    ax.set_ylabel("avg total_time (ticks)  — lower is better")
    ax.set_title("Scheduler comparison by traffic pattern  (avg total_time)")
    ax.legend(title="scheduler", loc="upper left")
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    fig.tight_layout()

    out = RESULTS_DIR / "comparison_avg_total.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def plot_wait_vs_tail(rows: list[dict[str, str]], plt) -> Path:
    """Scatter: avg wait (fairness) vs p95 total (tail) — one marker per run."""
    markers = {"nearest_car": "o", "round_robin": "s", "zone_based": "^"}
    fig, ax = plt.subplots(figsize=(9, 6))
    for sched in SCHEDULERS:
        xs = [float(r["wait_avg"]) for r in rows if r["scheduler"] == sched]
        ys = [float(r["total_p95"]) for r in rows if r["scheduler"] == sched]
        ax.scatter(xs, ys, s=90, color=COLORS[sched], marker=markers[sched],
                   label=sched, edgecolor="white", linewidth=0.6, zorder=3)

    ax.set_xlabel("avg wait_time (ticks)  — fairness")
    ax.set_ylabel("p95 total_time (ticks)  — tail latency")
    ax.set_title("Fairness vs. tail latency  (bottom-left is best)")
    ax.legend(title="scheduler")
    ax.grid(linestyle=":", alpha=0.5)
    fig.tight_layout()

    out = RESULTS_DIR / "comparison_wait_vs_tail.png"
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def main() -> int:
    try:
        import matplotlib
        matplotlib.use("Agg")  # headless-safe
        import matplotlib.pyplot as plt
    except ImportError:
        raise SystemExit(
            "matplotlib is required. Install with `uv sync --extra plot`."
        )

    rows = load_rows()
    p1 = plot_avg_total(rows, plt)
    p2 = plot_wait_vs_tail(rows, plt)
    print("Wrote:")
    for p in (p1, p2):
        print(f"  {p.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
