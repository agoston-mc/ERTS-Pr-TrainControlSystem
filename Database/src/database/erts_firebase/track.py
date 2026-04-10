from __future__ import annotations

from typing import Callable

from firebase_admin import db

from ._db import ref


def get_route(track_id: str) -> list[str]:
    """Return the ordered list of station IDs for the given track."""
    data = ref(f"/tracks/{track_id}/route").get()
    return list(data) if data else []


def listen_trains(
    track_id: str,
    callback: Callable[[str, object], None],
) -> db.ListenerRegistration:
    """Subscribe to all train state changes on a track.

    The callback receives (path, data) where path is relative to
    /tracks/{track_id}/trains (e.g. "/{train_id}" or "/{train_id}/stop_requested").

    The callback is invoked on a background thread by the Firebase SDK.
    Call .close() on the returned registration to stop listening.
    """
    def _on_event(event: db.Event) -> None:
        callback(event.path, event.data)

    return ref(f"/tracks/{track_id}/trains").listen(_on_event)
