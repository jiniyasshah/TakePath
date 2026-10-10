# Visual Action Studio V8 — Window picker and editor-toolbar polish

## Recorder target picker

- Filters taskbar-unrelated Windows HWNDs before showing them: shell desktop surfaces (`Progman` / `WorkerW`), Windows Input Experience, common shell/input processes, cloaked windows (DWM), tool windows, click-through/no-activate overlays, owned popups, and windows below a usable minimum size.
- Uses connected monitor entries under **Screens**. Live app windows appear under **Applications**; *Follow active application* remains available.
- Resolves the owning executable where Windows permits and shows recognizable app names and executable icons. Tooltips preserve full window titles.
- Removes identical same-title/process UI surface duplicates, including common Settings / Realtek mirrored host entries. Separate windows with distinct titles are preserved.
- Refreshes entries every time the picker opens. Keeps HWND-based capture and playback (no change to recorded action format).

## Action editor

- Replaced the footer's alternating tiny dark label blocks with a single soft-surface replay toolbar.
- Each setting now has a small caption **above** its input and consistent input height/padding: **Timing / Gap**, **Mouse Path**, **Typing Style**, **Cursor Start**, **Playback Speed**.
- Replaced the plain replay-center checkbox with a checkable icon-led pill; state still synchronizes with the dock.
- Replaced the boxed replay estimate with low-contrast typography; estimated time now responds to playback speed.
- No more tiny spinner arrows intruding on Uniform Gap. Values remain editable directly.
- On narrow windows/high display scaling, the toolbar scrolls horizontally instead of overlapping controls.

## Preserved behavior

- Minimal top-center recording dock and two-step replay.
- Secure-input auto-fill / session-only / credential storage and preflight prompts.
- Existing mouse and typing presets, uniform timing, action edits, multi-select deletion, optional visual map, side buttons, save/load.
- V1–V7 `.vas.json` compatibility.

## Validation / limitations

52 pure-Python regression checks passed; source compiles, and the release ZIP passed its CRC/integrity check. This build environment is Linux and does not have PySide6 or Windows APIs; **window enumeration, actual native icon extraction, Qt rendering and recording/replay have not been tested here**. Use a harmless workflow for an on-PC smoke test. The picker is deliberately a pragmatic *taskbar-like* approximation, not an exact Windows Task View clone. Certain specialized applications may be filtered; in that case use **Follow active application** or the screen entry.
