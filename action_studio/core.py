"""Data model, grouped typing, motion processing, and project JSON.

Pure Python for unit testing without Windows hooks or a GUI.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
from pathlib import Path
import uuid

KINDS = {"click", "type", "key", "scroll", "drag", "secure_input"}
MODES = {"original", "smooth", "straight", "gentle"}
TEXT_MODES = {"human", "instant", "original", "smooth"}
GLOBAL_TYPING_MODES = {"original", "smooth", "instant"}
SECURE_MODES = {"auto", "manual", "skip"}
MAX_ACTIONS = 12000
MAX_POINTS = 450
MAX_TEXT = 16000


@dataclass
class Action:
    kind: str
    delay: float = 0.5
    enabled: bool = True
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    x: int = 0
    y: int = 0
    end_x: int = 0
    end_y: int = 0
    button: str = "left"
    text: str = ""
    key: str = "enter"
    dx: int = 0
    dy: int = 0
    path_mode: str = "smooth"
    path_duration: float = 0.32
    raw_path: list[list[float]] = field(default_factory=list)
    typing_mode: str = "human"
    char_delay: float = 0.055
    char_timings: list[float] = field(default_factory=list)  # Non-secret relative typing rhythm
    secure_mode: str = "auto"       # auto, manual or skip; never a password
    secure_ref: str = ""             # Opaque reference to Windows Credential Manager

    @classmethod
    def from_dict(cls, obj: dict) -> 'Action':
        if not isinstance(obj, dict) or obj.get("kind") not in KINDS:
            raise ValueError("Unsupported action type")
        defaults = cls(kind=obj["kind"])
        for key in vars(defaults):
            if key in obj:
                setattr(defaults, key, obj[key])
        defaults.delay = finite_range(defaults.delay, 0, 600)
        defaults.path_duration = finite_range(defaults.path_duration, 0, 20)
        defaults.char_delay = finite_range(defaults.char_delay, 0, 2)
        defaults.enabled = bool(defaults.enabled)
        defaults.id = str(defaults.id)[:80]
        defaults.path_mode = defaults.path_mode if defaults.path_mode in MODES else "smooth"
        defaults.typing_mode = defaults.typing_mode if defaults.typing_mode in TEXT_MODES else "human"
        defaults.secure_mode = defaults.secure_mode if isinstance(defaults.secure_mode, str) and defaults.secure_mode in SECURE_MODES else "auto"
        from .secure_store import valid_reference
        defaults.secure_ref = defaults.secure_ref if valid_reference(defaults.secure_ref) else ""
        defaults.button = defaults.button if defaults.button in {"left", "right", "middle", "x1", "x2"} else "left"
        for attr in ("x", "y", "end_x", "end_y", "dx", "dy"):
            value = getattr(defaults, attr)
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"Invalid {attr}")
            setattr(defaults, attr, max(-100000, min(100000, int(value))))
        # A protected-input marker never carries a plaintext secret, even when
        # importing untrusted or hand-edited project JSON.
        defaults.text = "" if defaults.kind == "secure_input" else str(defaults.text)[:MAX_TEXT]
        defaults.key = "enter" if defaults.kind == "secure_input" else str(defaults.key)[:120]
        if not isinstance(defaults.raw_path, list):
            raise ValueError("Invalid mouse path")
        path = []
        for point in defaults.raw_path[:MAX_POINTS]:
            if not isinstance(point, (list, tuple)) or len(point) != 3:
                continue
            if all(isinstance(v, (int, float)) and math.isfinite(v) for v in point):
                path.append([float(point[0]), float(point[1]), max(0.0, float(point[2]))])
        defaults.raw_path = path
        if defaults.kind == "secure_input":
            defaults.char_timings = []  # Never retain timing or length of a protected field.
        elif isinstance(defaults.char_timings, list):
            defaults.char_timings = [min(60.0, max(0.0, float(v))) for v in defaults.char_timings[:MAX_TEXT]
                                     if isinstance(v, (int, float)) and math.isfinite(v)]
        else:
            defaults.char_timings = []
        return defaults

    def label(self) -> str:
        if self.kind == "click":
            return f"{ {'x1': 'Back', 'x2': 'Forward'}.get(self.button, self.button.title())} click at {self.x}, {self.y}"
        if self.kind == "secure_input":
            return {"auto": "Protected input · auto-fill", "manual": "Protected input · manual entry", "skip": "Protected input · skip"}.get(self.secure_mode, "Secure input")
        if self.kind == "type":
            shortened = self.text.replace("\n", " ↵ ")
            return shortened[:64] + ("…" if len(shortened) > 64 else "") or "(empty text)"
        if self.kind == "key":
            return self.key.replace("+", " + ").title()
        if self.kind == "scroll":
            return f"Scroll {self.dy:+d} vertical / {self.dx:+d} horizontal"
        return f"Drag {self.x},{self.y} → {self.end_x},{self.end_y}"


def finite_range(v: object, low: float, high: float) -> float:
    if not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError("Invalid numeric value")
    return min(high, max(low, float(v)))


@dataclass
class Project:
    name: str = "Untitled workflow"
    target_title: str = ""
    screen_size: list[int] = field(default_factory=lambda: [1920, 1080])
    screen_bounds: list[int] = field(default_factory=lambda: [0, 0, 1920, 1080])
    actions: list[Action] = field(default_factory=list)
    cursor_mode: str = "smooth"  # Global; keep original paths.
    global_typing_mode: str = "smooth"  # Original rhythm, smooth constant, instant.
    target_mode: str = "window"  # window: scoped to chosen app; screen: across foreground apps
    preview_jpeg: str = ""       # Optional local, window-scoped still image; not video.
    preview_bounds: list[int] = field(default_factory=lambda: [0, 0, 1920, 1080])

    def to_dict(self) -> dict:
        return {"schema": 2, "name": self.name, "target_title": self.target_title,
                "screen_size": self.screen_size, "screen_bounds": self.screen_bounds,
                "cursor_mode": self.cursor_mode, "global_typing_mode": self.global_typing_mode,
                "target_mode": self.target_mode, "preview_jpeg": self.preview_jpeg,
                "preview_bounds": self.preview_bounds, "actions": [
                    ({**asdict(a), "text": "", "key": "enter", "char_timings": []} if a.kind == "secure_input" else asdict(a))
                    for a in self.actions]}

    @classmethod
    def from_dict(cls, value: dict) -> 'Project':
        if not isinstance(value, dict) or value.get("schema") not in (1, 2):
            raise ValueError("Unrecognized project version")
        actions = value.get("actions", [])
        if not isinstance(actions, list) or len(actions) > MAX_ACTIONS:
            raise ValueError("Invalid number of actions")
        screen = value.get("screen_size", [1920, 1080])
        if not isinstance(screen, list) or len(screen) != 2 or any(
            not isinstance(v, int) or v <= 0 or v > 100000 for v in screen
        ):
            screen = [1920, 1080]
        bounds = value.get("screen_bounds", [0, 0, *screen])
        if not isinstance(bounds, list) or len(bounds) != 4 or any(
            not isinstance(v, int) or abs(v) > 100000 for v in bounds
        ) or bounds[2] <= 0 or bounds[3] <= 0:
            bounds = [0, 0, *screen]
        preview_bounds = value.get("preview_bounds", bounds)
        if not isinstance(preview_bounds, list) or len(preview_bounds) != 4 or any(
            not isinstance(v, int) or abs(v) > 100000 for v in preview_bounds
        ) or preview_bounds[2] <= 0 or preview_bounds[3] <= 0:
            preview_bounds = bounds
        preview = value.get("preview_jpeg", "")
        if not isinstance(preview, str) or len(preview) > 10_000_000:
            preview = ""
        mode = value.get("cursor_mode", "smooth")
        if mode not in MODES:
            mode = "smooth"
        global_typing = value.get('global_typing_mode', 'smooth')
        if global_typing not in GLOBAL_TYPING_MODES:
            global_typing = 'smooth'
        return cls(name=str(value.get("name", "Untitled workflow"))[:160],
                   target_title=str(value.get("target_title", ""))[:500],
                   screen_size=screen, screen_bounds=bounds, actions=[Action.from_dict(a) for a in actions],
                   cursor_mode=mode, global_typing_mode=global_typing, target_mode=value.get("target_mode", "window") if value.get("target_mode", "window") in ("window", "screen") else "window", preview_jpeg=preview, preview_bounds=preview_bounds)


def remove_actions(actions: list[Action], selected_ids: set[str]) -> list[Action]:
    """Delete all selected IDs in one operation while preserving remaining order."""
    return [action for action in actions if action.id not in selected_ids]


def save_project(project: Project, dest: str | Path):
    path = Path(dest)
    # Atomic save so power loss does not truncate an existing project.
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(project.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def load_project(src: str | Path) -> Project:
    path = Path(src)
    if path.stat().st_size > 15 * 1024 * 1024:
        raise ValueError("This project is too large to open")
    return Project.from_dict(json.loads(path.read_text(encoding="utf-8")))


def simplified_path(points: list[list[float]], epsilon: float = 2.0) -> list[list[float]]:
    """Reduce cursor samples while preserving significant turns."""
    if len(points) <= 2:
        return list(points)
    start, end = points[0], points[-1]
    vx, vy = end[0] - start[0], end[1] - start[1]
    length = vx * vx + vy * vy
    best, idx = 0.0, 0
    for i in range(1, len(points) - 1):
        pt = points[i]
        if length == 0:
            dist = math.dist(pt[:2], start[:2])
        else:
            projection = max(0, min(1, ((pt[0] - start[0]) * vx + (pt[1] - start[1]) * vy) / length))
            dist = math.hypot(pt[0] - (start[0] + projection * vx),
                              pt[1] - (start[1] + projection * vy))
        if dist > best:
            best, idx = dist, i
    if best > epsilon:
        return simplified_path(points[:idx + 1], epsilon)[:-1] + simplified_path(points[idx:], epsilon)
    return [start, end]


def anchor_original_path(path: list[list[float]], start: tuple[int, int]):
    """Yield original-time path coordinates without warping to old start point.

    Progressively blend the recorded displacement from the current cursor to
    the true recorded target. This preserves the overall recorded trajectory
    while respecting a centered mouse at replay start.
    """
    if len(path) < 2:
        return
    offset_x=start[0]-path[0][0]
    offset_y=start[1]-path[0][1]
    span=max(0.001,path[-1][2]-path[0][2])
    for x,y,stamp in path[1:]:
        progress=min(1.0,max(0.0,(stamp-path[0][2])/span))
        yield (round(x+offset_x*(1.0-progress)),
               round(y+offset_y*(1.0-progress)),stamp)


def interpolate_path(start: tuple[int, int], end: tuple[int, int], steps: int = 24):
    """Generate an eased gently curved cursor path with fixed endpoints."""
    steps = max(2, steps)
    dx, dy = end[0] - start[0], end[1] - start[1]
    # Subtle, predictable clean path. Keep endpoints fixed, with no target shift.
    cx = (start[0] + end[0]) / 2 - dy * 0.09
    cy = (start[1] + end[1]) / 2 + dx * 0.09
    for i in range(1, steps + 1):
        t = i / steps
        t = t * t * (3 - 2 * t)
        a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t * t
        yield (round(a * start[0] + b * cx + c * end[0]),
               round(a * start[1] + b * cy + c * end[1]))


class ActionBuilder:
    """Convert event callbacks into coherent edits with original path data.

    Input methods are called serially by a lock in RecordingEngine.
    """
    def __init__(self):
        self.actions: list[Action] = []
        self.last_time = 0.0
        self.move_points: list[list[float]] = []
        self.pending_text = ""
        self.pending_timings = []
        self.text_start = 0.0
        self.text_last = 0.0
        self.text_active = False
        self.drag_start: tuple[int, int, float] | None = None
        self.drag_points: list[list[float]] = []
        self.secure_active = False

    def _append(self, action: Action, stamp: float):
        action.delay = round(max(0, stamp - self.last_time), 3)
        self.actions.append(action)
        self.last_time = stamp

    def flush_text(self):
        if self.text_active:
            if self.pending_text:
                self._append(Action(kind="type", text=self.pending_text, char_timings=self.pending_timings[:]), self.text_start)
                # Recorded typing already occupies time; next delay is measured from final key.
                self.last_time = max(self.last_time, self.text_last)
            self.pending_text = ""
            self.pending_timings = []
            self.text_active = False

    def protected_input(self, stamp: float):
        """Record presence of a password-field interaction, not its keystrokes.

        One marker represents a contiguous focused protected-input session.
        No character values, lengths, key presses, or plaintext are retained.
        """
        self.flush_text()
        if not self.secure_active:
            self._append(Action(kind="secure_input"), stamp)
            self.secure_active = True

    def leave_protected_input(self):
        self.secure_active = False

    def char(self, ch: str, stamp: float):
        if not ch:
            return
        if self.text_active and stamp - self.text_last > 1.3:
            self.flush_text()
        if not self.text_active:
            self.text_active = True
            self.text_start = stamp
            self.pending_text = ""
            self.pending_timings = []
        self.pending_text += ch
        self.pending_timings.extend([round(max(0, stamp-self.text_start),3)] * len(ch))
        self.text_last = stamp

    def backspace(self, stamp: float):
        if self.text_active and stamp - self.text_last <= 1.3 and self.pending_text:
            self.pending_text = self.pending_text[:-1]
            self.pending_timings = self.pending_timings[:-1]
            self.text_last = stamp
        else:
            self.key("backspace", stamp)

    def key(self, key: str, stamp: float):
        self.flush_text()
        self._append(Action(kind="key", key=key), stamp)

    def move(self, x: int, y: int, stamp: float):
        if self.drag_start:
            if not self.drag_points or stamp - self.drag_points[-1][2] > 0.014:
                self.drag_points.append([x, y, stamp])
            return
        if not self.move_points or (
            stamp - self.move_points[-1][2] > 0.018 and
            math.hypot(x - self.move_points[-1][0], y - self.move_points[-1][1]) >= 3
        ):
            self.move_points.append([x, y, stamp])
        if len(self.move_points) > 500:
            self.move_points = self.move_points[::2]

    def mouse_down(self, x: int, y: int, stamp: float):
        self.flush_text()
        self.leave_protected_input()
        self.drag_start = (x, y, stamp)
        self.drag_points = [[x, y, stamp]]

    def mouse_up(self, x: int, y: int, button: str, stamp: float):
        if not self.drag_start:
            return
        sx, sy, press_stamp = self.drag_start
        self.drag_start = None
        self.drag_points.append([x, y, stamp])
        moved = math.hypot(x - sx, y - sy) >= 12
        if moved:
            # Path covers cursor motion while button held down.
            path = self._export_path(self.drag_points, self.drag_points[0][2])
            action = Action(kind="drag", x=sx, y=sy, end_x=x, end_y=y,
                            button=button, raw_path=path,
                            path_duration=round(min(10.0, stamp - press_stamp), 3))
        else:
            points = self.move_points + [[sx, sy, press_stamp]]
            action = Action(kind="click", x=x, y=y, button=button,
                            raw_path=self._export_path(points, points[0][2]) if points else [],
                            path_duration=min(1.5, max(0.16, press_stamp - self.last_time)))
        # Store delay before cursor movement; subtract recorded cursor travel time.
        if action.kind == "click":
            travel = min(action.path_duration, max(0, press_stamp - self.last_time))
            action.delay = round(max(0, press_stamp - self.last_time - travel), 3)
            self.actions.append(action)
            self.last_time = stamp
        else:
            self._append(action, press_stamp)
            self.last_time = stamp
        self.drag_points = []
        self.move_points = []

    @staticmethod
    def _export_path(points: list[list[float]], origin: float) -> list[list[float]]:
        return [[int(p[0]), int(p[1]), round(max(0, p[2] - origin), 3)]
                for p in simplified_path(points[-450:], 2.5)]

    def scroll(self, x: int, y: int, dx: int, dy: int, stamp: float):
        self.flush_text()
        if (self.actions and self.actions[-1].kind == "scroll"
            and stamp - self.last_time < 0.23
            and (dy == 0 or self.actions[-1].dy * dy >= 0)
            and (dx == 0 or self.actions[-1].dx * dx >= 0)):
            self.actions[-1].dx += dx
            self.actions[-1].dy += dy
            self.last_time = stamp
        else:
            self._append(Action(kind="scroll", x=x, y=y, dx=dx, dy=dy), stamp)
        self.move_points = []

    def finish(self) -> list[Action]:
        self.flush_text()
        return self.actions
