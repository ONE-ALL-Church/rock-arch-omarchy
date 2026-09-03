# Changelog

Rock Lens follows [Semantic Versioning](https://semver.org/). The GitHub
repository's default branch is the source used by Omarchy plugin updates.

## [0.14.0] - 2026-09-02

### Changed

- Replaced the README's early mock image with current, privacy-safe Search and
  Magnus keyboard-flow screenshots.
- Reorganized the user documentation around installation, first login, search,
  keyboard navigation, profiles, and optional Magnus capabilities.

### Removed

- Removed the dormant experimental OpenID Connect client, callback server,
  bearer-token storage, broker operations, CLI setup command, and tests. Rock
  Lens uses only the native Rock session shared by Search, links, and Magnus.
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

[0.14.0]: https://github.com/bscottdavis/rock-lens-omarchy/releases/tag/v0.14.0
[0.13.0]: https://github.com/bscottdavis/rock-lens-omarchy/releases/tag/v0.13.0
