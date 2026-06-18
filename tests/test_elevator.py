"""Unit tests for the Elevator car: movement, capacity, direction, express."""

from elevator_sim.elevator import Elevator
from elevator_sim.models import Direction, Passenger, PassengerState


def make_passenger(pid, source, dest, t=0):
    return Passenger(id=pid, source=source, dest=dest, request_time=t)


def test_moves_one_floor_per_tick():
    e = Elevator(index=0, capacity=4, start_floor=1)
    e.assign(make_passenger("a", 1, 5))
    floors = []
    for now in range(10):
        e.step(now)
        floors.append(e.floor)
    # Picks up at 1, then climbs one floor per tick: 1,2,3,4,5...
    diffs = [abs(floors[i] - floors[i - 1]) for i in range(1, len(floors))]
    assert all(d <= 1 for d in diffs), floors


def test_capacity_never_exceeded():
    e = Elevator(index=0, capacity=2, start_floor=1)
    for i in range(2):
        e.assign(make_passenger(f"p{i}", 1, 10))
    # A third assignment must be refused.
    assert not e.can_accept(make_passenger("p2", 1, 10))


def test_capacity_respected_during_boarding():
    e = Elevator(index=0, capacity=2, start_floor=1)
    e.assign(make_passenger("a", 1, 10))
    e.assign(make_passenger("b", 1, 10))
    e.step(0)  # board both at floor 1
    assert e.load == 2


def test_passenger_delivered_to_destination():
    e = Elevator(index=0, capacity=4, start_floor=1)
    p = make_passenger("a", 1, 4)
    e.assign(p)
    for now in range(20):
        e.step(now)
        if p.delivered:
            break
    assert p.delivered
    assert p.pickup_time is not None
    assert p.dropoff_time is not None
    assert p.dropoff_time > p.pickup_time


def test_passenger_state_progresses_waiting_to_delivered():
    e = Elevator(index=0, capacity=4, start_floor=1)
    p = make_passenger("a", 1, 4)

    # Before assignment.
    assert p.state is PassengerState.WAITING

    e.assign(p)
    assert p.state is PassengerState.ASSIGNED

    seen_onboard = False
    for now in range(20):
        e.step(now)
        if p.state is PassengerState.ONBOARD:
            seen_onboard = True
        if p.state is PassengerState.DELIVERED:
            break

    assert seen_onboard, "passenger should pass through ONBOARD before delivery"
    assert p.state is PassengerState.DELIVERED
    # State stays consistent with the boolean shortcuts.
    assert p.delivered and p.picked_up


def test_direction_logic_no_reverse_with_stops_ahead():
    e = Elevator(index=0, capacity=4, start_floor=5)
    # Two riders both going up from above the start floor.
    e.assign(make_passenger("a", 6, 10))
    e.assign(make_passenger("b", 7, 12))
    seen_down_while_targets_above = False
    for now in range(30):
        e.step(now)
        targets = e.target_floors()
        if e.direction == Direction.DOWN and any(t > e.floor for t in targets):
            seen_down_while_targets_above = True
    assert not seen_down_while_targets_above


def test_same_floor_request_handled_in_one_tick():
    e = Elevator(index=0, capacity=4, start_floor=3)
    p = make_passenger("a", 3, 3)
    e.assign(p)
    e.step(0)
    assert p.delivered
    assert p.wait_time == 0
    assert p.total_time == 0


def test_express_elevator_rejects_unserved_floors():
    e = Elevator(index=0, capacity=4, start_floor=1, served_floors={1, 30, 60})
    assert e.can_accept(make_passenger("ok", 1, 30))
    assert not e.can_accept(make_passenger("bad_src", 5, 30))
    assert not e.can_accept(make_passenger("bad_dst", 1, 45))
