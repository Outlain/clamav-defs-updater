#!/usr/bin/env python3
"""Fail when the shared ClamAV database is incomplete or stale."""

from __future__ import annotations

import os
import stat
import sys
import time
from pathlib import Path

DEFINITIONS_DIR = Path(os.environ.get("DEFINITIONS_DIR", "/var/lib/clamav"))
MAX_DEFINITION_AGE_SECONDS = max(
    int(os.environ.get("MAX_DEFINITION_AGE_SECONDS", "172800")), 300
)


def candidate(stem: str) -> Path:
    available: list[tuple[int, Path]] = []
    for suffix in ("cld", "cvd"):
        path = DEFINITIONS_DIR / f"{stem}.{suffix}"
        try:
            info = path.lstat()
        except OSError:
            continue
        if stat.S_ISREG(info.st_mode) and info.st_size > 0 and os.access(path, os.R_OK):
            available.append((info.st_mtime_ns, path))
    if not available:
        raise RuntimeError(f"missing readable {stem}.cld/{stem}.cvd in {DEFINITIONS_DIR}")
    return max(available, key=lambda item: item[0])[1]


def main() -> int:
    try:
        candidate("main")
        daily = candidate("daily")
        age = max(0, int(time.time() - daily.stat().st_mtime))
        if age > MAX_DEFINITION_AGE_SECONDS:
            raise RuntimeError(
                f"daily definitions are stale: age={age}s max={MAX_DEFINITION_AGE_SECONDS}s"
            )
        probe = DEFINITIONS_DIR / ".health-write-probe"
        with probe.open("w", encoding="ascii") as handle:
            handle.write("ok\n")
        probe.unlink()
        print(f"healthy: daily={daily.name} age={age}s")
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"unhealthy: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
