"""Nearest-car scheduler (the default).

Assigns each passenger to the elevator with the lowest estimated cost to reach
their origin, where cost combines:

* distance from the car to the pickup floor,
* a penalty when the car is moving away from / opposite to the passenger,
* the car's current load (prefer less-busy cars to spread work), and
* an **aging bonus**: the longer a passenger has already waited, the more we
  discount the cost. This guarantees the spec's "serve all requests eventually"
  goal — a passenger cannot be starved forever because their effective cost keeps
  dropping until some car takes them.
"""

from __future__ import annotations

from typing import List, Optional

from elevator_sim.elevator import Elevator
from elevator_sim.models import Direction, Passenger
from elevator_sim.schedulers.base import Scheduler, register


@register
class NearestCarScheduler(Scheduler):
    name = "nearest_car"

    def __init__(
        self,
        stop_cost: float = 1.0,
        aging_weight: float = 0.5,
    ) -> None:
        #: Estimated ticks "spent" per outstanding stop the car must service first.
        self.stop_cost = stop_cost
        self.aging_weight = aging_weight

    def _eta(self, elevator: Elevator, source: int) -> float:
        """Estimate ticks until ``elevator`` could reach ``source``.

        Rather than raw current-floor distance, account for the car's committed
        SCAN run: a busy car heading away must finish its current sweep before it
        can double back. This makes overloaded / wrong-direction cars genuinely
        expensive, so load spreads across the bank instead of piling on one car.
        """
        cur = elevator.floor
        direction = elevator.direction

        if direction == Direction.IDLE or not elevator.is_busy():
            return abs(cur - source)

        targets = elevator._target_floors()
        if direction == Direction.UP:
            extreme = max(targets | {cur})
            if source >= cur:
                return source - cur  # reachable on the way up
            # Up to the top of the run, then back down to source.
            return (extreme - cur) + (extreme - source)
        else:  # DOWN
            extreme = min(targets | {cur})
            if source <= cur:
                return cur - source
            return (cur - extreme) + (source - extreme)

    def _cost(self, elevator: Elevator, p: Passenger, now: int) -> float:
        eta = self._eta(elevator, p.source)
        # Each already-committed stop adds a little expected delay (proxy for the
        # extra dwell/detour a fuller car imposes).
        congestion = self.stop_cost * elevator.commitment
        aging_bonus = self.aging_weight * (now - p.request_time)
        return eta + congestion - aging_bonus

    def choose(
        self, passenger: Passenger, elevators: List[Elevator], now: int
    ) -> Optional[int]:
        candidates = [e for e in elevators if e.can_accept(passenger)]
        if not candidates:
            return None
        best = min(candidates, key=lambda e: self._cost(e, passenger, now))
        return best.index
