import tomllib
from dataclasses import dataclass
from pathlib import Path

_DATA_FILE = Path(__file__).parent.parent / ".data" / "tracks.toml"


@dataclass(frozen=True)
class Stop:
    id: str
    name: str
    position: float

    @classmethod
    def from_dict(cls, data: dict) -> "Stop":
        return cls(
            id=data["id"],
            name=str(data["name"]),
            position=float(data["position"]),
        )


@dataclass(frozen=True)
class Track:
    id: str
    name: str
    stops: list[Stop]

    @classmethod
    def from_dict(cls, data: dict) -> "Track":
        return cls(
            id=data["id"],
            name=data["name"],
            stops=sorted([Stop.from_dict(stop) for stop in data["stops"]], key=lambda stop: stop.position),
        )

    def next_stop(self, position: float) -> Stop | None:
        for stop in self.stops:
            if stop.position > position:
                return stop
        return None

    def get_stop(self, stop_id: str) -> Stop | None:
        for stop in self.stops:
            if stop.id == stop_id:
                return stop
        return None


def _load() -> dict[str, Track]:
    with open(_DATA_FILE, "rb") as f:
        raw = tomllib.load(f)

    return {t["id"] : Track.from_dict(t) for t in raw["tracks"]}


TRACKS: dict[str, Track] = _load()

def get_track(track_id: str) -> Track | None:
    return TRACKS.get(track_id)

if __name__ == "__main__":
    print(TRACKS)
