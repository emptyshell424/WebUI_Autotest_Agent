from __future__ import annotations

import os
import shutil
import unittest
import uuid
from pathlib import Path

TEST_RUNTIME_ROOT_ENV = "AUTOTEST_TEST_RUNTIME_ROOT"


def get_runtime_root() -> Path:
    configured_root = os.getenv(TEST_RUNTIME_ROOT_ENV)
    if configured_root:
        return Path(configured_root)
    return Path(__file__).resolve().parents[2] / ".tmp" / "test-runtimes"


class RuntimeWorkspaceTestCase(unittest.TestCase):
    def create_temp_dir(self, prefix: str) -> Path:
        runtime_root = get_runtime_root()
        runtime_root.mkdir(parents=True, exist_ok=True)
        temp_dir = runtime_root / f"{prefix}-{uuid.uuid4().hex[:8]}"
        temp_dir.mkdir(parents=True, exist_ok=False)
        self.addCleanup(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return temp_dir
