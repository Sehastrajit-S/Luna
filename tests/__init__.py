"""Compatibility package for tests that import ``tests.*``.

The actual test modules live under ``utilities/tests``. This shim keeps
``npm run test:tools`` working when unittest discovery starts below that tree.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_UTILITIES_TESTS = _ROOT / "utilities" / "tests"

if _UTILITIES_TESTS.exists():
    __path__.append(str(_UTILITIES_TESTS))  # type: ignore[name-defined]
