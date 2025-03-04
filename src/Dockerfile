FROM ghcr.io/astral-sh/uv:0.6.4-python3.10-alpine

RUN apk update && apk add \
    'restic>0.17.3' \
    dcron \
    mariadb-client \
    mariadb-connector-c-dev

RUN apk add postgresql-client --repository=http://dl-cdn.alpinelinux.org/alpine/edge/main

ADD . /app
WORKDIR /app
RUN uv sync --frozen
WORKDIR /app/src/restic-compose-backup
ENV XDG_CACHE_HOME=/cache

ENTRYPOINT []
CMD ["./entrypoint.sh"]
