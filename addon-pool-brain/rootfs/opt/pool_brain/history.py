"""In-memory time-series ring buffer for the dashboard sparklines.

We don't need long-term storage at this layer — that's what the HA
recorder / InfluxDB do. The brain only keeps a small rolling window
(default: 48 samples = 24 h at 30 min cadence) per metric so the comic
dashboard can draw sparklines without round-tripping to HA history.

The buffer is pure (no I/O) and trivially serialisable to JSON, which
is what the `/api/brain/history` endpoint returns.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Iterable

# 24 h coverage at one sample every 30 min = 48 samples. The aggregator
# ticks every 30 s; only every 60th tick is stored. That's enough
# resolution for a sparkline without ballooning memory.
DEFAULT_CAPACITY = 48
DEFAULT_DECIMATION = 60


@dataclass
class Series:
    """A single metric's ring buffer."""

    capacity: int = DEFAULT_CAPACITY
    samples: deque = field(default_factory=deque)

    def push(self, value: float | None) -> None:
        self.samples.append(value)
        while len(self.samples) > self.capacity:
            self.samples.popleft()

    def as_list(self) -> list[float | None]:
        return list(self.samples)


@dataclass
class History:
    """Multi-series ring buffer with decimation built in.

    Call `record(...)` on every aggregator tick. Only every
    `decimation` calls actually push to the buffers; in between calls
    just increment the counter.
    """

    capacity: int = DEFAULT_CAPACITY
    decimation: int = DEFAULT_DECIMATION
    _counter: int = 0
    series: dict[str, Series] = field(default_factory=dict)

    def _slot(self, key: str) -> Series:
        if key not in self.series:
            self.series[key] = Series(capacity=self.capacity)
        return self.series[key]

    def record(self, values: dict[str, float | None]) -> bool:
        """Push values for the named metrics. Returns True iff a sample
        was actually committed (vs decimated)."""
        self._counter += 1
        if self._counter < self.decimation:
            return False
        self._counter = 0
        for k, v in values.items():
            self._slot(k).push(v)
        return True

    def snapshot(self) -> dict[str, list[float | None]]:
        """Stable JSON-friendly view of all stored series."""
        return {k: s.as_list() for k, s in self.series.items()}

    def keys(self) -> Iterable[str]:
        return self.series.keys()
