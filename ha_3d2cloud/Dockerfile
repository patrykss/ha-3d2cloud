ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache curl bash

COPY rootfs /

WORKDIR /app

RUN pip install --no-cache-dir -r requirements.txt

RUN chmod +x /run.sh

CMD [ "/run.sh" ]
