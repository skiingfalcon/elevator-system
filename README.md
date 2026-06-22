# Elevator System Simulation

A discrete-time simulation of a modern **Destination Dispatch** elevator system.
Passengers submit their origin *and* destination at request time; a pluggable
scheduler immediately assigns each passenger to an elevator; the simulation ticks
forward one floor of travel at a time and reports per-passenger timing statistics.

This implements the take-home spec in [`Take_home_Elevator.md`](Take_home_Elevator.md).

---

## How to run

The core simulation depends only on the Python standard library (Python 3.9+).
Dependencies are managed with [uv](https://docs.astral.sh/uv/). The only
non-stdlib packages are optional extras: `matplotlib` (for `--plot`, in the
`plot` extra) and `pytest` (for the test suite, in the `dev` group).

```bash
# create the environment and install the optional plot extra
uv sync --extra plot

# run on the provided sample, using the default nearest-car scheduler
uv run elevator-sim \
    --floors 60 --elevators 3 --capacity 8 \
    --scheduler nearest_car \
    --input data/sample_requests.csv \
    --log-out positions.log
```

`uv run elevator-sim ...` and `uv run python -m elevator_sim ...` are
equivalent. Drop `--extra plot` if you don't need charts; the core simulation
needs no third-party packages at all.

### CLI options

| Flag | Default | Description |
|------|---------|-------------|
| `--input` | *(required)* | Requests CSV: `time,id,source,dest` (header optional) |
| `--floors` | `10` | Number of floors |
| `--elevators` | `3` | Number of elevator cars (1–10) |
| `--capacity` | `8` | Max passengers per car |
| `--start-floor` | `1` | Floor every car starts on |
| `--scheduler` | `nearest_car` | `nearest_car`, `round_robin`, or `zone_based` |
| `--express` | none | Make a car express: `IDX:F1,F2,...` (repeatable), e.g. `0:1,30,60` |
| `--log-out` | `positions.log` | Per-tick elevator positions log |
| `--plot` | off | Render wait/total-time histograms + movement chart (needs matplotlib) |
| `--plot-prefix` | none | Filename prefix for generated charts |

### Outputs

1. **Elevator positions log** (`--log-out`): one row per tick,
   `tick,elevator_0,elevator_1,...` giving every car's floor at that time.
2. **Passenger summary statistics** (stdout): min / max / average / median / p95
   of `wait_time`, `travel_time`, and `total_time`, plus notable observations
   (longest single wait, 95th-percentile tail latency, busiest pickup floor,
   throughput, and floors traveled per car).
3. **Charts** (with `--plot`): time-distribution histograms and an
   elevator-position-over-time line chart.

### Run the tests

```bash
uv run pytest
```

### Reproduce the scheduler comparison

```bash
python scripts/generate_results.py   # writes results/ (CSV, JSON, Markdown tables)
```

See [Scheduler comparison](#scheduler-comparison-fairness-vs-efficiency) below for
the findings, or [`results/`](results/) for the generated stats and charts.

---

## Model

Time is discrete: **one tick = one floor of travel** (up or down). Each tick the
engine, in order:

1. **Releases** the requests whose `time == now`. The scheduler only ever sees
   requests at or before the current tick — the simulation never peeks ahead.
2. **Dispatches** every unassigned passenger through the scheduler. A passenger the
   scheduler can't place yet (every car full) stays queued and is retried next
   tick — this is how capacity back-pressure is handled without dropping anyone.
3. **Advances** every car one floor and processes drop-offs then pick-ups.
4. **Logs** all car positions.

The loop ends when every passenger has been delivered.

### Components

| File | Responsibility |
|------|----------------|
| `elevator_sim/models.py` | `Passenger`, `Request`, `Direction`; derived wait/travel/total times |
| `elevator_sim/elevator.py` | The car — owns the hard constraints (one floor/tick, capacity, SCAN direction logic, express floors) |
| `elevator_sim/schedulers/` | Pluggable assignment strategies + a name→class registry |
| `elevator_sim/simulation.py` | The discrete-time tick loop |
| `elevator_sim/stats.py` | Summary statistics + report formatting |
| `elevator_sim/io_utils.py` | CSV parsing + positions-log writing |
| `elevator_sim/viz.py` | Optional matplotlib charts |
| `elevator_sim/cli.py` | Argument parsing / entry point |

### Schedulers

- **`nearest_car`** (default) — assigns each passenger to the car with the lowest
  estimated time-to-pickup. The estimate models the car's committed SCAN run (a
  car heading away must finish its sweep before doubling back), adds a congestion
  term per outstanding stop so load spreads across the bank, and subtracts an
  **aging bonus** that grows with how long the passenger has already waited.
- **`round_robin`** — cycles through cars regardless of position. Simple and
  spreads load evenly, but ignores distance/direction.
- **`zone_based`** — partitions floors into contiguous zones, one per car;
  passengers go to the car owning their origin's zone (with a nearest-car fallback
  when that car is full). Predictable service, good for tall buildings.

---

## How elevator constraints are guaranteed

- **Serve all requests eventually** — every scheduler always returns *some* car
  when one has spare capacity, and `nearest_car`'s aging bonus keeps lowering a
  waiting passenger's cost so they can't be starved. The randomized stress test
  (`tests/test_simulation.py::test_no_starvation_on_stress`) asserts every
  passenger is delivered.
- **Capacity** — enforced inside `Elevator`: assignments and boardings are refused
  past `capacity`; refused passengers stay queued. Asserted tick-by-tick in
  `test_capacity_never_exceeded_during_run`.
- **Direction logic** — the car uses a SCAN ("elevator algorithm") sweep: it
  commits to a direction, serves every stop that way in floor order, then reverses.
  A passenger may board only when their travel direction matches the car's.

---

## Scheduler comparison (fairness vs. efficiency)

On a 200-passenger randomized workload (60 floors, 4 cars, capacity 8, seed 42),
reproducible with `python bench.py`:

| Scheduler | avg `total_time` | max `wait_time` | sim length |
|-----------|-----------------:|----------------:|-----------:|
| `nearest_car` | **134.9** | **241** | 551 |
| `round_robin` | 146.8 | 265 | 583 |
| `zone_based`  | 144.9 | 277 | 563 |

`nearest_car` wins on realistic mixed traffic (~8% lower average total time and
the lowest worst-case wait). On *small, highly-clustered* inputs (e.g. the 15-row
sample where most traffic is floor 1 going up), blind `round_robin` spreading can
occasionally edge it out — the efficiency gain from bundling same-direction riders
only pays off at scale. All three deliver every passenger; the trade-off is in
average and tail latency, not completeness.

Regenerate the table (or sweep different parameters) with:

```bash
python bench.py                       # defaults match the table above
python bench.py --passengers 500 --elevators 6 --seed 7
```

### No universal winner (broader sweep)

A wider sweep across five traffic patterns confirms the trade-off is real — the
best scheduler depends on the traffic shape, not on one being strictly superior:

| Traffic pattern | Best scheduler | Why |
|-----------------|----------------|-----|
| Mixed (200) / tall building (300) | `nearest_car` | distance/direction awareness wins, and the edge grows with building height (~8% → ~20%) |
| Up-peak burst / 15-row sample | `round_robin` | everyone clusters at the lobby going up, so "nearest" barely differentiates and the system is throughput-bound |
| Down-peak | `zone_based` | contiguous zones naturally match "upper floors → lobby" flow |

The full per-scenario stats (CSV, JSON, slide-ready Markdown tables, and charts)
live in [`results/`](results/) and are reproducible with:

```bash
python scripts/generate_results.py                    # data -> results/*.{csv,json,md}
uv run --extra plot python scripts/plot_comparison.py  # charts -> results/*.png
```

---

## Bonus features implemented

- **Multiple algorithms**: nearest-car, round-robin, zone-based (selectable via
  `--scheduler`, registered through a pluggable interface — adding a fourth is a
  single new file).
- **Express elevators**: an `Elevator` can be given a `served_floors` set; the
  scheduler then only routes compatible passengers to it. Exposed on the CLI via
  `--express IDX:F1,F2,...` (repeatable), e.g.
  `--express 0:1,30,60` makes car 0 an express serving only floors 1, 30, and 60
  while the other cars stay full-service.
- **Fairness vs. efficiency** comparison (table above).
- **Visualizations** (`--plot`).

---

## Time spent

Roughly **4–5 hours**: ~1h reading the spec and designing the module layout, ~2h
on the core engine and schedulers, ~1h on the test suite, and ~1h tuning the
nearest-car cost function (the first version naively used current-floor distance
and piled passengers onto a single committed car, producing pathological waits —
switching to an ETA-along-the-SCAN-run estimate fixed it) plus the README.

## Assumptions, simplifications, and trade-offs

- **Boarding/alighting is instantaneous** — no dwell time at a stop; a tick is
  purely one floor of travel. Real systems add door-open time.
- **Assignment is permanent** — once a passenger is assigned to a car, they're not
  reassigned even if a better car frees up later. Real destination-dispatch systems
  re-optimize; this keeps the model simple and the guarantees easy to reason about.
- **A degenerate `source == dest` request** is picked up and dropped off in the
  same tick (wait = total = 0).
- **Input is validated up front, not silently tolerated.** A `source`/`dest`
  outside `1..floors`, a `start_floor` outside the building, or an express
  configuration where no car can serve a request all raise a clear `ValueError`
  before the simulation runs — rather than running to the safety tick-cap and
  failing with a confusing "undelivered passengers" error. Passenger IDs are
  assumed unique but not enforced (duplicates simulate as independent riders).
- **`zone_based` assumes contiguous equal zones**; uneven demand across zones isn't
  rebalanced beyond the nearest-car fallback when a zone's car is full.
- **The ETA cost is an estimate**, not an exact future-state simulation — it doesn't
  account for pick-ups that will be inserted into a car's plan after assignment.

## What I'd improve with more time

- **Dynamic reassignment** — let the scheduler re-home a waiting passenger when a
  closer car becomes free, to cut the tail latency.
- **Look-ahead / batching** within a tick — when several requests arrive together,
  solve the assignment jointly (e.g. Hungarian algorithm) instead of greedily.
- **Dwell time and acceleration** for a more realistic physical model.
- **Expose zone boundaries on the CLI** (express elevators are now configurable
  via `--express`), plus per-elevator configuration files.
- **Richer metrics** — distance per car and p95 latency are now reported; energy
  modeling and live load balancing under sustained traffic are still open.
