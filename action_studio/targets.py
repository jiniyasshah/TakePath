"""Windows capture-target discovery with taskbar-style filtering.

We list human-facing app windows, not arbitrary HWNDs; target identifiers remain
HWNDs so the rest of the V1–V7 recorder/playback flow is unchanged.
"""
from __future__ import annotations

import ctypes
import os
import re
import sys
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TargetWindow:
    hwnd: int
    title: str
    process_id: int
    process_path: str = ""
    app_name: str = ""


# Shell/IME/background surfaces that expose ordinary top-level HWNDs but should
# never appear as capture targets. Do not filter whole generic host processes:
# that would accidentally hide the real Settings window and similar apps.
SYSTEM_CLASSES = frozenset({
    "progman", "workerw", "shell_traywnd", "shell_secondarytraywnd",
    "dv2controlhost", "msctfime ui", "ime", "sysshadow",
    "tooltips_class32", "windows.ui.core.corewindow",
    "xaml_popup", "foregroundstaging",
})
SYSTEM_TITLES = frozenset({
    "program manager", "windows input experience", "microsoft text input application",
    "desktopwindowxamlsource", "task switching", "start",
})
SYSTEM_PROCESSES = frozenset({
    "textinputhost.exe", "sihost.exe", "startmenuexperiencehost.exe",
    "searchhost.exe", "searchapp.exe", "shellexperiencehost.exe",
    "lockapp.exe", "ctfmon.exe", "dwm.exe",
})
APP_NAMES = {
    "brave.exe": "Brave Browser", "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge", "firefox.exe": "Firefox",
    "code.exe": "Visual Studio Code", "devenv.exe": "Visual Studio",
    "explorer.exe": "File Explorer", "systemsettings.exe": "Settings",
    "notepad.exe": "Notepad", "notepad++.exe": "Notepad++",
    "windowsterminal.exe": "Windows Terminal", "powershell.exe": "PowerShell",
    "pwsh.exe": "PowerShell", "cmd.exe": "Command Prompt",
    "obs64.exe": "OBS Studio", "discord.exe": "Discord",
    "telegram.exe": "Telegram", "python.exe": "Python", "pythonw.exe": "Python",
}


def is_capture_candidate(title: str, class_name: str, process_name: str = "",
                         *, visible: bool = True, cloaked: bool = False,
                         tool_window: bool = False, no_activate: bool = False,
                         owned: bool = False, width: int = 100, height: int = 100) -> bool:
    """Pure, testable portion of the Windows taskbar-like HWND selection rule."""
    title = title.strip()
    if not title or not visible or cloaked or tool_window or no_activate or owned:
        return False
    if title.casefold() in SYSTEM_TITLES or class_name.casefold() in SYSTEM_CLASSES:
        return False
    if process_name.casefold() in SYSTEM_PROCESSES:
        return False
    return width >= 100 and height >= 75


def friendly_app_name(process_path: str, title: str) -> str:
    """Resolve an app label, retaining user-visible window titles separately."""
    binary = Path(process_path.replace('\\', '/')).name.casefold()
    if binary in APP_NAMES:
        return APP_NAMES[binary]
    # Unknown executables and Windows' generic ApplicationFrameHost should use
    # the actual app window title, not a confusing internal .exe name.
    return title


def window_menu_label(window: TargetWindow) -> str:
    """Short app-forward menu label; full window title stays available as tooltip."""
    app = window.app_name or friendly_app_name(window.process_path, window.title)
    title = window.title.strip()
    # Browser window titles already typically end with the product name.
    if title.casefold() == app.casefold():
        result = app
    elif app.casefold() in title.casefold():
        result = title
    else:
        result = f'{app} — {title}'
    return result if len(result) <= 65 else result[:62].rstrip() + '…'


def unique_application_windows(windows: list[TargetWindow]) -> list[TargetWindow]:
    """Collapse duplicate UI surfaces for one title/process, not all app windows.

    Two browser windows with different pages/titles remain independent targets.
    Exact same-title HWND clones belonging to one process are generally host
    surfaces, not separate selectable windows; preserve the first (topmost).
    """
    seen: set[tuple[str, str]] = set()
    output: list[TargetWindow] = []
    for window in windows:
        binary = Path(window.process_path.replace('\\', '/')).name.casefold()
        normalized_title = re.sub(r'\s+', ' ', window.title.strip()).casefold()
        # Common app-shell mirrors can be owned by a *different* host process.
        # Deduplicate these by display title; other windows still keep separate
        # app/window identities, including differently titled browser windows.
        shell_duplicates = {'settings', 'realtek audio console'}
        owner_key = 'shell-mirror' if normalized_title in shell_duplicates else (binary or f'pid:{window.process_id}')
        key = (owner_key, normalized_title)
        if key in seen:
            continue
        seen.add(key)
        output.append(window)
    return output


def _process_path(pid: int) -> str:
    if not pid:
        return ""
    kernel = ctypes.windll.kernel32
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                  wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    handle = kernel.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(buf))
        return buf.value if kernel.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(length)) else ""
    finally:
        kernel.CloseHandle(handle)


def open_windows() -> list[TargetWindow]:
    """Discover actual selectable Windows app windows; return topmost first.

    Unlike generic EnumWindows lists, rejects DWM-cloaked, tool, no-activate,
    owned, shell, and tiny windows. A minimized app remains selectable.
    """
    if sys.platform != 'win32':
        from .platform_api import target_windows, supported
        if not supported()[0]:
            return []
        try:
            return [TargetWindow(*entry) for entry in target_windows()]
        except Exception:
            return []
    user = ctypes.windll.user32
    dwm = getattr(ctypes.windll, 'dwmapi', None)
    result: list[TargetWindow] = []
    CALLBACK = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.IsWindowVisible.restype = wintypes.BOOL
    user.IsIconic.argtypes = [wintypes.HWND]
    user.IsIconic.restype = wintypes.BOOL
    user.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user.GetWindow.restype = wintypes.HWND
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.GetWindowRect.restype = wintypes.BOOL
    user.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user.GetWindowTextLengthW.restype = ctypes.c_int
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetWindowTextW.restype = ctypes.c_int
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetClassNameW.restype = ctypes.c_int
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowThreadProcessId.restype = wintypes.DWORD
    # GetWindowLongPtrW for 64-bit extension flags; GetWindowLongW for older APIs.
    get_style = getattr(user, 'GetWindowLongPtrW', None) or user.GetWindowLongW
    get_style.argtypes = [wintypes.HWND, ctypes.c_int]
    get_style.restype = ctypes.c_ssize_t
    if dwm:
        dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD,
                                             ctypes.c_void_p, wintypes.DWORD]
        dwm.DwmGetWindowAttribute.restype = ctypes.c_long
    path_cache: dict[int, str] = {}

    def visit(hwnd, _):
        try:
            if not user.IsWindowVisible(hwnd) or user.GetWindow(hwnd, 4):
                return True
            length = user.GetWindowTextLengthW(hwnd)
            if not (1 <= length <= 1024):
                return True
            title_buffer = ctypes.create_unicode_buffer(length + 1)
            user.GetWindowTextW(hwnd, title_buffer, length + 1)
            title = title_buffer.value.strip()
            cls_buffer = ctypes.create_unicode_buffer(256)
            user.GetClassNameW(hwnd, cls_buffer, len(cls_buffer))
            classname = cls_buffer.value
            extended_style = int(get_style(hwnd, -20))
            if dwm:
                cloak = wintypes.DWORD(0)
                if dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloak), ctypes.sizeof(cloak)) == 0 and cloak.value:
                    return True
            pid = wintypes.DWORD()
            user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value or pid.value == os.getpid():
                return True
            if pid.value not in path_cache:
                path_cache[pid.value] = _process_path(int(pid.value))
            path = path_cache[pid.value]
            rect = wintypes.RECT()
            if not user.GetWindowRect(hwnd, ctypes.byref(rect)):
                return True
            width = rect.right - rect.left
            height = rect.bottom - rect.top
            # Minimized HWND rects may be -32000, but retain their actual size.
            if not is_capture_candidate(title, classname, Path(path.replace('\\', '/')).name,
                                        tool_window=bool(extended_style & 0x80),
                                        no_activate=bool(extended_style & 0x08000000),
                                        width=width, height=height):
                return True
            result.append(TargetWindow(int(hwnd), title, int(pid.value), path,
                                       friendly_app_name(path, title)))
        except (OSError, ValueError, AttributeError):
            pass  # An app can exit between enumeration calls.
        return True

    cb = CALLBACK(visit)
    user.EnumWindows.argtypes = [CALLBACK, wintypes.LPARAM]
    user.EnumWindows.restype = wintypes.BOOL
    user.EnumWindows(cb, 0)
    return unique_application_windows(result)[:40]


def usable_window(hwnd: int) -> bool:
    from .platform_api import usable_window as check
    return check(hwnd)


def screen_entries(screens=None):
    """Physical pixel screen rectangles; native monitor enumeration on Windows.

    Qt's QScreen.geometry may be logical/DPI-scaled, but mouse hooks and mss
    screenshot positions use physical screen coordinates. Do not mix them.
    """
    if sys.platform == 'win32':
        class RECT(ctypes.Structure):
            _fields_=[('left',wintypes.LONG),('top',wintypes.LONG),
                      ('right',wintypes.LONG),('bottom',wintypes.LONG)]
        class MONITORINFO(ctypes.Structure):
            _fields_=[('cbSize',wintypes.DWORD),('rcMonitor',RECT),
                      ('rcWork',RECT),('dwFlags',wintypes.DWORD)]
        callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HMONITOR,
                                         wintypes.HDC,ctypes.POINTER(RECT),wintypes.LPARAM)
        user=ctypes.windll.user32
        user.GetMonitorInfoW.argtypes=[wintypes.HMONITOR,ctypes.POINTER(MONITORINFO)]
        user.GetMonitorInfoW.restype=wintypes.BOOL
        result=[]
        def each(monitor,dc,rect,data):
            info=MONITORINFO()
            info.cbSize=ctypes.sizeof(MONITORINFO)
            if user.GetMonitorInfoW(monitor,ctypes.byref(info)):
                r=info.rcMonitor
                result.append(((r.left,r.top,r.right-r.left,r.bottom-r.top),bool(info.dwFlags & 1)))
            return True
        callback=callback_type(each)
        user.EnumDisplayMonitors.argtypes=[wintypes.HDC,ctypes.POINTER(RECT),callback_type,wintypes.LPARAM]
        user.EnumDisplayMonitors.restype=wintypes.BOOL
        user.EnumDisplayMonitors(None,None,callback,0)
        result.sort(key=lambda row: (not row[1], row[0][0], row[0][1]))
        if result:
            return [(f'Screen {i}'+(' (Primary)' if primary else ''),bounds,primary)
                    for i,(bounds,primary) in enumerate(result,1)]
    if sys.platform != 'win32':
        try:
            import mss
            with mss.mss() as sct:
                monitors = list(sct.monitors[1:])
                if monitors:
                    return [(f'Screen {i}'+(' (Primary)' if i == 1 else ''),
                             (m['left'],m['top'],m['width'],m['height']),i == 1)
                            for i,m in enumerate(monitors,1)]
        except Exception:
            pass
    screens=list(screens or [])
    return [(f'Screen {i}'+(' (Primary)' if i==1 else ''),
             (s.geometry().x(),s.geometry().y(),s.geometry().width(),s.geometry().height()),i==1)
            for i,s in enumerate(screens,1)]
