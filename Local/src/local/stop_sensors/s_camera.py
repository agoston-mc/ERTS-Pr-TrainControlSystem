import logging
import time
from threading import Lock, Thread
from typing import Optional

import numpy as np

from local.stop_sensors.base import Sensor, SensorConfig

log = logging.getLogger(__name__)

try:
    from picamera2 import Picamera2
except Exception:
    Picamera2 = None
    log.debug("picamera2 not available: CameraSensor will run in mock mode.")


# Minimum fraction of frame pixels that must differ to count as presence.
_DEFAULT_THRESHOLD = 0.02
# Per-pixel intensity change to count as "different".
_PIXEL_DIFF_THRESHOLD = 30
# Seconds between captures.
_POLL_INTERVAL = 0.3


class CameraSensor(Sensor):
    """Presence-detection sensor using a Raspberry Pi camera module.

    Compares consecutive greyscale frames; if the fraction of significantly
    changed pixels exceeds a threshold the sensor reports presence (True).
    The state is sticky (latches True) until reset() is called.
    """

    def __init__(self, config: SensorConfig, **kwargs):
        super().__init__(config)
        self._lock = Lock()
        self._detected = False

        self._threshold: float = kwargs.get("threshold", _DEFAULT_THRESHOLD)
        self._pixel_diff: int = kwargs.get("pixel_diff", _PIXEL_DIFF_THRESHOLD)
        self._poll_interval: float = kwargs.get("poll_interval", _POLL_INTERVAL)

        self._camera: Optional[object] = None
        self._thread: Optional[Thread] = None
        self._running = False
        self._started = False
        self._prev_frame: Optional[np.ndarray] = None

    # ------------------------------------------------------------------
    # Sensor interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._started:
            return
        self._started = True

        if Picamera2 is not None:
            try:
                self._camera = Picamera2()
                self._camera.configure(
                    self._camera.create_still_configuration(
                        main={"size": (320, 240), "format": "RGB888"}
                    )
                )
                self._camera.start()
                self._running = True
                self._thread = Thread(
                    target=self._poll, daemon=True, name=f"{self.config.name}-camera"
                )
                self._thread.start()
                log.info("%s: CameraSensor started with picamera2", self.config.name)
                return
            except Exception:
                log.exception(
                    "%s: Failed to initialize camera; falling back to mock mode.",
                    self.config.name,
                )

        log.info("%s: CameraSensor started in mock mode (always False)", self.config.name)

    def read(self) -> bool:
        with self._lock:
            return self._detected

    def reset(self) -> None:
        with self._lock:
            self._detected = False
            log.info("%s: CameraSensor reset -> state cleared", self.config.name)

    def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        if self._camera is not None:
            try:
                self._camera.stop()
                self._camera.close()
            except Exception:
                pass
            self._camera = None
        self._prev_frame = None
        log.info("%s: CameraSensor stopped", self.config.name)

    async def aread(self) -> bool:
        return self.read()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _poll(self) -> None:
        while self._running:
            try:
                frame = self._capture_grey()
                if self._prev_frame is not None:
                    diff = np.abs(frame.astype(np.int16) - self._prev_frame.astype(np.int16))
                    changed_ratio = np.mean(diff > self._pixel_diff)
                    if changed_ratio >= self._threshold:
                        with self._lock:
                            if not self._detected:
                                log.debug(
                                    "%s: presence detected (%.1f%% changed)",
                                    self.config.name,
                                    changed_ratio * 100,
                                )
                            self._detected = True
                self._prev_frame = frame
            except Exception:
                log.exception("%s: Error during camera poll", self.config.name)
            time.sleep(self._poll_interval)

    def _capture_grey(self) -> np.ndarray:
        """Capture a frame and convert to greyscale."""
        frame = self._camera.capture_array()  # (H, W, 3) uint8
        grey = (
            0.2989 * frame[:, :, 0]
            + 0.5870 * frame[:, :, 1]
            + 0.1140 * frame[:, :, 2]
        ).astype(np.uint8)
        return grey

