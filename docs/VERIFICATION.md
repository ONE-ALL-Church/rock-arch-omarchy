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

## Final local integration verification

- Restarted the real Omarchy shell, rescanned plugins, and confirmed shell IPC
  recovered.
- The broker restarted under a new process, recreated its owner-only runtime
  boundary (`0700` directory and `0600` socket), and preserved explicit `DEV`
  context in the owner-only state file.
- `omarchy plugin list --json` reports `oneall.rock-lens` enabled, and
  `shell.json` retains it immediately after `omarchy.tailscale` on the right
  side of the bar.
- Hyprland reports the `Super+R` Rock Lens binding. After the shell restart,
  the binding's registered summon command returned `ok` and opened the panel.
- `hyprctl reload` succeeded and `hyprctl configerrors` was empty.
- The broker status contract returned exactly six mock categories, explicit
  `DEV`, `mock: healthy`, and no healthy live capability.
- The privacy-safe visual evidence is
  [`outputs/rock-lens-mock-launcher.png`](../outputs/rock-lens-mock-launcher.png).
  It is cropped to the Rock Lens panel and shows only synthetic records,
  explicit `DEV`, fail-closed live health, all six categories, and read-only
  wording. An earlier full-desktop capture was inspected, found to contain
  private desktop content, and deleted without being committed.
- A second bounded capture after shell restart matched the committed evidence
  visually; the temporary verification captures were removed.
- A full OS logout/login cycle was not performed. Shell restart, plugin rescan,
  broker process replacement, state persistence, binding registration, and
  post-restart panel opening were verified in the active session.

No telemetry, feedback, production write, job trigger, deploy, or publication
was performed.
