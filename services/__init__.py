"""Services package: long-running or CPU-bound services used by the app.

Import submodules to make them available as `services.game_simulation`,
etc. Implementations may be added incrementally.
"""

from .game_simulation import (
	advance_simulation,
	run_js_simulation,
	simulate_and_replace,
	simulate_turn_if_ready,
)

__all__ = [
	"advance_simulation",
	"run_js_simulation",
	"simulate_and_replace",
	"simulate_turn_if_ready",
]
