"""Round-robin scheduler: cycle through cars regardless of position.

Simple and fair in the sense that load is spread evenly, but it ignores distance
and direction, so it usually has worse total times than nearest-car. Included to
demonstrate the fairness-vs-efficiency trade-off.
"""

from __future__ import annotations

from typing import List, Optional

from elevator_sim.elevator import Elevator
from elevator_sim.models import Passenger
from elevator_sim.schedulers.base import Scheduler, register


@register
class RoundRobinScheduler(Scheduler):
    name = "round_robin"

    def __init__(self) -> None:
        self._cursor = 0

    def choose(
        self, passenger: Passenger, elevators: List[Elevator], now: int
    ) -> Optional[int]:
        n = len(elevators)
        # Try each car once, starting at the cursor, until one can accept.
        for offset in range(n):
            idx = (self._cursor + offset) % n
            if elevators[idx].can_accept(passenger):
                self._cursor = (idx + 1) % n
                return idx
        return None
