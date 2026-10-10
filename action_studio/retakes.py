"""In-memory recovery for successive takes. Never writes secrets to disk."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from .core import Project


@dataclass
class PreviousTake:
    project: Project
    path: Path | None
    dirty: bool
    session_secrets: dict
    target_hwnd: int = 0


class RetakeHistory:
    """One-step undo of a completed retake, scoped to the current app process."""
    def __init__(self):
        self._previous: PreviousTake | None = None

    @property
    def available(self) -> bool:
        return self._previous is not None

    def capture(self, project: Project, path: Path | None, dirty: bool, secrets: dict, target_hwnd: int = 0):
        self._previous = PreviousTake(deepcopy(project), path, bool(dirty), dict(secrets), int(target_hwnd))

    def restore(self) -> PreviousTake:
        if self._previous is None:
            raise ValueError('No previous take to restore')
        result = self._previous
        self._previous = None
        return result

    def clear(self):
        self._previous = None
