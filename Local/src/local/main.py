import asyncio

from database.erts_firebase import init as init_erts_firebase

from .train import Train
from .stop_sensors import SensorConfig


PUBLISH_FREQUENCY = 5


async def main():
    init_erts_firebase()

    sensor_config = [
        ("button", SensorConfig("button"), {"pull_up" : True}),
    ]
    ego = Train("track_0", "train_0", sensor_config)
    ego.start()

    while not ego.is_done:
        ego.update()
        await asyncio.sleep(0.1)

    asyncio.create_task(ego.publish())

    await asyncio.sleep(2)
    print(ego._train_state)


if __name__ == "__main__":
    asyncio.run(main())
