#!/usr/bin/env python3
"""Run FreshClam immediately and then on a fixed retry-safe interval."""

from __future__ import annotations

import os
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

DEFINITIONS_DIR = Path(os.environ.get("DEFINITIONS_DIR", "/var/lib/clamav"))
UPDATE_INTERVAL_SECONDS = max(int(os.environ.get("UPDATE_INTERVAL_SECONDS", "21600")), 300)
FAILURE_RETRY_SECONDS = max(int(os.environ.get("FAILURE_RETRY_SECONDS", "300")), 30)
FRESHCLAM_BINARY = os.environ.get("FRESHCLAM_BINARY", "freshclam")

_stop = False


def _stop_handler(_signum: int, _frame: object) -> None:
    global _stop
    _stop = True


def _database_candidate(directory: Path, stem: str) -> Path | None:
    candidates: list[tuple[int, Path]] = []
    for suffix in ("cld", "cvd"):
        path = directory / f"{stem}.{suffix}"
        try:
            info = path.lstat()
        except OSError:
            continue
        if stat.S_ISREG(info.st_mode) and info.st_size > 0 and os.access(path, os.R_OK):
            candidates.append((info.st_mtime_ns, path))
    return max(candidates, default=(0, None), key=lambda item: item[0])[1]


def definitions_ready() -> bool:
    return _database_candidate(DEFINITIONS_DIR, "main") is not None and _database_candidate(
        DEFINITIONS_DIR, "daily"
    ) is not None


def run_update() -> bool:
    DEFINITIONS_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        FRESHCLAM_BINARY,
        f"--datadir={DEFINITIONS_DIR}",
        "--stdout",
        "--no-warnings",
    ]
    print(f"[freshclam] running update for {DEFINITIONS_DIR}", flush=True)
    try:
        completed = subprocess.run(command, check=False)
    except OSError as exc:
        print(f"[freshclam] could not start: {exc}", file=sys.stderr, flush=True)
        return False

    if completed.returncode == 0:
        print("[freshclam] update completed", flush=True)
        return True

    print(
        f"[freshclam] update failed with exit code {completed.returncode}",
        file=sys.stderr,
        flush=True,
    )
    return False


def interruptible_sleep(seconds: int) -> None:
    deadline = time.monotonic() + seconds
    while not _stop:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 1.0))


def main() -> int:
    signal.signal(signal.SIGTERM, _stop_handler)
    signal.signal(signal.SIGINT, _stop_handler)

    while not _stop:
        succeeded = run_update()
        if succeeded or definitions_ready():
            delay = UPDATE_INTERVAL_SECONDS
        else:
            delay = FAILURE_RETRY_SECONDS
            print(
                "[freshclam] no complete usable database exists; retrying soon",
                file=sys.stderr,
                flush=True,
            )
        interruptible_sleep(delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
