import logging
from typing import Any

from database.erts_firebase import CurrentStatus, TrainState
from database.utils import get_track, Track, Stop

from .stop_sensors import create_sensor, SensorConfig, ButtonSensor

log = logging.getLogger(__name__)

TRACK_RESOLUTION = 100
STOP_LENGTH = 20
PUBLISH_FREQUENCY = 0


class Train:
    def __init__(self, track_id, train_id, sensors: list[tuple[str, SensorConfig, Any]]):
        track = get_track(track_id)
        if track is None:
            raise ValueError(f"Unknown track id: {track_id}")

        self.id = train_id
        self.track: Track = track
        self._sensors = [create_sensor(kind, config, **kw) for kind, config, kw in sensors]

        self._train_state: TrainState = self._make_initial_tstate()
        self._current_stop: Stop = self._resolve_next_stop()

        self._progress = 0
        self._stop_countdown = 0
        self._pub_counter = PUBLISH_FREQUENCY

        log.info(f"Initialized train {train_id} with track {track_id}")
        log.debug(f"Sensors: {self._sensors}")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._train_state = self._make_initial_tstate()
        self._current_stop = self._resolve_next_stop()

        for sensor in self._sensors:
            sensor.start()

        log.info(
            f"Train {self.id} started on track {self.track.id} "
            f"with next station {self._train_state.next_station}"
        )

    def update(self) -> None:
        cur_pos = self._train_state.progress_on_track

        self._update_station(cur_pos)

        if self._train_state.current_status == CurrentStatus.MOVING and self._progress < TRACK_RESOLUTION:
            self._progress += 1
            self._train_state.progress_on_track = self._progress / TRACK_RESOLUTION

        self._train_state.stop_requested = self.stop_requested

        if self._pub_counter == 0:
            self._pub_counter = PUBLISH_FREQUENCY
            pass  # TODO: publish self._train_state
        else:
            self._pub_counter -= 1

    # ------------------------------------------------------------------
    # Sensor-derived properties  (single source of truth: the sensors)
    # ------------------------------------------------------------------

    @property
    def stop_requested(self) -> bool:
        """True if any button sensor is currently latched."""
        return any(
            s.read() for s in self._sensors if isinstance(s, ButtonSensor)
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_station(self, cur_pos: float) -> None:
        if cur_pos < self._current_stop.position:
            return

        if self._should_stop():
            if self._train_state.current_status == CurrentStatus.MOVING:
                log.info(f"Train {self.id} stopped at station {self._train_state.next_station}")
                self._stop_countdown = STOP_LENGTH
                self._train_state.current_status = CurrentStatus.STOPPED
            else:
                # Already stopped — count down dwell time
                self._stop_countdown -= 1
                if self._stop_countdown == 0:
                    self._depart()
        else:
            self._train_state.current_delay -= STOP_LENGTH
            # TODO: update station delay info

    def _should_stop(self) -> bool:
        """Whether the train should stop at the current station."""
        return self.stop_requested or self._train_state.camera_detected

    def _depart(self) -> None:
        """Leave a station: resume motion, reset all sensors."""
        self._train_state.current_status = CurrentStatus.MOVING
        for sensor in self._sensors:
            sensor.reset()                          # clears ButtonSensor._state …
        # stop_requested is a live property — it automatically returns False now
        log.info(f"Train {self.id} departing from {self._train_state.next_station}")
        self._advance_next_station()

    def _advance_next_station(self) -> None:
        """Move the next-station pointer forward."""
        self._current_stop = self._resolve_next_stop()
        self._train_state.next_station = self._current_stop.id

    def _resolve_next_stop(self) -> Stop:
        """Return the Stop object for the current next_station, or a terminus sentinel."""
        opt = self.track.get_stop(self._train_state.next_station)
        if opt is None:
            log.info(f"Train {self.id} is at the last stop")
            return Stop(id="term", name="terminus", position=1.0)
        return opt

    def _make_initial_tstate(self) -> TrainState:
        return TrainState(
            stop_requested=False,
            camera_detected=False,
            current_delay=0,
            progress_on_track=0.0,
            next_station=self.track.stops[0].id if self.track.stops else "",
            current_status=CurrentStatus.MOVING,
        )
