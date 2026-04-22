import asyncio
import logging

from database.erts_firebase import init as init_erts_firebase

from .train import Train
from .stop_sensors import SensorConfig


PUBLISH_FREQUENCY = 5

log = logging.getLogger(__name__)


async def main():
    init_erts_firebase()

    sensor_config = [
        ("button", SensorConfig("button"), {"pull_up" : True}),
    ]
    ego = Train("track_0", "train_0", sensor_config)
    ego.start()

    frame = 0

    while not ego.is_done:
        ego.update()
        frame += 1
        if frame % PUBLISH_FREQUENCY == 0:
            log.info(f"Publishing frame {frame}")
            try:
                await ego.publish()
            except Exception:
                log.exception("Failed to publish train state")

        await asyncio.sleep(1)


    await asyncio.sleep(2)
    print(ego._train_state)


if __name__ == "__main__":
    asyncio.run(main())
