"""Explicitly started, single-window Windows input recorder.

Keyboard capture is fail-closed when UI Automation cannot inspect focus.
No input is written to disk unless the user chooses Save.
"""
from __future__ import annotations

import ctypes
import sys
import threading
import time
from PySide6.QtCore import QObject, Signal
from .core import ActionBuilder, is_repeatable_key
from .platform_api import activate_target_window, window_pid, focus_status, supported


def foreground() -> int:
    from .platform_api import foreground as native
    return native()


def title_of(hwnd: int) -> str:
    from .platform_api import title_of as native
    return native(hwnd)


def virtual_screen():
    from .platform_api import virtual_screen as native
    return native()


def window_rect(hwnd: int) -> list[int]:
    """Window rectangle in physical screen coordinates."""
    from .platform_api import window_rect as native
    return native(hwnd)



def center_cursor(hwnd: int) -> bool:
    """Place the cursor at the center of the target window's client region."""
    if sys.platform == 'win32':
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        rect = wintypes.RECT()
        point = wintypes.POINT()
        if user32.GetClientRect(hwnd, ctypes.byref(rect)):
            point.x, point.y = (rect.right - rect.left) // 2, (rect.bottom - rect.top) // 2
            if user32.ClientToScreen(hwnd, ctypes.byref(point)):
                return bool(user32.SetCursorPos(point.x, point.y))
    from .platform_api import center_cursor as native
    return native(hwnd)


class Recorder(QObject):
    finished = Signal(object, str, object)
    notice = Signal(str)
    started = Signal(str)
    pause_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lock = threading.RLock()
        self.active = False
        self.target_hwnd = 0
        self.builder: ActionBuilder | None = None
        self.mouse_listener = None
        self.key_listener = None
        self.modifiers = set()
        self.last_error_notice = 0.0
        self.pressed_keys = set()
        self.paused = False
        self.paused_at = 0.0
        self.pause_total = 0.0
        self.scope = "window"
        self.own_hwnd = 0
        self.recorded_window_bounds = []
        self.interactive_bounds = None  # Physical desktop rectangle of clickable dock controls
        self.excluded_buttons = set()    # Suppress a complete control-button gesture

    def set_interactive_bounds(self, rect):
        """Update hit test rectangle from Qt GUI thread; no QWidget calls in hooks."""
        self.interactive_bounds = (tuple(rect) if rect and len(rect) == 4 else None)

    def _over_interactive_controls(self, x, y):
        rect = self.interactive_bounds
        if rect is None:
            return False
        left, top, width, height = rect
        return left <= x < left + width and top <= y < top + height

    def begin(self, own_hwnd: int, target_hwnd: int = 0, scope: str = "window", capture_bounds=None, dock_bounds=None) -> bool:
        ok, reason = supported()
        if not ok:
            self.notice.emit(reason)
            return False
        target = target_hwnd or foreground()
        if not target or (sys.platform=='win32' and (target == own_hwnd or ctypes.windll.user32.IsChild(own_hwnd, target))):
            self.notice.emit("Select another application during the countdown, then retry.")
            return False
        self.own_hwnd = own_hwnd
        self.dock_bounds = dock_bounds
        self.scope = "screen" if scope == "screen" else "window"
        self.target_hwnd = target
        self.paused = False
        self.paused_at = 0.0
        self.pause_total = 0.0
        self.target_title = title_of(target) or "Untitled window"
        self.bounds = list(capture_bounds) if self.scope == "screen" and capture_bounds else virtual_screen()
        self.recorded_window_bounds = []
        if self.scope == "window":
            try:
                self.recorded_window_bounds = list(window_rect(target))
            except Exception:
                self.notice.emit("Could not record window geometry; this take will use absolute pointer positions.")
        self.started_at = time.monotonic()
        self.builder = ActionBuilder()
        self.modifiers.clear()
        self.pressed_keys.clear()
        self.excluded_buttons.clear()
        try:
            from pynput import mouse, keyboard
            self.active = True
            self.mouse_listener = mouse.Listener(on_move=self._move, on_click=self._click, on_scroll=self._scroll)
            self.key_listener = keyboard.Listener(on_press=self._press, on_release=self._release)
            self.mouse_listener.start()
            self.key_listener.start()
        except Exception as exc:
            self.active = False
            if self.mouse_listener:
                self.mouse_listener.stop()
            if self.key_listener:
                self.key_listener.stop()
            self.notice.emit(f"Could not start input hooks: {exc}")
            return False
        self.started.emit(self.target_title)
        return True

    def _inside(self):
        if not self.active or self.paused:
            return False
        current = foreground()
        if self.scope == "window":
            return current == self.target_hwnd
        if not current:
            return False
        import os
        if not window_pid(current) or window_pid(current) == os.getpid():
            return False
        if self.scope == 'screen':
            try:
                x,y,w,h=window_rect(current)
                sx,sy,sw,sh=self.bounds
                overlap=max(0,min(x+w,sx+sw)-max(x,sx))*max(0,min(y+h,sy+sh)-max(y,sy))
                if overlap <= 0:return False
            except OSError:
                return False
        return True

    def _inside_at(self, x, y):
        if not self._inside():
            return False
        # Windows' status dock is click-through; do NOT exclude its
        # entire rectangle or Brave address-bar clicks would be lost.
        # Only the separate interactive controller must be excluded.
        if sys.platform == 'win32':
            if self._over_interactive_controls(x, y):
                return False
            if self.excluded_buttons:
                return False  # A control drag may travel beyond its bounds.
        elif self.own_hwnd:
            # Other platforms keep their existing regular interactive dock.
            if self.dock_bounds:
                left, top, width, height = self.dock_bounds
                if left <= x < left + width and top <= y < top + height:
                    return False
        if self.scope == 'screen':
            l,t,w,h=self.bounds
            return l<=x<l+w and t<=y<t+h
        return True

    def _stamp(self):
        return max(0.0, time.monotonic() - self.started_at - self.pause_total)

    def elapsed(self):
        now = self.paused_at if self.paused else time.monotonic()
        return max(0.0, now - self.started_at - self.pause_total)

    def toggle_pause(self):
        with self.lock:
            if not self.active:
                return False
            if self.paused:
                self.pause_total += time.monotonic() - self.paused_at
                self.paused_at = 0.0
                self.paused = False
            else:
                self.builder.flush_text()
                self.paused = True
                self.paused_at = time.monotonic()
            current = self.paused
        self.pause_changed.emit(current)
        return current

    def _move(self, x, y):
        if not self._inside_at(x, y):
            return
        with self.lock:
            if self.active:
                self.builder.move(round(x), round(y), self._stamp())

    def _click(self, x, y, button, pressed):
        value = str(button).split('.')[-1]
        if value not in {"left", "right", "middle", "x1", "x2"}:
            return
        # Track controller button presses until release even if the user drags
        # the handle outside the control window. They must not appear in take.
        if sys.platform == 'win32':
            if pressed and self._over_interactive_controls(x, y):
                with self.lock:
                    self.excluded_buttons.add(value)
                return
            if value in self.excluded_buttons:
                if not pressed:
                    with self.lock:
                        self.excluded_buttons.discard(value)
                return
        if not self._inside_at(x, y):
            if not pressed and self.builder is not None:
                with self.lock:
                    self.builder.cancel_button(value)
            return
        with self.lock:
            if self.active:
                if pressed:
                    self.builder.mouse_down(round(x), round(y), self._stamp(), value)
                else:
                    self.builder.mouse_up(round(x), round(y), value, self._stamp())

    def _scroll(self, x, y, dx, dy):
        if not self._inside_at(x, y):
            return
        with self.lock:
            if self.active:
                self.builder.scroll(round(x), round(y), round(dx), round(dy), self._stamp())

    @staticmethod
    def _key_name(key):
        raw = str(key)
        if raw.startswith('Key.'):
            value = raw[4:].lower()
            names = {"return": "enter", "esc": "esc", "page_down": "pgdn",
                     "page_up": "pgup", "cmd": "win", "cmd_l": "win", "cmd_r": "win"}
            return names.get(value, value)
        return ""

    def _focus_status(self) -> str:
        """Return safe, protected, or unknown without reading field contents.

        Unknown is fail-closed; custom controls may not expose password status.
        """
        try:
            status = focus_status()
            if status != 'unknown':
                return status
            raise RuntimeError('Focused field could not be verified')
        except Exception:
            now = time.monotonic()
            if now - self.last_error_notice > 8:
                self.notice.emit("Keyboard input skipped: accessibility service could not verify the focused field.")
                self.last_error_notice = now
            return "unknown"

    def _press(self, key):
        name = self._key_name(key)
        if name == "f8" and self.active:
            self.stop()
            return False
        if name == "f7" and self.active:
            self.toggle_pause()
            return
        if not self._inside():
            return
        modifiers = {"ctrl", "ctrl_l", "ctrl_r", "shift", "shift_l", "shift_r", "alt", "alt_l", "alt_r", "alt_gr", "win", "cmd_l", "cmd_r"}
        with self.lock:
            if not self.active:
                return
            if name in modifiers:
                self.modifiers.add(name.split('_')[0].replace('cmd', 'win'))
                return
            char = getattr(key, 'char', None)
            key_id = name or str(char)
            if key_id in self.pressed_keys and not is_repeatable_key(name, char, self.modifiers):
                return
            self.pressed_keys.add(key_id)
            focus_status = self._focus_status()
            if focus_status == "protected":
                # UI Automation explicitly marks the focused control as a
                # password field: create just one non-secret placeholder.
                self.builder.protected_input(self._stamp())
                return
            if focus_status != "safe":
                self.builder.flush_text()
                self.builder.leave_protected_input()
                return
            self.builder.leave_protected_input()
            stamp = self._stamp()
            ctrl = 'ctrl' in self.modifiers
            alt = 'alt' in self.modifiers
            win = 'win' in self.modifiers
            if ctrl or alt or win:
                vk = getattr(key, 'vk', None)
                letter = chr(vk).lower() if isinstance(vk, int) and 65 <= vk <= 90 else None
                suffix = name or letter or (char.lower() if char and char.isprintable() else '')
                shortcut = "+".join([m for m in ("ctrl", "alt", "shift", "win") if m in self.modifiers] + [suffix])
                if shortcut == 'ctrl+v':
                    self.builder.flush_text()
                    self.notice.emit("Clipboard paste skipped for privacy. Add an editable Type action if needed.")
                elif char or name:
                    self.builder.key(shortcut, stamp)
            elif name == "backspace":
                self.builder.backspace(stamp)
            elif char and char.isprintable() and not (ord(char) < 32):
                self.builder.char(char, stamp)
            elif name in {"enter", "tab", "delete", "esc", "up", "down", "left", "right", "home", "end", "pgup", "pgdn", "space", "backspace"}:
                if name == 'space':
                    self.builder.char(' ', stamp)
                else:
                    self.builder.key(name, stamp)

    def _release(self, key):
        name = self._key_name(key)
        with self.lock:
            if name:
                self.pressed_keys.discard(name)
            else:
                self.pressed_keys.discard(str(getattr(key, 'char', '')))
            if name in {"ctrl", "ctrl_l", "ctrl_r", "shift", "shift_l", "shift_r", "alt", "alt_l", "alt_r", "alt_gr", "win", "cmd_l", "cmd_r"}:
                self.modifiers.discard(name.split('_')[0].replace('cmd', 'win'))

    def stop(self):
        with self.lock:
            if not self.active:
                return
            self.active = False
            if self.paused:
                self.pause_total += time.monotonic() - self.paused_at
                self.paused = False
                self.paused_at = 0.0
            actions = self.builder.finish()
            target = self.target_title
            bounds = self.bounds
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.key_listener:
            self.key_listener.stop()
        self.finished.emit(actions, target, bounds)
