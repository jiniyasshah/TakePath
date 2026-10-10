# Visual Action Studio V4 — changes

- Default floating recorder position: **top center** (fresh V4 settings namespace). Optional top-left, top-right and bottom-center presets; manual drag persists.
- Record button is now antialiased QPainter artwork with a geometrically centered white dot rather than a font glyph.
- Refined dock and editor spacing, surfaces, separators and action table styling.
- Action list is primary. Action map defaults to compact, can be hidden or expanded, and can be resized with a splitter. Inspector remains available regardless of preview size.
- **New capture** in editor now closes editor and presents the dock; recording only begins when you press Record and confirm replacing old actions.
- Playback no longer activates the editor on completion, and the dock exposes an **Open editor** label after replay; the target app remains in front.
- Side mouse buttons X1/Back and X2/Forward recorded from pynput hooks, serialized, exposed in action inspector, and replayed via Win32 SendInput.
- Duration-limit controls remain removed; recording and playback end on stop or natural playback completion.

The editor screenshot is an optional final-frame still, not a video. Window/input-hook runtime testing requires Windows.
