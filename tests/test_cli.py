"""Smoke tests for the CLI entry point (``main``)."""

import pytest

from elevator_sim.cli import main
from elevator_sim.schedulers.base import available, build


@pytest.mark.parametrize("scheduler", available())
def test_cli_runs_and_reports(tmp_path, capsys, scheduler):
    """Every scheduler runs end-to-end through the CLI and writes a positions log."""
    csv = tmp_path / "requests.csv"
    csv.write_text("time,id,source,dest\n0,a,1,51\n0,b,1,37\n10,c,20,1\n")
    log = tmp_path / "positions.log"

    rc = main(
        [
            "--input", str(csv),
            "--floors", "60",
            "--elevators", "3",
            "--capacity", "8",
            "--scheduler", scheduler,
            "--log-out", str(log),
        ]
    )

    assert rc == 0
    assert log.exists()
    out = capsys.readouterr().out
    assert "Passenger Summary Statistics" in out
    assert f"Scheduler: {scheduler}" in out


def test_cli_reports_unserveable_input_cleanly(tmp_path, capsys):
    """An out-of-range floor exits non-zero with a readable error, not a traceback."""
    csv = tmp_path / "bad.csv"
    csv.write_text("time,id,source,dest\n0,a,1,999\n")
    log = tmp_path / "positions.log"

    rc = main(["--input", str(csv), "--floors", "60", "--log-out", str(log)])

    assert rc == 2
    assert "out of range" in capsys.readouterr().err


def test_cli_empty_input_returns_one(tmp_path, capsys):
    csv = tmp_path / "empty.csv"
    csv.write_text("time,id,source,dest\n")
    rc = main(["--input", str(csv), "--log-out", str(tmp_path / "p.log")])
    assert rc == 1


def test_build_matches_direct_construction_for_zone_based():
    """``build`` supplies the building shape that zone_based needs."""
    sched = build("zone_based", floors=60, num_elevators=3)
    assert sched.floors == 60 and sched.num_elevators == 3
