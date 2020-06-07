FROM arm32v6/python:3-alpine AS base

RUN apk update
RUN apk upgrade

RUN pip install -U pip pipenv

##==----

FROM base AS compile

RUN apk add build-base linux-headers

ADD Pipfile* /tmp/
WORKDIR /tmp
RUN pipenv install --system --ignore-pipfile

##==----

FROM compile AS test

WORKDIR /tmp
RUN pipenv install --dev --system --ignore-pipfile

##==----

FROM test AS pylint

ADD .pylintrc /src/
ADD lifx.py /src/

WORKDIR /src
RUN pylint *.py

##==----

FROM base AS runtime

COPY --from=compile /usr/local/lib/python3.8/site-packages/ /usr/local/lib/python3.8/site-packages/
COPY --from=pylint /src/*.py /app/
RUN chmod -R a+r /app

USER 1982
WORKDIR /app
