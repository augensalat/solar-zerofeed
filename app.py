#!/usr/bin/env python3

from decouple import config
from os.path import basename,splitext
from paho.mqtt import client as mqtt_client
import random


broker = config("MQTT_BROKER")
port = config("MQTT_PORT", default=1883, cast=int)
topic_inverter_power = config("MQTT_TOPIC_INVERTER_POWER")
client_id = f"{splitext(basename(__file__))[0]}-{random.randint(0, 1000)}-{random.randint(0, 1000)}"
username = config("MQTT_USERNAME", default=None)
password = config("MQTT_PASSWORD", default=None)


def connect_mqtt() -> mqtt_client:
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print(f"Failed to connect, return code {rc}")

    client = mqtt_client.Client(client_id)
    client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(broker, port)

    return client


def subscribe(client: mqtt_client, topic: str):
    def on_message(client, userdata, msg):
        print(f"Received '{msg.payload.decode()}' from '{msg.topic}' topic")

    client.subscribe(topic)
    client.on_message = on_message


def run():
    try:
        client = connect_mqtt()
        subscribe(client, topic_inverter_power)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nTerminated!")
        exit(1)


if __name__ == "__main__":
    run()
