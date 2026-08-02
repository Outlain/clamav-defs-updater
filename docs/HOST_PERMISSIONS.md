# Host permissions

The image defaults to UID/GID `10001:10001`. The mounted definitions directory must be readable, writable, and searchable by the effective container user.

Default host path:

```text
/mnt/media/docker/clamav/defs
```

You can override `HELPER_UID` and `HELPER_GID` in `.env`, but the chosen account must be able to create, replace, and remove FreshClam database files in that directory.
