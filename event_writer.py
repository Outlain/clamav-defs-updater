#!/usr/bin/env python3
"""Write small durable JSON events for the central notifier."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EVENT_DIR = Path(os.environ.get("EVENT_DIR", "/events"))
SERVICE = "clamav-defs-updater"


def emit_event(
    event_type: str,
    severity: str,
    message: str,
    *,
    event_id: str | None = None,
    **fields: Any,
) -> Path:
    EVENT_DIR.mkdir(mode=0o750, parents=True, exist_ok=True)
    identifier = event_id or str(uuid.uuid4())
    payload: dict[str, Any] = {
        "schema_version": 1,
        "event_id": identifier,
        "event_type": event_type,
        "service": SERVICE,
        "severity": severity,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "message": message[:2000],
    }
    payload.update({key: value for key, value in fields.items() if value is not None})

    directory_info = EVENT_DIR.lstat()
    if not stat.S_ISDIR(directory_info.st_mode) or stat.S_ISLNK(directory_info.st_mode):
        raise RuntimeError(f"event path is not a real directory: {EVENT_DIR}")

    descriptor, name = tempfile.mkstemp(prefix=".event-", suffix=".tmp", dir=EVENT_DIR)
    temporary = Path(name)
    destination = EVENT_DIR / f"{identifier}.json"
    try:
        os.fchmod(descriptor, 0o640)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            json.dump(payload, handle, separators=(",", ":"), sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        directory_fd = os.open(EVENT_DIR, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return destination
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
