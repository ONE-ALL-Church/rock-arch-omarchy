# Verification record

- Target OS shell: Omarchy `4.0.2-1` (meets 4.0.2+ target).
- Target Rock version: unknown until an authenticated tenant capability is
  available; the mock contract is version-neutral.
- Rock KB: public service health `ok`; canonical projection ready; skill 1.12.1
  installed user-scoped. Important REST authorization guidance is official and
  source-backed; ServiceJob and ServiceJobHistory shapes are official Model Map
  evidence.
- Rock login: the production path now posts credentials directly to the
  selected instance's `/api/Auth/Login`, accepts only its `.ROCK` cookie, and
  stores only the per-profile username/password in Secret Service. The cookie
  remains memory-only with a 15-minute idle expiry.
- Public discovery probe: Rock's public demo returned its canonical HTTPS
  issuer and the expected `/Auth/Authorize` and `/Auth/Token` endpoints; the
  broker accepted that document under its exact-issuer/same-origin checks.
- ONE&ALL Rock RMS MCP V3: not exposed to this running host at implementation
  time.
- Production SQL: not attempted because V3 `/v3/sql/health` was unavailable and
  no guarded `sqlread` identity was proven.
- Magnus: Rock Lens implements bounded descriptor/tree/file reads and exact
  descriptor-provided mobile app builds natively with the authenticated Rock
  cookie. Neither `rock-magnus-cli`, Node, npm, nor Rock MCP is a runtime
  dependency. No file write, upload, create, or delete path is exposed.
- Live Rock reads: the six fixed REST v1 endpoint/OData requests and the
  Personal Links action all returned successfully with the native Rock session
  cookie. A privacy-safe no-match query returned no records and no unavailable
  categories; Personal Links returned 15 same-origin entries, recorded only as
  a count during verification. The tenant edge returned 403 for Python's
  default user-agent and 200 for the transparent `Rock-Lens/0.12` identifier,
  which is now fixed in the client.
- Broker/auth/Magnus/REST/navigation/instance tests: 79 passing via
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
  owner-only socket/state permissions remained `0700`/`0600`, the normal-mode
  context was migrated to `PROD`, plugin re-registration completed, and the
  final summon returned `ok`.
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
  boundary (`0700` directory and `0600` socket), and stored enforced `PROD`
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
- The installed navigation views expose no raw URL transport. Current-user
  Personal Links load through the authenticated same-origin action; local
  Recent Links are owner-only, per-origin, deduplicated, and limited to 20.
- Magnus setup is available inside the PROD panel with the Rock domain first,
  followed by username and masked password fields. The origin is HTTPS-only and
  owner-only; credentials are stored per origin by the broker in Secret Service,
  the password is cleared after submission, and neither credential is echoed in
  the response contract.
- Magnus 0.1.0's password prompt and nested cookie cache were verified against
  the installed CLI. Rock Lens handles both without persisting its ephemeral
  plaintext Magnus profile or exposing the password/cookie.
- Omarchy loaded plugin version `0.8.0` after shell restart, registered the
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
- Entity prefixes are broker-enforced scopes rather than display-only filters.
  Contract coverage checks short/full aliases, literal handling of unknown
  prefixes, empty scoped terms, invalid internal categories, and the single
  fixed-endpoint boundary. A live privacy-bounded `g:` check returned only three
  Groups; a warm Pages scope completed in 0.153 seconds. No record values were
  printed.
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
- The panel now combines its title and Search/Personal Links tabs in one compact
  header; uses a shorter search prompt, tighter row spacing, a concise
  connection line and footer, and shows the repeated Open control only on the
  selected row. An empty Search shows local Recent Links; Personal Links load
  only when their tab is selected. The context badge is absent in normal mode
  and reappears only when developer mode is enabled. DEV navigation omits the
  per-origin PROD Recent Link history.
- Plugin version `0.7.0` replaces the combined Links view with a dedicated
  Personal Links tab and shows the local Quick Return history as Recent Links
  whenever Search is empty. Typing swaps Recent Links for results immediately.
  The scoped broker contract returned six Recent Links in 0.0016 seconds with
  no Personal Links fields; the independent live Personal Links request
  returned 15 entries in 1.4136 seconds. Only counts and response keys were
  printed. After a clean shell restart, opening the empty Search view left the
  live REST health state `unknown`, confirming that it had not fetched Personal
  Links. Installed-panel checks confirmed the two-tab layout, Tab/Shift+Tab
  transitions, and Backspace returning from a selected Recent Link to an
  editable search field. Temporary captures were deleted.
- Plugin version `0.8.0` gates synthetic DEV behind the exact
  `ROCK_LENS_DEVELOPER_MODE=1` process setting. Contract tests cover the exact
  flag value, PROD default, migration of a persisted DEV value, disabled mock
  capability, and broker rejection of direct DEV requests. With the flag absent,
  the installed broker restarted in PROD, reported `developerMode: false`, and
  returned `developer_mode_disabled` for a direct context-switch request. The
  state file remained `0600`; the runtime directory/socket remained
  `0700`/`0600`. A panel-only visual check confirmed that the context badge and
  switch are absent, and its temporary capture was deleted.
- Plugin version `0.9.0` adds an in-panel Settings view and owner-only
  multi-profile metadata. Stable random profile IDs isolate credentials and
  Recent Links even when two accounts share one Rock origin. The broker supports
  add, switch, connection test, login update, sign-out, removal, category
  selection, person-context visibility, recent-history control, and
  close-after-open. Existing single-instance metadata and validated Recent Links
  migrate without deleting the rollback source. Unit tests cover migration,
  permissions, same-origin isolation, preferences, sign-out, and removal. The
  installed v0.9.0 panel loaded without QML errors, the migrated profile passed
  a credential-only connection test, and a post-migration scoped Groups read
  returned three live rows with no unavailable category in 0.545 seconds. Only
  counts and category names were printed. The temporary Settings capture was
  deleted after inspection.
- Plugin version `0.9.1` tightens the Settings hierarchy by collapsing saved
  credentials behind Change login, shortening connection and preference
  controls, and moving the confirmed Clear action into the Recent Links header.
  Workflow Types is now the user-facing category name; `w:`, `wt:`,
  `workflow:`, `workflowtype:`, and `workflowtypes:` all scope the fixed
  `/api/WorkflowTypes` read. The installed panel loaded without QML errors and
  fit the profiles, collapsed connection controls, all preferences, all six
  category controls, and footer in one view. A live `w:` check returned three
  Workflow Type rows with no unavailable category in 0.936 seconds; only the
  count and internal category label were printed. Sixty tests cover the broker
  Clear operation and local history-file removal. Temporary visual captures
  were deleted after inspection.
- Plugin version `0.10.0` separates universal Rock login from optional Magnus
  access. Every configured profile authenticates natively at its own Rock
  origin and can use the six allowlisted search categories, Personal Links,
  and local Recent Links without Magnus. A descriptor probe adds the Magnus tab
  only when the selected account is authorized; that tab currently exposes
  opaque-ID folder browsing, bounded UTF-8 preview, and SHA-256 only. Contract
  coverage explicitly verifies that live search and Personal Links continue
  when Magnus is unavailable.
- The packaged plugin now includes the Python broker and root manifest, starts
  with the system Python from its installed directory, and has no Rock MCP,
  Magnus CLI, Node, npm, pip, or uv runtime dependency. The full repository and
  installed copy both pass Omarchy plugin validation. The installed broker's
  working directory is the installed plugin path, and the live on-demand shell
  summon returns `ok`.
- The live installed v0.10.0 broker authenticated with the migrated profile,
  reported native Rock connected and Magnus available, returned a six-folder
  Magnus root without exposing names or paths, and completed a random no-match
  six-category Rock search with no unavailable category. Only counts and
  capability states were printed.
- Sixty-three unit tests pass. Python bytecode compilation, `git diff --check`,
  Omarchy plugin validation, standalone QML parsing, `hyprctl reload`, and an
  empty `hyprctl configerrors` check also pass. A full shell restart was not
  repeated because the session was locked; plugin rescan, installed-path broker
  execution, and live summon provided the non-disruptive checks.
- Plugin version `0.10.1` makes initial status and Rock login independent from
  the optional Magnus probe. PROD search cannot enter an in-flight state before
  the saved-login status is known, error and malformed-response paths clear all
  pending UI flags, and sign-in now shows progressive slow-response feedback
  with an 18-second UI watchdog. Magnus detection runs after the core response
  and no longer holds the login button on Saving. Switching accounts on the
  same Rock origin also resets Magnus entitlement state. Close-after-open is
  enabled for new preference stores by default. Sixty-five tests cover the
  updated status, account-switch, and preference behavior.
- Plugin version `0.10.2` fixes terminal Magnus folders that appeared empty.
  Live Magnus descriptors use the same `Uri` field for tree and file targets;
  the adapter now validates that URI as a tree path for folders and a content
  path for files. A privacy-bounded live check found files in a previously
  empty-looking leaf and completed a read-only preview without printing item
  names, paths, IDs, or content. Sixty-six tests pass, including a regression
  test shaped like the live descriptor.
- Plugin version `0.10.3` includes Settings in the keyboard Tab ring. Forward
  traversal is Search, a search/recent result when present, Personal Links,
  optional Magnus, Settings, then Search. Shift+Tab follows the exact reverse
  route. Entering Settings transfers focus to the shared key catcher so the
  next Tab or Shift+Tab remains deterministic. Sixty-seven tests pass,
  including a source-contract regression for both traversal directions.
- Plugin version `0.11.0` adds explicit Download, Copy, Copy hash, Refresh, and
  descriptor-provided Open in Rock actions for Magnus files. Binary and large
  files retain download/hash actions even when text preview is unavailable.
  Mobile app deployment is limited to same-origin numeric
  `/api/TriumphTech/Magnus/Build/mobileapps/{id}` descriptors and requires an
  inline confirmation plus `confirmed: true` at the broker boundary. Successful
  builds become profile-scoped Magnus Build Recent Links; re-triggering one
  requires confirmation again, and direct URL opening is rejected. All build
  execution tests used fakes; no live build was invoked.
  The installed v0.11.0 broker was then restarted in PROD and a privacy-bounded
  descriptor-only check found five mobile apps advertising the allowed build
  action. Sending one opaque ID without confirmation returned
  `build_confirmation_required`; no POST was sent. The replacement shell and
  broker responded normally, the runtime directory/socket remained
  `0700`/`0600`, plugin validation passed, and `hyprctl configerrors` was empty.
- Plugin version `0.12.0` makes mobile-app keyboard deployment explicit on each
  row (`B · Deploy`), repeats Enter/Esc instructions in the confirmation card,
  and shows the active profile's last Rock Lens deployment as a compact relative
  time or older local date/time. The live mobile-app descriptors were inspected
  read-only and contain no date or deployment field, so the UI does not claim to
  know about builds initiated elsewhere. A temporary panel-only visual check
  exercised `B` into the focused confirmation action and cancelled with `Esc`,
  which returned focus to the selected mobile app. No build POST was sent, and
  the captures were deleted.
- Scoped searches now use exact Rock `Id` or typed `Guid` OData filters for all
  six supported entities. An unscoped ID or GUID fans out only across enabled
  entity types; overlapping numeric IDs intentionally return every matching type.
  Privacy-bounded live no-match checks completed with zero unavailable
  categories. Seventy-nine tests, Ruff, ty, bytecode compilation, the installed
  socket checks, shell restart, `hyprctl reload`, and an empty
  `hyprctl configerrors` check pass.
- After the confirmation-focus fix, the user explicitly authorized one live
  deployment of the mobile app named `Test`. A fresh shell session navigated to
  that exact descriptor by keyboard, `B` opened the confirmation with **Deploy
  now** visibly focused, and `Enter` submitted it once. Magnus returned
  `Mobile application bundle deployed successfully.` The active profile's
  owner-only Recent Links then contained a new opaque `Deploy Test` entry with
  a current timestamp, and the app row rendered **Last deployed just now**.
  No other build descriptor was submitted. Temporary panel captures were
  deleted after inspection.
- The search field recognizes `p:`, `g:`, `w:`, `j:`, `pg:`/`page:`, and `c:`
  plus documented full aliases. It shows the active category as a removable
  badge; `Esc` clears that badge before closing, `Alt+0` clears it directly, and
  mnemonic Alt shortcuts apply each scope without conflicting with current
  Hyprland bindings.
- Opening Search selects the first Recent Link without taking typing focus from
  the search field. A completed search similarly selects its first result. Both
  selected rows use an accent tint, two-pixel accent outline, and solid accent
  marker, so selection remains visible while the search field keeps keyboard
  focus. The first row also paints this state directly from search-field focus,
  independent of asynchronous cursor updates.
  Unscoped search also ranks matching Personal Links by allowlisted title and
  section before entity results; explicit entity scopes exclude those links. An
  installed PROD socket check refreshed 15 links, searched one title, and
  returned that opaque link as the first result with no unavailable categories.
- Recent Links are globally ordered by their last-used timestamps, newest first,
  without grouping by entity type. Reopening an existing item refreshes its
  timestamp and returns it to the top while preserving deduplication and the
  20-item cap.
- Settings no longer repeats the active profile in a separate Connection
  section. The active Rock profile card now owns its login state, Magnus access
  indicator, and login/test/sign-out actions; add-profile and sign-in forms use
  distinct inset cards, while search preferences remain a separate section.
- Backspace on a highlighted search or link item is handled by the Rock
  Lens-local key catcher while the item owns focus. It returns focus to the
  search field, deletes the selection or character before the preserved cursor,
  and schedules the narrowed query without affecting native editing while the
  field itself has focus. An installed DEV interaction typed `ada`,
  moved Down to highlight the synthetic person, then Backspaced; the field
  regained focus as `ad` and the row highlight cleared. The temporary capture
  was restricted to synthetic panel content and deleted afterward.
- Person result context uses only age, connection/record status, and a bounded
  family-group projection for campus and Adult member names. Tests verify that
  a married record with exactly one other active Adult receives spouse context,
  that email fields in both Person and family responses never cross the public
  result contract, and that repeated searches reuse the in-memory family cache.
  A privacy-bounded installed PROD sample returned three People with connection
  status on all three, age on one, and family campus on two; no sampled row met
  the conservative spouse rule. Repeating it completed in 0.283 seconds. Only
  counts were printed, and no person values were retained.
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

No telemetry, feedback, production file write, job trigger, or publication was
performed during verification. The sole server-side mutation was the explicitly
authorized `Test` mobile-app deployment documented above.
