# Integration

The updater writes to `/var/lib/clamav` inside the container. Bind-mount the host definition directory there read-write.

Consumers should mount the same host directory read-only:

```yaml
volumes:
  - /mnt/media/docker/clamav/defs:/var/lib/clamav:ro
```

Recommended consumers:

- `clamav-scheduled`, which keeps one persistent `clamd` process.
- `web-scan-move`, which starts a new `clamscan` process for each settled intake item.

Only one FreshClam process should write to a given database directory.
