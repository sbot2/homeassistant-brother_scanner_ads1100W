#!/usr/bin/env bashio
set -e

bashio::log.info "Starting Brother Scanner SANE Bridge..."

# --- Read configuration from the add-on options ---------------------------
SANE_HOST="$(bashio::config 'saned_host' '192.168.178.101')"
SANE_DEVICE="$(bashio::config 'saned_device' 'brother4:net1;dev0')"
BRIDGE_PORT="$(bashio::config 'port' 8661)"

bashio::log.info "SANEd host  : ${SANE_HOST}"
bashio::log.info "SANE device : net:${SANE_HOST}:${SANE_DEVICE}"

# --- Sanity check: can we see the remote Brother device over the net backend?
# This add-on never runs brscan4; the remote host's saned exposes it. If the
# check fails, log a clear diagnostic but still start the bridge (the caller
# may fix the saned config and retry without a container restart).
if bashio::var.has_value "$(bashio::config 'saned_host')"; then
    if scanimage -L 2>/dev/null | grep -qi "${SANE_DEVICE}"; then
        bashio::log.info "Brother device visible via saned: ${SANE_DEVICE}"
    else
        bashio::log.warning \
            "Device 'net:${SANE_HOST}:${SANE_DEVICE}' not listed by scanimage -L."
        bashio::log.warning \
            "Check that 'saned' is running on ${SANE_HOST}, that the Brother" \
            "driver reports the same backend name, and that this add-on's" \
            "address is allowed in that host's saned.conf."
    fi
fi

# Launch the scan bridge (stdlib HTTP server). It reads /data/options.json so
# it picks up the current add-on options without environment indirection.
exec python3 /server.py
