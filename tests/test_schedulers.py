"""Unit tests for scheduler strategies."""

import pytest

from elevator_sim.elevator import Elevator
from elevator_sim.models import Passenger
from elevator_sim.schedulers.base import available, create


def make_passenger(pid, source, dest, t=0):
    return Passenger(id=pid, source=source, dest=dest, request_time=t)


def test_registry_has_all_builtin_schedulers():
    assert set(available()) == {"round_robin", "nearest_car", "zone_based"}


def test_create_unknown_raises():
    with pytest.raises(ValueError):
        create("does_not_exist")


def test_returns_none_when_all_full():
    sched = create("nearest_car")
    elevators = [Elevator(index=0, capacity=1, start_floor=1)]
    elevators[0].assign(make_passenger("x", 1, 5))  # car now at capacity
    assert sched.choose(make_passenger("y", 1, 5), elevators, now=0) is None


def test_round_robin_spreads_across_cars():
    sched = create("round_robin")
    elevators = [Elevator(index=i, capacity=4, start_floor=1) for i in range(3)]
    picks = [
        sched.choose(make_passenger(f"p{i}", 1, 5), elevators, now=0) for i in range(3)
    ]
    assert sorted(picks) == [0, 1, 2]


def test_nearest_car_prefers_closer_idle_car():
    sched = create("nearest_car")
    elevators = [
        Elevator(index=0, capacity=4, start_floor=1),
        Elevator(index=1, capacity=4, start_floor=20),
    ]
    # Pickup at floor 19 should go to the car already near floor 20.
    assert sched.choose(make_passenger("p", 19, 25), elevators, now=0) == 1


def test_zone_based_assigns_to_owning_zone():
    sched = create("zone_based", floors=60, num_elevators=3)
    elevators = [Elevator(index=i, capacity=4, start_floor=1) for i in range(3)]
    # Floors 1-20 -> car 0, 21-40 -> car 1, 41-60 -> car 2.
    assert sched.choose(make_passenger("low", 5, 1), elevators, now=0) == 0
    assert sched.choose(make_passenger("mid", 30, 1), elevators, now=0) == 1
    assert sched.choose(make_passenger("high", 55, 1), elevators, now=0) == 2
