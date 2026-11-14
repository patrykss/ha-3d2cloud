ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache \
    python3 \
    py3-pip \
    curl \
    bash

COPY rootfs /
COPY run.sh /run.sh

WORKDIR /app

RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

RUN chmod +x /run.sh

CMD [ "/run.sh" ]
