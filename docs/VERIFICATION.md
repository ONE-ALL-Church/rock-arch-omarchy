# Verification record

This record describes the prepared `0.26.0` release boundary. Historical feature
changes belong in [CHANGELOG.md](../CHANGELOG.md), not in this acceptance record.

## Automated checks

Run from the repository root:

```bash
python3 -m unittest discover -s tests -v
scripts/check-qml
uvx --from ruff==0.16.5 ruff check rock_arch_broker tests
uvx --from ty==0.0.78 ty check rock_arch_broker
python3 -m compileall -q rock_arch_broker
omarchy plugin validate .
/usr/lib/qt6/bin/qmllint plugin/oneall.rock-arch/*.qml plugin/oneall.rock-arch/*.js
git diff --check
```

The suite contains 232 Python tests and 35 Qt behavioral tests. Release-contract
coverage keeps the manifest, package, network user-agent, and displayed version
synchronized;
verifies the composed QML entry point and focused panel files; and prevents the
obsolete OpenID implementation or nested plugin manifest from returning.
Public-KB coverage verifies explicit scope parsing, fixed-origin credentialless
requests, response limits, schema validation, opaque IDs, cache behavior,
public-source URL validation, and keyboard-complete detail navigation. Updater
coverage verifies remote revision detection, manifest identity and
version validation, local-change refusal, fixed worker launch arguments, private
state permissions, broker routing, and the opt-in automatic-update preference.
CLI coverage verifies private stdin queries, the versioned schema, redacted
diagnostics, target descriptions, side-effect-free dry runs, Omarchy UI
handoffs, command routing, masked interactive login, confirmation gates,
bounded JSON transport, socket ownership checks, default-on preference
enforcement, and safe launcher installation without replacing another command.

GitHub Actions is configured to run Python tests, Ruff, ty, bytecode compilation,
and Qt behavioral tests on every push to `main` and on pull requests. Qt Test
runs headlessly through `scripts/check-qml`; it is a development dependency,
not a plugin runtime requirement.

The Qt suite executes the production connection component and response modules
with synthetic sockets and display state. It covers coalesced reconnects, partial
disconnects, no replay of sent mutations, queued credential purging, capability
recovery, stale Search and Knowledge results, retained selection, profile and
permission transitions, focus callbacks, error recovery, and build-acceptance
feedback. Existing static QML checks remain for layout and wiring contracts.

Shortcut coverage checks opt-in add/change/remove, conflict detection including
physical workspace keys and multiple XKB layouts, manual binding recognition,
stale config refusal, backup permissions, exact preservation of personal bytes,
reload activation checks, rollback and concurrent-edit protection. Preview and
source checkouts cannot write shortcuts. Qt tests execute the production shortcut
model's conflict checks, stale drafts, removal confirmation, icon recovery,
disconnect behavior, configured feedback and form cleanup.
Fixtures simulate Hyprland reloads; they do not edit the active desktop config
or substitute for exercising the shortcut in an installed Omarchy panel.

The installed 0.26.0 candidate was also checked on Omarchy 4.0.2 on
2026-09-04 and 2026-09-05. The Settings panel recognized the existing manual
Super+R binding. The simplified interface has no shortcut-test controls or
timed reopen behavior, and its global keypress path was verified again.
Standard-keymap Wayland input reopened the actual panel through Hyprland,
including with the menu-bar icon hidden. The icon preference was restored
afterward, and the user's binding file was preserved.

On 2026-09-05, a fresh plugin clone of the audited candidate was installed through
`omarchy plugin add` on the running Omarchy 4.0.2 desktop, with existing plugin
data and installation set aside in a private backup. The real panel opened from
its bar icon, the shell summon command, and an installed Super+R binding; Escape
and the shell hide route closed it. The production CLI added Super+R, changed it
to Super+Shift+R, and removed it through actual Hyprland reloads. Each operation
reported the expected active binding and no configuration errors. Other binding
bytes were preserved. Disable/re-enable, shell restart, plugin removal, and
managed-launcher removal also passed. The original profiles, state, bindings,
launcher, and bar layout were restored afterward. This was a fresh plugin
installation on an existing desktop, not an OS reinstall. No login or production
build was performed by this acceptance check.

The isolated distribution test copies the runtime into a temporary installation,
creates its launcher, exchanges real Unix-socket status requests, restarts the
broker against its stale socket, and cleans up the fixture. Keyring and network
access are forbidden in that test. It does not operate the user's installed
plugin or assert that the interactive Omarchy shell lifecycle was tested.

## Authentication boundary

- Rock Arch has one authentication path: a redirect-free HTTPS
  `POST /api/Auth/Login` to the selected, validated Rock origin.
- Only a bounded `.ROCK` cookie is accepted from `Set-Cookie`. It remains in
  broker memory and expires after 15 idle minutes.
- Profile usernames and passwords are stored by Secret Service. A subprocess
  contract test verifies that secret values are supplied to `secret-tool` only
  on stdin, never in argv.
- The experimental OpenID client, loopback callback server, bearer-token store,
  OpenID CLI configuration path, and broker operations are absent from the release.
  Legacy `auth_status`, `auth_login`, and `auth_disconnect` requests return
  `unsupported_operation`.
- Old user-owned `oidc.json` and keyring records are ignored and are not silently
  deleted during upgrade.

## Terminal and agent boundary

- `rock-arch` is a JSON client of the existing broker; it has no independent
  Rock, Knowledge, Magnus, cookie, or credential implementation.
- The client validates the Unix socket and parent directory as current-user
  owned with no group/other access. Requests are capped at 16 KiB and responses
  at 5 MiB. A missing broker may be started through fixed module arguments;
  `--no-start` refuses that behavior.
- Terminal access defaults on, is configured in Settings rather than onboarding,
  and marked Rock CLI requests fail with `terminal_access_disabled` when it is
  off. Local settings and shortcut management stay available for recovery.
  The Unix account remains the OS trust boundary.
- The launcher is installed atomically in `~/.local/bin`, refuses unsafe shapes
  and unrelated existing commands, and contains no credentials or profile data.
- `rock-arch login` reads the password from a masked prompt or a bounded JSON
  object with `--stdin`. No password argument exists. JSON responses never
  contain submitted credentials.
- Private Search and Knowledge queries can be read from bounded stdin. Native
  UI handoff moves the query through a one-time, 30-second broker value rather
  than an Omarchy process argument.
- Every emitted object has protocol version 1. `doctor` contains no profile,
  origin, path, query, target URL, or credential, while `describe` and
  `--dry-run` do not execute the requested action.
- Search, Knowledge, links, profiles, Magnus, and updates reuse the broker's
  allowlists and process-local opaque IDs. Browser, clipboard, download,
  deletion, sign-out, removal, update, and build actions require `--confirm`.

## Data and navigation boundary

- The QML process receives no credentials, cookies, raw Rock IDs, raw server
  URLs, or exception text. Content is limited to a user-selected bounded Magnus
  text preview and a user-selected bounded public Knowledge result.
- Search uses eight fixed Rock REST v1 resources with fixed projections, bounded
  results, contains-style Workflow Type matching, fast prefix matching for the
  other entity categories, exact ID/GUID matching, and exact-origin navigation
  targets. It exposes no generic HTTP, REST v2, SQL, mutation, job-run, or Run
  Now transport.
- A bounded post-login probe checks those same eight endpoints with only
  `$select=Id&$top=1`. Denied or unsupported categories are hidden, and the
  broker independently excludes them from scoped and unscoped requests.
- Transient access-check failures disable entity search until retry instead of
  treating an unknown category as authorized. The cached result is cleared when
  the active profile, origin, credentials, or context changes.
- Personal Links are same-origin and represented outside the broker by opaque
  IDs. Recent Links are owner-only, profile-scoped, deduplicated, and capped at
  20 entries.
- Person context is limited to age, conservatively inferred spouse, family
  campus, and connection status. Contact details, addresses, and full birth
  dates are not fetched.

## Public Knowledge boundary

- Knowledge is a dedicated workspace entered from its tab or `Ctrl+3` (default order).
  `kb:` and `knowledge:` transfer a main-Search query into that workspace;
  unscoped and entity-prefixed searches remain local to the selected Rock
  instance.
- Requests use redirect-free GETs to the fixed public Rock Agent KB origin and
  include no Rock cookie, credentials, profile details, or instance origin.
- Searches return at most ten transformed rows and are capped at 512 KiB.
  Generic and community searches require three characters; locally filtered
  Model Map, Lava, and concept areas require two. Fixed collections are capped
  at 3 MiB and exact details at 2 MiB, with at most 20,000 characters of plain
  body text exposed to QML.
- Result IDs, structured related targets, and external source URLs remain
  broker-private. QML receives opaque IDs for results and related items;
  opening a source is a separate action guarded by strict public HTTPS URL
  validation.
- Search and detail caches are memory-only and expire after five minutes.
  Knowledge results are not added to Recent Links.

## Magnus boundary

- Magnus is optional and reuses the native Rock session. A missing plugin or
  403/404 authorization response does not disable Search or links.
- Tree, file, view, and mobile-app build paths are validated against fixed
  same-origin prefixes and represented in QML by process-local opaque IDs.
- Previews, downloads, and tree responses are size-bounded. Cross-origin URLs,
  redirects, traversal, query strings, fragments, and control characters are
  rejected.
- Only a descriptor-advertised numeric mobile-app build endpoint can mutate the
  server, and every first or repeated build requires an explicit confirmation.
  No build is triggered by the automated suite.
- Accepted build requests create a profile-scoped mode-`0600` receipt and a
  privacy-minimized desktop notification. Status remains `accepted` with local
  provenance and `completionVerifiable: false` because Magnus exposes no
  dependable completion endpoint.

## Update boundary

- Update checks run only for the exact Git-managed
  `oneall.rock-arch` installation, require the canonical ONE&ALL Church
  repository as `origin`, and fetch the public remote without prompting for
  credentials.
- Remote metadata must contain the same plugin ID and a bounded semantic
  version. A non-fast-forward history or local tracked changes disables the
  install action and leaves the checkout untouched.
- Automatic installation is a persisted boolean preference that defaults to
  off. Manual and automatic installs both invoke Omarchy's fixed plugin updater,
  which performs its own fast-forward merge, validation, rollback, and rescan.
- The detached worker accepts only the canonical installed plugin directory and
  writes only owner-readable status. It never includes profile credentials,
  cookies, tenant data, or command output in its state or notifications.

## UI evidence

The README uses current, panel-only captures from two explicit sources:

- [`search-demo-decker.png`](../outputs/screenshots/search-demo-decker.png) is a
  live search of the intentionally public Rock Solid Church Demo.
- [`knowledge-model-map.png`](../outputs/screenshots/knowledge-model-map.png) and
  [`knowledge-model-map-detail.png`](../outputs/screenshots/knowledge-model-map-detail.png)
  use the credentialless public Rock Agent Knowledge Base.
- [`personal-links-preview.png`](../outputs/screenshots/personal-links-preview.png),
  [`recent-links-preview.png`](../outputs/screenshots/recent-links-preview.png),
  [`magnus-preview-browser.png`](../outputs/screenshots/magnus-preview-browser.png),
  [`magnus-preview-mobile-apps.png`](../outputs/screenshots/magnus-preview-mobile-apps.png),
  [`magnus-preview-file.png`](../outputs/screenshots/magnus-preview-file.png), and
  [`magnus-build-confirmation.png`](../outputs/screenshots/magnus-build-confirmation.png)
  contain deterministic, side-effect-free preview content because the public
  demo account has neither private Personal Links nor Magnus.

Every image is cropped to the Rock Arch panel. No production tenant, private
record, credential, raw identifier, Personal Link target, or private Magnus
file appears. The preview captures show no DEV/PROD badge and do not execute
browser, clipboard, download, history-clear, source-open, or build actions. See
[KEYBOARD-AUDIT.md](KEYBOARD-AUDIT.md) for the represented interaction coverage.

## Local acceptance

- Target shell: Omarchy 4.0.2 or newer.
- The root repository passes Omarchy plugin validation and contains no Rock MCP,
  Magnus CLI, Node.js, npm, pip, or uv runtime dependency.
- Standalone `qmllint` may report expected unresolved Omarchy import warnings;
  it must report no QML syntax error.
- `hyprctl reload` must succeed and `hyprctl configerrors` must be empty after
  updating the installed plugin.
- Full OS logout/login and a live Magnus deployment are intentionally outside
  this release check.

Automated verification writes temporary test fixtures only; it performs no
telemetry, live search, user profile or credential change, or production build.
The documentation captures intentionally use only the public Demo Church, the public Knowledge
service, and deterministic preview fixtures.
