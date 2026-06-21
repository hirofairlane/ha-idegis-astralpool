"""PNG chart generation for the weekly email report.

Matplotlib in Agg mode (no display). Each function returns a
base64-encoded PNG so the reporter can embed it inline with
`<img src="data:image/png;base64,...">`. That way the email survives
strict mail clients that strip remote images.

Three charts in v0.3.1:

- `runtime_7d`: vertical bar chart of pump runtime minutes per day for
  the last 7 days. Highlights gaps and oversized days.
- `health_7d`: line chart of the daily health score across 7 days.
- `vitals_24h`: 3-panel line chart of pH / salt / temperature for the
  last 24 h (taken from the in-memory ring buffer).
"""
from __future__ import annotations

import base64
import io
from datetime import datetime, timedelta

import matplotlib

matplotlib.use("Agg")  # no display, no Tk
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

_COMIC = {
    "facecolor": "#fff5d6",
    "axes.facecolor": "#ffffff",
    "edgecolor": "#1f1d1a",
    "ink": "#1f1d1a",
    "accent": "#ff6f3c",
    "ok": "#4caf50",
    "warn": "#ffb300",
    "danger": "#e53935",
}


def _new_fig(width: float = 6.4, height: float = 2.6) -> tuple[Figure, plt.Axes]:
    fig = Figure(figsize=(width, height), dpi=120)
    fig.patch.set_facecolor(_COMIC["facecolor"])
    ax = fig.add_subplot(111)
    ax.set_facecolor(_COMIC["axes.facecolor"])
    for spine in ax.spines.values():
        spine.set_color(_COMIC["edgecolor"])
        spine.set_linewidth(1.8)
    ax.tick_params(colors=_COMIC["ink"], labelsize=9)
    return fig, ax


def _png_b64(fig: Figure) -> str:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _last_n_days(history: dict[str, float], n: int = 7) -> list[tuple[str, float]]:
    today = datetime.now().date()
    out: list[tuple[str, float]] = []
    for i in range(n - 1, -1, -1):
        day = (today - timedelta(days=i)).isoformat()
        out.append((day, float(history.get(day, 0) or 0)))
    return out


def runtime_7d(runtime_history: dict[str, float]) -> str:
    """Bar chart of pump runtime minutes per day, last 7 days."""
    days = _last_n_days(runtime_history, n=7)
    labels = [d.split("-")[-1] for d, _ in days]  # show DD
    values = [v for _, v in days]
    fig, ax = _new_fig()
    bars = ax.bar(
        labels,
        values,
        color=_COMIC["accent"],
        edgecolor=_COMIC["ink"],
        linewidth=1.5,
    )
    ax.set_title("Filtración (min/día, 7d)", color=_COMIC["ink"], fontweight="bold")
    ax.set_ylabel("min")
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    for bar, v in zip(bars, values):
        if v > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                v + max(values) * 0.02,
                f"{int(v)}",
                ha="center",
                va="bottom",
                fontsize=8,
                color=_COMIC["ink"],
            )
    return _png_b64(fig)


def health_7d(health_history: dict[str, float]) -> str:
    """Line chart of daily health score, last 7 days."""
    days = _last_n_days(health_history, n=7)
    labels = [d.split("-")[-1] for d, _ in days]
    values = [v if v else None for _, v in days]
    fig, ax = _new_fig()
    # Use plot with markers; skip Nones gracefully.
    xs = list(range(len(values)))
    real_xs = [x for x, v in zip(xs, values) if v is not None]
    real_vs = [v for v in values if v is not None]
    if real_vs:
        ax.plot(
            real_xs,
            real_vs,
            color=_COMIC["accent"],
            marker="o",
            markersize=8,
            markeredgecolor=_COMIC["ink"],
            linewidth=2.5,
        )
    ax.set_xticks(xs)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 100)
    ax.set_title("Salud de la piscina (7d)", color=_COMIC["ink"], fontweight="bold")
    ax.set_ylabel("score")
    ax.axhspan(80, 100, alpha=0.12, color=_COMIC["ok"])
    ax.axhspan(60, 80, alpha=0.12, color=_COMIC["warn"])
    ax.axhspan(0, 60, alpha=0.12, color=_COMIC["danger"])
    ax.grid(axis="y", linestyle=":", alpha=0.4)
    return _png_b64(fig)


def vitals_24h(snapshot: dict[str, list[float | None]]) -> str:
    """Three stacked sparklines: pH, salt, temperature over 24 h."""
    fig = Figure(figsize=(6.4, 3.6), dpi=120)
    fig.patch.set_facecolor(_COMIC["facecolor"])
    metrics = [
        ("ph", "pH", _COMIC["accent"]),
        ("salt_g_l", "Sal (g/L)", "#1976d2"),
        ("temperature_c", "Temp (°C)", "#e53935"),
    ]
    for idx, (key, label, color) in enumerate(metrics, start=1):
        ax = fig.add_subplot(3, 1, idx)
        ax.set_facecolor(_COMIC["axes.facecolor"])
        for spine in ax.spines.values():
            spine.set_color(_COMIC["edgecolor"])
            spine.set_linewidth(1.4)
        series = snapshot.get(key, []) or []
        real = [(i, v) for i, v in enumerate(series) if v is not None]
        if real:
            xs = [r[0] for r in real]
            vs = [r[1] for r in real]
            ax.plot(xs, vs, color=color, linewidth=2.0)
            ax.scatter([xs[-1]], [vs[-1]], color=color, edgecolor=_COMIC["ink"], s=30, zorder=3)
        ax.set_ylabel(label, fontsize=8)
        ax.tick_params(colors=_COMIC["ink"], labelsize=7)
        ax.grid(axis="y", linestyle=":", alpha=0.3)
        if idx < len(metrics):
            ax.set_xticklabels([])
    fig.suptitle("Constantes vitales (24h)", color=_COMIC["ink"], fontweight="bold", fontsize=11)
    return _png_b64(fig)
