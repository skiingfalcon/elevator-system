"""Unit tests for summary statistics: percentiles and per-car distance."""

from elevator_sim.models import Passenger
from elevator_sim.stats import MetricStats, _distance_per_car, summarize


def delivered_passenger(pid, wait, travel):
    """A passenger with the given wait/travel times already realized."""
    p = Passenger(id=pid, source=1, dest=10, request_time=0)
    p.pickup_time = wait
    p.dropoff_time = wait + travel
    return p


def test_percentile_matches_known_values():
    m = MetricStats.of([0, 10, 20, 30, 40])
    assert m.minimum == 0
    assert m.maximum == 40
    assert m.median == 20
    # Linear-interpolated p95 over [0..40]: rank = 0.95 * 4 = 3.8 -> 30 + 0.8*10.
    assert m.p95 == 38.0


def test_percentile_single_value():
    m = MetricStats.of([7])
    assert m.p95 == 7.0


def test_empty_metrics_are_zero():
    m = MetricStats.of([])
    assert (m.minimum, m.maximum, m.average, m.median, m.p95) == (0, 0, 0, 0, 0)


def test_distance_per_car_sums_absolute_moves():
    # Two cars over 3 ticks. Car 0: 1->3->2 (2 + 1 = 3). Car 1: 5->5->8 (0 + 3 = 3).
    history = [[1, 5], [3, 5], [2, 8]]
    assert _distance_per_car(history) == [3, 3]


def test_distance_per_car_empty_history():
    assert _distance_per_car([]) == []


def test_summarize_includes_distance_when_history_given():
    passengers = [delivered_passenger("a", 2, 8), delivered_passenger("b", 4, 6)]
    history = [[1], [2], [4]]  # one car moving 1 then 2 floors
    summary = summarize(passengers, ticks_elapsed=3, position_history=history)
    assert summary.distance_per_car == [3]
    assert summary.total.p95 > 0


def test_summarize_without_history_has_empty_distance():
    passengers = [delivered_passenger("a", 2, 8)]
    summary = summarize(passengers, ticks_elapsed=10)
    assert summary.distance_per_car == []
