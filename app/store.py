"""In-memory store for the latest value of each signal."""

import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class Reading:
    value: float
    timestamp: float  # seconds since 1970


class LatestValues:
    """Keeps the newest reading per signal, safe to use from several threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._readings: dict[str, Reading] = {}

    def update(self, values: dict[str, float], timestamp: float) -> None:
        """Store each value, unless the stored reading is newer."""
        with self._lock:
            for name, value in values.items():
                current = self._readings.get(name)
                if current is None or timestamp >= current.timestamp:
                    self._readings[name] = Reading(value, timestamp)

    def get(self, name: str) -> Reading | None:
        """The latest reading of one signal, or None if nothing has arrived."""
        with self._lock:
            return self._readings.get(name)

    def snapshot(self) -> dict[str, Reading]:
        """A copy of all latest readings."""
        with self._lock:
            return dict(self._readings)
