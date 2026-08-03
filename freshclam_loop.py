#!/usr/bin/env python3
"""Run the suite's only FreshClam writer and report durable status events."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from definition_status import inspect_definitions, require_fresh_definitions
from event_writer import emit_event

DEFINITIONS_DIR = Path(os.environ.get("DEFINITIONS_DIR", "/var/lib/clamav"))
STATE_DIR = Path(os.environ.get("STATE_DIR", "/state"))
STATE_FILE = STATE_DIR / "updater-state.json"
UPDATE_INTERVAL_SECONDS = max(int(os.environ.get("UPDATE_INTERVAL_SECONDS", "21600")), 300)
FAILURE_RETRY_SECONDS = max(int(os.environ.get("FAILURE_RETRY_SECONDS", "300")), 30)
UPDATE_TIMEOUT_SECONDS = max(int(os.environ.get("UPDATE_TIMEOUT_SECONDS", "1800")), 60)
MAX_DEFINITION_AGE_SECONDS = max(
    int(os.environ.get("MAX_DEFINITION_AGE_SECONDS", "172800")), 300
)
FRESHCLAM_BINARY = os.environ.get("FRESHCLAM_BINARY", "freshclam")

_stop = False


def _stop_handler(_signum: int, _frame: object) -> None:
    global _stop
    _stop = True


def load_state() -> dict[str, Any]:
    try:
        with STATE_FILE.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
        return {}


def save_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(mode=0o750, parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".updater-state-", dir=STATE_DIR)
    temporary = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            json.dump(state, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, STATE_FILE)
        directory_descriptor = os.open(STATE_DIR, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def definitions_stale() -> tuple[bool, int | None]:
    try:
        status = inspect_definitions(DEFINITIONS_DIR)
    except (OSError, RuntimeError):
        return True, None
    return status.daily_age_seconds > MAX_DEFINITION_AGE_SECONDS, status.daily_age_seconds


def run_update() -> tuple[bool, str]:
    DEFINITIONS_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        FRESHCLAM_BINARY,
        "--config-file=/etc/clamav/freshclam.conf",
        f"--datadir={DEFINITIONS_DIR}",
        "--stdout",
    ]
    print(f"[freshclam] running update for {DEFINITIONS_DIR}", flush=True)
    try:
        completed = subprocess.run(
            command, check=False, timeout=UPDATE_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired:
        return False, f"FreshClam exceeded the {UPDATE_TIMEOUT_SECONDS}-second timeout"
    except OSError as exc:
        return False, f"FreshClam could not start: {exc}"
    if completed.returncode == 0:
        try:
            status = require_fresh_definitions(
                DEFINITIONS_DIR, MAX_DEFINITION_AGE_SECONDS
            )
        except (OSError, RuntimeError) as exc:
            return False, f"FreshClam exited successfully but definitions are unusable: {exc}"
        return (
            True,
            f"ClamAV definitions updated successfully (daily age {status.daily_age_seconds}s)",
        )
    return False, f"FreshClam failed with exit code {completed.returncode}"


def report_result(succeeded: bool, message: str, state: dict[str, Any]) -> None:
    was_degraded = bool(state.get("degraded"))
    if succeeded:
        emit_event("definitions_updated", "info", message, action_success=True)
        if was_degraded:
            emit_event(
                "service_recovered",
                "info",
                "ClamAV definition updates recovered",
                action_success=True,
            )
        state.update({"degraded": False, "last_success": int(time.time())})
        print(f"[freshclam] {message}", flush=True)
        return

    print(f"[freshclam] {message}", file=sys.stderr, flush=True)
    emit_event(
        "definitions_update_failed",
        "warning",
        message,
        action_success=False,
    )
    stale, age = definitions_stale()
    if stale and not state.get("stale_reported"):
        stale_message = (
            "ClamAV definition database is incomplete"
            if age is None
            else f"ClamAV daily definitions are stale ({age} seconds old)"
        )
        emit_event(
            "definitions_stale",
            "critical",
            stale_message,
            action_success=False,
            definition_age_seconds=age,
        )
        state["stale_reported"] = True
    state.update({"degraded": True, "last_failure": int(time.time())})


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
    state = load_state()

    while not _stop:
        succeeded, message = run_update()
        if succeeded:
            state["stale_reported"] = False
        report_result(succeeded, message, state)
        save_state(state)
        interruptible_sleep(UPDATE_INTERVAL_SECONDS if succeeded else FAILURE_RETRY_SECONDS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
