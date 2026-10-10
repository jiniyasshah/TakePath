# Visual Action Studio V9 — Final interface polish

An incremental update to V8. The project is not rebuilt.

## Updates

1. Removed the redundant editor-header READY TO EDIT label and its reserved spacing.
2. Replaced the problematic blank-looking Timing / Gap native spinbox with a dedicated numeric input. It displays `0.80 s`, accepts 0–3600 seconds to two decimal places, restores invalid/empty entries, and supports typing, Enter, Up/Down increments, and focused wheel increments.
3. Darkened the editor, header, action table, grouped replay bar, menus, and floating dock. Refined hover states and lowered border contrast.
4. Made labels transparent rather than inheriting dark widget backgrounds; this eliminates rectangular background artifacts behind several labels.
5. Preserved the screen/window picker, original/smooth/straight/gentle mouse replay, global typing, secure credentials, project loading and saving, and separate replay-ready dock.

## How to install

Extract the archive, run `setup_windows.bat` (only if dependencies are not installed), then `start_windows.bat`. The `build_windows_exe.bat` script can build a local unsigned executable.

## Testing

57 pure-Python checks pass and all Python files compile. Windows-rendered PySide6 GUI and Windows input APIs cannot be tested in the Linux packaging environment; test on Windows 10/11 before using the project for important workflows.
