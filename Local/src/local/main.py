import stop_sensors
import logging

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

def main():
    bcfg = stop_sensors.SensorConfig(name="TestButton")
    button = stop_sensors.create_sensor("button", bcfg)

    button.start()

    log.info(button.read())
    button._on_press()
    log.info(button.read())

    button.reset()

    log.info(button.read())

    button.stop()




if __name__ == "__main__":
    pass

