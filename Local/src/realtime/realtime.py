import os
import socket
import threading
import subprocess
import time
import paho.mqtt.client as mqtt
import json

class RealTimeDoorHub:
    def __init__(self, socket_path="/tmp/comms.sock"):
        self.socket_path = socket_path
        self.running = True
        self.door_processes = []
        self.sensor_process = None
        self.server = None
        self.start_time = None
        self.current_flag = -1 # Start with -1 to indicate no data received yet
        self.all_doors_have_closed = True
    def start_sensor(self):
        try:
            self.sensor_process = subprocess.Popen(["./sensor.out"])
            print("[*] Sensor monitoring started.")
        except FileNotFoundError:
            print("[!] Error: ./sensor.out not found.")

    def process_event(self, raw_data):
        """
        Parses: "ID:STATUS\n FLAG"
        """
        try:
            # Clean up the raw bytes/string
            message = raw_data.strip()
            if not message:
                return

            # Split by whitespace/newlines
            # parts[0] = "1:CLOSED", parts[1] = "0"
            parts = message.split()
            
            if len(parts) >= 2:
                flag_val = int(parts[-1])
                self.current_flag = flag_val
                # Uncomment the line below to see every update:
                # print(f"[DEBUG] Raw: {message.replace(chr(10), ' ')} | Flag: {self.current_flag}")
        except (ValueError, IndexError) as e:
            print(f"[!] Parsing error: {e} on message: {raw_data}")

    def _monitor_logic(self):
        print("[*] Monitor active. Waiting 10s before checking atomic flag...")
        while self.running:
            if self.start_time:
                elapsed = time.time() - self.start_time
                
                # Check for 0 flag only after 10 seconds
                if elapsed > 10.0:
                    if self.current_flag == 0:
                        print(f"\n[*] SUCCESS: Atomic flag is 0 after {elapsed:.2f}s.")
                        self.close_doors()
                        break
                    elif self.current_flag == -1:
                        # This tells us if we aren't getting ANY data
                        if int(elapsed) % 5 == 0: 
                            print("[WAIT] No data received from socket yet...")
            
            time.sleep(1) # Slow down polling for cleaner output

    def close_doors(self) -> bool:
        # 1. Guard clause: Ensure we only run shutdown once
        if not self.running: 
            return False
        
        self.running = False
        print("[*] Shutting down all processes...")

        # 2. Shutdown Sensor
        if self.sensor_process:
            try:
                if self.sensor_process.poll() is None: # Check if still running
                    self.sensor_process.terminate()
            except Exception as e:
                print(f"[!] Error terminating sensor: {e}")

        # 3. Shutdown Doors
        for p in self.door_processes:
            try:
                if p.poll() is None:
                    p.terminate()
            except Exception as e:
                print(f"[!] Error terminating door process: {e}")

        # 4. Clean up the Socket Server
        if self.server:
            try:
                self.server.close()
            except OSError:
                pass
        
        # 5. Final Output Requirement
        print("doors have closed")
        self.all_doors_have_closed = True
        self.send_mqtt_status()
        return True


    def _handle_client(self, conn):
        with conn:
            while self.running:
                try:
                    data = conn.recv(1024)
                    if not data: break
                    
                    raw_msg = data.decode('utf-8', errors='ignore')
                    self.process_event(raw_msg)
                except socket.error:
                    break

    def start_doors(self, num_doors):
        self.all_doors_have_closed = False
        self.start_time = time.time()
        
        # Start background threads
        threading.Thread(target=self._listen_for_doors, daemon=True).start()
        threading.Thread(target=self._monitor_logic, daemon=True).start()
        self.send_mqtt_status_doors_can_open()  # Notify that doors can open    
        print(f"[*] Launching {num_doors} doors...")
        for i in range(1, num_doors + 1):
            self.door_processes.append(subprocess.Popen(["./realtime.out", str(i)]))

    def _listen_for_doors(self):
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)
            
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(self.socket_path)
        self.server.listen(100)
        self.server.settimeout(1.0)
        
        while self.running:
            try:
                conn, _ = self.server.accept()
                threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _init_mqtt(self, broker="localhost", port=1883):
        self.mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        try:
            self.mqtt_client.connect(broker, port, 60)
            self.mqtt_client.loop_start()
            print("[*] MQTT Connected to broker")
        except Exception as e:
            print(f"[!] MQTT Connection failed: {e}")

    def send_mqtt_status(self, topic="train/doors/status", message=None):
        if not hasattr(self, 'mqtt_client'):
            self._init_mqtt()
        
        payload = message or {
            "status": "closed",
            "timestamp": time.time(),
            "all_doors_closed": self.all_doors_have_closed
        }
        
        self.mqtt_client.publish(topic, json.dumps(payload))
        print(f"[*] MQTT Message published to {topic}")
    
    def send_mqtt_status_doors_can_open(self, topic="train/doors/status", message=None):
        if not hasattr(self, 'mqtt_client'):
            self._init_mqtt()
        
        payload = {
            "status": "opened",
            "timestamp": time.time(),
            "all_doors_closed": self.all_doors_have_closed
        }
        self.mqtt_client.publish(topic, json.dumps(payload))
        print(f"[*] MQTT Message published to {topic}")
