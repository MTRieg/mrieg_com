"""Database package helpers.

Expose connection and initialization helpers so callers can import
from `db` directly (e.g. `from db import connect, init_db`).

Keeping these exports here keeps call sites simple and makes the
`db` package a small explicit public surface.
"""

from .connections import connect, init_db, ensure_db

__all__ = ["connect", "init_db", "ensure_db"]
