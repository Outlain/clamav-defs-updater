FROM alpine:3.24.1@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b

ARG CLAMAV_PACKAGE_VERSION=1.4.5-r0

RUN apk upgrade --no-cache \
    && apk add --no-cache "clamav=${CLAMAV_PACKAGE_VERSION}" python3 \
    && freshclam --version \
    && addgroup -S -g 10001 clamav-helper \
    && adduser -S -D -u 10001 -G clamav-helper -h /home/clamav-helper clamav-helper \
    && install -d -o 10001 -g 10001 -m 0750 /home/clamav-helper /var/lib/clamav

COPY freshclam_loop.py /usr/local/bin/freshclam_loop.py
COPY healthcheck.py /usr/local/bin/healthcheck.py
RUN chmod 0555 /usr/local/bin/freshclam_loop.py /usr/local/bin/healthcheck.py

ENV DEFINITIONS_DIR=/var/lib/clamav \
    UPDATE_INTERVAL_SECONDS=21600 \
    FAILURE_RETRY_SECONDS=300 \
    MAX_DEFINITION_AGE_SECONDS=172800 \
    HOME=/home/clamav-helper \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER 10001:10001
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=30m --timeout=15s --start-period=10m --retries=3 \
    CMD ["python3", "/usr/local/bin/healthcheck.py"]

CMD ["python3", "/usr/local/bin/freshclam_loop.py"]
