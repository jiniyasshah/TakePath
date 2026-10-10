# TakePath v1.1.0 — Release acceptance checklist

> Mark each OS as tested **only after actually running the compiled asset on that OS**.

## Windows 10/11 x64
- [ ] Standalone EXE and portable ZIP extract/launch and show the new icon on taskbar and tray at 100% and 150% DPI
- [ ] Select an open browser window and record click → type → scroll → click → stop
- [ ] Replay into the same maximized window without resizing it; verify every recorded action
- [ ] Center cursor before recording and replay; Original and Smooth path modes
- [ ] Retake button never confused with Replay; Restore previous take works
- [ ] Secure input prompt is centered/frontmost and password remains out of exported JSON
- [ ] Unsaved-changes modal is centered and doesn't hide behind browser
- [ ] F7 Pause/Resume, F8 Stop, side mouse buttons, save/load, and multi-select deletion

## macOS Apple Silicon and Intel
- [ ] DMG and ZIP app open with icon on Dock; note these builds are unsigned and not notarized
- [ ] Grant Accessibility and Input Monitoring to the running app
- [ ] Target app enumeration, global click/keyboard hooks, cursor movement, secure-field protection, replay
- [ ] macOS Keychain secure value storage (or session-only fallback)
- [ ] Test both Retina and external-screen coordinates and display scaling
- [ ] Test focus loss and keyboard privacy fail closed

## Linux X11
- [ ] AppImage and tarball work on X11 desktop (test Ubuntu GNOME-on-Xorg and KDE X11 if available)
- [ ] Verify target list, focus protection, click/drag/scroll/mouse side buttons and window boundaries
- [ ] Verify AT-SPI backend reports safe/protected/unknown correctly; never collect passwords as plain text
- [ ] Verify app blocks unsupported Wayland sessions with useful instructions
- [ ] Verify secure secrets use Secret Service only; no plaintext fallback
- [ ] Check multiple-monitor cursor geometry and HiDPI

## Publishing
- [ ] License author/ownership attribution checked
- [ ] v1.1.0 tag CI passes every OS job; checksums generated
- [ ] Download one of each asset from GitHub Releases and test on target system
- [ ] Verify SHA256SUMS.txt matches download files
- [ ] Add real screenshots from the shipping app to README, not mockups
- [ ] Sign/notarize binaries or clearly label unsigned releases
- [ ] Consider marking first macOS/Linux release **Pre-release** until native acceptance checks pass
