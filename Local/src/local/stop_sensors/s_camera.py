import logging
from threading import Lock, Thread
from typing import Optional
from local.stop_sensors.base import Sensor, SensorConfig

log = logging.getLogger(__name__)


from typing import Any, Optional

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

    def __init__(self, config: SensorConfig, device: int = 0, window_name: Optional[str] = None):
        super().__init__(config)
        self._lock = Lock()
        self._device = device
        self._window_name = window_name or f"camera-{config.name}"
        self._cap = None
        self._thread: Optional[Thread] = None
        self._running = False
        self._started = False
        # placeholder for last frame (can be used by detection later)
        self._last_frame = None

    def _poll(self) -> None:
        try:
            while self._running:
                if self._cap is None:
                    break
                ret, frame = self._cap.read()
                if not ret or frame is None:
                    # read failed; sleep a bit and try again
                    import time

                    time.sleep(0.1)
                    continue

                with self._lock:
                    self._last_frame = frame

                # display the frame if OpenCV GUI is available
                if cv2 is not None:
                    try:
                        cv2.imshow(self._window_name, frame)
                        # small wait to allow window to process events
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            # pressing 'q' in the window will stop the camera loop
                            self._running = False
                            break
                    except Exception:
                        # imshow may fail on headless systems; ignore and continue
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
            # help static analyzers: at this point cv2 is not None (we returned earlier)
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

        # try to close any OpenCV windows created
        if cv2 is not None:
            try:
                cv2.destroyWindow(self._window_name)
            except Exception:
                try:
                    cv2.destroyAllWindows()
                except Exception:
                    pass

        log.info("%s: CameraSensor stopped", self.config.name)


