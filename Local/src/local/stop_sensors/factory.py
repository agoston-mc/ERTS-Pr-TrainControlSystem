from typing import Dict
from local.stop_sensors.base import SensorConfig, Sensor
from local.stop_sensors.s_button import ButtonSensor

_REGISTRY: Dict[str, type] = {
    "button": ButtonSensor,
}


def create_sensor(kind: str, config: SensorConfig, **kwargs) -> Sensor:
    cls = _REGISTRY.get(kind)
    if cls is None:
        raise ValueError(f"Unknown sensor kind: {kind!r}")
    return cls(config, **kwargs)
