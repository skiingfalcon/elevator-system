"""Pluggable scheduler strategies.

Importing this package registers all built-in schedulers. Use
:func:`elevator_sim.schedulers.base.create` to instantiate one by name.
"""

from elevator_sim.schedulers.base import (
    Scheduler,
    available,
    create,
    register,
)

# Import side effects register each scheduler in the registry.
from elevator_sim.schedulers.nearest_car import NearestCarScheduler
from elevator_sim.schedulers.round_robin import RoundRobinScheduler
from elevator_sim.schedulers.zone_based import ZoneBasedScheduler

__all__ = [
    "Scheduler",
    "available",
    "create",
    "register",
    "NearestCarScheduler",
    "RoundRobinScheduler",
    "ZoneBasedScheduler",
]
