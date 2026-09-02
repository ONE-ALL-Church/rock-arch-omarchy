# Verification record

- Target OS shell: Omarchy `4.0.2-1` (meets 4.0.2+ target).
- Target Rock version: unknown until an authenticated tenant capability is
  available; the mock contract is version-neutral.
- Rock KB: public service health `ok`; canonical projection ready; skill 1.12.1
  installed user-scoped. Important REST authorization guidance is official and
  source-backed; ServiceJob and ServiceJobHistory shapes are official Model Map
  evidence.
- ONE&ALL Rock RMS MCP V3: not exposed to this running host at implementation
  time. No OAuth login was attempted.
- Production SQL: not attempted because V3 `/v3/sql/health` was unavailable and
  no guarded `sqlread` identity was proven.
- Magnus: requested npm metadata check for `rock-magnus-cli` returned registry
  `E404 Not Found`, so package identity could not be verified and installation
  was not attempted. `magnus` remains unavailable; authentication is gated.
- Live Rock reads: gated; no tenant, actor, or Rock version claimed.
- Mock tests: run `python3 -m unittest discover -s tests -v`.
- QML validation: run `qmllint plugin/oneall.rock-lens/*.qml` when available.
- Live shell: plugin discovered and enabled, bar entry added, `Super+R` binding
  loaded with no Hyprland config errors, and shell summon returned `ok`.

No telemetry, feedback, production write, job trigger, deploy, or publication
was performed.
