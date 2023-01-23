# virginmobile2mqtt

It is increadibly annoying that I don't get notifications before my data cap on my pay-as-you-go plan runs out. This has left me stranded without internet on multiple ocasions. 

The solution I'm proposing is periodically querying for the data about my 

It connects to virginmobile.pl throug rest and extracts the information about data, voice and sms balances, as well as the account balance for a specific phone number.

This project is based on [battery2mqtt](https://github.com/Tediore/battery2mqtt) and [vbalance](https://github.com/czak/vbalance). 

# Build

Build using the following command
```
docker build -t virginmobile2mqtt .
```

# Env file
```
MQTT_HOST=ip-mqtt-host
MQTT_PORT=1883
MQTT_USER=username
MQTT_PASSWORD=password
MQTT_QOS=1
INTERVAL=1200
LOG_LEVEL=info
VM_PHONE_IDS=coma-separated-phone-numbers
VM_USERNAME=username
VM_PASSWORD=password
```

Note: phone numbers are in form `48DDDDDDDDD`, where `D` denotes a digit.

# How to run
```
docker run --name virginmobile2mqtt \
  -d \
  --env-file=.env \
  --restart unless-stopped \
  ghcr.io/akowal3/virginmobile2mqtt:latest
```