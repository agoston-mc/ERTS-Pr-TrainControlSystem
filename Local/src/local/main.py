import argparse
import asyncio
import logging

from database.erts_firebase import init as init_erts_firebase

from .train import Train
from .stop_sensors import SensorConfig


PUBLISH_FREQUENCY = 5

log = logging.getLogger(__name__)


async def main(track_name: str = "track_0", train_name: str = "train_0", publish_frequency: int = PUBLISH_FREQUENCY):
    """Run a single train on a track.

    Parameters:
    - track_name: name/id of the track to create the train on
    - train_name: name/id of the train
    - publish_frequency: how many frames between publishes
    """
    init_erts_firebase()

    sensor_config = [
        ("button", SensorConfig("button"), {"pull_up": True}),
        ("camera", SensorConfig("camera"), {"device": 0}),
    ]
    ego = Train(track_name, train_name, sensor_config)
    ego.start()

    frame = 0

    while not ego.is_done:
        ego.update()
        frame += 1
        if frame % publish_frequency == 0:
            log.info(f"Publishing frame {frame}")
            try:
                await ego.publish()
            except Exception:
                log.exception("Failed to publish train state")

        await asyncio.sleep(1)


    await asyncio.sleep(2)
    print(ego._train_state)


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="local", description="Run a local train on a track")
    p.add_argument("--track", "-t", default="track_0", help="Track name/id to use")
    p.add_argument("--train", "-n", default="train_0", help="Train name/id to create")
    p.add_argument("--publish-frequency", "-p", type=int, default=PUBLISH_FREQUENCY, help="Frames between publishes")
    return p


if __name__ == "__main__":
    parser = _build_arg_parser()
    args = parser.parse_args()
    asyncio.run(main(track_name=args.track, train_name=args.train, publish_frequency=args.publish_frequency))
