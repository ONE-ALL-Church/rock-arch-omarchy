# Verification record

This record describes the prepared `0.26.1` release boundary and the unreleased
feature acceptance below. Historical feature changes belong in
[CHANGELOG.md](../CHANGELOG.md).

## Unreleased Recent Link actions

On 2026-09-08, selected Recent Links gained Open and Bookmark actions, with
Run for accessible jobs and Deploy for build entries. 363 Python tests and
99 Qt cases pass. The offscreen keyboard integration exercises list selection,
Tab through Run/Bookmark/Open, Enter opening without a trigger, R preparing a
confirmed run, Ctrl+B preparing a bookmark, and hidden Run without access.
Broker tests cover persisted recent jobs without a search registry, fresh access
denial, expired references, exact route/kind validation, foreign-origin rejection,
and CLI bookmark previews without writes. All job and bookmark tests use isolated
fixtures. No production mutation is performed by these checks.

## Unreleased job Recent Links

On 2026-09-08, accepted Run Job requests began recording the verified job entity
in the active profile's Recent Links. 360 Python tests and 99 Qt cases pass,
alongside Ruff, ty, Omarchy validation, and keyboard/socket integration checks.
New isolated broker tests exercise real history persistence, deduplication with
opened jobs, disabled history, unconfirmed/rejected/uncertain requests, and a
history-write failure after acceptance. Activating the saved entry opens its job
page and issues no additional RunNow request. QML tests cover immediate Recent
Links updates without changing search focus and rejection of stale job responses.
All job requests in these tests use synthetic transport; no real job was run.

## Unreleased Defined Types search

On 2026-09-08, Defined Types became the ninth development search category.
356 Python tests and 90 Qt cases pass, alongside Ruff, ty, bytecode compilation,
Omarchy manifest validation, and whitespace checks. Tests cover name matching,
ID/GUID filters, exact definition routes, restricted reads, disabled and denied
categories, aliases, CLI routing, QML hints and shortcut wiring, and the profile
version 1/2 upgrade to version 3. Disabling the new category remains saved after
reopening the profile store. These tests do not simulate a physical Alt+D keypress.
The published 0.26.1 release still has eight entity categories.

## Development integration of the 0.26.1 security patch

On 2026-09-06, the 0.26.1 marketplace fixes were merged into the development
branch while preserving its unreleased features. The combined tree passed
352 Python tests and 90 Qt cases, Ruff, ty, bytecode compilation, Omarchy plugin
validation, and whitespace checks. The public 0.26.1 patch remains scoped to
242 Python tests and 43 Qt cases; its full remediation evidence is in
[SECURITY-REVIEW-0.26.1.md](SECURITY-REVIEW-0.26.1.md).

## Unreleased CLI permissions and bookmarks

On 2026-09-05, development commit `47ab992` passed 342 Python tests, 90 Qt checks,
Ruff, ty, bytecode compilation, Omarchy plugin validation, and `git diff --check`.
The installed development checkout reported read access on, mutations off, and
an empty action-grant list. Invalid verification targets at every direct write
entry point were refused by the mutation gate before execution. The native
Search panel rendered the outline bookmark beside Run and Open. No production
writes were made in these permission checks. The new Ctrl+B physical key path
was not exercised by this automated review; Ctrl+S remains the form-save shortcut.

## Unreleased Personal Link management

On 2026-09-05, the feature branch passed 289 Python tests and 62 Qt behavioral
tests (74 Qt results including fixture setup and cleanup), Ruff, ty, bytecode
compilation, Omarchy manifest validation, and `git diff --check`. Standalone
`qmllint` exited successfully with expected warnings for shell-provided imports.

The new coverage checks account and section ownership, same-origin URLs, explicit
confirmation, single-use drafts, expiration and profile changes, duplicate saves,
uncertain POST outcomes, verified readback, bounded responses, and authorization
denial without replay. Qt tests exercise stale replies, cancellation, interruption,
field retention, queued-request removal, local form errors, and saved-row selection.

With the account owner's permission, an isolated review plugin on the real Omarchy
desktop created three temporary Personal Links in the active Rock account:
one through Links, one prefilled from Search, and one through the JSON CLI.
Readback verified each record's name, URL, owner, and section. Native keyboard
checks covered Ctrl+N, Ctrl+S, section selection, and Escape. Saving an existing
link selected and scrolled to its row, and success feedback cleared automatically.
The CLI dry run made no write, and a repeated confirmed save returned the existing
link without creating a duplicate.

All three temporary records were then removed, verified absent by their exact
IDs, and confirmed absent from the plugin's refreshed Personal Links. The review
plugin was removed, the shell restarted, and the original bar layout and profile
metadata preserved. Private account data and screenshots are not included here.
The submitted `main` branch and installed release were not changed.

The grouped Links follow-up was checked in a temporary native review plugin
using the account's real bookmark list and a private preference copy. Enter
toggled sections; multiple sections stayed open; recessed children retained
Rock's ordering. V opened the native view menu, and keyboard selection switched
to the flat Alphabetical list without discarding expansion. A full shell and
broker restart restored the view and expanded section. Existing group IDs stayed
stable while a newly encountered group started collapsed. Actual CLI commands
changed the view and reset expansion; the panel reflected the changes. The review
installation was then removed and the original desktop layout preserved.
No bookmarks were created, edited, or deleted during the view checks.

Standalone section creation was then checked with two temporary private sections
and one bookmark, each recorded by exact ID in a private review harness. The
native Add menu offered Link and Section, kept its Add label after selection,
and opened a name-only section form. Saving revealed the empty section with
Add a link; activating that row preselected the section in the bookmark form.
Saving from Alphabetical switched to Groups and revealed the section. A shell
and broker restart preserved both empty-section visibility and expansion.
The actual CLI created the second section, while a dry run and a repeated save
made no writes. Qt and Python tests additionally cover typed draft misuse,
case-insensitive section duplicates, uncertain saves, account changes, limits,
optional catalog authorization, and section metadata without raw owner IDs.

Cleanup verified the exact recorded fields before deleting the test bookmark,
then checked that both test sections were empty before deleting them. Readback
confirmed all three records absent and the original 16 bookmarks and two
sections restored. The temporary plugin was removed and the shell restarted;
the original bar layout and canonical profile file were preserved byte for byte.
The submitted main branch and installed public release remain unchanged.

The deletion follow-up used four newly created, tracked records: a private
section and bookmark for each of the UI and CLI paths. Enter on the UI's initially
focused Cancel left the record intact and preserved selection. Delete then opened
an exact-name, section, and URL confirmation; explicit button activation removed
only the selected bookmark. Its empty section remained available and was deleted
through its own confirmation. Both CLI dry runs made no writes; confirmed CLI
commands deleted the other bookmark and its empty section. Attempting to delete
a populated section was refused before any DELETE was issued.

Each successful deletion checked exact-ID absence. The refreshed list matched
the original bookmarks and sections, all four tracked records were gone, and the
review plugin was removed. Original profile metadata and bar layout were preserved;
the shell was restarted and no review-plugin runtime errors were recorded.
Additional tests cover duplicate-URL record identity and selection, scoped delete
references, raw-ID and shared/foreign-owner rejection, expiry and draft misuse,
account and record changes, links added after preparation, missing records,
failed readback, and interrupted deletions without replay. Tests do not establish
atomic empty-only deletion; that Rock API limitation is described in architecture.

Section-and-contents deletion was then checked with two tracked private sections
and five temporary bookmarks. The native confirmation displayed the section name,
Rock's verified count, and a permanent-deletion warning, with Cancel initially
focused. Enter on Cancel left all records intact. Adding a third link while the
two-link confirmation was open caused the explicit deletion attempt to stop
without issuing DELETE. Reload showed the new count of three and focused Cancel
again. A fresh explicit confirmation deleted that section and its three links.

The actual CLI refused the other populated section without `--with-links`, refused
an unconfirmed flagged command, and reported two links in a dry run without a
write. `--with-links --confirm` deleted its section and children. Exactly two
parent section DELETEs were issued, with no loop of child DELETEs. Exact-ID
readback verified all seven tracked records absent; the original 16 bookmarks
and two sections matched their initial names, grouping, and privacy. The temporary
review plugin was removed and original bar configuration and canonical profile
metadata were preserved byte for byte. The submitted main branch and installed
release were not changed.

Additional regression coverage checks immutable deletion scope, same-count child
replacement, additions and removals before confirmation, invalid or oversized
counts, children hidden by panel filtering, failed cascade readback, and refusal
to replay consumed drafts. QML checks require a verified count before enabling
section deletion and pass the reviewed scope through both requests.

The compact × row action was rendered in an isolated native review panel with
synthetic data and no broker connection. Group and bookmark rows retained their
alignment, keyboard focus visibly highlighted the square button, and activation
opened the real confirmation component with Cancel focused. The confirmation
footer placed Cancel immediately left of Delete. Native Left/Right navigation
moved between them; Enter on Cancel made no request, while Right then Enter and
Tab then Enter each made one synthetic confirmation request. When a draft needed
Reload, Right reached Reload and reloading returned focus to Cancel. The existing
74 Qt checks and standalone QML lint passed. No account records were used for
this visual change.

Regression tests cover distinct same-named sections, case-insensitive sorting,
multiple open groups, Left/Right navigation, selection during refresh and removal,
save-and-reveal behavior, per-account state, stable non-action group references,
legacy preference defaults, profile removal, and atomic rejection of invalid
preferences. Groups and Alphabetical use the existing bookmark read only; there
is no newest-first mode or creation-date request.

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

At the `0.26.1` release boundary, the suite contains 242 Python tests and 35 Qt
behavioral tests (43 Qt cases including setup and cleanup). One Python test
additionally runs the production Magnus preview in Qt and verifies its network
and local-file resource boundary. Release-contract
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
Real Git fixtures advance remote HEAD and FETCH_HEAD between check and install;
manual and automatic updates still install and activate only the checked commit.
Additional cases cover invalid targets, concurrent workers, validation failures,
tracked/untracked edits, ignored-file collisions, diverged history, revision
mismatch, and restart failure. No real shell restart occurs in these fixtures.
Magnus resource tests display literal HTML through the production plain-text
control, observe no HTTP requests or local fixture opens, and use rich-text
positive controls to prove both observers work. See
[the marketplace follow-up](SECURITY-REVIEW-0.26.1.md) for scope and limitations.
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
- CLI read access defaults on, is configured in Settings rather than onboarding,
  and marked Rock CLI requests fail with `terminal_access_disabled` when it is
  off. Local settings and shortcut management stay available for recovery.
  The Unix account remains the OS trust boundary.
- Mutations and individual grants default off for new and existing stores.
  Synthetic tests cover every write entry point, draft-based deletion scope,
  combined section/link grants, implicit first-section creation, permission
  changes after preview, Recent Links builds, and independent interactive actions.
  Settings changes remain available while Rock CLI access is disabled.
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
  URLs, or exception text, apart from the validated same-origin URL in the
  explicit Personal Link editor. Content is limited to a user-selected bounded Magnus
  text preview and a user-selected bounded public Knowledge result.
- Search uses nine fixed Rock REST v1 resources with fixed projections, bounded
  results, contains-style Workflow Type matching, fast prefix matching for the
  other entity categories, exact ID/GUID matching, and exact-origin navigation
  targets. The search client exposes no writes, SQL, or generic HTTP transport.
  Separate Personal Link and job clients provide the narrowly scoped, confirmed
  writes described in [SECURITY.md](../SECURITY.md).
- A bounded post-login probe checks those same nine endpoints with only
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
- Within Magnus, only a descriptor-advertised numeric mobile-app build endpoint
  can mutate the server, and every first or repeated build requires an explicit confirmation.
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
  off. Manual and automatic installs pass the full checked commit unchanged to
  the worker. It privately validates that exact commit with Omarchy, refuses
  local changes, fast-forwards only to that ID, and verifies installed identity
  and clean state before requesting a shell restart. It never refetches a
  mutable target. Candidate validation failure leaves the live checkout intact.
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
