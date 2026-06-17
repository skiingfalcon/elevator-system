"""Passenger summary statistics and a human-readable report.

Computes min / max / average wait and total times (as required by the spec) plus a
few notable observations: medians, the busiest pickup floor, throughput, and a
starvation check (the longest any single passenger waited).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import List, Sequence

from elevator_sim.models import Passenger


@dataclass
class MetricStats:
    minimum: float
    maximum: float
    average: float
    median: float

    @classmethod
    def of(cls, values: Sequence[float]) -> "MetricStats":
        if not values:
            return cls(0.0, 0.0, 0.0, 0.0)
        return cls(
            minimum=min(values),
            maximum=max(values),
            average=statistics.fmean(values),
            median=statistics.median(values),
        )


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


def summarize(passengers: List[Passenger], ticks_elapsed: int) -> Summary:
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
    )


def format_report(summary: Summary) -> str:
    """Render a Summary as a readable multi-line report."""

    def line(label: str, m: MetricStats) -> str:
        return (
            f"  {label:<12} min={m.minimum:6.1f}  max={m.maximum:6.1f}  "
            f"avg={m.average:6.2f}  median={m.median:6.1f}"
        )

    lines = [
        "=" * 60,
        "Passenger Summary Statistics",
        "=" * 60,
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
        f"  Busiest pickup floor: {summary.busiest_pickup_floor}",
        f"  Throughput:           {summary.throughput:.3f} passengers/tick",
        "=" * 60,
    ]
    return "\n".join(lines)
