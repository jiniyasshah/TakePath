# TakePath V10 — First public-release candidate

- **New name and icon:** TakePath. The custom icon is provided as a PNG and multi-resolution Windows ICO, and is installed into the app window, dock tray icon, and PyInstaller-generated `.exe`.
- **Retake in recorder dock:** after a completed recording or replay, click **Retake** to record again with the same target and countdown. No editor round-trip and no extra prompt. The previous finished workflow is only replaced after a nonempty retake is completed.
- **Retake during recording:** the circular-arrow icon beside Pause/Stop discards the current incomplete attempt and starts a fresh countdown.
- **Restore previous take:** after finishing a retake, select **More → Restore previous take**. Keeps exactly one prior take in app memory until restored, another retake completes, a different project is loaded, or the app exits.
- **Safe file behavior:** a successful retake clears the active save path. Pressing Save will prompt for a new path, so a previously saved workflow is never automatically overwritten.
- **GitHub-ready:** MIT license template, contributing/security docs, CI test workflow, source `.zip`, local PyInstaller script with icon and included runtime assets.

Unchanged: target picker, global cursor and typing modes, secure-input preflight/storage, editable action list, pause/stop hotkeys, editor UI, staged replay and V1–V9 `.vas.json` compatibility.

**Limitations:** This is a local input automation app, not a video recorder. Requires Windows 10/11 for native input replay. Native Qt UI, Windows input hooks, and Windows Credential Manager remain to be validated by manual testing on a Windows PC before posting a public compiled binary.
