# Visual Action Studio V5 — changes

### Protected-field handling

- Recognized password fields no longer disappear silently from the workflow. Recording creates one **Protected input** marker per contiguous protected typing session, not a record of the characters, text length, or keys.
- The project loader and exporter redact any `text`/`key` payload attached to a protected marker; passwords are never written to `.vas.json`.
- During replay the worker safely pauses at protected input until the user types the password directly into the target app and presses Continue in the dock or F7. F8 stops playback at any time.
- Add Protected input actions manually for fields that cannot be recognized by Windows UI Automation.

### Two-stage replay

- Clicking **Replay** in the editor **only hides the editor and prepares the dock** in a blue Play-ready state; no countdown starts yet.
- Clicking **Play on the dock** starts the playback countdown, and then the action replay.
- Clicking **Open editor** on the dock cancels replay-ready state and returns to editing; canceling the countdown leaves the dock ready for replay.
- When playback ends, the target application stays in front and the dock offers Open editor; no automatic return to the editor.

### Compatibility

- V1–V4 JSON projects remain loadable. No new project schema is required.
- Recording, editing, global motion settings, mouse side-buttons, saving/loading, and timing controls remain.
- 30 regression checks pass on a non-Windows system. Windows UI and input-hooks must still be smoke-tested on a Windows PC.
