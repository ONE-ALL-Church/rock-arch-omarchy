# Verification record

This record describes the current `0.25.3` release boundary. Historical feature
changes belong in [CHANGELOG.md](../CHANGELOG.md), not in this acceptance record.

## Automated checks

Run from the repository root:

```bash
python3 -m unittest discover -s tests -v
uvx --from ruff==0.16.5 ruff check rock_lens_broker tests
uvx --from ty==0.0.78 ty check rock_lens_broker
python3 -m compileall -q rock_lens_broker
omarchy plugin validate .
/usr/lib/qt6/bin/qmllint plugin/oneall.rock-arch/*.qml plugin/oneall.rock-arch/*.js
git diff --check
```

The suite contains 190 passing tests. Release-contract coverage keeps
the manifest, package, network user-agent, and displayed version synchronized;
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

GitHub Actions runs the unit tests, Ruff, ty, and bytecode compilation on every
push to `main` and on pull requests.

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
  and marked CLI requests fail with `terminal_access_disabled` when it is off.
  The Unix account remains the OS trust boundary.
- The launcher is installed atomically in `~/.local/bin`, refuses unsafe shapes
  and unrelated existing commands, and contains no credentials or profile data.
- `rock-arch login` always reads the password from a masked prompt. No password
  argument exists. JSON responses never contain submitted credentials.
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

- Knowledge is a dedicated workspace entered from its tab or `Alt+K`.
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

Automated verification performs no telemetry, live search, profile change,
credential change, file mutation, or production build. The documentation
captures intentionally use only the public Demo Church, the public Knowledge
service, and deterministic preview fixtures.
