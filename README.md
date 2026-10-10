<div align="center">
  <img src="assets/takepath-icon.png" width="112" alt="TakePath app icon" />
  <h1>TakePath</h1>
  <p><strong>Record actions. Fix mistakes. Replay a cleaner take.</strong></p>
  <p>Local-first mouse and keyboard action recording, editing and replay.</p>
  <p><strong>Windows stable candidate · macOS preview · Linux X11 preview</strong></p>
</div>

> **1.1.0 cross-platform release candidate.** TakePath records **editable actions**, not video pixels. Use OBS or another screen recorder to capture the corrected replay as video. The Windows version builds on the V10.2 release; Linux and macOS adapters have been implemented but **have not yet passed native-device acceptance testing**. Don't describe them as fully tested until you have checked the downloadable builds.

## Download from GitHub Releases

When a `v1.1.0` tag is pushed, `.github/workflows/release.yml` builds and creates a GitHub Release with these assets (if all jobs succeed):

| Operating system | Release asset | Notes |
|---|---|---|
| Windows x64 | `TakePath-windows-x64.exe` | Single unsigned portable executable |
| Windows x64 | `TakePath-windows-x64-portable.zip` | One-folder build, extract before running |
| macOS Apple Silicon | `TakePath-macos-arm64.dmg` / `.zip` | Unsigned/unnotarized app; Accessibility and Input Monitoring permissions required |
| macOS Intel | `TakePath-macos-x64.dmg` / `.zip` | Unsigned/unnotarized app; Accessibility and Input Monitoring permissions required |
| Linux x64 | `TakePath-linux-x64.AppImage` | **X11 only**; `chmod +x`, then launch |
| Linux x64 | `TakePath-linux-x64.tar.gz` | Portable directory, X11 only |
| All assets | `SHA256SUMS.txt` | Verify download integrity |

GitHub automatically adds **Source code (zip)** and **Source code (tar.gz)** to each published Release.

These binary assets **are built on GitHub runners**, not included in the source ZIP. macOS app signing, notarization, Windows Authenticode signing and auto-updating are **not** configured. Native testing is essential before advertising full support.

## Features

- Discreet, draggable, top-center floating dock with target selection, countdown, pause, stop and explicit Retake.
- Save editable mouse clicks, dragging, scrolls, side buttons, typed text and hotkeys in `.vas.json` project files.
- Action-first editor with multi-select, delete, duplicate, reorder and per-step/bulk timing controls.
- Global original, smooth, straight and gentle cursor movement; original, smooth and instant typing.
- Stage replay via the dock: editor hides, then click **Play** to begin. Play and Retake stay distinct afterward.
- Protected inputs: auto-fill from per-user secure storage or session memory, optionally ask for missing values once before replay, manual-entry, or skip.
- Local project storage, restore a previous completed take in memory, and a visual action map that can be hidden.

## Install and run from source

Use Python **3.12**. Clone the repo or extract the source archive.

**Windows 10/11:** Run `setup_windows.bat`, then `start_windows.bat`. Compile an unsigned one-folder `.exe` with `build_windows_exe.bat`.

**macOS (preview):** Run `bash scripts/setup_unix.sh`, then `.venv/bin/python main.py`. For local app-bundle packaging run `bash scripts/build_macos.sh`. Give Python / TakePath **Accessibility** and **Input Monitoring** permissions in System Settings → Privacy & Security. Some system-controlled windows cannot be automated.

**Linux X11 (preview):** Log into an **X11** session (not Wayland), then `bash scripts/setup_unix.sh` and `.venv/bin/python main.py`. For portable packaging run `bash scripts/build_linux.sh`. For secure text-field recognition, install and make available the distribution's **AT-SPI Python bindings (`pyatspi`)** and a running accessibility service. When field safety cannot be verified, typed characters are **not captured**, rather than risking password disclosure. Most distributions also require a running Secret Service keyring to persist secrets. XWayland sessions hosted by a Wayland compositor are not supported for reliable global recording.

**On all platforms:** Launch target applications at the same user privilege as TakePath, select a window or screen from the dock, and test with a harmless demo workflow first. The operating system may block input injection into secure dialogs, system prompts, or privileged windows.

## Create a GitHub Release like the screenshot

1. Create a public or private GitHub repository and push **this project's contents** to the repository root, including `.github/workflows/release.yml`.
2. Open **Actions** on GitHub and ensure workflows are enabled; repository **Actions permissions** must allow releases to be created by `GITHUB_TOKEN`.
3. Create an annotated tag `v1.1.0` on the intended commit and push it:

   ```bash
   git tag -a v1.1.0 -m "TakePath 1.1.0 cross-platform preview"
   git push origin v1.1.0
   ```

4. Watch **Actions → Cross-platform Release**. Windows, Linux and macOS runners independently build their downloads, then the final job creates a GitHub Release, attaches the files and SHA256SUMS, and generates notes. If any build fails, the release publishing job will **not** run.
5. Download and test each artifact on its target operating system. Mark the release **pre-release** manually until real Windows, Linux X11 and macOS tests pass.

The workflow also supports **Run workflow** for checking builds without publishing a release (no version tag).

## Privacy and known limitations

- TakePath does not transmit workflows to our servers. User-selected project files can include screenshots, text and screen positions; inspect files before sharing them.
- Passwords are never written to project JSON. Windows uses Credential Manager; macOS and Linux use a supported native OS keyring where available; otherwise values stay session-only.
- Focused-field verification fails closed: custom password widgets, incomplete accessibility trees, or missing OS permissions can cause typing actions to be skipped. You can add/edit safe text actions manually.
- Don't run untrusted saved workflows with access to passwords, and never replay unknown actions into a privileged app. Window layouts, scaling, permissions and browser state affect repeatability.
- Linux **Wayland is unsupported** because ordinary apps can't globally intercept/replay input reliably in that security model. X11 support is experimental.
- Windows GUI, macOS and Linux hooks, screenshot geometry and secure storage must still be tested on their native OS; automated checks are primarily pure-Python tests.

## Development

```bash
python -m unittest discover -s tests -q
python -m compileall -q action_studio main.py
```

`action_studio/platform_api.py` supplies platform window discovery, window activation and focused-field safety checks. `recorder.py` and `playback.py` preserve the editor's existing model; Qt UI is in `ui.py`. The platform-specific secure stores are in `secure_store.py`. Release automation lives at `.github/workflows/release.yml`.

Issues, contributions and security disclosures: see [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) and [LICENSE](LICENSE). Review the copyright attribution and license choice before publishing.
