# clamav-defs-updater

A standalone Docker image that runs `freshclam` immediately and then keeps a shared ClamAV definition directory updated on a retry-safe interval.

This repository is intended to be uploaded by itself to a GitHub repository named `clamav-defs-updater`.

## What it does

- Runs FreshClam immediately at container startup.
- Retries quickly when no complete database exists.
- Uses the normal update interval after a successful update or when a usable database already exists.
- Exposes a Docker health check that requires readable `main` and `daily` databases and rejects stale daily definitions.
- Runs as non-root UID/GID `10001:10001` by default.
- Publishes amd64 and arm64 images to GHCR through GitHub Actions.

## Shared-definition rule

This container must be the **only writer** to the mounted definition directory. Other containers such as `clamav-scheduled` and `web-scan-move` should mount the same host directory read-only.

Do not attach this updater to Torrent Intake's separate ClamAV sidecar database while that sidecar is also running FreshClam.

## Deploy

1. Upload this entire folder to a new GitHub repository.
2. Keep the default branch named `main`.
3. Enable GitHub Actions and package publishing.
4. Copy `.env.example` to `.env` on the Docker host and adjust the host path and UID/GID.
5. Deploy `docker-compose.example.yml`.

The published image will be:

```text
ghcr.io/<github-owner>/clamav-defs-updater:latest
```

## Local validation

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile freshclam_loop.py healthcheck.py
docker compose -f docker-compose.example.yml config --quiet
docker build -t clamav-defs-updater:test .
```
