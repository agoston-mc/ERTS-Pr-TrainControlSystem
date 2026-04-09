import logging
from threading import Lock
from typing import Optional
from local.stop_sensors.base import Sensor, SensorConfig

log = logging.getLogger(__name__)

try:
    from gpiozero import Button as GPIOButton
except Exception:
    GPIOButton = None
    log.debug("gpiozero not available: ButtonSensor will run in mock mode.")


class ButtonSensor(Sensor):
    def __init__(self, config: SensorConfig, pin: int = 17, pull_up: bool = True, bounce_time: Optional[float] = 0.02):
        super().__init__(config)
        self.pin = pin
        self.pull_up = pull_up
        self.bounce_time = bounce_time
        self._lock = Lock()
        self._state = False
        self._btn = None
        self._started = False

    def _on_press(self) -> None:
        with self._lock:
            self._state = True
            log.debug("%s: button pressed -> state set True (sticky)", self.config.name)

    def start(self) -> None:
        if self._started:
            return
        self._started = True

        if GPIOButton is not None:
            try:
                self._btn = GPIOButton(self.pin, pull_up=self.pull_up, bounce_time=self.bounce_time)
                self._btn.when_pressed = self._on_press
                log.info("%s: ButtonSensor started with gpiozero on pin %s", self.config.name, self.pin)
                return
            except Exception:
                log.exception("%s: Failed to initialize gpiozero Button; falling back to mock mode.", self.config.name)

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
        if self._btn is not None:
            try:
                self._btn.close()
            except Exception:
                pass
            self._btn = None
        log.info("%s: ButtonSensor stopped", self.config.name)
