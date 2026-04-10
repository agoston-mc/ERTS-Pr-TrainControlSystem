from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class CurrentStatus(Enum):
    """Whether the train is currently in motion or stopped at a station."""
    MOVING  = "moving"
    STOPPED = "stopped"

    def __str__(self) -> str:
        return self.value


@dataclass
class TrainState:
    """State of the train."""
    stop_requested:    bool
    camera_detected:   bool
    current_delay:     int
    progress_on_track: float
    next_station:      str
    current_status:    CurrentStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "stop_requested":    bool(self.stop_requested),
            "camera_detected":   bool(self.camera_detected),
            "current_delay":     int(self.current_delay),
            "progress_on_track": float(self.progress_on_track),
            "next_station":      str(self.next_station),
            "current_status":    self.current_status.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TrainState:
        try:
            status = CurrentStatus(data["current_status"])
        except KeyError:
            raise ValueError("missing required field 'current_status'")
        except ValueError:
            raise ValueError(
                f"invalid current_status {data['current_status']!r}; "
                f"expected one of {[s.value for s in CurrentStatus]}"
            )

        return cls(
            stop_requested    = bool(data["stop_requested"]),
            camera_detected   = bool(data["camera_detected"]),
            current_delay     = int(data["current_delay"]),
            progress_on_track = float(data["progress_on_track"]),
            next_station      = str(data["next_station"]),
            current_status    = status,
        )

    @property
    def will_stop(self) -> bool:
        return self.stop_requested or self.camera_detected


@dataclass
class StationStats:
    total_delay_sum: int
    stop_count:      int
    no_stop_count:   int

    @classmethod
    def from_dict(cls, data: dict) -> StationStats:
        return cls(
            total_delay_sum = int(data.get("total_delay_sum", 0)),
            stop_count      = int(data.get("stop_count", 0)),
            no_stop_count   = int(data.get("no_stop_count", 0)),
        )
