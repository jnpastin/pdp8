"""Add the project root to sys.path so test files can import pdp8_* modules."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
