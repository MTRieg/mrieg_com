"""Time utilities: timezone-aware helpers and ISO formatting/parsing.

These helpers keep code that deals with timestamps consistent across modules.
"""
from datetime import datetime, timezone
from typing import Optional
import zoneinfo


def now_utc() -> datetime:
	"""Return current UTC datetime with tzinfo set."""
	return datetime.now(timezone.utc)


def now_tz(tz_name: str) -> datetime:
	"""Return current datetime in the given timezone name (e.g. 'America/Toronto')."""
	try:
		tz = zoneinfo.ZoneInfo(tz_name)
	except Exception:
		tz = timezone.utc
	return datetime.now(tz)


def to_iso(dt: datetime) -> str:
	"""Serialize a datetime to ISO8601 string."""
	return dt.isoformat()


def parse_iso(s: str) -> Optional[datetime]:
	"""Parse an ISO8601 string into a timezone-aware datetime when possible.

	Returns None on obvious parse failures.
	"""
	if not s:
		return None
	try:
		# Python's fromisoformat handles most variants; tolerate trailing Z.
		if s.endswith("Z"):
			s = s[:-1] + "+00:00"
		return datetime.fromisoformat(s)
	except Exception:
		return None
