#!/usr/bin/env python3

from decouple import config, UndefinedValueError
import json
from os.path import basename,splitext
from paho.mqtt import client as mqtt_client
import random
from time import time

feed = 0
burn = 0

try:
    broker = config("MQTT_BROKER")
    port = config("MQTT_PORT", default=1883, cast=int)
    topic_inverter_power = config("MQTT_TOPIC_INVERTER_POWER")
    topic_smartmeter_power = config("MQTT_TOPIC_SMARTMETER_POWER")
    client_id = f"{splitext(basename(__file__))[0]}-{random.randint(0, 1000)}-{random.randint(0, 1000)}"
    username = config("MQTT_USERNAME", default=None)
    password = config("MQTT_PASSWORD", default=None)
except UndefinedValueError as inst:
    print(inst)
    exit(1)


def runtime():
    if not hasattr(runtime, "start_time"):
        runtime.start_time = time()

    return time() - runtime.start_time


def connect_mqtt() -> mqtt_client:
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print(f"{runtime():6.1f} - Connected to MQTT Broker!")
        else:
            print(f"Failed to connect, return code {rc}")

    client = mqtt_client.Client(client_id)
    client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(broker, port)

    return client


def subscribe(client: mqtt_client, topic_path: str, handler):

    def handle_message(client, userdata, msg):
        data = msg.payload.decode()
        path = subscribe.handlers[msg.topic][1]

        if path:    # fetch element from JSON data
            data = json.loads(data)
            for element in path.split("."):
                data = data[element]

        subscribe.handlers[msg.topic][0](client, float(data))


    if not hasattr(subscribe, "handlers"):
        subscribe.handlers = {}

    topic, *rest = topic_path.split(":")
    path = rest[0] if len(rest) else None

    subscribe.handlers[topic] = [handler, path]
    client.subscribe(topic)

    if not client.on_message:
        client.on_message = handle_message


def handle_inverter_power(client, data):
    global feed

    feed = data
    print(f"{runtime():6.1f} - feed: {feed}")


def handle_smartmeter_power(client, data):
    global burn

    burn = data
    print(f"{runtime():6.1f} - burn: {burn}")
    limit = round(feed + burn)

    if limit > 0:
        print(f"         Set inverter power limit to {limit}")


def run():
    try:
        client = connect_mqtt()
        subscribe(client, topic_inverter_power, handle_inverter_power)
        subscribe(client, topic_smartmeter_power, handle_smartmeter_power)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nTerminated!")
        exit(1)


if __name__ == "__main__":
    run()
