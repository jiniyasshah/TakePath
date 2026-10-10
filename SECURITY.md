# Security and privacy

TakePath works with the real keyboard/mouse and may interact with sensitive applications. Use only on systems and apps you control or have permission to automate.

**Secure input:** Recognized password fields are represented by protected markers. Optional credentials are stored in Windows Credential Manager under the current Windows user, or in session memory. Project JSON files must never contain those passwords. An untrusted workflow may direct credential input to an unintended app or field; verify the target before replay.

**Input capture:** Start and stop recording explicitly; the UI displays a visible recording state. F8 stops. Input hooks and UI Automation support vary by app and privilege level.

**Reporting vulnerabilities:** Before publishing the repo, configure a private security reporting mechanism in GitHub's Security tab; avoid posting exploitable details or captured secrets in public issues. The repository owner should supply a support contact before inviting public reports.

TakePath does not upload captured actions to a server. Recording files and snapshots can still contain private information; do not publish those files or grant them to untrusted parties.

## Cross-platform notes

TakePath relies on OS-specific accessibility permissions. Linux recording requires X11; Wayland is not supported. macOS requires Accessibility and Input Monitoring permission. Secret values are never embedded into `.vas.json` files. If a native keyring is unavailable or untrusted, use session-only secrets.
