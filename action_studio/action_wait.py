"""Bounded, cancellable readiness waits used by explicit Wait actions.

Checks are read-only: this module never clicks, changes focus, or types.
A condition must be true twice in succession to avoid transient UI states.
"""
from __future__ import annotations

import time
from typing import Callable


class ConditionTimeout(RuntimeError):
    pass


class ConditionCancelled(RuntimeError):
    pass


def wait_until_ready(
    check: Callable[[], bool],
    *,
    timeout: float,
    cancel: Callable[[], bool] = lambda: False,
    paused: Callable[[], bool] = lambda: False,
    poll: float = 0.12,
    stable_polls: int = 2,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    status: Callable[[bool], None] | None = None,
) -> None:
    """Wait for a stable UI condition without sending input.

    The timeout measures real running time; time spent paused does not count.
    Exceptions from `check` are intentionally propagated (for example
    unsupported native accessibility backend). Cancelling is checked even
    when paused, and the UI waiting indicator always clears on exit.
    """
    if not isinstance(timeout, (int, float)) or not 0 < timeout <= 120:
        raise ValueError("Wait timeout must be between 0 and 120 seconds")
    if poll <= 0 or not 1 <= stable_polls <= 10:
        raise ValueError("Invalid wait polling configuration")
    remaining = float(timeout)
    last = clock()
    successes = 0
    if status:
        status(True)
    try:
        while True:
            if cancel():
                raise ConditionCancelled("Playback stopped by user during Wait step")
            now = clock()
            if not paused():
                remaining -= max(0.0, now - last)
            last = now
            if paused():
                sleep(min(poll, 0.05))
                continue
            # A simulated (or real) clock cannot advance by a floating-point
            # remainder smaller than its resolution. Treat this as timed out
            # rather than busy-looping forever on a zero-progress sleep.
            if remaining <= 1e-6:
                raise ConditionTimeout("Wait condition was not met before its timeout")
            if check():
                successes += 1
                if successes >= stable_polls:
                    return
            else:
                successes = 0
            sleep(min(poll, remaining))
    finally:
        if status:
            status(False)


def contains_title(actual: str, expected: str) -> bool:
    """Case-insensitive title matching; never match the empty string."""
    return bool(expected and expected.strip() and
                expected.casefold() in (actual or "").casefold())
