<!-- TakePath: application overview and user guide -->

<div align="center">
  <img src="assets/takepath-icon.png" alt="TakePath icon" width="108" />
  <h1>TakePath</h1>
  <p><strong>Record your actions. Fix your mistakes. Replay a cleaner take.</strong></p>
  <p>An open-source, local-first mouse and keyboard action recorder and editor for polished software demos, tutorials, and screen recordings.</p>
  <p>
    <a href="https://github.com/jiniyasshah/TakePath/releases"><strong>Download TakePath</strong></a>
    · <a href="#how-it-works">How it works</a>
    · <a href="#features">Features</a>
    · <a href="#download">Platform downloads</a>
  </p>
  <p>
    <a href="https://github.com/jiniyasshah/TakePath/releases"><img alt="GitHub Release" src="https://img.shields.io/github/v/release/jiniyasshah/TakePath?include_prereleases&label=release" /></a>
    <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue" /></a>
    <img alt="Windows, macOS and Linux" src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-303747" />
  </p>
</div>

---

## Why TakePath?

Ever finished a screen-recording take only to notice a typo, an awkward mouse movement, or an accidental click?

**TakePath records the actions behind your demonstration**, so you can correct them before replaying the workflow. Instead of repeating every click and keystroke, edit the sequence, adjust the timing, and produce a cleaner take.

**TakePath is an action recorder, not a video recorder.** It does not edit recorded video frames or export MP4 files. Replay your corrected actions into the original app, and use OBS or your preferred screen recorder to capture the finished video.

## How it works

1. **Choose a target.** From the minimal floating dock, select a screen or application window, set an optional countdown, and choose whether to center the cursor before starting.
2. **Record normally.** TakePath captures clicks, cursor movement, dragging, scrolling, typing, and supported keyboard/mouse buttons while you work.
3. **Edit your take.** After recording, use the action-first editor to fix text, remove mistakes, reorder or duplicate steps, and adjust delays. The visual action map is optional.
4. **Replay when ready.** Click **Replay** in the editor to return to the dock, then press **Play** there. Your edited sequence runs in the target application, ready to capture with a screen recorder.
5. **Retake if needed.** Start a fresh attempt from the dock without confusing Retake with Replay. You can restore the previous completed take from the session when available.

## Features

### Smarter replay (1.2.0 beta)

- **Adaptive wait:** optionally let TakePath pause briefly after clicks and navigation while visible changes settle. This is best-effort; complex or very slow pages may still need a manual Wait step.
- **Editable Wait steps:** choose a **fixed-duration pause** (useful for holding a screen during recording) or a conditional checkpoint for a window title, focused field, or Windows UI Automation control. The fixed pause defaults to three seconds; conditional steps have a configurable timeout.
- **Window-relative coordinates:** newly recorded window-scoped projects adjust click and drag locations when the target window moves or moderately resizes. Major layout changes can still break alignment.
- **Safer focus handling:** if a window-scoped replay loses focus, TakePath waits briefly for the original target and stops instead of typing elsewhere.
- **More reliable input capture:** improved overlapping mouse buttons and held-key repeats.

### Capture and replay

- **Smart click-through dock (Windows):** while recording or replaying, the floating status bar lets mouse clicks reach the underlying app (including browser address bars), while a **separate small controller** keeps **Pause, Stop and a drag handle clickable with the mouse**. **F7/F8** continue to work. Controller clicks and drags are excluded from the recorded actions.
- **Taskbar minimize and smooth dock transitions (Windows):** The dock minimizes into the normal taskbar instead of hiding only in the tray. Restoring returns to the dock. Compact/expanded resizing is eased around the existing visual center; the drag grip remains on the far left.
- **Short recording/replay dock by default:** TakePath automatically shrinks the status bar when a capture or replay starts, with the clickable Pause/Stop controller alongside it. The controller's compact/expand button can restore the extended layout, and the preference persists. The normal full dock returns when the session ends.
- **Detailed action capture:** mouse clicks, moves, drags, scrolls, side buttons, typed text, and shortcuts.
- **Type-aware action context menu:** Right-click selected action rows to configure **Mouse speed** for clicks/drags/scrolls, **Typing speed** (Original, Normal, Fast, Slow, Instant or global default) for Type actions, or **Wait duration** for fixed Wait steps. Multi-select applies a setting to only the applicable action types. Enable/Disable, Duplicate and Delete stay available for all. A zero action delay does not by itself make mouse motion instant.
- **Global cursor paths:** Original, Smooth, Straight, and Gentle movement styles remain available as separate global controls.
- **Global typing presets:** Original recorded rhythm, Smooth typing, or Instant insertion.
- **Precise playback:** control timing per step, apply a uniform gap, change replay speed, and optionally center the cursor.
- **Two-step replay:** the editor hides first; playback starts only when you press Play on the dock.

### Edit without recording again

- Correct captured text and customize typing behavior.
- Select one or multiple actions to delete, duplicate, or reorder.
- Tune individual delays and apply timing changes across selected steps.
- Use **+ Before** to insert a new action before the selected step, or at the beginning if no step is selected. Click blank editor space to deselect; property controls retain selection so you can edit safely.
- Show a visual action map when you need to inspect or adjust click positions; hide it to focus on the action list.
- Save and reopen automatically encrypted editable `.vas.json` projects.
- Previously saved projects continue to open; projects without recorded window bounds retain their previous screen-coordinate behavior.

### Protected inputs

- Recognized password fields become **Secure Input** steps rather than plain recorded keystrokes.
- Choose **Auto-fill**, **Manual**, or **Skip** for each secure step.
- Enter a value in the editor or supply missing values in a prompt before playback.
- Optionally reveal a configured value for verification; values are hidden by default.
- **Remember securely on this device** is selected by default when a supported OS credential vault is available; session-only storage remains an option. OS-protected values stay on the same computer/account and are not automatically portable.
- **Use for all auto-fill secure input steps** is an explicit opt-in when multiple protected fields require the same value. Individual steps can still use distinct values.
- **Save, Save As, and Export copy encrypt automatically.** The entire `.vas.json` file—including the action list, typed text, preview image, window metadata, and any configured secure inputs—is encrypted with AES-256-GCM. No project/export passphrase is requested, even for projects with no secure inputs.
- The random encryption key lives in the local OS credential vault. Reopening or exporting on the **same device and user account** works automatically. Files are **not directly readable on a different device/account** without the associated protected key; TakePath does not offer cloud key sync. Do not delete the OS vault entry if you need old encrypted files.
- Legacy plain `.vas.json` files can be opened and automatically become encrypted when saved again. If the OS vault is unavailable, Save/Export fails instead of writing sensitive data unencrypted. Older manually passphrase-encrypted exports cannot be silently decrypted by the new device key.

## Download

Get the latest builds from **[GitHub Releases](https://github.com/jiniyasshah/TakePath/releases)**.

| Platform | Download | Notes |
| --- | --- | --- |
| **Windows 10/11 (x64)** | `TakePath-windows-x64-setup.exe` | Recommended installer: Start Menu shortcut, optional desktop shortcut, uninstaller |
| **Windows 10/11 (x64)** | `TakePath-windows-x64.exe` | Standalone portable executable |
| **Windows 10/11 (x64)** | `TakePath-windows-x64-portable.zip` | Extract and run the app from its folder |
| **macOS — Apple Silicon** | `TakePath-macos-arm64.dmg` | Preview support; requires accessibility permissions |
| **macOS — Intel** | `TakePath-macos-x64.dmg` | Preview support; requires accessibility permissions |
| **Linux (x64, X11)** | `TakePath-linux-x64.AppImage` | Preview support; Wayland is not supported |
| **Linux (x64, X11)** | `TakePath-linux-x64.tar.gz` | Portable alternative |

The first cross-platform packages are **unsigned**; macOS applications are not notarized. Operating systems may show trust or security warnings. Only run files obtained from releases you trust.

### Quick start

**Windows:** For a normal installation, download the `-setup.exe` and follow the installer (no Python or admin rights needed). Or use the standalone portable `.exe` without installing, or extract the portable ZIP and launch `TakePath.exe`. The installer creates an uninstall entry in Windows Installed Apps.

**macOS (preview):** Download the build for your processor. Grant **Accessibility** and **Input Monitoring** permissions in **System Settings → Privacy & Security**. Some protected windows cannot be automated.

**Linux X11 (preview):** Run in an **X11 session**. Make the AppImage executable, then launch it:

```bash
chmod +x TakePath-linux-x64.AppImage
./TakePath-linux-x64.AppImage
```

Linux protected-field detection may need AT-SPI bindings and a running accessibility service; persistent credential storage may need a configured Secret Service keyring. **Wayland is currently unsupported** for reliable global recording and replay.

> **Platform status:** Windows is the primary target. macOS and Linux X11 builds are previews and still need broader native-device testing. Window geometry, display scaling, OS permissions, and application privilege levels can affect replay.

## Privacy and safety

TakePath is **local-first**: it does not require an account or upload your workflows to a TakePath server.

- Saved projects may contain entered text, click positions, window information, and screenshots. **Review projects before sharing them.**
- Secure-input values are excluded from project JSON.
- Replay can interact with real applications. Review imported workflows and test them in a harmless environment before using sensitive accounts or privileged windows.
- TakePath may skip text capture when it cannot confidently identify whether a field is protected, rather than risk recording a password.

## Run from source

For contributors or anyone who prefers Python, use **Python 3.12**.

**Windows:**
```bat
setup_windows.bat
start_windows.bat
```

**macOS / Linux X11:**
```bash
bash scripts/setup_unix.sh
.venv/bin/python main.py
```

Run the unit tests with:

```bash
python -m unittest discover -s tests -v
```

## Contribute

Bug reports, ideas, and contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines and [SECURITY.md](SECURITY.md) for security reporting.

TakePath is distributed under the [MIT License](LICENSE).

---

<div align="center">
  <strong>Spend less time re-recording. Spend more time creating.</strong>
</div>
