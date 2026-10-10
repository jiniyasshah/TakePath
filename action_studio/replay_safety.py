"""Small, GUI-independent guardrails for desktop replay.

This module does not activate windows, log passwords, or dispatch input.
Callers may wait for the *same* target window to regain focus, but must
never change to another window simply because it happens to be foreground.
"""
from __future__ import annotations

import time
from typing import Callable


class ReplaySafetyError(RuntimeError):
    """Replay must stop instead of dispatching input into an uncertain target."""


def wait_for_target_window(
    expected: int,
    foreground: Callable[[], int],
    *,
    timeout: float = 2.0,
    cancelled: Callable[[], bool] = lambda: False,
    paused: Callable[[], bool] = lambda: False,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    poll: float = 0.05,
    status: Callable[[bool], None] | None = None,
) -> None:
    """Wait for the exact recorded window, aborting after a bounded timeout.

    This is intended for *between* actions and at playback start, not while
    holding a mouse button or injecting keystrokes. Paused time does not count
    toward the timeout. Status callbacks only indicate that focus is missing;
    they never activate a different window.
    """
    if not isinstance(expected, int) or expected <= 0:
        raise ReplaySafetyError("The original target window is unavailable.")
    if timeout < 0 or poll <= 0:
        raise ValueError("Invalid focus wait duration")
    deadline = clock() + timeout
    waiting = False
    try:
        while True:
            if cancelled():
                raise ReplaySafetyError("Playback stopped by user")
            if paused():
                before = clock()
                sleep(poll)
                deadline += max(0.0, clock() - before)
                continue
            if foreground() == expected:
                return
            if not waiting:
                waiting = True
                if status is not None:
                    status(True)
            remaining = deadline - clock()
            if remaining <= 0:
                raise ReplaySafetyError(
                    "The selected window did not regain focus in time. "
                    "Playback stopped without sending further input. "
                    "Return to the original window, then press Play again."
                )
            sleep(min(poll, remaining))
    finally:
        if waiting and status is not None:
            status(False)


def require_protected_field(get_status: Callable[[], str]) -> None:
    """Reject unknown/non-password destinations before inserting a secret.

    Do not include user-provided values in errors or logs. Detection can be
    imperfect for custom browser controls; failing closed is intentional.
    """
    try:
        state = get_status()
    except Exception:
        state = "unknown"
    if state != "protected":
        raise ReplaySafetyError(
            "Secure input blocked: a password field could not be verified "
            "at the playback destination. Focus the intended password field "
            "and retry; no password was sent to this unverified field."
        )
