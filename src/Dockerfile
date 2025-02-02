FROM ghcr.io/astral-sh/uv:0.5.26-alpine

RUN apk update && apk add \
    'restic=0.17.3' \
    dcron \
    mariadb-client \
    mariadb-connector-c-dev

RUN apk add postgresql-client --repository=http://dl-cdn.alpinelinux.org/alpine/edge/main

ADD . /restic-compose-backup
WORKDIR /restic-compose-backup
RUN uv sync --frozen
ENV XDG_CACHE_HOME=/cache

ENTRYPOINT []
CMD ["./entrypoint.sh"]
