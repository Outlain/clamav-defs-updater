# Integration

Start this container before scanners. Wait for its health check to pass, then
mount the exact same host directory in every consumer:

```yaml
volumes:
  - /opt/docker/clamav-shared/defs:/var/lib/clamav:ro
```

Consumers are `clamav-scheduled`, `torrent-intake-clamd`, and
`web-scan-move-clamd`. The Torrent Intake and web application containers do not
need the definitions mount because they stream data to their private sidecars.

Do not configure FreshClam in a scanner and do not run two updater instances
against the same directory. A scanner's persistent ClamD uses `SelfCheck 300` by
default. The scheduled scanner also supports an explicit operator reload through
its health helper; no service uses the Docker socket.

Updater events are written to
`/opt/docker/clamav-shared/events/clamav-defs-updater`. The notifier mounts the
parent `/opt/docker/clamav-shared/events` directory.
