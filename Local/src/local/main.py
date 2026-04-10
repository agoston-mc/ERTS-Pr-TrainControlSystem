import logging

from database.erts_firebase import CurrentStatus, TrainState
from database.utils import get_track, Track

log = logging.getLogger(__name__)


class Train:

    def __init__(self, track_id):
        track = get_track(track_id)
        if track is None:
            raise ValueError(f"Unknown track id: {track_id}")
        self.track: Track = track
        self._train_state: TrainState = self._make_initial_tstate()
        log.info(f"Initialized train state with track {track_id}")

    def start(self) -> None:
        self._train_state = self._make_initial_tstate()
        log.info(f"Train started on track {self.track.id} with next station {self._train_state.next_station}")

    def update(self):
        pass

    def _make_initial_tstate(self) -> TrainState:
        return TrainState(
            stop_requested    = False,
            camera_detected   = False,
            current_delay     = 0,
            progress_on_track = 0.0,
            next_station      = self.track.stops[0].id if self.track.stops else "",
            current_status    = CurrentStatus.MOVING,
        )


def main():
    ego = Train("track_0")
    ego.start()


if __name__ == "__main__":
    main()
