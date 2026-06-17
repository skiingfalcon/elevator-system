"""Scheduler strategy interface and registry.

A scheduler decides *which* elevator a newly-arrived passenger is assigned to. It
does **not** move elevators — that is the elevator's job. Schedulers see only the
current state of the system (no look-ahead into future requests).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Type

from elevator_sim.elevator import Elevator
from elevator_sim.models import Passenger


class Scheduler(ABC):
    """Base class for assignment strategies."""

    #: Human-friendly name used by the CLI / registry.
    name: str = "base"

    @abstractmethod
    def choose(
        self, passenger: Passenger, elevators: List[Elevator], now: int
    ) -> Optional[int]:
        """Return the index of the elevator to assign ``passenger`` to.

        Return ``None`` if no elevator can currently accept the passenger (the
        simulation will retry on a later tick — this is how capacity back-pressure
        is handled without dropping anyone).
        """
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
_REGISTRY: Dict[str, Type[Scheduler]] = {}


def register(cls: Type[Scheduler]) -> Type[Scheduler]:
    """Class decorator that registers a scheduler under its ``name``."""
    _REGISTRY[cls.name] = cls
    return cls


def available() -> List[str]:
    return sorted(_REGISTRY)


def create(name: str, **kwargs) -> Scheduler:
    """Instantiate a scheduler by name (factory used by the CLI)."""
    try:
        cls = _REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"Unknown scheduler {name!r}. Available: {', '.join(available())}"
        )
    return cls(**kwargs)
