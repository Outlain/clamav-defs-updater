# clamav-defs-updater

The suite's only ClamAV signature writer. It runs FreshClam immediately at
startup, repeats successful updates on a configurable interval, and retries every
failed invocation without treating an older database as a successful update.

## Contract

- This container alone mounts `/var/lib/clamav` read/write.
- `clamav-scheduled`, `torrent-intake-clamd`, and `web-scan-move-clamd` mount the
  same host directory read-only.
- The updater never needs a scanner socket or the Docker socket.
- Scanner daemons notice atomic FreshClam updates through `SelfCheck` (300 seconds
  in the examples).
- FreshClam updates signatures only. ClamAV, Alpine packages, application source,
  Python dependencies, and images are updated by reviewed image builds.

After each attempt the loop verifies that readable, non-empty `main.cvd/main.cld`
and `daily.cvd/daily.cld` files exist and that the daily database is fresh. A zero
FreshClam exit code with an unusable database is still a failure. State is written
atomically to `/state/updater-state.json`.

The service emits atomic schema-v1 events to `/events`:

- `definitions_updated` (informational and suppressed by the notifier)
- `definitions_update_failed`
- `definitions_stale`
- `service_recovered`

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DEFINITIONS_DIR` | `/var/lib/clamav` | sole writable signature directory |
| `UPDATE_INTERVAL_SECONDS` | `21600` | delay after a successful update |
| `FAILURE_RETRY_SECONDS` | `300` | delay after a failed update |
| `UPDATE_TIMEOUT_SECONDS` | `1800` | hard limit for one FreshClam attempt |
| `MAX_DEFINITION_AGE_SECONDS` | `172800` | health/stale threshold |
| `EVENT_DIR` | `/events` | updater event spool |
| `STATE_DIR` | `/state` | durable updater status |

Copy `.env.example` to `.env`, prepare the host directories as UID/GID 10001 (or
set one consistent replacement identity), and run:

```sh
docker compose -f docker-compose.example.yml up -d
docker inspect --format '{{json .State.Health}}' clamav-defs-updater
```

The example uses:

- `/opt/docker/clamav-shared/defs`
- `/opt/docker/clamav-shared/events/clamav-defs-updater`
- `/opt/docker/clamav-shared/state/defs-updater`

It has a read-only root filesystem, bounded logs/resources, no added capabilities,
and only the three writable bind mounts above plus a small `/tmp` tmpfs. The
image supplies a minimal FreshClam configuration without Alpine's local
`NotifyClamd` setting; scanner daemons reload independently through `SelfCheck`.

FreshClam load-tests each downloaded database before publishing it. This briefly
requires substantially more memory than downloading the file, so the Compose
example permits up to 4 GiB. Docker memory limits are ceilings, not reservations.
Do not reduce this to 512 MiB: `Database load killed by signal 9` during an update
normally means the cgroup out-of-memory killer terminated the database test.
`TestDatabases yes` is intentionally retained so an unvalidated database is not
shared with every scanner.

## Validation and publishing

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile freshclam_loop.py healthcheck.py definition_status.py event_writer.py
docker compose -f docker-compose.example.yml config --quiet
docker build -t clamav-defs-updater:test .
```

GitHub Actions validates the project and publishes multi-architecture
`ghcr.io/<owner>/clamav-defs-updater` images for `linux/amd64` and `linux/arm64`.
