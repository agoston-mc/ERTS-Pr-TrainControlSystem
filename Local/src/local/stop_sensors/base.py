from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class SensorConfig:
    name: str


class Sensor(ABC):
    def __init__(self, config: SensorConfig):
        self.config = config

    @abstractmethod
    def read(self) -> bool:
        raise NotImplementedError

    async def aread(self) -> bool:
        return self.read()

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def reset(self) -> None:
        return None
