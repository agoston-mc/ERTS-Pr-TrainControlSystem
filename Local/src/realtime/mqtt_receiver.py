import paho.mqtt.client as mqtt
import json

def on_connect(client, userdata, flags, rc, properties):
    print(f"Connected with result code {rc}")
    # Subscribing in on_connect() means if we lose the connection and
    # reconnect, subscriptions will be renewed.
    client.subscribe("train/doors/status")

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        print(f"\n[RECEIVER] Topic: {msg.topic}")
        print(f"[RECEIVER] Status: {data.get('status')}")
        print(f"[RECEIVER] Timestamp: {data.get('timestamp')}")
    except Exception as e:
        print(f"Error parsing message: {e}")

def run_receiver():
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    print("[*] Starting MQTT Receiver... (Ctrl+C to exit)")
    client.connect("localhost", 1883, 60)

    # Blocking call that processes network traffic, dispatches callbacks and
    # handles reconnecting.
    client.loop_forever()

if __name__ == "__main__":
    run_receiver()
