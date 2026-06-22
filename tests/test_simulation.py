"""End-to-end simulation tests: completeness, no-look-ahead, log shape, constraints."""

import random

import pytest

from elevator_sim.io_utils import parse_requests
from elevator_sim.models import Request
from elevator_sim.schedulers.base import (
    Scheduler,
    available,
    build,
    create,
    register,
    unregister,
)
from elevator_sim.simulation import Simulation, SimulationConfig

SPEC_EXAMPLE = [
    Request(time=0, id="passenger1", source=1, dest=51),
    Request(time=0, id="passenger2", source=1, dest=37),
    Request(time=10, id="passenger3", source=20, dest=1),
]


def make_sim(scheduler_name="nearest_car", floors=60, elevators=3, capacity=8):
    cfg = SimulationConfig(floors=floors, num_elevators=elevators, capacity=capacity)
    sched = build(scheduler_name, floors=floors, num_elevators=elevators)
    return Simulation(cfg, sched)


@pytest.mark.parametrize("name", available())
def test_all_passengers_delivered(name):
    sim = make_sim(name)
    result = sim.run(SPEC_EXAMPLE)
    assert all(p.delivered for p in result.passengers)
    assert len(result.passengers) == 3


@pytest.mark.parametrize("name", available())
def test_no_starvation_on_stress(name):
    """A randomized workload: everyone must eventually be served."""
    rng = random.Random(7)
    reqs = []
    t = 0
    for i in range(120):
        t += rng.randint(0, 2)
        src = rng.randint(1, 40)
        dst = rng.randint(1, 40)
        while dst == src:
            dst = rng.randint(1, 40)
        reqs.append(Request(time=t, id=f"p{i}", source=src, dest=dst))
    result = make_sim(name, floors=40, elevators=4, capacity=6).run(reqs)
    assert all(p.delivered for p in result.passengers)


def test_no_look_ahead():
    """The scheduler must never see a request before its release time."""
    seen_times = []

    @register
    class SpyScheduler(Scheduler):
        name = "spy"

        def choose(self, passenger, elevators, now):
            # Record (now, request_time): request_time must never exceed now.
            seen_times.append((now, passenger.request_time))
            return 0  # always assign to car 0

    reqs = [
        Request(time=0, id="a", source=1, dest=10),
        Request(time=5, id="b", source=1, dest=10),
        Request(time=20, id="c", source=10, dest=1),
    ]
    try:
        sim = make_sim("spy", floors=10, elevators=1, capacity=10)
        sim.run(reqs)
    finally:
        # Leave the global registry as we found it.
        unregister("spy")
    assert seen_times, "scheduler was never consulted"
    assert all(req_time <= now for now, req_time in seen_times)


def test_capacity_never_exceeded_during_run():
    """Drive the sim tick-by-tick and assert no car ever exceeds capacity."""
    rng = random.Random(3)
    reqs = [
        Request(time=rng.randint(0, 10), id=f"p{i}", source=1, dest=rng.randint(2, 20))
        for i in range(30)
    ]
    cfg = SimulationConfig(floors=20, num_elevators=2, capacity=3)
    sim = Simulation(cfg, create("nearest_car"))

    # Wrap each elevator's step() so we can assert the invariant after every tick.
    for e in sim.elevators:
        original = e.step

        def checked_step(now, _e=e, _orig=original):
            delivered = _orig(now)
            assert _e.load <= _e.capacity, f"capacity exceeded: {_e}"
            return delivered

        e.step = checked_step

    sim.run(reqs)


def test_positions_log_shape(tmp_path):
    log = tmp_path / "positions.log"
    sim = make_sim("nearest_car", floors=60, elevators=3)
    result = sim.run(SPEC_EXAMPLE, log_path=str(log))

    lines = log.read_text().strip().splitlines()
    header = lines[0].split(",")
    assert header == ["tick", "elevator_0", "elevator_1", "elevator_2"]
    # One data row per tick.
    assert len(lines) - 1 == result.ticks_elapsed
    # Each row: tick + one floor per elevator.
    for i, row in enumerate(lines[1:]):
        cols = row.split(",")
        assert len(cols) == 4
        assert int(cols[0]) == i


def test_parse_requests_roundtrip(tmp_path):
    csv = tmp_path / "r.csv"
    csv.write_text("time,id,source,dest\n0,a,1,5\n3,b,5,1\n")
    reqs = parse_requests(str(csv))
    assert len(reqs) == 2
    assert reqs[0].id == "a" and reqs[0].source == 1 and reqs[0].dest == 5
    assert reqs[1].time == 3


def test_parse_requests_sorts_by_time(tmp_path):
    csv = tmp_path / "r.csv"
    csv.write_text("10,late,1,5\n0,early,5,1\n")  # no header, out of order
    reqs = parse_requests(str(csv))
    assert [r.id for r in reqs] == ["early", "late"]


# --------------------------------------------------------------------------- #
# Boundary-condition validation
# --------------------------------------------------------------------------- #
def test_bad_start_floor_rejected():
    with pytest.raises(ValueError, match="start_floor"):
        SimulationConfig(floors=10, num_elevators=2, capacity=4, start_floor=11)
    with pytest.raises(ValueError, match="start_floor"):
        SimulationConfig(floors=10, num_elevators=2, capacity=4, start_floor=0)


@pytest.mark.parametrize(
    "source,dest",
    [
        (0, 5),    # source below 1
        (1, 11),   # dest above floors
        (-3, 5),   # negative source
        (5, 0),    # dest below 1
    ],
)
def test_out_of_range_floors_rejected(source, dest):
    sim = make_sim("nearest_car", floors=10, elevators=2, capacity=4)
    reqs = [Request(time=0, id="oops", source=source, dest=dest)]
    with pytest.raises(ValueError, match="out of range"):
        sim.run(reqs)


def test_in_range_floors_accepted():
    """A request touching the exact boundaries (1 and floors) is fine."""
    sim = make_sim("nearest_car", floors=10, elevators=2, capacity=4)
    result = sim.run([Request(time=0, id="edge", source=1, dest=10)])
    assert all(p.delivered for p in result.passengers)


def test_unserveable_express_passenger_rejected():
    """No car covers floor 25, so this request can never be served -> fail fast."""
    cfg = SimulationConfig(
        floors=60,
        num_elevators=2,
        capacity=4,
        express_floors=[{1, 30, 60}, {1, 30, 60}],
    )
    sim = Simulation(cfg, create("nearest_car"))
    reqs = [Request(time=0, id="stranded", source=1, dest=25)]
    with pytest.raises(ValueError, match="cannot be served"):
        sim.run(reqs)
