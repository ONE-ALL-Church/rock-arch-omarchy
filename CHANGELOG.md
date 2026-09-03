# Changelog

Rock Arch follows [Semantic Versioning](https://semver.org/). The GitHub
repository's default branch is the source used by Omarchy plugin updates.

## [Unreleased]

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

[0.18.0]: https://github.com/bscottdavis/rock-arch-omarchy/releases/tag/v0.18.0
[0.17.0]: https://github.com/bscottdavis/rock-arch-omarchy/releases/tag/v0.17.0
[0.16.2]: https://github.com/bscottdavis/rock-arch-omarchy/releases/tag/v0.16.2
[0.16.1]: https://github.com/bscottdavis/rock-arch-omarchy/releases/tag/v0.16.1
[0.16.0]: https://github.com/bscottdavis/rock-arch-omarchy/releases/tag/v0.16.0
[0.15.1]: https://github.com/bscottdavis/rock-arch-omarchy/releases/tag/v0.15.1
[0.15.0]: https://github.com/bscottdavis/rock-arch-omarchy/releases/tag/v0.15.0
[0.14.0]: https://github.com/bscottdavis/rock-arch-omarchy/releases/tag/v0.14.0
[0.13.0]: https://github.com/bscottdavis/rock-arch-omarchy/releases/tag/v0.13.0
