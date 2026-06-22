# Scheduler Comparison Results

Reproducible with `python scripts/generate_results.py`. All workloads are seeded. Times are in ticks (1 tick = 1 floor of travel).

## Provided sample (15 reqs)

_3 cars, 60 floors, capacity 8, 15 passengers._

| Scheduler | avg total | p95 total | max wait | avg wait | sim length | distance | delivered |
|-----------|----------:|----------:|---------:|---------:|-----------:|---------:|----------:|
| nearest_car | 77.7 | 118.0 | 81 | 41.9 | 146 | 321 | 15/15 |
| round_robin **(best)** | 73.1 | 110.3 | 61 | 37.4 | 133 | 370 | 15/15 |
| zone_based | 88.1 | 131.3 | 87 | 52.4 | 161 | 387 | 15/15 |

## Mixed traffic (200 reqs)

_4 cars, 60 floors, capacity 8, 200 passengers._

| Scheduler | avg total | p95 total | max wait | avg wait | sim length | distance | delivered |
|-----------|----------:|----------:|---------:|---------:|-----------:|---------:|----------:|
| nearest_car **(best)** | 134.9 | 236.0 | 241 | 114.7 | 551 | 1990 | 200/200 |
| round_robin | 146.8 | 256.1 | 265 | 126.6 | 583 | 2227 | 200/200 |
| zone_based | 144.9 | 253.2 | 277 | 124.7 | 563 | 2123 | 200/200 |

## Up-peak rush (150 reqs)

_4 cars, 60 floors, capacity 10, 150 passengers._

| Scheduler | avg total | p95 total | max wait | avg wait | sim length | distance | delivered |
|-----------|----------:|----------:|---------:|---------:|-----------:|---------:|----------:|
| nearest_car | 212.6 | 380.1 | 371 | 182.7 | 487 | 1725 | 150/150 |
| round_robin **(best)** | 210.5 | 386.6 | 375 | 180.7 | 466 | 1771 | 150/150 |
| zone_based | 226.7 | 409.0 | 389 | 196.8 | 498 | 1901 | 150/150 |

## Down-peak rush (150 reqs)

_4 cars, 60 floors, capacity 10, 150 passengers._

| Scheduler | avg total | p95 total | max wait | avg wait | sim length | distance | delivered |
|-----------|----------:|----------:|---------:|---------:|-----------:|---------:|----------:|
| nearest_car | 230.9 | 395.0 | 383 | 201.1 | 457 | 1636 | 150/150 |
| round_robin | 235.3 | 398.0 | 386 | 205.5 | 460 | 1656 | 150/150 |
| zone_based **(best)** | 217.3 | 384.0 | 372 | 187.4 | 446 | 1588 | 150/150 |

## Tall building (300 reqs)

_6 cars, 100 floors, capacity 12, 300 passengers._

| Scheduler | avg total | p95 total | max wait | avg wait | sim length | distance | delivered |
|-----------|----------:|----------:|---------:|---------:|-----------:|---------:|----------:|
| nearest_car **(best)** | 131.4 | 236.1 | 242 | 95.9 | 674 | 3807 | 300/300 |
| round_robin | 163.6 | 263.1 | 258 | 128.1 | 720 | 3982 | 300/300 |
| zone_based | 150.0 | 263.1 | 262 | 114.5 | 686 | 3797 | 300/300 |

## Headline — lowest avg total_time per scenario

| Scenario | Winner | avg total (ticks) |
|----------|--------|------------------:|
| Provided sample (15 reqs) | round_robin | 73.1 |
| Mixed traffic (200 reqs) | nearest_car | 134.9 |
| Up-peak rush (150 reqs) | round_robin | 210.5 |
| Down-peak rush (150 reqs) | zone_based | 217.3 |
| Tall building (300 reqs) | nearest_car | 131.4 |
