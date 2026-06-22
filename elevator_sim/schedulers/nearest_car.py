"""Nearest-car scheduler (the default).

Assigns each passenger to the elevator with the lowest estimated cost to reach
their origin, where cost combines:

* the estimated time-to-pickup along the car's committed SCAN run (a car heading
  away must finish its sweep before it can double back), and
* a congestion term per outstanding stop, so load spreads across the bank instead
  of piling onto one car.

Fairness / "serve all requests eventually" is handled by the *simulation*, not
here: the dispatcher considers waiting passengers oldest-first, and a car is always
offered whenever one has spare capacity, so no passenger can be starved. (An
earlier version subtracted a per-passenger "aging bonus" from this cost, but that
term is identical across every candidate car for a given passenger, so it could
never change the ``argmin`` — it was a no-op and has been removed.)
"""

from elevator_sim.elevator import Elevator
from elevator_sim.models import Passenger
from elevator_sim.schedulers.base import Scheduler, register


@register
class NearestCarScheduler(Scheduler):
    name = "nearest_car"

    def __init__(self, stop_cost: float = 1.0) -> None:
        #: Estimated ticks "spent" per outstanding stop the car must service first.
        self.stop_cost = stop_cost

    def _cost(self, elevator: Elevator, p: Passenger) -> float:
        eta = elevator.eta_to(p.source)
        # Each already-committed stop adds a little expected delay (proxy for the
        # extra dwell/detour a fuller car imposes).
        congestion = self.stop_cost * elevator.commitment
        return eta + congestion

    def choose(
        self, passenger: Passenger, elevators: list[Elevator], now: int
    ) -> int | None:
        candidates = [e for e in elevators if e.can_accept(passenger)]
        if not candidates:
            return None
        best = min(candidates, key=lambda e: self._cost(e, passenger))
        return best.index
