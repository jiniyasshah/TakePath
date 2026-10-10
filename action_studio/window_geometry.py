"""Map recorded screen-space actions to the current target window geometry.

Input project actions remain immutable during replay. Never apply the mapping
to screen-wide recordings or projects without a valid recorded window anchor.
"""
from __future__ import annotations

from dataclasses import replace
from math import isfinite

from .core import Action


def valid_rect(value) -> bool:
    return (
        isinstance(value, (list, tuple)) and len(value) == 4
        and all(isinstance(n, (int, float)) and isfinite(n) for n in value)
        and 0 < value[2] <= 100000 and 0 < value[3] <= 100000
        and abs(value[0]) <= 100000 and abs(value[1]) <= 100000
    )


def remap_point(x: float, y: float, source, target) -> tuple[int, int]:
    """Preserve relative position within the window, including negative origins."""
    if not valid_rect(source) or not valid_rect(target):
        raise ValueError("Window geometry is unavailable for coordinate mapping")
    sx = target[2] / source[2]
    sy = target[3] / source[3]
    # A drastic layout change is likely a different window/state. Do not
    # blindly send potentially destructive clicks using this guessed mapping.
    if not (0.35 <= sx <= 2.5 and 0.35 <= sy <= 2.5):
        raise ValueError("Target window size changed too much for safe replay. Adjust the window or re-record.")
    return (round(target[0] + (x - source[0]) * sx),
            round(target[1] + (y - source[1]) * sy))


def remap_action(action: Action, source, target) -> Action:
    """Return a copy with transformed pointer points and original mouse path."""
    if action.kind not in ("click", "drag", "scroll"):
        return action
    x, y = remap_point(action.x, action.y, source, target)
    end_x, end_y = (remap_point(action.end_x, action.end_y, source, target)
                    if action.kind == "drag" else (action.end_x, action.end_y))
    path = [[*remap_point(point[0], point[1], source, target), point[2]]
            for point in action.raw_path]
    return replace(action, x=x, y=y, end_x=end_x, end_y=end_y, raw_path=path)
