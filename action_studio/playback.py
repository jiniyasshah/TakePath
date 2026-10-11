"""Interactive, stoppable playback in a worker thread."""
from __future__ import annotations

import ctypes
import math
import sys
import threading
import time
from PySide6.QtCore import QThread, Signal
from .core import Action, interpolate_path, anchor_original_path, MOUSE_SPEED_FACTORS, effective_mouse_speed
from .recorder import foreground, center_cursor
from .platform_api import window_pid, supported, focus_status, title_of, named_control_available, window_rect
from .window_geometry import remap_action, valid_rect
from .adaptive_ready import wait_for_visual_settle, sample_window_thumbnail, VisualSettlingInterrupted
from .action_wait import wait_until_ready, contains_title, ConditionCancelled, ConditionTimeout
from .replay_safety import ReplaySafetyError, wait_for_target_window, require_protected_field


def send_side_button(button: str, pressed: bool):
    """Replay Windows auxiliary mouse buttons (XBUTTON1=Back, XBUTTON2=Forward).

    PyAutoGUI may reject auxiliary names, so send genuine Win32 X-button
    events using SendInput instead. This runs only on Windows.
    """
    if sys.platform != 'win32':
        # Side-button support depends on the OS and input backend.
        from pynput.mouse import Controller, Button
        key = getattr(Button, button, None)
        if key is None:
            raise RuntimeError(f'{button} mouse button is not supported by this backend')
        mouse = Controller()
        (mouse.press if pressed else mouse.release)(key)
        return
    from ctypes import wintypes as wt
    class MOUSEINPUT(ctypes.Structure):
        _fields_=[('dx',wt.LONG),('dy',wt.LONG),('mouseData',wt.DWORD),
                  ('dwFlags',wt.DWORD),('time',wt.DWORD),('dwExtraInfo',ctypes.c_size_t)]
    class KEYBDINPUT(ctypes.Structure):
        _fields_=[('wVk',wt.WORD),('wScan',wt.WORD),('dwFlags',wt.DWORD),
                  ('time',wt.DWORD),('dwExtraInfo',ctypes.c_size_t)]
    class HARDWAREINPUT(ctypes.Structure):
        _fields_=[('uMsg',wt.DWORD),('wParamL',wt.WORD),('wParamH',wt.WORD)]
    class INPUTUNION(ctypes.Union):
        _fields_=[('mi',MOUSEINPUT),('ki',KEYBDINPUT),('hi',HARDWAREINPUT)]
    class INPUT(ctypes.Structure):
        _fields_=[('type',wt.DWORD),('data',INPUTUNION)]
    if button not in ('x1','x2'):
        raise ValueError(f'Not an auxiliary mouse button: {button}')
    mouse_data=1 if button=='x1' else 2
    flags=0x0080 if pressed else 0x0100  # MOUSEEVENTF_XDOWN / MOUSEEVENTF_XUP
    event=INPUT(type=0,data=INPUTUNION(mi=MOUSEINPUT(0,0,mouse_data,flags,0,0)))
    if ctypes.windll.user32.SendInput(1,ctypes.byref(event),ctypes.sizeof(event))!=1:
        raise RuntimeError(f'Windows rejected {button} mouse event')


def press_mouse(button: str):
    if button in ('x1','x2'):
        send_side_button(button,True)
    else:
        import pyautogui as pg
        pg.mouseDown(button=button)


def release_mouse(button: str):
    if button in ('x1','x2'):
        send_side_button(button,False)
    else:
        import pyautogui as pg
        pg.mouseUp(button=button)


class Stopped(Exception):
    pass


class Player(QThread):
    progress = Signal(int)
    finished_result = Signal(str)
    paused_signal = Signal(bool)
    secure_input_requested = Signal()
    focus_waiting = Signal(bool)
    readiness_waiting = Signal(bool)
    adaptive_waiting = Signal(bool)

    def __init__(self, actions: list[Action], target_hwnd: int, speed: float = 1.0,
                 cursor_mode: str = "smooth", center_at_start: bool = False,
                 parent=None, target_mode: str = "window", secure_values: dict[str, str] | None = None,
                 typing_mode: str = "smooth", screen_bounds: list[int] | None = None,
                 recorded_window_bounds: list[int] | None = None, adaptive_wait: bool = False,
                 mouse_speed_mode: str = "normal"):
        super().__init__(parent)
        self.actions = actions
        self.target_hwnd = target_hwnd
        self.target_mode = "screen" if target_mode == "screen" else "window"
        self.speed = max(0.25, min(4, speed))
        self.mouse_speed_mode = mouse_speed_mode if mouse_speed_mode in MOUSE_SPEED_FACTORS else "normal"
        self.cursor_mode = cursor_mode if cursor_mode in ("smooth", "original", "straight", "gentle") else "smooth"
        self.typing_mode = typing_mode if typing_mode in ("original", "smooth", "instant") else "smooth"
        self.center_at_start = center_at_start
        self.screen_bounds = list(screen_bounds) if screen_bounds else None
        self.recorded_window_bounds = list(recorded_window_bounds) if valid_rect(recorded_window_bounds) else None
        self.adaptive_wait = bool(adaptive_wait)
        self.began_at = 0.0
        self.paused_at = 0.0
        self.pause_accumulated = 0.0
        self.abort = threading.Event()
        self.pause_flag = threading.Event()
        self.key_guard = None
        self.awaiting_secure_input = False
        self.secure_values = dict(secure_values or {})

    def cancel(self):
        self.abort.set()
        self.pause_flag.clear()

    def toggle_pause(self):
        if self.pause_flag.is_set():
            self.pause_flag.clear()
            self.awaiting_secure_input = False
            if self.paused_at:
                self.pause_accumulated += time.monotonic() - self.paused_at
                self.paused_at = 0.0
            self.paused_signal.emit(False)
            return False
        self.pause_flag.set()
        self.paused_at = time.monotonic()
        self.paused_signal.emit(True)
        return True

    def _wait(self, seconds: float, *, recover_focus: bool = False):
        elapsed = 0.0
        while elapsed < seconds:
            if self.abort.is_set():
                raise Stopped("Playback stopped by user")
            if self.pause_flag.is_set():
                time.sleep(0.04)
                continue
            self._guard(recover_focus=recover_focus)
            chunk = min(0.025, seconds - elapsed)
            time.sleep(chunk)
            elapsed += chunk

    def _guard(self, *, recover_focus: bool = False):
        if self.abort.is_set():
            raise Stopped("Playback stopped by user")
        if self.target_mode == "window":
            active = foreground()
            # Strict window identity protects against injecting edited text or
            # secrets into the wrong window of the same application.
            if active != self.target_hwnd:
                if recover_focus:
                    try:
                        wait_for_target_window(
                            self.target_hwnd, foreground, timeout=2.0,
                            cancelled=self.abort.is_set, paused=self.pause_flag.is_set,
                            status=self.focus_waiting.emit,
                        )
                    except ReplaySafetyError as exc:
                        raise Stopped(str(exc)) from exc
                else:
                    raise Stopped(
                        "The selected window lost focus during an action. "
                        "Playback stopped to protect other applications."
                    )
        else:
            # Screen mode can intentionally switch between Windows applications.
            # Never type into our own editor if it takes foreground unexpectedly.
            import os
            hwnd = foreground()
            if not hwnd or not window_pid(hwnd) or window_pid(hwnd) == os.getpid():
                raise Stopped("Studio window received focus; screen replay stopped for safety.")

    def _move(self, x: int, y: int):
        import pyautogui as pg
        self._guard()
        pg.moveTo(x, y, duration=0)

    def _straight_move(self, x: int, y: int, duration: float):
        """Straight linear travel with a gentle ease-in/out, no curve."""
        import pyautogui as pg
        start = pg.position()
        count = max(2, min(90, int(duration * 70)))
        for i in range(1, count+1):
            t = i/count
            t = t*t*(3-2*t)
            self._move(round(start.x+(x-start.x)*t), round(start.y+(y-start.y)*t))
            self._wait(duration/count/self.speed)

    def _gentle_move(self, x: int, y: int, duration: float):
        """Near-straight subtle curved path, slower acceleration."""
        import pyautogui as pg
        start = pg.position()
        dx,dy=x-start.x,y-start.y
        count = max(2,min(90,int(duration*70)))
        for i in range(1,count+1):
            t=i/count
            ease=t*t*t*(t*(6*t-15)+10)
            bend=math.sin(math.pi*t)*0.035
            self._move(round(start.x+dx*ease-dy*bend),round(start.y+dy*ease+dx*bend))
            self._wait(duration/count/self.speed)

    def _smooth_move(self, x: int, y: int, duration: float):
        import pyautogui as pg
        start = pg.position()
        points = list(interpolate_path((start.x, start.y), (x, y), max(2, min(70, int(duration * 65)))))
        for px, py in points:
            self._guard()
            self._move(px, py)
            self._wait(duration / len(points) / self.speed)

    def _original_move(self, path: list[list[float]], dest: tuple[int, int], duration: float):
        if len(path) < 2:
            return self._smooth_move(*dest, duration)
        # Never teleport to an old recorded screen position. In particular,
        # doing so undoes Center before replay and often jumps to the dock.
        # Keep the original path shape, anchored at the actual current cursor,
        # and taper the start offset to zero at the exact action destination.
        import pyautogui as pg
        initial = pg.position()
        span = max(0.001, path[-1][2] - path[0][2])
        prev = path[0][2]
        for x, y, stamp in anchor_original_path(path, (initial.x, initial.y)):
            self._wait((max(0, stamp - prev) / span) * duration / self.speed)
            self._move(x, y)
            prev = stamp
        self._move(*dest)

    def _mouse_duration(self, duration: float, *, dragging: bool = False,
                        action: Action | None = None) -> float:
        # Resolve an individual action's speed override only for mouse
        # actions. Keep delays, typing and fixed Wait steps unchanged.
        mode = (effective_mouse_speed(action, self.mouse_speed_mode)
                if action is not None else self.mouse_speed_mode)
        seconds = max(0.0, float(duration)) * MOUSE_SPEED_FACTORS[mode]
        return max(0.06, seconds) if dragging else seconds

    def _cursor(self, a: Action, x: int, y: int, *, dragging: bool = False):
        duration = self._mouse_duration(a.path_duration, dragging=dragging, action=a)
        if duration == 0:
            self._move(x, y)
            return
        if self.cursor_mode == "original" and a.raw_path:
            self._original_move(a.raw_path, (x, y), duration)
        elif self.cursor_mode == "straight":
            self._straight_move(x, y, duration)
        elif self.cursor_mode == "gentle":
            self._gentle_move(x, y, duration)
        else:
            self._smooth_move(x, y, duration)

    def _unicode_type(self, text: str, char_delay: float, *, protected: bool = False):
        """Send UTF-16 Unicode keystrokes without modifying clipboard."""
        if sys.platform != 'win32':
            from pynput.keyboard import Controller
            keyboard = Controller()
            for char in text:
                self._guard()
                if protected:
                    require_protected_field(focus_status)
                keyboard.type(char)
                if char_delay:
                    self._wait(char_delay / self.speed)
            return
        import ctypes.wintypes as wt
        ULONG_PTR = wt.WPARAM
        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                        ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]
        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                        ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]
        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [("uMsg", wt.DWORD), ("wParamL", wt.WORD), ("wParamH", wt.WORD)]
        class U(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]
        class INPUT(ctypes.Structure):
            _fields_ = [("type", wt.DWORD), ("union", U)]
        send = ctypes.windll.user32.SendInput
        raw = text.encode('utf-16-le')
        for index in range(0, len(raw), 2):
            self._guard()
            if protected:
                require_protected_field(focus_status)
            scancode = raw[index] | (raw[index + 1] << 8)
            for flags in (0x0004, 0x0004 | 0x0002):
                inp = INPUT(type=1, union=U(ki=KEYBDINPUT(0, scancode, flags, 0, 0)))
                if send(1, ctypes.byref(inp), ctypes.sizeof(inp)) != 1:
                    raise RuntimeError("Windows rejected a Unicode keystroke")
            if char_delay:
                self._wait(char_delay / self.speed)

    def _recorded_type(self, text: str, timings: list[float], smooth_delay: float):
        """Honor recorded timing when it still matches the edited text."""
        if len(timings) != len(text) or not timings:
            return self._unicode_type(text, smooth_delay)
        previous=timings[0]
        for i,ch in enumerate(text):
            if i:
                self._wait(min(4.0,max(0.0,timings[i]-previous))/self.speed)
                previous=timings[i]
            self._unicode_type(ch, 0)

    def _protected_input(self):
        """Pause the workflow for manual password entry, without storing it."""
        self.awaiting_secure_input = True
        self.pause_flag.set()
        self.paused_at = time.monotonic()
        self.secure_input_requested.emit()
        self.paused_signal.emit(True)
        while self.pause_flag.is_set():
            if self.abort.is_set():
                raise Stopped("Playback stopped by user")
            time.sleep(0.04)
        self.awaiting_secure_input = False
        # Continue only when the target app has focus again.
        self._guard()

    def _readiness_check(self, a: Action) -> bool:
        if a.wait_mode == "target_title":
            self._guard()
            return contains_title(title_of(self.target_hwnd), a.wait_value)
        if a.wait_mode == "active_title":
            self._guard()
            return contains_title(title_of(foreground()), a.wait_value)
        self._guard()
        if a.wait_mode == "focused_safe":
            return focus_status() == "safe"
        if a.wait_mode == "focused_protected":
            return focus_status() == "protected"
        if a.wait_mode == "control_name":
            return named_control_available(a.wait_value)
        raise RuntimeError("Unknown Wait condition")

    def _run_wait_action(self, a: Action):
        if a.wait_mode == "duration":
            # The duration is handled once in _action; never add a
            # second timeout or ask for a window/control name.
            return
        if a.wait_mode in ("target_title", "active_title", "control_name") and not a.wait_value.strip():
            raise RuntimeError("Wait condition needs a window or control name")
        try:
            wait_until_ready(
                lambda: self._readiness_check(a),
                timeout=a.wait_timeout,
                cancel=self.abort.is_set,
                paused=self.pause_flag.is_set,
                status=self.readiness_waiting.emit,
            )
        except (ConditionCancelled, ConditionTimeout) as exc:
            raise Stopped(f"Wait step: {exc}") from exc

    def _action(self, a: Action):
        import pyautogui as pg
        # Briefly tolerate the *same* window regaining focus between steps.
        # Never recover focus mid-click, mid-drag, or mid-keystroke.
        if a.kind == "wait" and a.wait_mode == "duration":
            # A fixed pause is wall-clock time for a screen demo.
            # Keep checking the original target and F8 during the pause.
            self._wait(a.delay, recover_focus=True)
        else:
            self._wait(a.delay / self.speed, recover_focus=True)
        self._guard(recover_focus=True)
        if a.kind == "wait":
            self._run_wait_action(a)
        elif a.kind == "secure_input":
            if a.secure_mode == 'manual':
                self._protected_input()
            elif a.secure_mode == 'auto':
                # Only memory-resident values. Never use the clipboard or
                # insert sensitive text into project actions or logs.
                secret = self.secure_values.pop(a.id, None)
                if secret is None:
                    raise RuntimeError('Secure input is missing; replay stopped safely.')
                # Passwords must not be inserted unless OS accessibility
                # verifies a protected field. Recheck during injection so a
                # focus change cannot silently redirect later characters.
                self._guard()
                require_protected_field(focus_status)
                self._unicode_type(secret, 0.0 if self.typing_mode == 'instant' else a.char_delay,
                                   protected=True)
                del secret
            # skip intentionally does nothing

        elif a.kind == "click":
            self._cursor(a, a.x, a.y)
            if a.button in ('x1','x2'):
                press_mouse(a.button)
                release_mouse(a.button)
            else:
                pg.click(button=a.button)
        elif a.kind == "drag":
            self._smooth_move(a.x, a.y, self._mouse_duration(0.18, action=a))
            self._guard()
            press_mouse(a.button)
            try:
                if self.cursor_mode == 'original' and len(a.raw_path) > 1:
                    self._original_move(a.raw_path, (a.end_x, a.end_y),
                                        self._mouse_duration(a.path_duration, dragging=True, action=a))
                else:
                    self._cursor(a,a.end_x,a.end_y,dragging=True)
            finally:
                release_mouse(a.button)
        elif a.kind == "scroll":
            self._smooth_move(a.x, a.y, self._mouse_duration(0.15, action=a))
            steps = max(abs(a.dy), abs(a.dx), 1)
            for i in range(steps):
                self._guard()
                if i < abs(a.dy):
                    pg.scroll(1 if a.dy > 0 else -1)
                if i < abs(a.dx):
                    pg.hscroll(1 if a.dx > 0 else -1)
                self._wait(.025 / self.speed)
        elif a.kind == "type":
            if self.typing_mode == 'instant':
                self._unicode_type(a.text,0)
            elif self.typing_mode == 'original':
                self._recorded_type(a.text,a.char_timings,a.char_delay)
            else:
                self._unicode_type(a.text,a.char_delay)
        elif a.kind == "key":
            keys = a.key.lower().split('+')
            allowed = set(pg.KEYBOARD_KEYS)
            if any(k not in allowed for k in keys):
                raise ValueError(f"Unsupported keyboard shortcut: {a.key}")
            self._guard()
            if len(keys) > 1:
                pg.hotkey(*keys)
            else:
                pg.press(keys[0])

    def _map_to_current_window(self, action: Action) -> Action:
        # Screen-wide workflows retain their global coordinates. Historical
        # projects without a recorded anchor retain their previous behavior.
        if self.target_mode != "window" or not self.recorded_window_bounds:
            return action
        if action.kind not in ('click','drag','scroll'):
            return action
        self._guard()
        try:
            return remap_action(action, self.recorded_window_bounds,
                                window_rect(self.target_hwnd))
        except (OSError, ValueError) as exc:
            raise Stopped(f"Cannot safely map pointer coordinates: {exc}") from exc

    def _wait_for_visual_idle(self):
        # This is a best-effort visual quiet period, not browser DOM-ready.
        # Keep samples only in memory and never store or log captured pixels.
        if not self.adaptive_wait or self.target_mode != 'window':
            return
        self.adaptive_waiting.emit(True)
        try:
            wait_for_visual_settle(
                lambda: sample_window_thumbnail(window_rect(self.target_hwnd)),
                guard=self._guard, cancel=self.abort.is_set,
                paused=self.pause_flag.is_set,
            )
        except VisualSettlingInterrupted as exc:
            raise Stopped(str(exc)) from exc
        finally:
            self.adaptive_waiting.emit(False)

    def run(self):
        try:
            ok, reason = supported()
            if not ok:
                raise RuntimeError(reason)
            import pyautogui as pg
            from pynput import keyboard
            pg.FAILSAFE = True
            pg.PAUSE = 0.0
            self._guard(recover_focus=True)
            if self.center_at_start:
                if self.target_mode == 'screen' and self.screen_bounds:
                    x,y,w,h=self.screen_bounds
                    from .platform_api import center_cursor as center_native
                    centered = center_native(self.target_hwnd, (x,y,w,h))
                else:
                    centered = center_cursor(self.target_hwnd)
                if not centered:
                    raise RuntimeError('Windows could not center the mouse in the target')
            self.began_at = time.monotonic()
            def hotkey(key):
                if key == keyboard.Key.f8:
                    self.cancel()
                elif key == keyboard.Key.f7:
                    self.toggle_pause()
            self.key_guard = keyboard.Listener(on_press=hotkey)
            self.key_guard.start()
            for i, action in enumerate(self.actions):
                if not action.enabled:
                    continue
                self._guard(recover_focus=True)
                self.progress.emit(i)
                mapped = self._map_to_current_window(action)
                self._action(mapped)
                # An explicit Wait action takes precedence over automatic
                # visual settling. Avoid extra delays when the user provided
                # a precise readiness condition for the next step.
                next_action = next(
                    (item for item in self.actions[i+1:] if item.enabled), None
                )
                navigation = action.kind == 'click' or (
                    action.kind == 'key' and action.key.lower() in
                    ('enter','f5','ctrl+r','alt+left','alt+right')
                )
                # An adaptive check is most useful when the next action
                # follows quickly. A longer user-edited delay already gives
                # the UI settling time, and the final step needs no wait.
                if (navigation and next_action and next_action.kind != 'wait'
                        and next_action.delay < 0.75):
                    self._wait_for_visual_idle()
            self.finished_result.emit("Playback finished successfully.")
        except Stopped as ex:
            self.finished_result.emit(str(ex))
        except Exception as ex:
            self.finished_result.emit(f"Playback stopped: {ex}")
        finally:
            self.secure_values.clear()
            if self.key_guard:
                self.key_guard.stop()
