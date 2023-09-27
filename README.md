# Zero Feed-in for a local solar power plant

Dynamic control power limit of a Hoymiles inverter via Ahoy DTU.

## Initial Project Setup

```shell
# *ix shell only
git clone git@github.com:augensalat/solar-zerofeed.git
cd solar-zerofeed
make install

# optionally
. .venv/bin/activate
pip install --upgrade pip
```

## Running the App

You must set some environment variables:

- `MQTT_BROKER`: Hostname or IP address of MQTT broker
- `MQTT_TOPIC_INVERTER_POWER`: Inverter (AC) Power MQTT topic

Optionally you may want to set:

- `MQTT_PORT`: default 1883
- `MQTT_USERNAME`: if broker requires authentication
- `MQTT_PASSWORD`: ditto

You can place these in a file called `.env` in the project root directory.

Then start the app with

```shell
# *ix shell
./app.py

# Windows
python3 app.py
```
