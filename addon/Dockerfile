ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apk add --no-cache python3 py3-pip \
    && pip3 install --no-cache-dir --break-system-packages \
        "aiohttp==3.11.11"

COPY rootfs /

RUN mkdir -p /data/captures /data/state

EXPOSE 80 8765

LABEL \
    io.hass.name="Idegis / AstralPool cloud capturer" \
    io.hass.description="Local capture & decode of Idegis pool chlorinator cloud telemetry" \
    io.hass.type="addon" \
    io.hass.version="0.6.4"
