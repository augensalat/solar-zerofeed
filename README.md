# Zero feed-in for a local solar power plant

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

- `INVERTER_MAX_POWER`: A positive integer value denoting the inverter's maximum power
- `MQTT_BROKER`: Hostname or IP address of MQTT broker
- `MQTT_TOPIC_INVERTER_POWER`: Inverter (AC) power MQTT topic in Watts
- `MQTT_TOPIC_SMARTMETER_POWER`: Smartmeter consumption power MQTT topic in Watts

The `MQTT_TOPIC_*_POWER` environment may contain a path if the value contains a JSON string.

> **Example**:
>
> The smartmeter topic `smartmeter/SENSOR` returns a string containing the following data
>
> ```json
> {
>   "Time": "2023-09-29T15:38:54",
>   "em": {
>     "consumption_total": 10169.029,
>     "feed_total": 0.0,
>     "consumption": 169,
>     "amperage": 1.11,
>     "voltage": 229.5,
>     "frequency": 50,
>     "phase_deviation": -46
>   }
> }
> ```
>
> then you want to configure
>
> ```
> MQTT_TOPIC_SMARTMETER_POWER=smartmeter/SENSOR:em.consumption
> ```

Optionally you may want to set:

- `MQTT_PORT`: default 1883
- `MQTT_USERNAME`: if broker requires authentication
- `MQTT_PASSWORD`: ditto
- `MQTT_TOPIC_INVERTER_LIMITER`: MQTT topic where to _set_ the inverter limit,
  which is probably "inverter/ctrl/limit/0". If this is not set, the inverter power
  will not be adjusted.

You can place these in a file called `.env` in the project root directory.

Then start the app with

```shell
# *ix shell
./app.py

# Windows
python3 app.py
```
