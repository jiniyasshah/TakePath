# TakePath 1.2.0 Beta 2 — Release acceptance checklist

> Automated CI verifies code and package creation; it **does not** demonstrate that recording/replay works on a real desktop. Check an item only after testing the **downloadable compiled artifact** on that OS.

## Windows 10/11 x64 — release gate

- [ ] Run `TakePath-windows-x64-setup.exe` on a clean **non-Python** Windows profile; no `python.exe` or `pip install` required
- [ ] Confirm Setup installs under `%LOCALAPPDATA%\Programs\TakePath`, creates a Start Menu shortcut, and optionally a desktop shortcut
- [ ] Launch via Start Menu and verify the app title displays `1.2.0-beta.2`; verify `Windows Settings → Installed Apps → TakePath → Uninstall` removes the installed application
- [ ] Check installing the same version again updates in place without a duplicate Installed Apps entry; check the program is closed before install/uninstall

- [ ] Run the built `TakePath-windows-x64.exe` and extracted portable ZIP app; tray/dock launch without Python installed
- [ ] At 100% and 125%/150% display scaling, record and replay a simple non-sensitive Chrome workflow: click → type → scroll → click → stop
- [ ] Record a drag-and-drop plus side-button/shortcut workflow; check F7 pause/resume, F8 stop, click and drag release, and key-repeat/held Backspace
- [ ] Save a new `.vas.json` project, reopen it, and verify edited actions, mouse presets, and Adaptive wait setting survive
- [ ] Replay a *new window-scoped* workflow after moving the same Chrome window 200+ pixels; clicks and drags target the intended controls
- [ ] Replay after **moderate** window resize; verify the page's responsive layout has not moved the controls in unexpected ways
- [ ] Test a secondary monitor (including a monitor left of primary, if available); check target coordinates and screenshot crop
- [ ] Verify **old** `.vas.json` projects still open and use their previous absolute positions when no window anchor exists
- [ ] With **Adaptive wait on**, test a slow page load after a click, an unchanged page, a continuously animating page, and F8 cancellation
- [ ] Add a manual **Wait** step for expected window title; check a matching condition and a deliberately impossible condition (timeout stops safely)
- [ ] While replaying a window-scoped take, open the Start menu; replay enters WAIT TARGET and stops safely if the original window stays unfocused
- [ ] Use a **dummy password** in a real native/browser password field and check secure auto-fill is blocked if the destination cannot be verified
- [ ] Confirm no secret is written to project JSON; manual/skip modes work; replay errors remain visible on the dock
- [ ] Test Replay vs Retake, session restore, multi-select deletion, and unsaved-project confirmation

## macOS Apple Silicon and Intel — preview checks

- [ ] DMG and ZIP app launch, dock icon renders, no unhandled startup errors
- [ ] Grant Accessibility and Input Monitoring; record click/type/drag/scroll and replay in an ordinary app
- [ ] Check secure input fail-closed behavior with a **dummy password**, then remove saved dummy values from keychain
- [ ] Wait-step title/focus behavior and adaptive visual wait, including cancellation
- [ ] External display / Retina coordinate scaling and moderate window movement; old project compatibility
- [ ] Document unsigned and unnotarized status; avoid claiming native acceptance without testing both architectures

## Linux X11 — preview checks

- [ ] AppImage and tarball launch in an X11 desktop session
- [ ] Verify global mouse/keyboard hooks and pointer replay work with an ordinary unprivileged target
- [ ] Check Wait step, adaptive wait and F8 cancellation with two normal X11 apps
- [ ] Check moved/resized window coordinate mapping, including HiDPI and multi-monitor
- [ ] Protected input handling uses AT-SPI where available; no plaintext secret fallback; dummy credentials only
- [ ] Wayland is rejected with a useful message; do not claim Wayland support

## Packaging and publication

- [ ] **Main CI** has passed for the intended release commit
- [ ] Trigger **Actions → Cross-platform Release → Run workflow** on `main`; all 4 platform builds succeed
- [ ] Download the **Windows Actions artifact** from that run and complete the Windows release-gate checks *before creating the beta tag*
- [ ] Review packaging output for missing DLLs/plugins and unexpected dependencies
- [ ] Confirm release note warnings are accurate (signed/notarized status; preview platform limitations)
- [ ] Push a **new** `v1.2.0-beta.2` tag against the tested commit; never repoint an already published tag
- [ ] The tag-triggered workflow finishes Windows, Linux, macOS x64, macOS arm64 and Publish jobs
- [ ] Release page is explicitly marked **Pre-release**, contains the version notes and all ten downloadable assets including Windows Setup
- [ ] Download the published Setup EXE, standalone EXE, and portable ZIP; confirm all three launch independently after publishing
- [ ] Validate `SHA256SUMS.txt` against downloads
- [ ] Native macOS/Linux devices are tested **before** promoting a later stable tag
- [ ] License attribution and release notes reviewed; README remains user-facing

If a native test fails, keep the beta tag unpublished until fixed, or clearly disclose the tested limitations. A green Actions run alone does not establish production stability.
