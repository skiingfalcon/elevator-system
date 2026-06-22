"""Input/output helpers: parse the request CSV, write the positions log.

The request format (from the spec) is::

    time,id,source,dest
    0,passenger1,1,51
    0,passenger2,1,37
    10,passenger3,20,1

A header row is optional and auto-detected.
"""

import csv
from collections.abc import Iterable
from pathlib import Path
from typing import TextIO

from elevator_sim.models import Request

PathLike = str | Path


def _looks_like_header(row: list[str]) -> bool:
    return row[:1] == ["time"] or (len(row) >= 1 and not row[0].lstrip("-").isdigit())


def parse_requests(source: PathLike | Iterable[str]) -> list[Request]:
    """Parse requests from a CSV file path or an iterable of lines.

    Returns requests sorted by time (stable), so the simulation can release them
    in chronological order. Blank lines and an optional header are skipped.
    """
    if isinstance(source, (str, Path)):
        with open(source, newline="") as fh:
            rows = list(csv.reader(fh))
    else:
        rows = list(csv.reader(source))

    requests: list[Request] = []
    for i, row in enumerate(rows):
        if not row or all(not c.strip() for c in row):
            continue
        if i == 0 and _looks_like_header(row):
            continue
        if len(row) < 4:
            raise ValueError(f"Malformed request row {i}: {row!r}")
        time, rid, src, dest = (c.strip() for c in row[:4])
        requests.append(
            Request(time=int(time), id=rid, source=int(src), dest=int(dest))
        )

    requests.sort(key=lambda r: r.time)
    return requests


class PositionLogWriter:
    """Writes one row per tick: ``tick, e0_floor, e1_floor, ...``.

    Usable as a context manager so the file is always closed cleanly.
    """

    def __init__(self, path: PathLike, num_elevators: int) -> None:
        self.path = Path(path)
        self.num_elevators = num_elevators
        self._fh: TextIO = open(self.path, "w", newline="")
        self._writer = csv.writer(self._fh)
        header = ["tick"] + [f"elevator_{i}" for i in range(num_elevators)]
        self._writer.writerow(header)

    def write(self, tick: int, floors: list[int]) -> None:
        self._writer.writerow([tick, *floors])

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    def __enter__(self) -> "PositionLogWriter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
