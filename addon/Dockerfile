ARG BUILD_FROM
FROM $BUILD_FROM

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# nginx + Python + tools
RUN apk add --no-cache \
        nginx \
        python3 \
        py3-pip \
    && pip3 install --no-cache-dir --break-system-packages \
        "fastapi==0.115.6" \
        "uvicorn[standard]==0.34.0"

# Copy the s6 service definitions, nginx config and Python app
COPY rootfs /

# nginx writeable dirs (Alpine doesn't create them by default)
RUN mkdir -p /var/log/nginx /var/lib/nginx/tmp /run/nginx \
    && chmod -R a+rwx /var/log/nginx /var/lib/nginx /run/nginx

# Capturer state dir (logs and history live under /data so they persist)
RUN mkdir -p /data/captures /data/state

EXPOSE 80 8765

LABEL \
    io.hass.name="Idegis / AstralPool cloud capturer" \
    io.hass.description="Local capture & decode of Idegis pool chlorinator cloud telemetry" \
    io.hass.type="addon" \
    io.hass.version="0.1.0"
