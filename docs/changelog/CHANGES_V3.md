# Visual Action Studio V3 — changes from V2

- Replaced the tall configuration dock with a rounded dark **horizontal floating recorder bar**; opens by default and can be dragged or snapped left/center/right.
- Added a compact target menu (**focused window** or **desktop-wide actions**), stopwatch menu (0 / 3 / 5 / 10 seconds), and quick center-cursor toggle.
- Added condensed live REC / PAUSED / PLAY status with timer and Stop/Pause actions, keyboard F7 pause for recording, and minimized system-tray restore.
- Removed duration-limit UI and playback-limit enforcement. Recording and playback end only when finished or explicitly stopped/cancelled.
- Moved the **single global Smooth/Original setting** out of the recorder bar into the editor, preserving original cursor samples.
- Restructured the editor with a dark header, small left action rail, enlarged visual still/coordinate preview, conditional inspector, and bottom timeline.
- Uniform gap now acts on *selected* actions when selection exists, or all actions otherwise. Multiselect Delete is retained.
- Added 'Center before replay' in the editor, independent of the recording-center toggle.
- Added editable project `target_mode` with fallback for older V1/V2 files. Multi-app desktop recording is an optional advanced scope, not a video recorder.
- Suppresses mouse samples that hit the always-on-top control bar; attempts Windows capture-exclusion affinity and uses safe target-focus checks.
- Added four V3 regression tests. See README for known limitations and Windows testing caveats.
