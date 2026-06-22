#!/usr/bin/env python3
"""Generate comparison statistics across scenarios and schedulers.

Runs every registered scheduler against a set of representative workloads and
writes the results to ``results/`` in three forms:

* ``results/scheduler_comparison.csv``   — raw rows (one per scenario x scheduler)
* ``results/results.json``               — full nested stats (machine-readable)
* ``results/scheduler_comparison.md``     — slide-ready Markdown tables

All workloads are seeded, so the numbers are fully reproducible:

    python scripts/generate_results.py
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from elevator_sim.io_utils import parse_requests
from elevator_sim.models import Request
from elevator_sim.schedulers.base import available, create
from elevator_sim.simulation import Simulation, SimulationConfig
from elevator_sim.stats import Summary, summarize

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results"


# --------------------------------------------------------------------------- #
# Workload generators (all deterministic)
# --------------------------------------------------------------------------- #
def random_mixed(n: int, floors: int, seed: int, arrival_gap: int = 3) -> List[Request]:
    """Uniformly random origin/destination traffic (general office flow)."""
    rng = random.Random(seed)
    reqs: List[Request] = []
    t = 0
    for i in range(n):
        t += rng.randint(0, arrival_gap)
        src = rng.randint(1, floors)
        dst = rng.randint(1, floors)
        while dst == src:
            dst = rng.randint(1, floors)
        reqs.append(Request(time=t, id=f"p{i}", source=src, dest=dst))
    return reqs


def up_peak(n: int, floors: int, seed: int) -> List[Request]:
    """Morning up-peak: almost everyone enters at the lobby heading up."""
    rng = random.Random(seed)
    reqs: List[Request] = []
    t = 0
    for i in range(n):
        t += rng.randint(0, 1)  # tight clustering, like a swipe-in rush
        dst = rng.randint(2, floors)
        reqs.append(Request(time=t, id=f"p{i}", source=1, dest=dst))
    return reqs


def down_peak(n: int, floors: int, seed: int) -> List[Request]:
    """Evening down-peak: everyone heading to the lobby from upper floors."""
    rng = random.Random(seed)
    reqs: List[Request] = []
    t = 0
    for i in range(n):
        t += rng.randint(0, 1)
        src = rng.randint(2, floors)
        reqs.append(Request(time=t, id=f"p{i}", source=src, dest=1))
    return reqs


# --------------------------------------------------------------------------- #
# Scenarios: (label, requests, floors, elevators, capacity)
# --------------------------------------------------------------------------- #
def build_scenarios() -> List[Dict]:
    sample_csv = REPO_ROOT / "data" / "sample_requests.csv"
    scenarios = [
        {
            "label": "Provided sample (15 reqs)",
            "reqs": parse_requests(str(sample_csv)),
            "floors": 60,
            "elevators": 3,
            "capacity": 8,
        },
        {
            "label": "Mixed traffic (200 reqs)",
            "reqs": random_mixed(200, 60, seed=42),
            "floors": 60,
            "elevators": 4,
            "capacity": 8,
        },
        {
            "label": "Up-peak rush (150 reqs)",
            "reqs": up_peak(150, 60, seed=11),
            "floors": 60,
            "elevators": 4,
            "capacity": 10,
        },
        {
            "label": "Down-peak rush (150 reqs)",
            "reqs": down_peak(150, 60, seed=11),
            "floors": 60,
            "elevators": 4,
            "capacity": 10,
        },
        {
            "label": "Tall building (300 reqs)",
            "reqs": random_mixed(300, 100, seed=7),
            "floors": 100,
            "elevators": 6,
            "capacity": 12,
        },
    ]
    return scenarios


def run(scenario: Dict, scheduler_name: str) -> Summary:
    cfg = SimulationConfig(
        floors=scenario["floors"],
        num_elevators=scenario["elevators"],
        capacity=scenario["capacity"],
    )
    if scheduler_name == "zone_based":
        sched = create(scheduler_name, floors=scenario["floors"],
                       num_elevators=scenario["elevators"])
    else:
        sched = create(scheduler_name)
    result = Simulation(cfg, sched).run(scenario["reqs"])
    return summarize(result.passengers, result.ticks_elapsed, result.position_history)


# --------------------------------------------------------------------------- #
# Output writers
# --------------------------------------------------------------------------- #
CSV_FIELDS = [
    "scenario", "scheduler", "passengers", "delivered",
    "wait_avg", "wait_max", "wait_p95",
    "total_avg", "total_max", "total_p95",
    "travel_avg", "sim_length", "throughput", "total_distance",
]


def summary_row(scenario_label: str, name: str, s: Summary) -> Dict:
    return {
        "scenario": scenario_label,
        "scheduler": name,
        "passengers": s.count,
        "delivered": s.delivered,
        "wait_avg": round(s.wait.average, 1),
        "wait_max": round(s.wait.maximum, 0),
        "wait_p95": round(s.wait.p95, 1),
        "total_avg": round(s.total.average, 1),
        "total_max": round(s.total.maximum, 0),
        "total_p95": round(s.total.p95, 1),
        "travel_avg": round(s.travel.average, 1),
        "sim_length": s.ticks_elapsed,
        "throughput": round(s.throughput, 3),
        "total_distance": sum(s.distance_per_car) if s.distance_per_car else 0,
    }


def write_csv(rows: List[Dict]) -> Path:
    path = RESULTS_DIR / "scheduler_comparison.csv"
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_json(nested: Dict) -> Path:
    path = RESULTS_DIR / "results.json"
    with open(path, "w") as fh:
        json.dump(nested, fh, indent=2)
    return path


def write_markdown(rows: List[Dict], scenarios: List[Dict]) -> Path:
    path = RESULTS_DIR / "scheduler_comparison.md"
    lines: List[str] = [
        "# Scheduler Comparison Results",
        "",
        "Reproducible with `python scripts/generate_results.py`. "
        "All workloads are seeded. Times are in ticks (1 tick = 1 floor of travel).",
        "",
    ]

    by_scenario: Dict[str, List[Dict]] = {}
    for r in rows:
        by_scenario.setdefault(r["scenario"], []).append(r)

    for sc in scenarios:
        label = sc["label"]
        lines.append(f"## {label}")
        lines.append("")
        lines.append(
            f"_{sc['elevators']} cars, {sc['floors']} floors, capacity "
            f"{sc['capacity']}, {len(sc['reqs'])} passengers._"
        )
        lines.append("")
        lines.append(
            "| Scheduler | avg total | p95 total | max wait | avg wait | "
            "sim length | distance | delivered |"
        )
        lines.append(
            "|-----------|----------:|----------:|---------:|---------:|"
            "-----------:|---------:|----------:|"
        )
        scenario_rows = by_scenario[label]
        best_total = min(r["total_avg"] for r in scenario_rows)
        for r in scenario_rows:
            star = " **(best)**" if r["total_avg"] == best_total else ""
            lines.append(
                f"| {r['scheduler']}{star} | {r['total_avg']} | {r['total_p95']} | "
                f"{r['wait_max']:.0f} | {r['wait_avg']} | {r['sim_length']} | "
                f"{r['total_distance']} | {r['delivered']}/{r['passengers']} |"
            )
        lines.append("")

    # Headline summary: who wins each scenario on avg total_time.
    lines.append("## Headline — lowest avg total_time per scenario")
    lines.append("")
    lines.append("| Scenario | Winner | avg total (ticks) |")
    lines.append("|----------|--------|------------------:|")
    for sc in scenarios:
        srows = by_scenario[sc["label"]]
        best = min(srows, key=lambda r: r["total_avg"])
        lines.append(f"| {sc['label']} | {best['scheduler']} | {best['total_avg']} |")
    lines.append("")

    path.write_text("\n".join(lines))
    return path


def main() -> int:
    RESULTS_DIR.mkdir(exist_ok=True)
    scenarios = build_scenarios()
    schedulers = available()

    rows: List[Dict] = []
    nested: Dict = {"scenarios": {}}

    for sc in scenarios:
        nested["scenarios"][sc["label"]] = {
            "config": {
                "floors": sc["floors"],
                "elevators": sc["elevators"],
                "capacity": sc["capacity"],
                "passengers": len(sc["reqs"]),
            },
            "schedulers": {},
        }
        for name in schedulers:
            s = run(sc, name)
            rows.append(summary_row(sc["label"], name, s))
            nested["scenarios"][sc["label"]]["schedulers"][name] = {
                "wait": asdict(s.wait),
                "travel": asdict(s.travel),
                "total": asdict(s.total),
                "sim_length": s.ticks_elapsed,
                "throughput": s.throughput,
                "delivered": s.delivered,
                "distance_per_car": s.distance_per_car,
            }

    csv_path = write_csv(rows)
    json_path = write_json(nested)
    md_path = write_markdown(rows, scenarios)

    print("Wrote:")
    for p in (csv_path, json_path, md_path):
        print(f"  {p.relative_to(REPO_ROOT)}")
    print()
    # Echo the markdown so it shows up in the console too.
    print(md_path.read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
