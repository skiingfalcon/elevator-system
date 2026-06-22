#!/usr/bin/env python3
"""Reproducible scheduler benchmark.

Generates a deterministic randomized workload and runs every registered scheduler
against it, printing the fairness-vs-efficiency comparison table that the README
cites. Because the workload is seeded, the numbers are reproducible:

    python bench.py
    python bench.py --passengers 200 --floors 60 --elevators 4 --capacity 8 --seed 42

The default parameters match the table in README.md.
"""

import argparse
import random

from elevator_sim.models import Request
from elevator_sim.schedulers.base import available, build
from elevator_sim.simulation import Simulation, SimulationConfig
from elevator_sim.stats import summarize


def make_workload(
    n: int, floors: int, seed: int, arrival_gap: int = 3
) -> list[Request]:
    """A deterministic stream of ``n`` mixed-direction requests over time."""
    rng = random.Random(seed)
    reqs: list[Request] = []
    t = 0
    for i in range(n):
        t += rng.randint(0, arrival_gap)
        src = rng.randint(1, floors)
        dst = rng.randint(1, floors)
        while dst == src:
            dst = rng.randint(1, floors)
        reqs.append(Request(time=t, id=f"p{i}", source=src, dest=dst))
    return reqs


def run_one(name: str, reqs, floors: int, elevators: int, capacity: int):
    cfg = SimulationConfig(floors=floors, num_elevators=elevators, capacity=capacity)
    sched = build(name, floors=floors, num_elevators=elevators)
    result = Simulation(cfg, sched).run(reqs)
    return summarize(result.passengers, result.ticks_elapsed)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Reproducible scheduler benchmark.")
    p.add_argument("--passengers", type=int, default=200)
    p.add_argument("--floors", type=int, default=60)
    p.add_argument("--elevators", type=int, default=4)
    p.add_argument("--capacity", type=int, default=8)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args(argv)

    reqs = make_workload(args.passengers, args.floors, args.seed)

    print(
        f"Workload: {args.passengers} passengers, {args.floors} floors, "
        f"{args.elevators} cars, capacity {args.capacity}, seed {args.seed}\n"
    )
    header = f"| {'Scheduler':<12} | {'avg total_time':>14} | {'max wait_time':>13} | {'sim length':>10} | {'delivered':>9} |"
    rule = "|" + "-" * 14 + "|" + "-" * 16 + "|" + "-" * 15 + "|" + "-" * 12 + "|" + "-" * 11 + "|"
    print(header)
    print(rule)

    rows = []
    for name in available():
        s = run_one(name, reqs, args.floors, args.elevators, args.capacity)
        rows.append((name, s))
        print(
            f"| {name:<12} | {s.total.average:>14.1f} | {s.wait.maximum:>13.0f} | "
            f"{s.ticks_elapsed:>10} | {s.delivered:>4}/{s.count:<4} |"
        )

    best = min(rows, key=lambda r: r[1].total.average)
    print(f"\nLowest avg total_time: {best[0]} ({best[1].total.average:.1f} ticks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
