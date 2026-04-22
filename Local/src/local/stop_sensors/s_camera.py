import logging
import os
from threading import Lock, Thread
from typing import Optional
from local.stop_sensors.base import Sensor, SensorConfig

log = logging.getLogger(__name__)


from typing import Any

try:
    import cv2
except Exception:
    cv2 = None  # type: Optional[Any]
    log.debug("OpenCV (cv2) not available: CameraSensor will run in mock mode.")


class CameraSensor(Sensor):
    """Simple camera sensor that displays a live camera feed while running.

    Intended to be used with a Raspberry Pi Camera Module (via V4L2 / libcamera)
    where the camera is exposed as a video device (e.g. /dev/video0) so OpenCV
    can open it. If OpenCV is not available the sensor runs in mock mode.

    This class does NOT perform presence detection yet; `read()` currently
    returns False. It is structured so a detection algorithm can be added later
    using the latest frame captured in the background thread.
    """

    def __init__(
        self,
        config: SensorConfig,
        device: int = 0,
        window_name: Optional[str] = None,
        *,
        show_on_display: bool = False,
        display: str = ":0",
    ):
        super().__init__(config)
        self._lock = Lock()
        self._device = device
        self._window_name = window_name or f"camera-{config.name}"
        self._cap = None
        self._thread: Optional[Thread] = None
        self._running = False
        self._started = False
        self._show_on_display = bool(show_on_display)
        self._display = str(display)
        self._last_frame = None
        self._frame_count = 0
        log.debug("%s: CameraSensor initialized (device=%s, show_on_display=%s, display=%s)",
                  self.config.name, self._device, self._show_on_display, self._display)

    def _poll(self) -> None:
        try:
            log.debug("%s: camera poll thread started", self.config.name)
            while self._running:
                if self._cap is None:
                    break
                ret, frame = self._cap.read()
                if not ret or frame is None:
                    import time

                    time.sleep(0.1)
                    log.debug("%s: camera read returned no frame", self.config.name)
                    continue

                with self._lock:
                    self._last_frame = frame
                self._frame_count += 1
                if self._frame_count % 200 == 0:
                    log.debug("%s: captured %d frames", self.config.name, self._frame_count)

                if cv2 is not None:
                    try:
                        # only log the first few display events to avoid spamming
                        if self._frame_count < 3:
                            log.debug("%s: displaying frame (frame_count=%d)", self.config.name, self._frame_count)
                        cv2.imshow(self._window_name, frame)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            self._running = False
                            break
                    except Exception:
                        pass
        except Exception:
            log.exception("%s: Error while reading camera feed", self.config.name)

    def start(self) -> None:
        if self._started:
            return
        self._started = True

        if cv2 is None:
            log.info("%s: CameraSensor started in mock mode (cv2 unavailable)", self.config.name)
            return

        try:
            # if requested, set the DISPLAY (and XAUTHORITY if available) so
            # launching over SSH will target the attached display on the Pi.
            if self._show_on_display:
                log.debug("%s: show_on_display requested; current DISPLAY=%s XAUTHORITY=%s",
                          self.config.name, os.environ.get("DISPLAY"), os.environ.get("XAUTHORITY"))
                os.environ.setdefault("DISPLAY", self._display)
                try:
                    home = os.path.expanduser("~")
                    xa = os.path.join(home, ".Xauthority")
                    if os.path.exists(xa):
                        os.environ.setdefault("XAUTHORITY", xa)
                        log.debug("%s: using XAUTHORITY=%s", self.config.name, xa)
                except Exception:
                    log.debug("%s: failed to set XAUTHORITY", self.config.name, exc_info=True)
                log.debug("%s: effective DISPLAY=%s XAUTHORITY=%s",
                          self.config.name, os.environ.get("DISPLAY"), os.environ.get("XAUTHORITY"))
            assert cv2 is not None
            cap = cv2.VideoCapture(self._device)

            # try to set reasonable defaults; these may be ignored by the backend
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

            if not cap.isOpened():
                log.warning("%s: cv2.VideoCapture failed to open device %s", self.config.name, self._device)
                # keep mock behaviour
                cap.release()
                return
            else:
                log.debug("%s: cv2.VideoCapture opened device %s", self.config.name, self._device)

            self._cap = cap
            self._running = True
            self._thread = Thread(target=self._poll, daemon=True, name=f"{self.config.name}-camera")
            self._thread.start()
            log.info("%s: CameraSensor started and displaying feed", self.config.name)
        except Exception:
            log.exception("%s: Failed to start CameraSensor; running in mock mode", self.config.name)

    def read(self) -> bool:
        # Presence detection not implemented yet; return False for now.
        return False

    async def aread(self):
        return self.read()

    def reset(self) -> None:
        # nothing to reset for now
        return None

    def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                log.exception("%s: Error releasing camera", self.config.name)
            self._cap = None

        if cv2 is not None:
            try:
                cv2.destroyWindow(self._window_name)
            except Exception:
                try:
                    cv2.destroyAllWindows()
                except Exception:
                    pass

        log.info("%s: CameraSensor stopped", self.config.name)


