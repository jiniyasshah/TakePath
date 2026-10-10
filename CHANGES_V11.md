# TakePath 1.1.0 — Cross-platform release candidate

- Redrew the taskbar/tray icon for clear readability at 16–48px. Includes multi-resolution `.ico`, `.icns`, and PNG.
- Added desktop platform adapters for Windows, Linux X11, and macOS, using native window enumeration/focus and cross-platform input hooks.
- Added best-effort native protected-field detection for macOS Accessibility / Linux AT-SPI, failing closed when controls cannot be inspected.
- Added per-user system credential-store support for macOS Keychain and Linux Secret Service, without plaintext fallback.
- Added local setup/build scripts for macOS and Linux.
- Added GitHub Actions release pipeline for Windows standalone EXE, Windows portable ZIP, Intel and Apple Silicon macOS DMG/ZIP, Linux X11 AppImage/tarball, and SHA-256 checksums.
- Updated README with release instructions and platform limitations.

## Release warning

This is **not** a validated all-platform stable release: native macOS and Linux functional testing, Gatekeeper/code signing, Windows signing, and real-machine replay testing remain open. Do not publish it as stable until the release CI succeeds and devices pass acceptance checks.
