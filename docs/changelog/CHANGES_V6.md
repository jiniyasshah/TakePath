# V6 — editable secure input and preflight replay

- Recognized password inputs record safe action markers, never keystrokes.
- Secure actions default to Auto-fill, with Manual entry and Skip options available.
- Editor can configure a secret for the current session or persist it in Windows Credential Manager.
- Secure values are not written into `.vas.json` files, QSettings or clipboard.
- Missing values are requested together when Play is clicked on the replay-ready dock, *before* countdown.
- Canceling the preflight does not start playback. Only explicitly Manual actions pause at the target application.
- Forget saved credential removes its persisted value; Type actions can be converted to secure markers.
- Preserved top-center minimal dock, staged replay, action-first editor, global cursor smoothing, X1/X2 mouse click replay and V1–V5 project loading.
- 37 pure-Python automated regression checks pass; Windows GUI and Credential Manager need real-device validation.
