"""Validation and sanitization helpers.

This module provides lightweight input validation used by route handlers.
If you need stronger guarantees, replace these with project-specific rules.
"""
from typing import Any
import regex as re


# Allow: any Unicode letter/mark/number, spaces, plus a small, explicit set of name punctuation
# For extra protection against things like sql injection, although the code should be safe without this
VALID_NAME_RE = re.compile(r"^[\p{L}\p{M}\p{N} .'\-`’·]+$", flags=re.UNICODE)


def is_valid_name(s: str) -> bool:
	"""Return True if `s` is a reasonable name for players/games.

	- Strips and enforces a sensible maximum length.
	- Uses Unicode-aware character class matching.
	"""
	if not s:
		return False
	if (s.isspace() or s == "system"):
		return False
	s = s.strip()
	if len(s) == 0 or len(s) > 200:
		return False
	return bool(VALID_NAME_RE.match(s))


def sanitize_json(obj: Any, *, _depth: int = 0, _max_depth: int = 10) -> Any:
	"""Recursively sanitize an input JSON-like structure.

	- Rejects keys that start with '$' or contain '..' (basic prototype
	  pollution protection).
	- Enforces max depth to avoid excessive recursion.
	- Returns a cleaned structure containing only dict/list/primitives.
	"""
	if _depth > _max_depth:
		raise ValueError("Input too deeply nested")

	if isinstance(obj, dict):
		clean = {}
		for k, v in obj.items():
			if not isinstance(k, str):
				continue
			if k.startswith("$") or ".." in k:
				continue
			clean[k] = sanitize_json(v, _depth=_depth + 1, _max_depth=_max_depth)
		return clean
	elif isinstance(obj, list):
		return [sanitize_json(v, _depth=_depth + 1, _max_depth=_max_depth) for v in obj]
	elif isinstance(obj, (str, int, float, bool)) or obj is None:
		return obj
	else:
		# Unknown types are rejected
		raise ValueError("Unsupported JSON value type")

