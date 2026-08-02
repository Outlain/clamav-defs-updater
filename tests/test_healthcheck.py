from __future__ import annotations

import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "healthcheck.py"
spec = importlib.util.spec_from_file_location("defs_healthcheck", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class DefinitionHealthTests(unittest.TestCase):
    def test_accepts_complete_fresh_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "main.cvd").write_bytes(b"main")
            (directory / "daily.cld").write_bytes(b"daily")
            old_directory = module.DEFINITIONS_DIR
            old_age = module.MAX_DEFINITION_AGE_SECONDS
            module.DEFINITIONS_DIR = directory
            module.MAX_DEFINITION_AGE_SECONDS = 3600
            try:
                self.assertEqual(module.main(), 0)
            finally:
                module.DEFINITIONS_DIR = old_directory
                module.MAX_DEFINITION_AGE_SECONDS = old_age

    def test_rejects_stale_daily_database(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "main.cvd").write_bytes(b"main")
            daily = directory / "daily.cvd"
            daily.write_bytes(b"daily")
            old_time = time.time() - 7200
            os.utime(daily, (old_time, old_time))
            old_directory = module.DEFINITIONS_DIR
            old_age = module.MAX_DEFINITION_AGE_SECONDS
            module.DEFINITIONS_DIR = directory
            module.MAX_DEFINITION_AGE_SECONDS = 3600
            try:
                self.assertEqual(module.main(), 1)
            finally:
                module.DEFINITIONS_DIR = old_directory
                module.MAX_DEFINITION_AGE_SECONDS = old_age


if __name__ == "__main__":
    unittest.main()
