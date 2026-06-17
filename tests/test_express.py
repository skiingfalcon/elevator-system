"""Tests for express elevators: CLI parsing + end-to-end routing/delivery."""

import pytest

from elevator_sim.cli import parse_express
from elevator_sim.models import Request
from elevator_sim.schedulers.base import create
from elevator_sim.simulation import Simulation, SimulationConfig


# --------------------------------------------------------------------------- #
# CLI spec parsing
# --------------------------------------------------------------------------- #
def test_parse_express_none_when_unset():
    assert parse_express(None, 3) is None
    assert parse_express([], 3) is None


def test_parse_express_single_car():
    served = parse_express(["0:1,30,60"], 3)
    assert served == [{1, 30, 60}, None, None]


def test_parse_express_multiple_cars():
    served = parse_express(["0:1,30", "2:1,45"], 3)
    assert served == [{1, 30}, None, {1, 45}]


@pytest.mark.parametrize(
    "spec",
    [
        "nocolon",          # missing ':'
        "x:1,2",            # non-integer index
        "0:a,b",            # non-integer floors
        "0:",               # no floors listed
        "5:1,2",            # index out of range (only 3 cars)
        "-1:1,2",           # negative index
    ],
)
def test_parse_express_rejects_malformed(spec):
    with pytest.raises(ValueError):
        parse_express([spec], 3)


# --------------------------------------------------------------------------- #
# End-to-end: express cars only serve their floors, full-service cars cover rest
# --------------------------------------------------------------------------- #
def test_express_car_only_serves_its_floors():
    # Car 0 is express (floors 1, 60 only); cars 1-2 are full-service.
    cfg = SimulationConfig(
        floors=60,
        num_elevators=3,
        capacity=8,
        express_floors=[{1, 60}, None, None],
    )
    sim = Simulation(cfg, create("nearest_car"))

    reqs = [
        Request(time=0, id="express_ok", source=1, dest=60),   # only car 0 is ideal
        Request(time=0, id="mid", source=12, dest=37),         # car 0 cannot serve
    ]
    result = sim.run(reqs)

    assert all(p.delivered for p in result.passengers)
    by_id = {p.id: p for p in result.passengers}
    # The mid-floor passenger must NOT have been assigned to the express car.
    assert by_id["mid"].assigned_elevator != 0


def test_express_does_not_strand_passengers_full_service_fallback():
    # One express car + one full-service car. A flood of mixed requests must all
    # be delivered — express-incompatible ones fall to the full-service car.
    cfg = SimulationConfig(
        floors=40,
        num_elevators=2,
        capacity=4,
        express_floors=[{1, 20, 40}, None],
    )
    sim = Simulation(cfg, create("nearest_car"))
    reqs = [
        Request(time=i, id=f"p{i}", source=1 + (i % 39), dest=1 + ((i + 17) % 39))
        for i in range(30)
    ]
    result = sim.run(reqs)
    assert all(p.delivered for p in result.passengers)
