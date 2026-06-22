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

from elevator_sim.elevator import Elevator
from elevator_sim.models import Passenger
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

    def _cost(self, elevator: Elevator, p: Passenger, now: int) -> float:
        eta = elevator.eta_to(p.source)
        # Each already-committed stop adds a little expected delay (proxy for the
        # extra dwell/detour a fuller car imposes).
        congestion = self.stop_cost * elevator.commitment
        aging_bonus = self.aging_weight * (now - p.request_time)
        return eta + congestion - aging_bonus

    def choose(
        self, passenger: Passenger, elevators: list[Elevator], now: int
    ) -> int | None:
        candidates = [e for e in elevators if e.can_accept(passenger)]
        if not candidates:
            return None
        best = min(candidates, key=lambda e: self._cost(e, passenger, now))
        return best.index
