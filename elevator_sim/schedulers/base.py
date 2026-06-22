"""Scheduler strategy interface and registry.

A scheduler decides *which* elevator a newly-arrived passenger is assigned to. It
does **not** move elevators — that is the elevator's job. Schedulers see only the
current state of the system (no look-ahead into future requests).
"""

from abc import ABC, abstractmethod

from elevator_sim.elevator import Elevator
from elevator_sim.models import Passenger


class Scheduler(ABC):
    """Base class for assignment strategies."""

    #: Human-friendly name used by the CLI / registry.
    name: str = "base"

    @abstractmethod
    def choose(
        self, passenger: Passenger, elevators: list[Elevator], now: int
    ) -> int | None:
        """Return the index of the elevator to assign ``passenger`` to.

        Return ``None`` if no elevator can currently accept the passenger (the
        simulation will retry on a later tick — this is how capacity back-pressure
        is handled without dropping anyone).
        """
        raise NotImplementedError

    @classmethod
    def from_config(cls, *, floors: int, num_elevators: int) -> "Scheduler":
        """Build a scheduler given the building's shape.

        The default ignores both dimensions; schedulers that need them (e.g.
        ``zone_based``) override this. Having one construction hook keeps callers
        from special-casing individual schedulers — see :func:`build`.
        """
        return cls()


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
_REGISTRY: dict[str, type[Scheduler]] = {}


def register(cls: type[Scheduler]) -> type[Scheduler]:
    """Class decorator that registers a scheduler under its ``name``."""
    _REGISTRY[cls.name] = cls
    return cls


def unregister(name: str) -> None:
    """Remove a scheduler from the registry (no-op if absent).

    Mainly useful for tests that register a throwaway scheduler and want to leave
    the global registry as they found it.
    """
    _REGISTRY.pop(name, None)


def available() -> list[str]:
    return sorted(_REGISTRY)


def _lookup(name: str) -> type[Scheduler]:
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"Unknown scheduler {name!r}. Available: {', '.join(available())}"
        ) from None


def create(name: str, **kwargs) -> Scheduler:
    """Instantiate a scheduler by name with explicit kwargs (low-level factory)."""
    return _lookup(name)(**kwargs)


def build(name: str, *, floors: int, num_elevators: int) -> Scheduler:
    """Instantiate a scheduler by name, supplying the building shape uniformly.

    Every caller that knows the building dimensions should use this instead of
    branching on the scheduler name: each scheduler's :meth:`Scheduler.from_config`
    decides for itself which dimensions it needs.
    """
    return _lookup(name).from_config(floors=floors, num_elevators=num_elevators)
