# Contributing to TakePath

Thanks for considering a contribution! Windows GUI and input automation tests are especially valuable.

1. Fork the repository and create a focused branch.
2. Keep secrets, recordings, screenshots, cookies and `.vas.json` files out of commits (except the included harmless example).
3. Run `python -m unittest discover -s tests -v` and `python -m compileall -q action_studio main.py`.
4. For UI/input changes, manually verify on Windows 10/11 using a harmless application before opening a PR.
5. Describe the behavior change, screenshots if helpful (redact private data), and a reproduction/test plan.

This app synthesizes real mouse and keyboard input. Changes affecting privileges, protected-input behavior, screen/window selection or hotkeys require extra review. Never add functionality that stores captured passwords, exports credentials or silently records user activity.
