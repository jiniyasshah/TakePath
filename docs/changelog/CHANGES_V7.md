# V7 — Smoother dock, stronger editor, better replay presets

## Recording dock
- Top-centered floating bar retained; capture picker arrow now rendered via an aligned SVG icon.
- Target picker discovers physical monitors and enumerates open top-level application windows by title each time it opens.
- Choose one actual window, the active window, or a specific monitor; selected windows are brought to the front when recording starts.
- Physical-pixel monitor bounds are used when recording on a specific screen, to avoid mixing Qt logical coordinates with Windows input coordinates.

## Editing and playback
- Cursor presets are project-wide: Smooth curved, Straight, Gentle curved, Original recorded path.
- Typing is project-wide: Original keypress rhythm, Smooth fixed-delay typing, Instant. Original rhythm is newly recorded for text actions; edited text of a different length falls back to smooth.
- Password values, length, and keypress timings are never recorded in secure-input actions. Secure inputs are still auto-fillable using the V6 credential workflow.
- The visual action map is hidden by default (still supports compact, large, and fullscreen). The selected-action inspector is no longer nested inside the preview, so it remains available even with the preview hidden.
- Action timeline, single/multi-select delete, editable text, and per-action delays remain.

## Compatibility
- Reads older V1–V6 projects. New fields use safe defaults when absent.
- This is source code plus Windows install/build scripts, not a precompiled EXE.
- Automated core/model regression tests passed; native Windows UI, monitor discovery, and live input hooks require a real Windows smoke test.
