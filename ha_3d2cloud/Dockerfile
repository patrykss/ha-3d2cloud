ARG BUILD_FROM
FROM ${BUILD_FROM}

# Instalacja Pythona, pip, curl i bash na bazie systemowej Home Assistant
RUN apk add --no-cache \
    python3 \
    py3-pip \
    curl \
    bash

COPY rootfs /
COPY run.sh /run.sh

WORKDIR /app

# Użycie pip3 oraz flagi --break-system-packages dla nowoczesnego Alpine
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

RUN chmod +x /run.sh

CMD [ "/run.sh" ]