from __future__ import annotations

from firebase_admin import db

from ._db import ref
from .models import StationStats


def _station_ref(track_id: str, station_id: str) -> db.Reference:
    return ref(f"/tracks/{track_id}/stations/{station_id}")


def _apply(current: dict | None, delay: int, *, stop: bool) -> dict:
    current = current or {"total_delay_sum": 0, "stop_count": 0, "no_stop_count": 0}
    current["total_delay_sum"] = current.get("total_delay_sum", 0) + delay
    if stop:
        current["stop_count"] = current.get("stop_count", 0) + 1
    else:
        current["no_stop_count"] = current.get("no_stop_count", 0) + 1
    return current


def record_stop(track_id: str, station_id: str, delay: int) -> None:
    """Atomically record a train stop at this station and add its delay contribution."""
    _station_ref(track_id, station_id).transaction(
        lambda current: _apply(current, delay, stop=True)
    )


def record_pass(track_id: str, station_id: str, delay: int) -> None:
    """Atomically record a pass-through (no stop) and add its delay contribution."""
    _station_ref(track_id, station_id).transaction(
        lambda current: _apply(current, delay, stop=False)
    )


def get_station(track_id: str, station_id: str) -> StationStats | None:
    data = _station_ref(track_id, station_id).get()
    return StationStats.from_dict(data) if data else None
