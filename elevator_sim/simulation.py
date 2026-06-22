"""The discrete-time simulation engine.

Each tick (``now`` starting at 0):

1. **Release** requests whose ``time == now`` into the dispatch pool. The pool is
   the *only* thing the scheduler can see — the simulation never reveals a request
   before its time, enforcing the spec's "no peeking ahead" rule.
2. **Dispatch** every pending (unassigned) passenger via the scheduler. Passengers
   the scheduler cannot place yet (e.g. all cars full) stay pending and are retried
   next tick.
3. **Step** every elevator one floor, processing alight/board.
4. **Log** all elevator positions for this tick.

The loop runs until every passenger has been delivered, with a safety cap to avoid
infinite loops on pathological input.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from elevator_sim.elevator import Elevator
from elevator_sim.io_utils import PathLike, PositionLogWriter
from elevator_sim.models import Passenger, PassengerState, Request
from elevator_sim.schedulers.base import Scheduler


@dataclass
class SimulationConfig:
    floors: int
    num_elevators: int
    capacity: int
    start_floor: int = 1
    #: Optional per-elevator express floor sets. ``None`` entries are full-service.
    express_floors: Sequence[set[int] | None] | None = None
    #: Hard cap on ticks (safety net). ``None`` => derive from problem size.
    max_ticks: int | None = None

    def __post_init__(self) -> None:
        if self.num_elevators < 1:
            raise ValueError("num_elevators must be >= 1")
        if self.floors < 1:
            raise ValueError("floors must be >= 1")
        if self.capacity < 1:
            raise ValueError("capacity must be >= 1")
        if not 1 <= self.start_floor <= self.floors:
            raise ValueError(
                f"start_floor {self.start_floor} out of range "
                f"(building has floors 1..{self.floors})"
            )


@dataclass
class SimulationResult:
    passengers: list[Passenger]
    ticks_elapsed: int
    config: SimulationConfig
    position_history: list[list[int]] = field(default_factory=list)


class Simulation:
    def __init__(self, config: SimulationConfig, scheduler: Scheduler) -> None:
        self.config = config
        self.scheduler = scheduler
        self.elevators: list[Elevator] = self._build_elevators()

    def _build_elevators(self) -> list[Elevator]:
        express = self.config.express_floors or [None] * self.config.num_elevators
        elevators = []
        for i in range(self.config.num_elevators):
            served = express[i] if i < len(express) else None
            elevators.append(
                Elevator(
                    index=i,
                    capacity=self.config.capacity,
                    start_floor=self.config.start_floor,
                    served_floors=served,
                )
            )
        return elevators

    # ------------------------------------------------------------------ #
    def run(
        self,
        requests: Sequence[Request],
        log_path: PathLike | None = None,
    ) -> SimulationResult:
        """Run the simulation to completion.

        ``requests`` may be in any order; they are released strictly by ``time``.
        If ``log_path`` is given, per-tick positions are streamed to that file.

        Requests are validated up front (floor ranges, and that some car can serve
        each one) so impossible input fails fast with a clear error rather than
        silently running to the tick cap.
        """
        self._validate_requests(requests)

        # Group requests by release time without exposing the future to the scheduler.
        by_time: dict[int, list[Request]] = {}
        for r in requests:
            by_time.setdefault(r.time, []).append(r)

        all_passengers: list[Passenger] = []
        pending: list[Passenger] = []  # released, not yet assigned to a car
        total = len(requests)
        delivered = 0

        last_release = max(by_time) if by_time else 0
        cap = self.config.max_ticks or self._default_max_ticks(last_release)

        history: list[list[int]] = []
        log = (
            PositionLogWriter(log_path, self.config.num_elevators)
            if log_path is not None
            else None
        )

        now = 0
        try:
            while delivered < total and now <= cap:
                # 1. Release this tick's requests (chronological gate).
                for r in by_time.get(now, []):
                    p = Passenger.from_request(r)
                    pending.append(p)
                    all_passengers.append(p)

                # 2. Dispatch pending passengers.
                pending = self._dispatch(pending, now)

                # 3. Advance every elevator one floor.
                for e in self.elevators:
                    e.step(now)

                # 4. Count deliveries and log positions.
                delivered = sum(
                    1 for p in all_passengers if p.state is PassengerState.DELIVERED
                )
                floors = [e.floor for e in self.elevators]
                history.append(floors)
                if log is not None:
                    log.write(now, floors)

                now += 1
        finally:
            if log is not None:
                log.close()

        if delivered < total:
            undelivered = [p.id for p in all_passengers if not p.delivered]
            raise RuntimeError(
                f"Simulation hit tick cap ({cap}) with {len(undelivered)} "
                f"undelivered passengers: {undelivered[:10]}"
                + ("..." if len(undelivered) > 10 else "")
            )

        return SimulationResult(
            passengers=all_passengers,
            ticks_elapsed=now,
            config=self.config,
            position_history=history,
        )

    def _validate_requests(self, requests: Sequence[Request]) -> None:
        """Reject input that the building can never serve, before simulating.

        Catches two boundary conditions that would otherwise only surface as a
        confusing "hit tick cap" error many ticks later:

        * a ``source`` or ``dest`` outside the building's ``1..floors`` range, and
        * a request no car can serve because every car's express ``served_floors``
          excludes its ``source`` or ``dest``.
        """
        floors = self.config.floors
        for r in requests:
            for label, floor in (("source", r.source), ("dest", r.dest)):
                if not 1 <= floor <= floors:
                    raise ValueError(
                        f"Request {r.id!r} has {label} floor {floor} out of range "
                        f"(building has floors 1..{floors})"
                    )
            if not any(
                e.serves(r.source) and e.serves(r.dest) for e in self.elevators
            ):
                raise ValueError(
                    f"Request {r.id!r} ({r.source} -> {r.dest}) cannot be served by "
                    f"any elevator; check express (--express) floor coverage"
                )

    def _dispatch(self, pending: list[Passenger], now: int) -> list[Passenger]:
        """Assign as many pending passengers as possible; return those still waiting."""
        still_pending: list[Passenger] = []
        for p in pending:
            idx = self.scheduler.choose(p, self.elevators, now)
            if idx is None:
                still_pending.append(p)
                continue
            self.elevators[idx].assign(p)
        return still_pending

    def _default_max_ticks(self, last_release: int) -> int:
        """A generous safety cap: even a single car can clear all work within this."""
        # Worst case per passenger is roughly a full sweep of the building twice.
        return last_release + 8 * self.config.floors * max(1, len(self.elevators)) + 1000
