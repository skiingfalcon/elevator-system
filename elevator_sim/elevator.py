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

from elevator_sim.models import Direction, Passenger


class Elevator:
    def __init__(
        self,
        index: int,
        capacity: int,
        start_floor: int = 1,
        served_floors: set[int] | None = None,
    ) -> None:
        self.index = index
        self.capacity = capacity
        self.floor = start_floor
        self.direction = Direction.IDLE
        # Passengers who have boarded and not yet alighted.
        self.onboard: list[Passenger] = []
        # Passengers assigned to this car but not yet picked up (waiting at a floor).
        self.assigned: list[Passenger] = []
        # If non-empty, an express car that only serves these floors.
        self.served_floors: set[int] | None = served_floors

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

    def eta_to(self, floor: int) -> int:
        """Estimate ticks until this car could reach ``floor``.

        Rather than raw current-floor distance, this accounts for the car's
        committed SCAN run: a busy car heading away must finish its current sweep
        before it can double back, which makes overloaded / wrong-direction cars
        genuinely expensive. Schedulers use this to spread load instead of piling
        onto one car.
        """
        cur = self.floor
        if self.direction == Direction.IDLE or not self.is_busy():
            return abs(cur - floor)

        targets = self.target_floors()
        if self.direction == Direction.UP:
            extreme = max(targets | {cur})
            if floor >= cur:
                return floor - cur  # reachable on the way up
            # Up to the top of the run, then back down to the floor.
            return (extreme - cur) + (extreme - floor)
        # DOWN
        extreme = min(targets | {cur})
        if floor <= cur:
            return cur - floor
        return (cur - extreme) + (floor - extreme)

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
    def target_floors(self) -> set[int]:
        """All floors this car still needs to visit (pickups + dropoffs).

        Part of the public query surface schedulers use to reason about a car's
        committed plan.
        """
        floors: set[int] = {p.dest for p in self.onboard}
        floors |= {p.source for p in self.assigned}
        return floors

    def _next_direction(self) -> Direction:
        """Decide the committed direction for this tick (SCAN logic).

        Keep going in the current direction while stops remain ahead; otherwise
        flip toward the nearest pending stop; otherwise go idle.
        """
        targets = self.target_floors()
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
    def step(self, now: int) -> int:
        """Advance the elevator by one tick; return how many passengers it delivered.

        Order of operations within a tick:
          1. Decide direction based on outstanding stops.
          2. Move one floor in that direction (if any).
          3. Drop off arrivals, then board waiting assignees (respecting capacity
             and direction).

        Returning the delivered count lets the simulation maintain a running total
        without rescanning every passenger each tick.
        """
        self.direction = self._next_direction()

        if self.direction != Direction.IDLE:
            self.floor += self.direction.value

        delivered = self._alight(now)
        delivered += self._board(now)

        # If nothing remains, settle to idle.
        if not self.target_floors():
            self.direction = Direction.IDLE

        return delivered

    def _alight(self, now: int) -> int:
        """Drop off onboard passengers at the current floor; return how many."""
        staying: list[Passenger] = []
        delivered = 0
        for p in self.onboard:
            if p.dest == self.floor:
                p.dropoff_time = now
                delivered += 1
            else:
                staying.append(p)
        self.onboard = staying
        return delivered

    def _board(self, now: int) -> int:
        """Board waiting assignees at the current floor that match our direction.

        Returns the number delivered *in this same tick* — i.e. degenerate
        ``source == dest`` requests that are picked up and dropped off at once.
        """
        still_waiting: list[Passenger] = []
        delivered = 0
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
                    delivered += 1
                else:
                    self.onboard.append(p)
                    # Adopt the passenger's direction if we were idle.
                    if self.direction == Direction.IDLE:
                        self.direction = p.direction
            else:
                still_waiting.append(p)
        self.assigned = still_waiting
        return delivered

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
