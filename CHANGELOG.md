# Changelog

Rock Arch follows [Semantic Versioning](https://semver.org/). The GitHub
repository's default branch is the source used by Omarchy plugin updates.

## [Unreleased]

### Changed

- Move the canonical repository and install links to the ONE&ALL Church
  GitHub organization.

## [0.24.4] - 2026-09-03

### Fixed

- Keep contains-style matching for Workflow Types while restoring fast prefix
  queries for the other seven entity categories, avoiding a multi-second
  general-search regression on larger Rock instances.

## [0.24.3] - 2026-09-03

### Fixed

- Match search terms anywhere in Rock entity names so general search finds
  Workflow Types and other entities when the query is not the first word.
- Keep existing results in place while a replacement search is running, block
  stale-result activation, and reserve the transient status row so the panel's
  bottom edge no longer jumps during search.

## [0.24.2] - 2026-09-03

### Fixed

- Keep keyboard selection stable when a live search refresh completes, avoid
  duplicate same-query refreshes, and shorten the search input delay.
- Defer optional Magnus detection until typing and searches are idle so it
  cannot delay the primary search workflow.
- Clip panel content and normalize its closed state to prevent stale views or
  underlying window text from flashing at the panel edge.

## [0.24.1] - 2026-09-03

### Fixed

- Restart the Omarchy shell after an in-plugin update so newly added IPC
  methods are registered immediately instead of requiring a manual restart.

## [0.24.0] - 2026-09-03

### Added

- Add private query input for Rock and Knowledge search through `--stdin`, `-`,
  or an interactive prompt when the positional query is omitted.
- Add redacted `doctor` diagnostics and a versioned `schema` command. Every CLI
  JSON result now carries `protocolVersion`.
- Add side-effect-free opaque-ID descriptions and `--dry-run` previews for
  every confirmed browser, clipboard, download, deletion, sign-out, profile
  removal, update, and Magnus build action.
- Add `ui open` and `ui close` handoff commands through Omarchy IPC. Search
  terms move through a one-time owner-only broker handoff instead of an IPC
  process argument.
- Add owner-only Magnus build receipts, opaque build IDs, build list/status
  commands, and a local notification when Magnus accepts a deployment request.

### Changed

- Describe Magnus build history as “started” or “accepted,” not “deployed.” The
  currently available Magnus action endpoint acknowledges a request but does
  not expose a dependable completion-status endpoint.

### Security

- Cap private stdin input at 8 KiB, expire unclaimed UI handoffs after 30
  seconds, keep build records profile-scoped and mode `0600`, and exclude Rock
  origins, profile identities, target URLs, queries, and credentials from
  diagnostics and build receipts.

## [0.23.0] - 2026-09-03

### Added

- Add the owner-local `rock-arch` JSON CLI for Rock status and login, detected
  search capabilities, entity search and person context, public Knowledge and
  related-item traversal, Personal and Recent Links, profiles, controlled
  Magnus operations, and plugin updates.
- Install a small managed launcher into `~/.local/bin` when the broker starts,
  without replacing an unrelated existing command.
- Add a default-on **Allow terminal and agent access** preference in Settings.
  Keep it out of onboarding so the initial Rock connection flow stays focused.
- Add a registered-file Magnus hash command that returns only title, size, and
  SHA-256 without returning file contents.

### Security

- Reuse the existing owner-only broker, Secret Service login, memory-only
  cookie, fixed endpoints, permission detection, and process-local opaque IDs;
  the CLI has no parallel HTTP or authentication implementation.
- Validate socket ownership and permissions, cap CLI requests and responses,
  never accept a password argument, and require `--confirm` for browser,
  clipboard, download, history deletion, sign-out, removal, update, and build
  actions.
- Refuse unsafe launcher directories, symlinks, non-files, foreign files,
  unrelated existing `rock-arch` commands, and source-checkout attempts to
  repoint the managed launcher.

## [0.22.0] - 2026-09-03

### Added

- Add a dedicated **Knowledge** workspace with its own public-search field,
  privacy boundary, keyboard navigation, and search-area hints for Model Map,
  issues, ideas, Lava contexts, recipes, and concept guides.
- Add local `mm:`, `is:`, `issue:`, `idea:`, `lava:`, `recipe:`, and `guide:`
  routing over the Knowledge service's fixed read-only endpoints.
- Turn typed relationships in knowledge results into safe in-panel links.
  Articles and community reports can open referenced Model Map records, Lava
  roots can open their models, and models can traverse to related models with
  a nested Back history.

### Changed

- Remove Knowledge controls and explanatory copy from the main Rock Search
  interface. The existing `kb:` and `knowledge:` prefixes remain as quiet
  shortcuts that transfer the query into the Knowledge workspace.
- Route generic Model Map search hits into the richer typed model detail view.

### Security

- Keep every new Knowledge area credentialless, fixed-origin, redirect-free,
  GET-only, response-bounded, and represented in QML by process-local opaque
  identifiers. Community issues and ideas retain their unreviewed labels.

## [0.21.0] - 2026-09-03

### Added

- Add an explicit public Rock Knowledge search scope through `kb:`,
  `knowledge:`, `Alt+K`, or the visible Knowledge selector beside Search.
- Open selected knowledge results inside Rock Arch with source authority,
  claim tier, version scope, attribution, and a keyboard-accessible public
  source action.

### Security

- Keep public KB requests completely separate from the authenticated Rock
  client. Rock cookies, credentials, profile metadata, and instance domains are
  never attached to KB requests.
- Send queries to the fixed, redirect-free Rock Agent KB origin only after the
  user explicitly enters Knowledge scope. Bound and validate every response,
  expose opaque result IDs, and validate external HTTPS sources before opening.
- Label the public-search boundary in the UI so users know not to enter person
  names or private church data.

## [0.20.0] - 2026-09-03

### Added

- Detect which of Rock Arch's eight fixed entity endpoints the signed-in Rock
  account can read after login and cache that bounded capability result per
  active profile.
- Show only accessible entity categories during Finish setup and in Settings,
  with a retry path when the access check cannot complete.

### Security

- Intersect saved search preferences with the account's detected Rock access
  in the broker. Scoped prefixes and unscoped searches cannot request an
  unavailable entity endpoint, even if a client bypasses the QML controls.
- Fail closed on transient capability-check errors while preserving Personal
  Links, Recent Links, and independently authorized Magnus features.

## [0.19.0] - 2026-09-03

### Added

- Added Group Types and Content Channel Types to the bounded Rock REST v1
  search, including exact ID/GUID lookup, same-origin admin navigation,
  Settings controls, `gt:`/`ct:` prefixes, and keyboard shortcuts.
- Replaced the separate update question with one post-login **Finish setup**
  screen for choosing search categories and optional automatic updates. All
  eight categories default on, automatic updates default off, and one Enter
  accepts the defaults.

### Changed

- Migrate existing profile stores once so both new categories are enabled by
  default while preserving later user choices.

## [0.18.0] - 2026-09-03

### Added

- Added a one-time post-login choice to enable automatic Rock Arch updates on
  Git-managed Omarchy installations. The prompt is keyboard-complete, Escape
  selects `Not now`, and either choice continues directly to Search.
- Persist the completed choice so it is not shown repeatedly. Existing users
  who already enabled automatic updates are treated as having completed it.

## [0.17.0] - 2026-09-03

### Changed

- Rebuilt every Rock Arch surface around the current Omarchy shell design
  system: first-party panel geometry, hero anatomy, theme typography, semantic
  spacing, native controls, separators, and cursor/focus states.
- Reduced the panel to the same compact width and height used by the official
  Basecamp and HEY Omarchy plugins, with profile identity moved into the hero
  and persistent tutorial copy removed from the footer.
- Simplified Search, Recent Links, Personal Links, and Magnus into consistent
  title-and-metadata rows with restrained selection chrome and clearer empty,
  loading, preview, and production-build states.
- Reorganized Settings into four clear groups: profiles, preferences, search
  categories, and updates. Replaced platform-default checkboxes with Omarchy
  toggle rows and selected category buttons.
- Added a documented Rock Arch design system grounded in the official Omarchy
  shell, Basecamp-owned plugins, desktop HIG guidance, and visible-focus
  requirements.
- Replaced the public screenshots with privacy-safe captures of the redesigned
  Search result and Updates surfaces.

## [0.16.2] - 2026-09-03

### Fixed

- Keep the custom icon button opaque when its text label is intentionally
  hidden, allowing the rock-arch mark to render in the Omarchy bar.

## [0.16.1] - 2026-09-03

### Fixed

- Render the rock-arch mark as a native theme-colored QML shape so it remains
  visible in the compact Omarchy bar slot.

## [0.16.0] - 2026-09-03

### Added

- Added a required Profile Name to first-run onboarding and a keyboard-complete
  inline rename action for every existing Rock profile.
- Added a theme-colored rock-arch menu-bar logo and a Settings option to hide
  the bar item while keeping `Super+R` access available.

## [0.15.1] - 2026-09-03

### Fixed

- Allow a first login to complete when legacy credentials are already absent
  from Secret Service. Rock Arch now confirms the item is missing before
  treating the cleanup as successful, while genuine keyring errors still fail
  closed.

## [0.15.0] - 2026-09-02

### Added

- Added daily update checks, a Settings availability indicator, a manual
  **Update now** action, and optional automatic installation that is disabled
  by default.
- Added owner-only updater state and a detached update worker so Omarchy can
  validate, roll back, and reload the plugin without being interrupted by QML
  hot reloads.

### Changed

- Renamed the project to **Rock Arch — Bridging Rock RMS and Omarchy**, including
  its GitHub repository, Omarchy plugin ID, UI, install commands, and public
  documentation.
- Split the Quickshell UI into focused Login, Search, Personal Links, Magnus,
  Settings, and navigation components without changing keyboard behavior.
- Moved broker request routing into operation-specific handlers and centralized
  redirect, cookie-header, and bounded JSON validation shared by every Rock
  HTTP client.
- Delegated every update installation to Omarchy's fast-forward-only updater,
  validation, rollback, and plugin rescan flow.

### Security

- Fail closed when Secret Service cannot delete profile credentials or legacy
  records during migration.
- Reject raw, percent-encoded, and multiply encoded Magnus traversal plus every
  HTTP route outside the explicit read/build allowlist.
- Refuse unsafe runtime socket objects and revalidate stale sockets before
  unlinking them.
- Purge unsent QML credential requests on connection timeout or panel close.
- Report local Recent Links deletion failures instead of presenting stale
  history as cleared.
- Treat excessively nested local or remote JSON as a stable fail-closed error.
- Return a bounded public error when a socket request exceeds the stream limit.
- Pin CI actions and lint/type-check tool versions to immutable revisions.
- Launch the broker with the absolute system Python path.

### Fixed

- Use native Qt tab-focus properties in every split panel and retry the initial
  status request until the local broker is ready, preventing an empty or frozen
  startup after an Omarchy shell reload.
- Use a valid Qt item for the Recent Links clear-button background.

## [0.14.0] - 2026-09-02

### Changed

- Replaced the README's early mock image with current, privacy-safe Search and
  Magnus keyboard-flow screenshots.
- Reorganized the user documentation around installation, first login, search,
  keyboard navigation, profiles, and optional Magnus capabilities.

### Removed

- Removed the dormant experimental OpenID Connect client, callback server,
  bearer-token storage, broker operations, CLI setup command, and tests. Rock
  Arch uses only the native Rock session shared by Search, links, and Magnus.
- Kept desktop Secret Service support as a small independent adapter for
  per-profile Rock usernames and passwords.

## [0.13.0] - 2026-09-02

### Added

- First-run Rock profile onboarding with desktop password-manager storage.
- Multi-profile settings, per-profile login state, sign out, and removal.
- Optional Magnus browsing, downloads, hashing, previews, and confirmed mobile
  app builds for accounts that have Magnus access.
- Workflow Type search, entity prefixes, all-entity ID/GUID search, Personal
  Links search, and last-used Recent Links.
- Full keyboard navigation across search, Personal Links, Magnus, deployment
  confirmations, onboarding, and settings.
- Continuous integration and release-contract checks for distributable builds.

### Changed

- Unified selection styling and tightened copy, spacing, and overflow behavior.
- Enabled close-after-open by default.
- Replaced the development tenant fallback with a reserved example origin; each
  real connection always uses the selected user's Rock profile domain.

[0.20.0]: https://github.com/ONE-ALL-Church/rock-arch-omarchy/releases/tag/v0.20.0
[0.19.0]: https://github.com/ONE-ALL-Church/rock-arch-omarchy/releases/tag/v0.19.0
[0.18.0]: https://github.com/ONE-ALL-Church/rock-arch-omarchy/releases/tag/v0.18.0
[0.17.0]: https://github.com/ONE-ALL-Church/rock-arch-omarchy/releases/tag/v0.17.0
[0.16.2]: https://github.com/ONE-ALL-Church/rock-arch-omarchy/releases/tag/v0.16.2
[0.16.1]: https://github.com/ONE-ALL-Church/rock-arch-omarchy/releases/tag/v0.16.1
[0.16.0]: https://github.com/ONE-ALL-Church/rock-arch-omarchy/releases/tag/v0.16.0
[0.15.1]: https://github.com/ONE-ALL-Church/rock-arch-omarchy/releases/tag/v0.15.1
[0.15.0]: https://github.com/ONE-ALL-Church/rock-arch-omarchy/releases/tag/v0.15.0
[0.14.0]: https://github.com/ONE-ALL-Church/rock-arch-omarchy/releases/tag/v0.14.0
[0.13.0]: https://github.com/ONE-ALL-Church/rock-arch-omarchy/releases/tag/v0.13.0
