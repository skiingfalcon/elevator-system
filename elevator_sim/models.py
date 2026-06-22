"""Core data types for the elevator simulation.

A passenger submits a :class:`Request` (origin + destination known up front, as in
a Destination Dispatch system). Once the simulation picks the passenger up and drops
them off, the derived ``wait_time`` / ``travel_time`` / ``total_time`` become available.
"""

from dataclasses import dataclass, field
from enum import Enum


class Direction(Enum):
    """Direction of travel. ``IDLE`` means no committed direction."""

    UP = 1
    DOWN = -1
    IDLE = 0

    @staticmethod
    def between(origin: int, dest: int) -> "Direction":
        """The direction needed to travel from ``origin`` to ``dest``."""
        if dest > origin:
            return Direction.UP
        if dest < origin:
            return Direction.DOWN
        return Direction.IDLE


class PassengerState(Enum):
    """A passenger's position in the service lifecycle.

    The progression is strictly forward::

        WAITING -> ASSIGNED -> ONBOARD -> DELIVERED

    * ``WAITING``   — request released, not yet assigned to a car.
    * ``ASSIGNED``  — a car has accepted the passenger but they have not boarded.
    * ``ONBOARD``   — picked up, riding, not yet dropped off.
    * ``DELIVERED`` — dropped off at the destination.

    The state is *derived* from the passenger's timestamps and assignment (see
    :attr:`Passenger.state`) so it can never drift out of sync with them.
    """

    WAITING = "waiting"
    ASSIGNED = "assigned"
    ONBOARD = "onboard"
    DELIVERED = "delivered"


@dataclass(frozen=True)
class Request:
    """A single elevator request, exactly as it appears in the input file.

    Fields mirror the spec's ``time,id,source,dest`` columns.
    """

    time: int
    id: str
    source: int
    dest: int

    @property
    def direction(self) -> Direction:
        return Direction.between(self.source, self.dest)


@dataclass
class Passenger:
    """A request that is being (or has been) served by the simulation.

    ``request_time`` is when the request entered the system. ``pickup_time`` and
    ``dropoff_time`` are filled in by the simulation as the passenger is served.
    """

    id: str
    source: int
    dest: int
    request_time: int
    pickup_time: int | None = None
    dropoff_time: int | None = None
    # Bookkeeping for schedulers / dispatch.
    assigned_elevator: int | None = field(default=None)

    @classmethod
    def from_request(cls, req: Request) -> "Passenger":
        return cls(
            id=req.id,
            source=req.source,
            dest=req.dest,
            request_time=req.time,
        )

    @property
    def direction(self) -> Direction:
        return Direction.between(self.source, self.dest)

    @property
    def picked_up(self) -> bool:
        return self.pickup_time is not None

    @property
    def delivered(self) -> bool:
        return self.dropoff_time is not None

    @property
    def state(self) -> PassengerState:
        """Current lifecycle state, derived from timestamps and assignment.

        Single source of truth: the underlying timestamps drive the state, so it
        cannot disagree with :attr:`picked_up` / :attr:`delivered`.
        """
        if self.dropoff_time is not None:
            return PassengerState.DELIVERED
        if self.pickup_time is not None:
            return PassengerState.ONBOARD
        if self.assigned_elevator is not None:
            return PassengerState.ASSIGNED
        return PassengerState.WAITING

    @property
    def wait_time(self) -> int | None:
        """Ticks between request and pickup."""
        if self.pickup_time is None:
            return None
        return self.pickup_time - self.request_time

    @property
    def travel_time(self) -> int | None:
        """Ticks between pickup and dropoff."""
        if self.pickup_time is None or self.dropoff_time is None:
            return None
        return self.dropoff_time - self.pickup_time

    @property
    def total_time(self) -> int | None:
        """wait_time + travel_time (i.e. request -> dropoff)."""
        if self.dropoff_time is None:
            return None
        return self.dropoff_time - self.request_time
