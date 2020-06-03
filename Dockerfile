FROM arm32v6/python:3-alpine

RUN pip install -U pip pipenv

RUN apk update

RUN apk add build-base

RUN apk add linux-headers

RUN pip install -U lifxlan

RUN pip install -U gpiozero

RUN pip install -U rpi.gpio

ADD lifx.py /src/
