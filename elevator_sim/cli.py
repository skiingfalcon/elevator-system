"""Command-line entry point for the elevator simulation.

Example::

    python -m elevator_sim \\
        --floors 60 --elevators 3 --capacity 8 \\
        --scheduler nearest_car \\
        --input data/sample_requests.csv \\
        --log-out positions.log --plot
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from elevator_sim import schedulers
from elevator_sim.io_utils import parse_requests
from elevator_sim.schedulers.base import available, create
from elevator_sim.simulation import Simulation, SimulationConfig
from elevator_sim.stats import format_report, summarize


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="elevator_sim",
        description="Discrete-time Destination Dispatch elevator simulation.",
    )
    p.add_argument("--input", required=True, help="Path to requests CSV (time,id,source,dest)")
    p.add_argument("--floors", type=int, default=10, help="Number of floors (default: 10)")
    p.add_argument("--elevators", type=int, default=3, help="Number of elevators (default: 3)")
    p.add_argument("--capacity", type=int, default=8, help="Max passengers per elevator (default: 8)")
    p.add_argument("--start-floor", type=int, default=1, help="Floor all cars start on (default: 1)")
    p.add_argument(
        "--scheduler",
        default="nearest_car",
        choices=available(),
        help="Assignment strategy (default: nearest_car)",
    )
    p.add_argument(
        "--log-out",
        default="positions.log",
        help="Where to write the per-tick positions log (default: positions.log)",
    )
    p.add_argument("--plot", action="store_true", help="Render matplotlib charts (requires matplotlib)")
    p.add_argument(
        "--plot-prefix",
        default=None,
        help="Filename prefix for generated charts",
    )
    return p


def _make_scheduler(name: str, floors: int, num_elevators: int):
    # zone_based needs to know the building shape to compute zones.
    if name == "zone_based":
        return create(name, floors=floors, num_elevators=num_elevators)
    return create(name)


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    requests = parse_requests(args.input)
    if not requests:
        print("No requests found in input; nothing to simulate.", file=sys.stderr)
        return 1

    config = SimulationConfig(
        floors=args.floors,
        num_elevators=args.elevators,
        capacity=args.capacity,
        start_floor=args.start_floor,
    )
    scheduler = _make_scheduler(args.scheduler, args.floors, args.elevators)

    sim = Simulation(config, scheduler)
    result = sim.run(requests, log_path=args.log_out)

    summary = summarize(result.passengers, result.ticks_elapsed)
    print(f"Scheduler: {args.scheduler}  |  "
          f"{config.num_elevators} elevators, {config.floors} floors, "
          f"capacity {config.capacity}")
    print(f"Positions log written to: {args.log_out}")
    print()
    print(format_report(summary))

    if args.plot:
        from elevator_sim import viz

        paths = viz.plot_all(result, prefix=args.plot_prefix)
        print("\nCharts written:")
        for path in paths:
            print(f"  {path}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
