"""The :class:`Elevator` car.

The elevator owns all hard physical constraints so that every scheduler inherits
them for free:

* **One floor per tick** — :meth:`step` moves at most one floor.
* **Capacity** — never carries more than ``capacity`` passengers.
* **Direction (SCAN / elevator algorithm)** — the car commits to a direction and
  serves every stop in that direction (in floor order) before reversing. A
  passenger may only board if their travel direction matches the car's committed
  direction (or the car is idle).
* **Express (optional)** — if ``served_floors`` is set, the car only stops at /
  accepts passengers for those floors.

The scheduler decides *which* car a passenger is assigned to; the elevator decides
*how* that passenger is physically served over time.
"""

from __future__ import annotations

from typing import List, Optional, Set

from elevator_sim.models import Direction, Passenger


class Elevator:
    def __init__(
        self,
        index: int,
        capacity: int,
        start_floor: int = 1,
        served_floors: Optional[Set[int]] = None,
    ) -> None:
        self.index = index
        self.capacity = capacity
        self.floor = start_floor
        self.direction = Direction.IDLE
        # Passengers who have boarded and not yet alighted.
        self.onboard: List[Passenger] = []
        # Passengers assigned to this car but not yet picked up (waiting at a floor).
        self.assigned: List[Passenger] = []
        # If non-empty, an express car that only serves these floors.
        self.served_floors: Optional[Set[int]] = served_floors

    # ------------------------------------------------------------------ #
    # Queries used by schedulers
    # ------------------------------------------------------------------ #
    @property
    def load(self) -> int:
        """Passengers currently aboard."""
        return len(self.onboard)

    @property
    def commitment(self) -> int:
        """Passengers aboard plus assigned-but-not-yet-picked-up.

        Used so a scheduler does not over-subscribe a car beyond its capacity.
        """
        return len(self.onboard) + len(self.assigned)

    def serves(self, floor: int) -> bool:
        """Whether this car is allowed to stop at ``floor`` (always True unless express)."""
        return self.served_floors is None or floor in self.served_floors

    def can_serve_passenger(self, p: Passenger) -> bool:
        """Express cars only serve passengers whose origin and dest they cover."""
        return self.serves(p.source) and self.serves(p.dest)

    def can_accept(self, p: Passenger) -> bool:
        """Whether the scheduler may assign ``p`` to this car right now."""
        return self.commitment < self.capacity and self.can_serve_passenger(p)

    # ------------------------------------------------------------------ #
    # Assignment
    # ------------------------------------------------------------------ #
    def assign(self, p: Passenger) -> None:
        """Accept a passenger assignment. Raises if it would violate constraints."""
        if not self.can_accept(p):
            raise ValueError(
                f"Elevator {self.index} cannot accept passenger {p.id} "
                f"(commitment={self.commitment}, capacity={self.capacity})"
            )
        p.assigned_elevator = self.index
        self.assigned.append(p)

    # ------------------------------------------------------------------ #
    # Stop planning
    # ------------------------------------------------------------------ #
    def _target_floors(self) -> Set[int]:
        """All floors this car still needs to visit (pickups + dropoffs)."""
        floors: Set[int] = {p.dest for p in self.onboard}
        floors |= {p.source for p in self.assigned}
        return floors

    def _next_direction(self) -> Direction:
        """Decide the committed direction for this tick (SCAN logic).

        Keep going in the current direction while stops remain ahead; otherwise
        flip toward the nearest pending stop; otherwise go idle.
        """
        targets = self._target_floors()
        if not targets:
            return Direction.IDLE

        above = any(f > self.floor for f in targets)
        below = any(f < self.floor for f in targets)

        if self.direction == Direction.UP and above:
            return Direction.UP
        if self.direction == Direction.DOWN and below:
            return Direction.DOWN
        # Need to (re)pick a direction: head toward the nearest target.
        nearest = min(targets, key=lambda f: abs(f - self.floor))
        return Direction.between(self.floor, nearest)

    # ------------------------------------------------------------------ #
    # Per-tick advance
    # ------------------------------------------------------------------ #
    def step(self, now: int) -> None:
        """Advance the elevator by one tick.

        Order of operations within a tick:
          1. Decide direction based on outstanding stops.
          2. Move one floor in that direction (if any).
          3. Drop off arrivals, then board waiting assignees (respecting capacity
             and direction).
        """
        self.direction = self._next_direction()

        if self.direction != Direction.IDLE:
            self.floor += self.direction.value

        self._alight(now)
        self._board(now)

        # If nothing remains, settle to idle.
        if not self._target_floors():
            self.direction = Direction.IDLE

    def _alight(self, now: int) -> None:
        """Drop off any onboard passengers whose destination is the current floor."""
        staying: List[Passenger] = []
        for p in self.onboard:
            if p.dest == self.floor:
                p.dropoff_time = now
            else:
                staying.append(p)
        self.onboard = staying

    def _board(self, now: int) -> None:
        """Board waiting assignees at the current floor that match our direction."""
        still_waiting: List[Passenger] = []
        for p in self.assigned:
            boardable = (
                p.source == self.floor
                and len(self.onboard) < self.capacity
                and self._direction_ok_for(p)
            )
            if boardable:
                p.pickup_time = now
                if p.dest == self.floor:
                    # Degenerate request (source == dest): pick up and drop off
                    # in the same tick rather than carrying them.
                    p.dropoff_time = now
                else:
                    self.onboard.append(p)
                    # Adopt the passenger's direction if we were idle.
                    if self.direction == Direction.IDLE:
                        self.direction = p.direction
            else:
                still_waiting.append(p)
        self.assigned = still_waiting

    def _direction_ok_for(self, p: Passenger) -> bool:
        """A passenger may board only if their travel direction matches ours."""
        if self.direction == Direction.IDLE:
            return True
        return p.direction == self.direction or p.direction == Direction.IDLE

    # ------------------------------------------------------------------ #
    def is_busy(self) -> bool:
        """Whether the car still has work (passengers aboard or assigned)."""
        return bool(self.onboard or self.assigned)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"Elevator(idx={self.index}, floor={self.floor}, dir={self.direction.name}, "
            f"load={self.load}/{self.capacity}, assigned={len(self.assigned)})"
        )
