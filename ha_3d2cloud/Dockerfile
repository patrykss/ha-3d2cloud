ARG BUILD_FROM=python:3.11-alpine
FROM ${BUILD_FROM}

RUN apk add --no-cache curl bash

COPY rootfs /
COPY run.sh /run.sh

WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt

RUN chmod +x /run.sh

CMD [ "/run.sh" ]
