import time
import os
from realtime import RealTimeDoorHub

def test_close_doors():
    num_doors = 10
    hub = RealTimeDoorHub()
    
    try:
        hub.start_sensor()
        hub.start_doors(num_doors)
        print(hub.all_doors_have_closed)
        deadline = time.time() + 500 
        success = False

        while time.time() < deadline:
            # Check if all processes are dead
            # poll() returns None if process is running, and exit code if finished
            if all(p.poll() is not None for p in hub.door_processes):
                success = True
                break
            
            # If the hub says it's done, give it a second to finish the kills
            if not hub.running:
                time.sleep(1)
                
            time.sleep(0.5)

        assert success, f"AssertionError: Not all {num_doors} doors closed within timeout"
        print(f"SUCCESS: All {num_doors} doors have closed.")

    finally:
        hub.close_doors()
        print(hub.all_doors_have_closed)
if __name__ == "__main__":
    test_close_doors()