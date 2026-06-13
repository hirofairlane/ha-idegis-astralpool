ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apk add --no-cache python3 py3-pip \
    && pip3 install --no-cache-dir --break-system-packages \
        "aiohttp==3.11.11" \
        "aiomqtt==2.3.0" \
        "aiosmtplib==3.0.2" \
        "apscheduler==3.10.4" \
        "jinja2==3.1.4" \
        "tzlocal==5.2"

COPY rootfs /

RUN mkdir -p /data/charts /data/state

EXPOSE 8099

LABEL \
    io.hass.name="Idegis Pool Brain" \
    io.hass.description="Closed-loop brain for the Idegis pool stack" \
    io.hass.type="addon" \
    io.hass.version="0.1.0"
