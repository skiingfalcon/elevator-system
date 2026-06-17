"""Zone-based scheduler.

The building's floors are partitioned into contiguous zones, one per elevator. A
passenger is preferentially assigned to the car owning the zone of their origin
floor. This keeps each car within a band of the building (good for tall buildings
and predictable service), at the cost of some efficiency when demand is uneven.

If the zone's owner is full, we fall back to the nearest available car so the
"serve all eventually" guarantee still holds.
"""

from __future__ import annotations

from typing import List, Optional

from elevator_sim.elevator import Elevator
from elevator_sim.models import Passenger
from elevator_sim.schedulers.base import Scheduler, register


@register
class ZoneBasedScheduler(Scheduler):
    name = "zone_based"

    def __init__(self, floors: int = 10, num_elevators: int = 1) -> None:
        self.floors = floors
        self.num_elevators = num_elevators

    def _owner_for_floor(self, floor: int) -> int:
        """Map a floor (1-based) to the elevator index owning its zone."""
        n = max(self.num_elevators, 1)
        zone_size = max(self.floors / n, 1)
        idx = int((floor - 1) // zone_size)
        return min(idx, n - 1)

    def choose(
        self, passenger: Passenger, elevators: List[Elevator], now: int
    ) -> Optional[int]:
        owner = self._owner_for_floor(passenger.source)
        if owner < len(elevators) and elevators[owner].can_accept(passenger):
            return owner

        # Fallback: nearest car that can accept, so nobody is starved.
        candidates = [e for e in elevators if e.can_accept(passenger)]
        if not candidates:
            return None
        best = min(candidates, key=lambda e: abs(e.floor - passenger.source))
        return best.index
