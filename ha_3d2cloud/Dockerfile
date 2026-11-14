ARG BUILD_FROM=python:3.11-alpine
FROM ${BUILD_FROM}

RUN apk add --no-cache curl bash

WORKDIR /app

# Instalacja zależności
COPY rootfs/app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Kopiowanie kodu aplikacji i skryptu startowego
COPY rootfs/app/main.py /app/main.py
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD [ "/run.sh" ]