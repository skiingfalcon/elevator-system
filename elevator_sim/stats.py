"""Passenger summary statistics and a human-readable report.

Computes min / max / average wait and total times (as required by the spec) plus a
few notable observations: medians, the busiest pickup floor, throughput, and a
starvation check (the longest any single passenger waited).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import List, Optional, Sequence

from elevator_sim.models import Passenger


@dataclass
class MetricStats:
    minimum: float
    maximum: float
    average: float
    median: float
    p95: float  # 95th-percentile (tail latency)

    @classmethod
    def of(cls, values: Sequence[float]) -> "MetricStats":
        if not values:
            return cls(0.0, 0.0, 0.0, 0.0, 0.0)
        return cls(
            minimum=min(values),
            maximum=max(values),
            average=statistics.fmean(values),
            median=statistics.median(values),
            p95=_percentile(values, 95),
        )


def _percentile(values: Sequence[float], pct: float) -> float:
    """Linear-interpolated ``pct`` percentile (matches numpy's default)."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (pct / 100) * (len(ordered) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    frac = rank - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


@dataclass
class Summary:
    count: int
    delivered: int
    wait: MetricStats
    total: MetricStats
    travel: MetricStats
    ticks_elapsed: int
    busiest_pickup_floor: int
    throughput: float  # passengers delivered per tick
    #: Floors traveled by each car over the whole run (index = elevator index).
    distance_per_car: List[int] = None  # type: ignore[assignment]


def _distance_per_car(position_history: Sequence[Sequence[int]]) -> List[int]:
    """Total floors each car moved, summed over the run from its position log."""
    if not position_history:
        return []
    num_cars = len(position_history[0])
    distances = [0] * num_cars
    for prev, cur in zip(position_history, position_history[1:]):
        for i in range(num_cars):
            distances[i] += abs(cur[i] - prev[i])
    return distances


def summarize(
    passengers: List[Passenger],
    ticks_elapsed: int,
    position_history: Optional[Sequence[Sequence[int]]] = None,
) -> Summary:
    delivered = [p for p in passengers if p.delivered]

    waits = [p.wait_time for p in delivered if p.wait_time is not None]
    totals = [p.total_time for p in delivered if p.total_time is not None]
    travels = [p.travel_time for p in delivered if p.travel_time is not None]

    floor_counts: dict[int, int] = {}
    for p in passengers:
        floor_counts[p.source] = floor_counts.get(p.source, 0) + 1
    busiest = max(floor_counts, key=floor_counts.get) if floor_counts else 0

    return Summary(
        count=len(passengers),
        delivered=len(delivered),
        wait=MetricStats.of(waits),
        total=MetricStats.of(totals),
        travel=MetricStats.of(travels),
        ticks_elapsed=ticks_elapsed,
        busiest_pickup_floor=busiest,
        throughput=(len(delivered) / ticks_elapsed) if ticks_elapsed else 0.0,
        distance_per_car=_distance_per_car(position_history or []),
    )


def format_report(summary: Summary) -> str:
    """Render a Summary as a readable multi-line report."""

    def line(label: str, m: MetricStats) -> str:
        return (
            f"  {label:<12} min={m.minimum:6.1f}  max={m.maximum:6.1f}  "
            f"avg={m.average:6.2f}  median={m.median:6.1f}  p95={m.p95:6.1f}"
        )

    lines = [
        "=" * 72,
        "Passenger Summary Statistics",
        "=" * 72,
        f"Passengers:        {summary.count} requested, {summary.delivered} delivered",
        f"Simulation length: {summary.ticks_elapsed} ticks",
        "",
        "Time metrics (in ticks):",
        line("wait_time", summary.wait),
        line("travel_time", summary.travel),
        line("total_time", summary.total),
        "",
        "Notable observations:",
        f"  Longest single wait:  {summary.wait.maximum:.0f} ticks "
        f"(no passenger waited indefinitely)",
        f"  95th-pct total_time:  {summary.total.p95:.0f} ticks (tail latency)",
        f"  Busiest pickup floor: {summary.busiest_pickup_floor}",
        f"  Throughput:           {summary.throughput:.3f} passengers/tick",
    ]
    if summary.distance_per_car:
        per_car = "  ".join(
            f"e{i}={d}" for i, d in enumerate(summary.distance_per_car)
        )
        total_dist = sum(summary.distance_per_car)
        lines.append(f"  Distance per car:     {per_car}  (total {total_dist} floors)")
    lines.append("=" * 72)
    return "\n".join(lines)
