#!/usr/bin/env python3
"""Shared ClamAV definition completeness and freshness checks."""

from __future__ import annotations

import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DefinitionStatus:
    main: Path
    daily: Path
    daily_age_seconds: int


def database_candidate(directory: Path, stem: str) -> Path:
    available: list[tuple[int, Path]] = []
    for suffix in ("cld", "cvd"):
        path = directory / f"{stem}.{suffix}"
        try:
            info = path.lstat()
        except OSError:
            continue
        if stat.S_ISREG(info.st_mode) and info.st_size > 0 and os.access(path, os.R_OK):
            available.append((info.st_mtime_ns, path))
    if not available:
        raise RuntimeError(f"missing readable {stem}.cld/{stem}.cvd in {directory}")
    return max(available, key=lambda item: item[0])[1]


def inspect_definitions(directory: Path, now: float | None = None) -> DefinitionStatus:
    main = database_candidate(directory, "main")
    daily = database_candidate(directory, "daily")
    current_time = time.time() if now is None else now
    age = max(0, int(current_time - daily.stat().st_mtime))
    return DefinitionStatus(main=main, daily=daily, daily_age_seconds=age)


def require_fresh_definitions(
    directory: Path, max_age_seconds: int, now: float | None = None
) -> DefinitionStatus:
    status = inspect_definitions(directory, now=now)
    if status.daily_age_seconds > max_age_seconds:
        raise RuntimeError(
            "daily definitions are stale: "
            f"age={status.daily_age_seconds}s max={max_age_seconds}s"
        )
    return status
