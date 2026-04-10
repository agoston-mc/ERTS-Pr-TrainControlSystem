from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class TrainState:
    stop_requested: bool
    camera_detected: bool
    current_delay: int
    progress_on_track: float
    next_station: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> TrainState:
        return cls(
            stop_requested=bool(data["stop_requested"]),
            camera_detected=bool(data["camera_detected"]),
            current_delay=int(data["current_delay"]),
            progress_on_track=float(data["progress_on_track"]),
            next_station=str(data["next_station"]),
        )

    @property
    def will_stop(self) -> bool:
        return self.stop_requested or self.camera_detected


@dataclass
class StationStats:
    total_delay_sum: int
    stop_count: int
    no_stop_count: int

    @classmethod
    def from_dict(cls, data: dict) -> StationStats:
        return cls(
            total_delay_sum=int(data.get("total_delay_sum", 0)),
            stop_count=int(data.get("stop_count", 0)),
            no_stop_count=int(data.get("no_stop_count", 0)),
        )
