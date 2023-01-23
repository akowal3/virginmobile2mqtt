FROM python:3-alpine

ADD virginmobile2mqtt.py /

RUN pip install paho.mqtt requests

RUN apk update && \
    apk upgrade 

CMD [ "python", "./virginmobile2mqtt.py" ]