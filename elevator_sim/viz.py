"""Optional matplotlib visualizations.

Kept import-light: matplotlib is only imported when a plotting function is actually
called, so the core simulation runs in a stdlib-only environment.
"""

from elevator_sim.models import Passenger
from elevator_sim.simulation import SimulationResult


def _require_matplotlib():
    try:
        import matplotlib

        matplotlib.use("Agg")  # headless-safe backend
        import matplotlib.pyplot as plt

        return plt
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "matplotlib is required for plotting. Install it with "
            "`uv sync --extra plot` (or `pip install matplotlib`)."
        ) from exc


def plot_time_distributions(
    passengers: list[Passenger], out_path: str = "time_distributions.png"
) -> str:
    """Histogram of wait and total times across delivered passengers."""
    plt = _require_matplotlib()
    delivered = [p for p in passengers if p.delivered]
    waits = [p.wait_time for p in delivered]
    totals = [p.total_time for p in delivered]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].hist(waits, bins="auto", color="#4C72B0", edgecolor="white")
    axes[0].set_title("Wait time distribution")
    axes[0].set_xlabel("wait_time (ticks)")
    axes[0].set_ylabel("passengers")

    axes[1].hist(totals, bins="auto", color="#55A868", edgecolor="white")
    axes[1].set_title("Total time distribution")
    axes[1].set_xlabel("total_time (ticks)")
    axes[1].set_ylabel("passengers")

    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def plot_elevator_movement(
    result: SimulationResult, out_path: str = "elevator_movement.png"
) -> str:
    """Line chart of every elevator's floor over time."""
    plt = _require_matplotlib()
    history = result.position_history
    if not history:
        raise RuntimeError("No position history to plot.")

    ticks = list(range(len(history)))
    n = result.config.num_elevators

    fig, ax = plt.subplots(figsize=(11, 5))
    for i in range(n):
        floors = [row[i] for row in history]
        ax.plot(ticks, floors, label=f"elevator {i}", linewidth=1.3)
    ax.set_title("Elevator positions over time")
    ax.set_xlabel("tick")
    ax.set_ylabel("floor")
    ax.legend(loc="upper right", ncol=min(n, 5), fontsize="small")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def plot_all(
    result: SimulationResult, prefix: str | None = None
) -> list[str]:
    """Render both charts; returns the written file paths."""
    p = f"{prefix}_" if prefix else ""
    return [
        plot_time_distributions(result.passengers, f"{p}time_distributions.png"),
        plot_elevator_movement(result, f"{p}elevator_movement.png"),
    ]
