from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class RealTimeDoorHub:
    def __init__(self, socket_path="/tmp/comms.sock"):
        self.socket_path = socket_path
        self.running = True

    def _listen_for_doors(self):
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(self.socket_path)
        # listen(10) allows up to 10 connections to queue up
        server.listen(10) 
        server.settimeout(1.0)

        while self.running:
            try:
                # Accept a new door connection
                conn, _ = server.accept()
                # Use a thread per connection for true concurrency
                client_thread = threading.Thread(target=self._handle_client, args=(conn,))
                client_thread.start()
            except socket.timeout:
                continue

    def _handle_client(self, conn):
        """Each door gets its own mini-handler here."""
        with conn:
            data = conn.recv(1024)
            if data:
                message = data.decode('utf-8')
                self.process_event(message)

    def process_event(self, message):
        # Expecting a format like "DOOR_ID:STATUS" (e.g., "01:OPEN")
        print(f"[*] Alert: {message}")

    def start_doors(self, num_doors):
        # 1. Start the central hub
        threading.Thread(target=self._listen_for_doors, daemon=True).start()
        # 2. Launch multiple binary instances
        for i in range(num_doors):
            door_id = str(i).zfill(2)
            print(f"Launching Door {door_id}...")
            # Popen is non-blocking so they all run at once
            subprocess.Popen(["./realtime/realtime.out"])

class CurrentStatus(Enum):
    """Whether the train is currently in motion or stopped at a station."""
    MOVING  = "moving"
    STOPPED = "stopped"

    def __str__(self) -> str:
        return self.value


@dataclass
class TrainState:
    """State of the train."""
    stop_requested:    bool
    camera_detected:   bool
    current_delay:     int
    progress_on_track: float
    next_station:      str
    current_status:    CurrentStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "stop_requested":    bool(self.stop_requested),
            "camera_detected":   bool(self.camera_detected),
            "current_delay":     int(self.current_delay),
            "progress_on_track": float(self.progress_on_track),
            "next_station":      str(self.next_station),
            "current_status":    self.current_status.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TrainState:
        try:
            status = CurrentStatus(data["current_status"])
        except KeyError:
            raise ValueError("missing required field 'current_status'")
        except ValueError:
            raise ValueError(
                f"invalid current_status {data['current_status']!r}; "
                f"expected one of {[s.value for s in CurrentStatus]}"
            )

        return cls(
            stop_requested    = bool(data["stop_requested"]),
            camera_detected   = bool(data["camera_detected"]),
            current_delay     = int(data["current_delay"]),
            progress_on_track = float(data["progress_on_track"]),
            next_station      = str(data["next_station"]),
            current_status    = status,
        )

    @property
    def will_stop(self) -> bool:
        return self.stop_requested or self.camera_detected


@dataclass
class StationStats:
    total_delay_sum: int
    stop_count:      int
    no_stop_count:   int

    @classmethod
    def from_dict(cls, data: dict) -> StationStats:
        return cls(
            total_delay_sum = int(data.get("total_delay_sum", 0)),
            stop_count      = int(data.get("stop_count", 0)),
            no_stop_count   = int(data.get("no_stop_count", 0)),
        )
