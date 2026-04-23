from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

from tests.runtime_support import TEST_RUNTIME_ROOT_ENV, get_runtime_root


def main() -> int:
    backend_root = Path(__file__).resolve().parent
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    runtime_root = get_runtime_root()
    runtime_root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault(TEST_RUNTIME_ROOT_ENV, str(runtime_root))

    suite = unittest.defaultTestLoader.discover(
        start_dir=str(backend_root / "tests"),
        pattern="test_*.py",
        top_level_dir=str(backend_root),
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
