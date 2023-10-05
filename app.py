#!/usr/bin/env python3

import atexit
from decouple import config, UndefinedValueError
import json
from math import sqrt
from os.path import basename,splitext
from paho.mqtt import client as mqtt_client
import random
from time import time

feed = 0
burn = 0
last_set_limit = 0
current_limit = 0


def setup():
    global inverter_max_power, inverter_default_power
    global broker, port, topic_inverter_power, topic_inverter_limiter, topic_smartmeter_power
    global client_id, username, password

    try:
        inverter_max_power = config("INVERTER_MAX_POWER", cast = int)
        if inverter_max_power <= 0:
            raise ValueError(f"invalid value {inverter_max_power} for INVERTER_MAX_POWER")
        inverter_default_power = config("INVERTER_DEFAULT_POWER", default=inverter_max_power, cast=int)
        if inverter_default_power <= 0:
            raise ValueError(f"invalid value {inverter_default_power} for INVERTER_DEFAULT_POWER")
        broker = config("MQTT_BROKER")
        port = config("MQTT_PORT", default=1883, cast=int)
        topic_inverter_power = config("MQTT_TOPIC_INVERTER_POWER")
        topic_inverter_limiter = config("MQTT_TOPIC_INVERTER_LIMITER", default=None)
        topic_smartmeter_power = config("MQTT_TOPIC_SMARTMETER_POWER")
        client_id = f"{splitext(basename(__file__))[0]}-{random.randint(0, 1000)}-{random.randint(0, 1000)}"
        username = config("MQTT_USERNAME", default=None)
        password = config("MQTT_PASSWORD", default=None)
    except (UndefinedValueError, ValueError) as inst:
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


def set_inverter_limit(client: mqtt_client, limit: float):
    global current_limit, last_set_limit
    actual_limit: int = min(round(limit), inverter_max_power)   # do not exceed inverter_max_power

    if actual_limit != current_limit:
        if client.publish(topic_inverter_limiter, f"{actual_limit}W"):
            current_limit = actual_limit
            last_set_limit = time()
            print(f"         Set inverter power limit to {actual_limit} W")
        else:
            print(f"         Failed to set inverter power limit")


def handle_smartmeter_power(client: mqtt_client, data):
    global burn, last_set_limit, current_limit

    def should_set_limit(limit: float):
        # limit may be smaller than 0 since feed and burn are not synced
        if limit <= 0:
            return False

        # time passed in seconds since inverter limit was updated
        time_passed = time() - last_set_limit

        # difference betewwn new limit and current inverter limit
        drift = abs(limit - current_limit) + 1

        # Set new inverter limit if enough time has passed
        # or drift is big enough since we last updated the inverter limit
        return time_passed > 200 / sqrt(drift)


    burn = data
    print(f"{runtime():6.1f} - burn: {burn}")
    limit = feed + burn

    if topic_inverter_limiter is not None and should_set_limit(limit):
        set_inverter_limit(client, limit)


def run():
    try:
        client = connect_mqtt()

        atexit.register(set_inverter_limit, client, inverter_default_power)

        subscribe(client, topic_inverter_power, handle_inverter_power)
        subscribe(client, topic_smartmeter_power, handle_smartmeter_power)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nTerminated!")
        exit()


if __name__ == "__main__":
    setup()
    run()
