#!/usr/bin/env python3

"""Dynamically limit the power of a Hoymiles HM-xxx inverter via Ahoy DTU

This tool controls the power output of a Hoymiles HM-xxx inverter by
observing the power consumption of a smartmeter and adjusting the inverter.
"""

import atexit
from decouple import config, UndefinedValueError
import json
from math import sqrt
from os.path import basename, splitext
import paho.mqtt.client as mqtt_client
import random
from time import time

feed: float = 0
burn: float = 0
last_set_limit: float = 0
current_limit: float = 0
client_id: str = None
username: str = None
password: str = None


def setup():
    """Set up the application

    Set up the global variables for the application by reading the
    configuration values from the environment.
    Also generate a unique client ID for the MQTT client.
    """

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


def runtime() -> float:
    """Return the number of seconds since this function's first call

    If runtime is called for the first time, it will keep the start time
    and the elapsed time will be 0.

    Returns:
        float: The number of seconds since the runtime started.
    """

    if not hasattr(runtime, "start_time"):
        runtime.start_time = time()

    return time() - runtime.start_time


def connect_mqtt() -> mqtt_client:
    """Connect to an MQTT broker

    Connect to an MQTT broker using the specified credentials.

    Returns:
        mqtt_client: The connected MQTT client object.
    """

    def on_connect(client: mqtt_client, userdata: any, flags: dict, rc: int):
        """Callback is called when the client connects to the MQTT broker

        Parameters:
            client (mqtt_client): The MQTT client object.
            userdata(any): The private user data as set in Client() or userdata_set().
            flags(dict): Response flags sent by the broker.
            rc (int): The connection result. 0 means success, any other value
                indicates failure.

        Returns:
            None
        """

        if rc == 0:
            print(f"{runtime():6.1f} - Connected to MQTT Broker!")
        else:
            print(f"Failed to connect, return code {rc}")

    client = mqtt_client.Client(client_id)
    client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(broker, port)

    return client


def subscribe(client: mqtt_client, topic_path: str, handler: callable):
    """Subscribe to a given MQTT topic

    Subscribe and set a handler function to be called when a message is received.

    Args:
        client(mqtt_client): The MQTT client instance to use for subscribing.
        topic_path(str): The topic to subscribe to, in the format "path/to/topic"
        or "topic/to/topic:path.to.json.element".
        handler(callable): The function to call when a message is received on the subscribed topic.

    Returns:
        None
    """

    def handle_message(client: mqtt_client, userdata: any, msg: mqtt_client.MQTTMessage):
        """Callback function that handles incoming messages from an MQTT broker

        UTF-8-decode the message payload, JSON-decode the message if the topic contains
        a JSON pointer, and call the handler function with the decoded data.

        Args:
            client(mqtt_client): The MQTT client instance that received the message.
            userdata(any): User-defined data that is passed to callbacks.
            msg(MQTTMessage): The message received from the broker, including topic and payload.
        """
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


def handle_inverter_power(client: mqtt_client, data: float):
    """Handler for an MQTT message received on the inverter power topic

    Update the global `feed` variable with the given `data` value and
    print the current `feed` value along with the current runtime.

    Args:
        client(mqtt_client): The MQTT client instance that triggered the callback.
        data(float): The power data received from the inverter.

    Returns:
        None
    """

    global feed

    feed = data
    print(f"{runtime():6.1f} - feed: {feed}")


def set_inverter_limit(client: mqtt_client, limit: float):
    """Set the power limit of the inverter

    Args:
        client (mqtt_client): The MQTT client used to publish the power limit.
        limit (float): The desired power limit in watts.

    Returns:
        None
    """

    global current_limit, last_set_limit
    actual_limit: int = min(round(limit), inverter_max_power)   # do not exceed inverter_max_power

    if actual_limit != current_limit:
        if client.publish(topic_inverter_limiter, f"{actual_limit}W"):
            current_limit = actual_limit
            last_set_limit = time()
            print(f"         Set inverter power limit to {actual_limit} W")
        else:
            print(f"         Failed to set inverter power limit")


def handle_smartmeter_power(client: mqtt_client, data: float):
    """Handler for an MQTT message received on the smartmeter power topic

    Update the global `burn` variable with the given `data` value and
    print the current `burn` value along with the current runtime.
    Update the inverter power limit if necessary.

    Args:
        client (mqtt_client): The MQTT client instance.
        data (float): The power data received from the smartmeter.

    Returns:
        None
    """

    global burn, last_set_limit, current_limit

    def should_set_limit(limit: float):
        """Determine whether a new limit should be set on the inverter

        The retention period for the next update is shorter the more the new power
        limit differs from the last one. The minimum period is calculated by

            time_passed > (200 / sqrt(abs(current_limit - new_limit) + 1)

        Args:
            limit (float): The new limit value to be set on the inverter.

        Returns:
            bool: True if a new limit should be set on the inverter, False otherwise.
        """

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
    """Run the main code

    Connect to an MQTT client, register a function to be called when the
    program exits, subscribe to the two MQTT topics "smartmeter consumption"
    and "inverter power" and  start the MQTT client loop to receive messages
    indefinitely.
    """

    try:
        client = connect_mqtt()

        atexit.register(set_inverter_limit, client, inverter_default_power)

        subscribe(client, topic_inverter_power, handle_inverter_power)
        subscribe(client, topic_smartmeter_power, handle_smartmeter_power)
        client.loop_forever()
    except KeyboardInterrupt:
        print(f"\n{runtime():6.1f} - Terminated!")
        exit()


if __name__ == "__main__":
    setup()
    run()
