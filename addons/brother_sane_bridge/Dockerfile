# Build an add-on image for the Brother scanner SANE scan bridge.
#
# NOTE: since Supervisor 2026.04.0 an explicit FROM is required (BUILD_FROM is
# no longer injected automatically). 'latest' is used so local builds always
# resolve; pin the tag when you publish to a registry.
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest
FROM ${BUILD_FROM}

# SANE client + the net backend are enough: this add-on never runs the Brother
# brscan4 driver itself. It dials OUT to a remote `saned` (on the Linux host)
# via scanimage -d net:<host>:<device>. Keeping brscan4 out keeps the image
# small and avoids re-licensing/installing exact Brother .deb files in a VM.
RUN \
    apk add --no-cache \
        sane-utils \
        sane-saned \
        sane-backend-net \
        python3 \
        ca-certificates \
        bash \
    && rm -rf /var/cache/apk/* \
    && rm -rf /tmp/*

# Copy the scan bridge service + startup wrapper.
COPY run.sh /
COPY server.py /
RUN chmod a+x /run.sh /server.py

WORKDIR /
CMD ["/run.sh"]
