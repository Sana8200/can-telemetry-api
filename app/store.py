"""In-memory store for the latest value of each signal."""

import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class Reading:
    value: float
    timestamp: float  # unix time


class LatestValues:
    """Latest reading of each signal. Thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._readings: dict[str, Reading] = {}

    def update(self, values: dict[str, float], timestamp: float) -> None:
        """Save the values, but never replace a newer reading with an older one."""
        with self._lock:
            for name, value in values.items():
                current = self._readings.get(name)
                if current is None or timestamp >= current.timestamp:
                    self._readings[name] = Reading(value, timestamp)

    def get(self, name: str) -> Reading | None:
        """None if nothing has come in for this signal yet."""
        with self._lock:
            return self._readings.get(name)

    def snapshot(self) -> dict[str, Reading]:
        """Copy of all readings, so the caller can loop over it without the lock."""
        with self._lock:
            return dict(self._readings)
