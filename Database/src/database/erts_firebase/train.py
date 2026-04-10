from __future__ import annotations

from typing import Callable

from firebase_admin import db

from ._db import ref
from .models import CurrentStatus, TrainState


def _train_ref(track_id: str, train_id: str) -> db.Reference:
    return ref(f"/tracks/{track_id}/trains/{train_id}")


def set_train(track_id: str, train_id: str, state: TrainState) -> None:
    """Fully replace a train's state in the database."""
    _train_ref(track_id, train_id).set(state.to_dict())


def update_train(track_id: str, train_id: str, **fields) -> None:
    """Partially update one or more fields of a train's state.

    CurrentStatus enum values are automatically converted to their string
    representation before being sent to Firebase.

    Example:
        update_train("t1", "train_42", stop_requested=True, current_delay=30)
        update_train("t1", "train_42", current_status=CurrentStatus.STOPPED)
    """
    # Coerce enum to string so Firebase always receives a plain string
    if isinstance(fields.get("current_status"), CurrentStatus):
        fields = {**fields, "current_status": fields["current_status"].value}

    _train_ref(track_id, train_id).update(fields)


def get_train(track_id: str, train_id: str) -> TrainState | None:
    data = _train_ref(track_id, train_id).get()
    if not isinstance(data, dict):
        return None
    return TrainState.from_dict(data)


def listen_train(
    track_id: str,
    train_id: str,
    callback: Callable[[str, object], None],
) -> db.ListenerRegistration:
    """Subscribe to changes on a single train node.

    The callback receives (path, data) where:
    - path is the changed sub-path relative to the train root
      (e.g. "/" for a full replacement, "/stop_requested" for a field update)
    - data is the new value at that path

    The callback is invoked on a background thread by the Firebase SDK.
    Call .close() on the returned registration to stop listening.
    """
    def _on_event(event: db.Event) -> None:
        callback(event.path, event.data)

    return _train_ref(track_id, train_id).listen(_on_event)
