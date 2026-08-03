#!/usr/bin/env python3
"""Fail when the shared ClamAV database is incomplete, stale, or unwritable."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from definition_status import database_candidate, require_fresh_definitions

DEFINITIONS_DIR = Path(os.environ.get("DEFINITIONS_DIR", "/var/lib/clamav"))
MAX_DEFINITION_AGE_SECONDS = max(
    int(os.environ.get("MAX_DEFINITION_AGE_SECONDS", "172800")), 300
)


def candidate(stem: str) -> Path:
    """Compatibility wrapper retained for callers and tests."""
    return database_candidate(DEFINITIONS_DIR, stem)


def main() -> int:
    temporary: Path | None = None
    descriptor = -1
    try:
        status = require_fresh_definitions(
            DEFINITIONS_DIR, MAX_DEFINITION_AGE_SECONDS
        )
        descriptor, name = tempfile.mkstemp(prefix=".health-write-", dir=DEFINITIONS_DIR)
        temporary = Path(name)
        os.write(descriptor, b"ok\n")
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        temporary.unlink()
        temporary = None
        print(f"healthy: daily={status.daily.name} age={status.daily_age_seconds}s")
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"unhealthy: {exc}", file=sys.stderr)
        return 1
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
