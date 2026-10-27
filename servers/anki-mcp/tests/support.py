"""Shared test setup: puts src/ on sys.path."""
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SRC = TESTS.parent / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
