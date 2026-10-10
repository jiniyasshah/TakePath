# TakePath V10.1 — Replay reliability hotfix

Fixed release-blocking V10 issues reported during Windows smoke testing.

- Do not call `SW_RESTORE` on every selected replay target. Only restore
  windows if minimized; maximized browser windows keep their original size.
- Correctly type HWND pointers in several Win32 calls, including foreground
  detection, geometry and window activation.
- Anchor Original cursor paths to current position, allowing the Center before
  replay toggle to work without snapping back to the recorded dock position.
- Use modal, topmost, foreground-activated secure input dialogs in replay-ready
  mode. Password values are still never written to project JSON.
- Show Unsaved changes, Replace recording, and Restore previous take prompts
  relative to the visible dock when the editor is hidden.
- Replay failures now show the failing step and error message above the target
  app; the dock remains replay-ready. Success still leaves the target visible.
- Preserve project compatibility, retake history, presets, existing UI and icons.

Verification: unit/source regression suite passed on Linux. Windows input
hooks, Chrome focus behavior, DPI and Qt window stacking require a real Windows
smoke test before public release.
