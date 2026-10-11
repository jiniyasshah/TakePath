# TakePath 1.2.0 Beta 1

**Pre-release · Windows primary target · macOS and Linux X11 preview**

TakePath records editable mouse and keyboard actions so you can clean up a take and replay it in the target application. It is **not a video recorder or MP4 exporter**; use OBS or another screen recorder if you need a finished video.

## What's improved

- **More reliable capture:** independent mouse-button handling for overlapping presses and drags, plus repeated typing/backspace/arrow input during held keys.
- **Safer replay:** playback briefly waits for the original selected window to regain focus between actions. If it does not return, replay stops instead of sending input elsewhere.
- **Protected inputs:** saved passwords are only auto-filled when the OS reports a protected field is focused. Unknown or custom fields can be blocked intentionally.
- **Manual Wait steps:** insert a Wait action into the action editor for a window title, focused field, or (on Windows) a named accessible control, with an editable timeout.
- **Adaptive visual waiting:** optional visual-settling checks after clicks/navigation to reduce timing problems. The check is bounded and can fall back; it does **not** guarantee DOM readiness, network idle, or that a particular web button is clickable.
- **Window-relative replay:** new window-scoped recordings remember the target's original bounds and adjust pointer actions if the window is moved or moderately resized. Older projects without an anchor keep their original screen coordinates; screen-wide workflows are unchanged.
- **Regression fixes:** added tests and fixes for edge-case timeout loops that could hang the test workflow.

## How to try the beta

1. Download the file for your platform from this release and open TakePath.
2. Record a short workflow in a harmless app. In the editor, review the action list and choose optional **Adaptive wait**.
3. Try adding a **Wait** step after a page/navigation click when a concrete condition must be met.
4. Replay in the original target window. Try moving the window between capture and replay to check coordinate remapping. Use **F8** to stop at any time.
5. Capture the corrected replay with a separate screen recorder if needed.

## Known limitations and precautions

- **Beta quality:** automated tests and CI builds do not replace native desktop tests. The new UI behavior, display scaling, focus security and multi-monitor mapping require real-device smoke tests.
- Visual stillness does **not** prove that an app or website is ready. Use an explicit Wait step for important transitions.
- Proportional window remapping cannot reliably compensate for responsive reflow, changing browser zoom, different page layouts, or a rearranged toolbar. Very large resizing may stop replay for safety.
- Focusing a different window during window-scoped replay causes a short wait and then a safe stop. Screen-scoped workflows have different focus rules.
- macOS and Linux X11 remain **preview** platforms. Linux Wayland is not supported.
- Downloads are **unsigned**; macOS packages are **not notarized**. The OS may show security warnings.
- Saved project files can contain text and screenshots. Review them before sharing. Do not replay untrusted workflows in sensitive applications.

Report reproducible issues at https://github.com/jiniyasshah/TakePath/issues and see [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) for native acceptance checks.

