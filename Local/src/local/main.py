import logging

from database.erts_firebase import TrainState
from database.utils import get_track, Track, Stop

log = logging.getLogger(__name__)


class State:

    def __init__(self, track_id):
        self.track : Track = get_track(track_id)
        self._state : TrainState | None = None

        log.info(f"Initialized train state with track {track_id}")

    def start(self) -> None:
        self._state = TrainState(
            stop_requested=False,
            camera_detected=False,
            current_delay=0,
            progress_on_track=0.0,
            next_station=self.track.stops[0].id if self.track.stops else "",
        )

        log.info(f"Train started on track {self.track.id} with next station {self._state.next_station}")



def main():
    ego = State("track_0")

    ego.start()

    pass


if __name__ == "__main__":
    main()
