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
  its existing metadata file is `0600`. Credentials are now configured in
  Secret Service for the selected origin. A live bounded `magnus ls` completed
  successfully; no Magnus mutation command was exposed or attempted.
- Live Rock reads: the six fixed REST v1 endpoint/OData requests and the
  Personal Links action all returned successfully with the Magnus-backed
  cookie. A privacy-safe no-match query returned no records and no unavailable
  categories; Personal Links returned 15 same-origin entries, recorded only as
  a count during verification. The tenant edge returned 403 for Python's
  default user-agent and 200 for the transparent `Rock-Lens/0.1` identifier,
  which is now fixed in the client.
- Broker/OAuth/Magnus/REST/navigation/instance tests: 43 passing via
  `python3 -m unittest discover -s tests -v`; `ruff check`, `ty check`, bytecode
  compilation, and `git diff --check` also pass.
- QML validation: Qt's full-path `qmllint` parsed the plugin without errors
  (standalone lint reports expected unresolved Omarchy import warnings). The
  installed plugin hot-reloaded, re-registered, started a replacement broker,
  and opened in the running shell with no Rock Lens QML errors in the bounded
  log inspection.
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
- The broker status contract returns exactly six categories and an explicit
  context. PROD is active after setup; it uses only live Rock responses and has
  no synthetic fallback.
- The installed Links view exposes no raw URL transport. Current-user Personal
  Links now load through the authenticated same-origin action; local Quick
  Returns are owner-only, per-origin, deduplicated, and limited to 20.
- Magnus setup is available inside the PROD panel with the Rock domain first,
  followed by username and masked password fields. The origin is HTTPS-only and
  owner-only; credentials are stored per origin by the broker in Secret Service,
  the password is cleared after submission, and neither credential is echoed in
  the response contract.
- Magnus 0.1.0's password prompt and nested cookie cache were verified against
  the installed CLI. Rock Lens handles both without persisting its ephemeral
  plaintext Magnus profile or exposing the password/cookie.
- Omarchy loaded plugin version `0.5.0` after shell restart, registered the
  Rock Lens IPC target, started the updated broker, and opened the panel. The
  owner-only runtime boundary remained `0700`/`0600`.
- The final installed broker was exercised through its real Unix socket in
  PROD. It returned 15 Personal Links and 18 live search rows (three from each
  of the six categories), with zero unavailable categories. After the all-route
  update, all 18 rows reported `canOpen: true`. Only counts and category names
  were printed during verification; no record or link values were retained.
- The Group projection now uses the Rock Model Map relationship
  `Group.GroupType` and requests only `GroupType.Name`. A live privacy-bounded
  check returned three Group rows with three populated Group Type subtitles;
  only counts were printed.
- The six fixed REST reads now start concurrently while retaining deterministic
  category ordering. A final clean-restart PROD socket measurement improved
  from the prior 2.432/2.197-second samples to 1.843 seconds cold and 0.315
  seconds warm. Cold timing remains dependent on Rock/Magnus login latency. The
  validated cookie is reused only in broker memory with a 15-minute idle
  timeout and is cleared by a timer, domain or credential change, total
  authenticated request failure, or broker restart. No Magnus temporary profile
  remained afterward.
- Search keyboard editing was verified against the installed panel after a
  shell restart. The injected sequence `zzzz`, Space, `z`, Backspace,
  Backspace produced `zzzz`, confirming that both Space insertion and
  Backspace deletion reach the focused native search field. The test query was
  cleared afterward, and the temporary capture was deleted because its crop
  included desktop edges.
- Keyboard traversal was verified in the installed DEV panel: Down selected
  successive results, Tab moved from the search field to the first result and
  then to Links, and Shift+Tab returned to the final result. Selection remained
  visible and the panel followed it automatically. Enter and Space dispatch the
  selected verified live target through the existing opaque-ID navigation
  operation; DEV remains non-opening.
- All six live search categories now create opaque, exact-origin navigation
  targets. Adapter coverage asserts the canonical Person, Group, Workflow Type,
  Scheduled Job, Page, and Content Channel Item routes and requires `canOpen`
  for every transformed live result.
- The panel now combines its title, environment badge, and Search/Links tabs in
  one compact header; uses a shorter search prompt, tighter row spacing, a
  concise connection line and footer, and shows the repeated Open control only
  on the selected row. Personal Links load only when Links is selected, so that
  network read cannot block the initial Search view. DEV navigation omits the
  per-origin PROD Quick Return history.
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
