from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import event_writer
import freshclam_loop


class UpdateLoopTests(unittest.TestCase):
    def test_hung_freshclam_is_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with (
                patch.object(freshclam_loop, "DEFINITIONS_DIR", Path(temporary)),
                patch.object(freshclam_loop, "UPDATE_TIMEOUT_SECONDS", 60),
                patch.object(
                    freshclam_loop.subprocess,
                    "run",
                    side_effect=freshclam_loop.subprocess.TimeoutExpired("freshclam", 60),
                ),
            ):
                succeeded, message = freshclam_loop.run_update()
        self.assertFalse(succeeded)
        self.assertIn("60-second timeout", message)

    def test_success_exit_still_requires_complete_definitions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with (
                patch.object(freshclam_loop, "DEFINITIONS_DIR", directory),
                patch.object(
                    freshclam_loop.subprocess,
                    "run",
                    return_value=SimpleNamespace(returncode=0),
                ),
            ):
                succeeded, message = freshclam_loop.run_update()
            self.assertFalse(succeeded)
            self.assertIn("unusable", message)

    def test_success_requires_fresh_main_and_daily_databases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "main.cvd").write_bytes(b"main")
            (directory / "daily.cvd").write_bytes(b"daily")
            with (
                patch.object(freshclam_loop, "DEFINITIONS_DIR", directory),
                patch.object(
                    freshclam_loop.subprocess,
                    "run",
                    return_value=SimpleNamespace(returncode=0),
                ),
            ):
                succeeded, message = freshclam_loop.run_update()
            self.assertTrue(succeeded)
            self.assertIn("updated successfully", message)

    def test_failure_and_recovery_events_are_emitted(self) -> None:
        state: dict[str, object] = {}
        with (
            patch.object(freshclam_loop, "emit_event") as emit,
            patch.object(freshclam_loop, "definitions_stale", return_value=(True, 999)),
        ):
            freshclam_loop.report_result(False, "offline", state)
            freshclam_loop.report_result(True, "updated", state)
        event_types = [call.args[0] for call in emit.call_args_list]
        self.assertEqual(
            event_types,
            [
                "definitions_update_failed",
                "definitions_stale",
                "definitions_updated",
                "service_recovered",
            ],
        )
        self.assertFalse(state["degraded"])


class EventWriterTests(unittest.TestCase):
    def test_event_is_atomic_schema_v1_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with patch.object(event_writer, "EVENT_DIR", directory):
                destination = event_writer.emit_event(
                    "definitions_update_failed",
                    "warning",
                    "mirror unavailable",
                    action_success=False,
                )
            payload = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["service"], "clamav-defs-updater")
            self.assertEqual(payload["event_type"], "definitions_update_failed")
            self.assertEqual(list(directory.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
