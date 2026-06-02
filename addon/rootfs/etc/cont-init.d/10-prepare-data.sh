#!/command/with-contenv bashio
# Ensure /data subdirs exist (the volume is empty on first start).

set -euo pipefail

bashio::log.info "Ensuring /data layout"
mkdir -p /data/captures /data/state
touch /data/captures/idegis_full.jsonl

bashio::log.info "Init done."
