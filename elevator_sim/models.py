"""Core data types for the elevator simulation.

A passenger submits a :class:`Request` (origin + destination known up front, as in
a Destination Dispatch system). Once the simulation picks the passenger up and drops
them off, the derived ``wait_time`` / ``travel_time`` / ``total_time`` become available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


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
    pickup_time: Optional[int] = None
    dropoff_time: Optional[int] = None
    # Bookkeeping for schedulers / dispatch.
    assigned_elevator: Optional[int] = field(default=None)

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
    def wait_time(self) -> Optional[int]:
        """Ticks between request and pickup."""
        if self.pickup_time is None:
            return None
        return self.pickup_time - self.request_time

    @property
    def travel_time(self) -> Optional[int]:
        """Ticks between pickup and dropoff."""
        if self.pickup_time is None or self.dropoff_time is None:
            return None
        return self.dropoff_time - self.pickup_time

    @property
    def total_time(self) -> Optional[int]:
        """wait_time + travel_time (i.e. request -> dropoff)."""
        if self.dropoff_time is None:
            return None
        return self.dropoff_time - self.request_time
