# Verification record

- Target OS shell: Omarchy `4.0.2-1` (meets 4.0.2+ target).
- Target Rock version: unknown until an authenticated tenant capability is
  available; the mock contract is version-neutral.
- Rock KB: public service health `ok`; canonical projection ready; skill 1.12.1
  installed user-scoped. Important REST authorization guidance is official and
  source-backed; ServiceJob and ServiceJobHistory shapes are official Model Map
  evidence.
- Rock OAuth: authorization-code, S256 PKCE, exact state validation, refresh,
  owner-only config, Secret Service stdin handling, and public response
  redaction are covered by local tests. No live login was attempted because no
  tenant-specific OpenID client is configured on this machine.
- Public discovery probe: Rock's public demo returned its canonical HTTPS
  issuer and the expected `/Auth/Authorize` and `/Auth/Token` endpoints; the
  broker accepted that document under its exact-issuer/same-origin checks.
- ONE&ALL Rock RMS MCP V3: not exposed to this running host at implementation
  time.
- Production SQL: not attempted because V3 `/v3/sql/health` was unavailable and
  no guarded `sqlread` identity was proven.
- Magnus: upstream package `rock-magnus-cli` version `0.1.0` is installed. Its
  raw credential/cookie persistence and URL handling were isolated behind the
  HTTPS-only, exact-origin, same-origin, read-only adapter documented in
  `docs/MAGNUS.md`; no production mutation path is exposed.
- Magnus's three existing local config directories are owner-only (`0700`) and
  its existing metadata file is `0600`. The hardened adapter reports available
  but not configured; no live tenant request was made because credentials have
  not yet been entered.
- Live Rock reads: gated; no tenant, actor, or Rock version claimed.
- Broker/OAuth/Magnus tests: 18 passing via
  `python3 -m unittest discover -s tests -v`; `ruff check`, `ty check`, bytecode
  compilation, and `git diff --check` also pass.
- QML validation: run `qmllint plugin/oneall.rock-lens/*.qml` when available.
- Live shell: plugin discovered and enabled, bar entry added, `Super+R` binding
  loaded with no Hyprland config errors, and shell summon returned `ok`.
- Restart persistence: broker PID changed across an Omarchy shell restart,
  owner-only socket/state permissions remained `0700`/`0600`, explicit context
  remained `DEV`, plugin re-registration completed, and the final summon
  returned `ok`.
- Shortcut registration: Hyprland reports `modmask: 64`, key `R`, description
  `Rock Lens`. Synthetic input injection was inconclusive, so the registered
  binding plus its exact IPC target were verified separately.
- Visual verification: `outputs/rock-lens-mvp.png` is a panel-only capture. It
  shows explicit DEV context, mock/live health separation, all six synthetic
  entity categories, read-only job status, and a privacy-safe Person Quick
  Look. The full desktop was excluded from the retained artifact.
- Full OS logout/login was not performed; shell restart and user-config
  persistence cover the non-disruptive acceptance check.

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
  `DEV`, `mock: healthy`, a sanitized `OAuth setup needed` state, and no
  healthy live capability. Calling login while unconfigured failed closed and
  did not open a browser.
- Omarchy loaded plugin version `0.2.0` after shell restart, registered the
  Rock Lens IPC target, started the updated broker, and opened the panel. The
  owner-only runtime boundary remained `0700`/`0600`.
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
