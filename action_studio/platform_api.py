"""OS-specific desktop plumbing. Input hooks live in recorder.py, UI lives in Qt.

Windows: native HWNDs. Linux: X11/EWMH IDs (Wayland is intentionally
unsupported because unprivileged global hooks are blocked by design).
macOS: Quartz CGWindowID and AppKit activation; Accessibility/Input Monitoring
permissions must be granted by the user.
"""
from __future__ import annotations

import os
import sys
import time


def supported() -> tuple[bool, str]:
    if sys.platform == 'win32':
        return True, ''
    if sys.platform == 'darwin':
        try:
            import Quartz  # noqa: F401
            import AppKit  # noqa: F401
            return True, ''
        except ImportError:
            return False, 'Install PyObjC macOS dependencies before recording.'
    if sys.platform.startswith('linux'):
        if os.environ.get('XDG_SESSION_TYPE', '').lower() == 'wayland' or not os.environ.get('DISPLAY'):
            return False, 'Linux recording requires an X11 desktop session (Wayland is not yet supported).'
        try:
            import Xlib  # noqa: F401
            d = _xdisplay()
            d.close()
            return True, ''
        except ImportError:
            return False, 'Install python-xlib to use the Linux X11 backend.'
        except Exception:
            return False, 'Cannot connect to the X11 display. Check DISPLAY/XAUTHORITY.'
    return False, f'Unsupported desktop platform: {sys.platform}'


def _xdisplay():
    from Xlib import display
    return display.Display()


def _xproperty(window, atom):
    from Xlib import Xatom
    prop = window.get_full_property(atom, Xatom.ANY_PROPERTY_TYPE)
    return prop.value if prop is not None else None


def _x_active(display_obj):
    root = display_obj.screen().root
    value = _xproperty(root, display_obj.intern_atom('_NET_ACTIVE_WINDOW'))
    return int(value[0]) if value is not None and len(value) else 0


def _mac_windows():
    import Quartz
    options = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
    return list(Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID) or [])


def foreground() -> int:
    if sys.platform == 'win32':
        from ctypes import windll, wintypes
        u = windll.user32
        u.GetForegroundWindow.restype = wintypes.HWND
        return int(u.GetForegroundWindow() or 0)
    if sys.platform == 'darwin':
        import AppKit
        app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
        pid = int(app.processIdentifier()) if app else 0
        for item in _mac_windows():
            if int(item.get('kCGWindowOwnerPID', 0)) == pid and int(item.get('kCGWindowLayer', 0)) == 0:
                return int(item.get('kCGWindowNumber', 0))
        return 0
    d = _xdisplay()
    try:
        return _x_active(d)
    finally:
        d.close()


def window_pid(handle: int) -> int:
    if not handle:
        return 0
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(int(handle), ctypes.byref(pid))
        return int(pid.value)
    if sys.platform == 'darwin':
        for item in _mac_windows():
            if int(item.get('kCGWindowNumber', 0)) == int(handle):
                return int(item.get('kCGWindowOwnerPID', 0))
        return 0
    d = _xdisplay()
    try:
        w = d.create_resource_object('window', int(handle))
        val = _xproperty(w, d.intern_atom('_NET_WM_PID'))
        return int(val[0]) if val is not None and len(val) else 0
    except Exception:
        return 0
    finally:
        d.close()


def title_of(handle: int) -> str:
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        buf = ctypes.create_unicode_buffer(1024)
        ctypes.windll.user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        ctypes.windll.user32.GetWindowTextW(int(handle), buf, len(buf))
        return buf.value
    if sys.platform == 'darwin':
        for item in _mac_windows():
            if int(item.get('kCGWindowNumber', 0)) == int(handle):
                return str(item.get('kCGWindowName') or item.get('kCGWindowOwnerName') or '')
        return ''
    d = _xdisplay()
    try:
        w = d.create_resource_object('window', int(handle))
        v = _xproperty(w, d.intern_atom('_NET_WM_NAME'))
        if v is not None:
            return bytes(v).decode('utf-8', 'replace')
        return str(w.get_wm_name() or '')
    except Exception:
        return ''
    finally:
        d.close()


def window_rect(handle: int) -> list[int]:
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        rc = wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(int(handle), ctypes.byref(rc)):
            raise OSError('Window geometry unavailable')
        return [rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top]
    if sys.platform == 'darwin':
        for item in _mac_windows():
            if int(item.get('kCGWindowNumber', 0)) == int(handle):
                r = item.get('kCGWindowBounds', {})
                return [int(r['X']), int(r['Y']), int(r['Width']), int(r['Height'])]
        raise OSError('macOS window is no longer available')
    d = _xdisplay()
    try:
        w = d.create_resource_object('window', int(handle))
        geo = w.get_geometry()
        root = d.screen().root
        p = w.translate_coords(root, 0, 0)
        return [int(p.x), int(p.y), int(geo.width), int(geo.height)]
    finally:
        d.close()


def virtual_screen() -> list[int]:
    if sys.platform == 'win32':
        import ctypes
        return [ctypes.windll.user32.GetSystemMetrics(i) for i in (76, 77, 78, 79)]
    import pyautogui
    width, height = pyautogui.size()
    return [0, 0, int(width), int(height)]


def center_cursor(handle: int, bounds=None) -> bool:
    try:
        import pyautogui
        x, y, w, h = list(bounds) if bounds else window_rect(handle)
        pyautogui.moveTo(int(x + w/2), int(y + h/2), duration=0)
        return True
    except Exception:
        return False


def usable_window(handle: int) -> bool:
    if not handle:
        return False
    if sys.platform == 'win32':
        import ctypes
        return bool(ctypes.windll.user32.IsWindow(int(handle)))
    try:
        return bool(window_rect(handle)[2] > 0)
    except Exception:
        return False


def activate_target_window(handle: int, timeout: float = 0.9) -> bool:
    if not usable_window(handle):
        return False
    if sys.platform == 'win32':
        from .win_focus import activate_target_window as native
        return native(handle, timeout=timeout)
    if sys.platform == 'darwin':
        try:
            import AppKit
            pid = window_pid(handle)
            app = AppKit.NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
            if app:
                app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
        except Exception:
            return False
    else:
        try:
            from Xlib import X, protocol
            d = _xdisplay()
            try:
                root = d.screen().root
                event = protocol.event.ClientMessage(window=int(handle),
                    client_type=d.intern_atom('_NET_ACTIVE_WINDOW'),
                    data=(32, [1, X.CurrentTime, 0, 0, 0]))
                root.send_event(event, event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
                d.flush()
            finally:
                d.close()
        except Exception:
            return False
    expires = time.monotonic() + timeout
    while time.monotonic() < expires:
        try:
            if foreground() == int(handle):
                return True
        except Exception:
            pass
        time.sleep(.05)
    return foreground() == int(handle)


def is_ours(handle: int) -> bool:
    return not handle or window_pid(handle) == os.getpid()


def target_windows():
    """Yield (native_id, title, pid, process_path, app_name), best effort."""
    if sys.platform == 'darwin':
        seen = set()
        for item in _mac_windows():
            if int(item.get('kCGWindowLayer', 1)) != 0:
                continue
            handle = int(item.get('kCGWindowNumber', 0))
            pid = int(item.get('kCGWindowOwnerPID', 0))
            title = str(item.get('kCGWindowName') or '').strip()
            app = str(item.get('kCGWindowOwnerName') or '').strip()
            r = item.get('kCGWindowBounds', {})
            if not title or pid == os.getpid() or int(r.get('Width', 0)) < 100 or int(r.get('Height', 0)) < 75:
                continue
            key = (pid, title)
            if key not in seen:
                seen.add(key)
                yield handle, title, pid, '', app
    elif sys.platform.startswith('linux'):
        d = _xdisplay()
        try:
            root = d.screen().root
            stacking = _xproperty(root, d.intern_atom('_NET_CLIENT_LIST_STACKING'))
            if stacking is None:
                stacking = _xproperty(root, d.intern_atom('_NET_CLIENT_LIST'))
            if stacking is None:
                return
            seen = set()
            from Xlib import X
            for handle in reversed(list(stacking)):
                try:
                    w = d.create_resource_object('window', int(handle))
                    if w.get_attributes().map_state != X.IsViewable:
                        continue
                    geo = w.get_geometry()
                    if geo.width < 100 or geo.height < 75:
                        continue
                    pid_value = _xproperty(w, d.intern_atom('_NET_WM_PID'))
                    pid = int(pid_value[0]) if pid_value is not None and len(pid_value) else 0
                    if not pid or pid == os.getpid():
                        continue
                    text = _xproperty(w, d.intern_atom('_NET_WM_NAME'))
                    title = bytes(text).decode('utf-8', 'replace').strip() if text is not None else str(w.get_wm_name() or '').strip()
                    if not title:
                        continue
                    key = (pid, title)
                    if key in seen:
                        continue
                    seen.add(key)
                    name = title.split(' - ')[-1].split(' — ')[-1]
                    yield int(handle), title, pid, '', name
                except Exception:
                    continue
        finally:
            d.close()


def focus_status() -> str:
    """Fail closed if protected-field status cannot be queried; never read content."""
    if sys.platform == 'win32':
        try:
            import uiautomation as auto
            with auto.UIAutomationInitializerInThread():
                ctrl = auto.GetFocusedControl()
                if ctrl is None:
                    return 'unknown'
                return 'protected' if bool(ctrl.IsPassword) else 'safe'
        except Exception:
            return 'unknown'
    if sys.platform == 'darwin':
        try:
            import Quartz
            element = Quartz.AXUIElementCreateSystemWide()
            err, focused = Quartz.AXUIElementCopyAttributeValue(element, 'AXFocusedUIElement', None)
            if err != 0 or focused is None:
                return 'unknown'
            err, role = Quartz.AXUIElementCopyAttributeValue(focused, 'AXRole', None)
            if err != 0:
                return 'unknown'
            if role in ('AXSecureTextField',):
                return 'protected'
            err, subrole = Quartz.AXUIElementCopyAttributeValue(focused, 'AXSubrole', None)
            if not err and subrole in ('AXSecureTextField', 'AXSecureTextFieldSubrole'):
                return 'protected'
            return 'safe'
        except Exception:
            return 'unknown'
    # Linux: AT-SPI via distribution-provided pyatspi package.
    try:
        import pyatspi
        focused = []
        desktop = pyatspi.Registry.getDesktop(0)
        def walk(node, depth=0):
            if depth > 15:
                return
            try:
                state = node.getState()
                if state.contains(pyatspi.STATE_FOCUSED):
                    focused.append(node)
                    return
                for child in node:
                    if child:
                        walk(child, depth + 1)
            except Exception:
                return
        for app in desktop:
            walk(app)
            if focused:
                break
        if not focused:
            return 'unknown'
        state = focused[0].getState()
        if state.contains(pyatspi.STATE_PROTECTED):
            return 'protected'
        return 'safe'
    except Exception:
        return 'unknown'


def named_control_available(name: str) -> bool:
    """Whether a visible enabled control with this name exists in focused window.

    Windows UIA only. No clicking, text retrieval, or focus switching.
    Other platforms deliberately reject this advanced mode for now.
    """
    if sys.platform != 'win32':
        raise RuntimeError("Named-control waits currently require Windows UI Automation")
    if not name or not name.strip():
        raise ValueError("Control name cannot be blank")
    try:
        import uiautomation as auto
        with auto.UIAutomationInitializerInThread():
            focused = auto.GetForegroundControl()
            if focused is None:
                return False
            control = focused.Control(Name=name, searchDepth=8)
            return bool(control.Exists(0, 0) and control.IsEnabled and not control.IsOffscreen)
    except (OSError, AttributeError, RuntimeError):
        return False
