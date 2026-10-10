"""Focused-window activation without resizing maximized windows. Qt-free."""
from __future__ import annotations
import ctypes
import time
def activate_target_window(hwnd: int, user32=None, timeout: float = 0.7) -> bool:
    """Focus a playback target WITHOUT unmaximizing an already-visible window.

    SW_RESTORE changes the size of maximized windows. Only restore when the
    target is actually minimized. Give foreground activation a short chance to
    settle before the playback worker checks focus.
    """
    if user32 is None:
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.IsWindow.argtypes = [wintypes.HWND]
        user32.IsIconic.argtypes = [wintypes.HWND]
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.GetForegroundWindow.restype = wintypes.HWND
    if not hwnd or not user32.IsWindow(hwnd):
        return False
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE only for minimized windows
    if user32.GetForegroundWindow() == hwnd:
        return True
    user32.SetForegroundWindow(hwnd)
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if user32.GetForegroundWindow() == hwnd:
            return True
        time.sleep(0.035)
    return user32.GetForegroundWindow() == hwnd

