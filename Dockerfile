FROM arm32v6/python:3-alpine

RUN pip install -U pip pipenv

RUN apk update
RUN apk upgrade
RUN apk add build-base linux-headers

RUN pip install -U pip pipenv
ADD Pipfile* /tmp/
WORKDIR /tmp
RUN pipenv install --system --ignore-pipfile

ADD lifx.py /src/
