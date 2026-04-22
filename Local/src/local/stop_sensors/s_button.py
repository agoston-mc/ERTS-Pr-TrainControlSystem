import logging
from threading import Lock, Thread
from typing import Optional
from local.stop_sensors.base import Sensor, SensorConfig

log = logging.getLogger(__name__)

try:
    from sense_hat import SenseHat
except Exception:
    SenseHat = None
    log.debug("sense_hat not available: ButtonSensor will run in mock mode.")


class ButtonSensor(Sensor):
    def __init__(self, config: SensorConfig, **kwargs):
        super().__init__(config)
        self._lock = Lock()
        self._state = False
        self._sense = None
        self._thread: Optional[Thread] = None
        self._running = False
        self._started = False

    def _poll(self) -> None:
        while self._running:
            try:
                events = self._sense.stick.get_events()
                if events:
                    with self._lock:
                        self._state = True
                        log.debug("%s: joystick event -> state set True (sticky)", self.config.name)
            except Exception:
                log.exception("%s: Error reading joystick events", self.config.name)

    def start(self) -> None:
        if self._started:
            return
        self._started = True

        if SenseHat is not None:
            try:
                self._sense = SenseHat()
                self._running = True
                self._thread = Thread(target=self._poll, daemon=True, name=f"{self.config.name}-joystick")
                self._thread.start()
                log.info("%s: ButtonSensor started with SenseHat joystick", self.config.name)
                return
            except Exception:
                log.exception("%s: Failed to initialize SenseHat; falling back to mock mode.", self.config.name)

        log.info("%s: ButtonSensor started in mock mode", self.config.name)

    def read(self) -> bool:
        with self._lock:
            return bool(self._state)

    def reset(self) -> None:
        with self._lock:
            self._state = False
            log.info("%s: ButtonSensor reset -> state cleared", self.config.name)

    async def aread(self):
        return self.read()

    def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        self._sense = None
        log.info("%s: ButtonSensor stopped", self.config.name)
