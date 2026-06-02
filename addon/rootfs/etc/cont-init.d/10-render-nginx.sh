#!/command/with-contenv bashio
# cont-init.d/10-render-nginx.sh
# Render the nginx upstream block with the values from the add-on options.

set -euo pipefail

UPSTREAM_HOST=$(bashio::config 'upstream_host')
UPSTREAM_HOST_HEADER=$(bashio::config 'upstream_host_header')

bashio::log.info "Rendering nginx with upstream=${UPSTREAM_HOST}, host=${UPSTREAM_HOST_HEADER}"

sed -i "s|_UPSTREAM_HOST_|${UPSTREAM_HOST}|g; s|_UPSTREAM_HOST_HEADER_|${UPSTREAM_HOST_HEADER}|g" \
    /etc/nginx/nginx.conf

bashio::log.info "nginx config rendered."
