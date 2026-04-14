from .train import Train
from .stop_sensors import SensorConfig


def main():
    sensor_config = [
        ("button", SensorConfig("button"), {"pull_up" : True}),
    ]
    ego = Train("track_0", "train_0", sensor_config)
    ego.start()

    for _ in range(10):
        ego.update()

    print(ego._train_state)


if __name__ == "__main__":
    main()
