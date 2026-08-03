# Host permissions

The image runs as UID/GID `10001:10001` by default. Prepare only its operational
directories; no media mount is required.

```sh
sudo install -d -m 0750 -o 10001 -g 10001 \
  /opt/docker/clamav-shared/defs \
  /opt/docker/clamav-shared/events/clamav-defs-updater \
  /opt/docker/clamav-shared/state/defs-updater
```

The updater needs read/write/search permission on all three. Scanners need only
read/search permission on the definition directory and mount it `:ro`. Keeping
the same numeric UID/GID across the suite is the simplest deployment. Do not put
the definition directory back under `/mnt/media`, where the broad `/downloads`
alias would expose it to content-processing containers.
