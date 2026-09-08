# Release security review — 0.27.0

Reviewed on 2026-09-08. This is a maintainer source review, static scan, and
synthetic regression exercise, not an independent certification or a penetration
test of a Rock server. The release tag identifies the exact reviewed source.

## Scope and result

Reviewed the changes from the marketplace-verified 0.26.1 snapshot through the
0.27.0 candidate: private bookmark/section writes and deletion, scheduled job
discovery and triggering, CLI mutation grants, Recent Link actions and reference
resolution, profile migrations, public Knowledge source/detail rendering, and
keyboard/broker lifecycle changes. Rechecked the existing exact-commit updater
and literal Magnus preview boundaries. No unresolved release-blocking security
finding was identified within this scope.

## Fixed finding

**Low: confirmation expiry during validation reads.** Bookmark/section save and
delete checked the draft deadline on entry, but validation could finish after
the deadline and still issue a write. A synthetic delayed-read test reproduced
this for bookmark creation, section creation, and deletion. They now recheck
expiry after validation and before writes. Bookmark creation also rechecks after
its duplicate lookup, including when a first section has already been created.
The regression proves that expiration during identity/ownership validation or
the duplicate lookup issues no subsequent write. Already-created sections are
not rolled back automatically. Job runs already rechecked expiry immediately
before their POST; their origin guard now raises a stable error explicitly
instead of relying on an assertion.

## Reviewed boundaries

- Private link and section writes derive the authenticated person/alias, enforce
  owner/private scope, validate same-origin HTTPS URLs, and reread saved records.
  Deletion checks the exact record and reviewed child-ID set; populated-section
  deletion requires explicit scope. Clients cannot choose raw owners or delete
  raw record IDs. Consumed drafts and uncertain writes are never replayed.
- Job Run requires a current search reference or a persisted Scheduled Job
  reference matching the exact active-origin entity route. Fresh discovery
  verifies page/block identity and Edit permission. The single-use draft binds
  job GUID, title, placement, and expiry, and all are rechecked before RunNow.
  Opening a recent job never triggers it. Accepted requests do not claim completion.
- CLI read access and mutation access are separate. Mutations and all six grants
  default off, including upgrades. Execution checks the current action grant;
  combined section/link actions require both grants. Recent job and build actions
  use the same gates. These are supported-client controls, not isolation from
  arbitrary code already running as the same desktop Unix user.
- Profile/context changes clear pending drafts and scoped references. Profile
  schema migration preserves existing profiles and preferences. History stays
  profile-scoped and owner-only; history-save failure cannot turn an accepted
  job request into a retryable failure.
- Knowledge requests remain credentialless and fixed-origin. Source navigation
  validates HTTPS public URLs. Model sections are bounded and rendered as plain
  text. All plugin Text elements and the installed Omarchy label controls use
  PlainText; Magnus retains its explicit PlainText boundary.
- The updater still passes the full checked SHA unchanged, validates an isolated
  worktree, performs an exact-ID fast-forward with hooks disabled, and verifies
  installed identity before restart. The 0.26.1 race and resource-loading tests
  remain in the passing suite.

## Scans and checks

- **Gitleaks:** no leaks in the working tree or commits since v0.26.1; reports
  are redacted and retained outside the repository.
- **Bandit 1.9.4:** no high findings; 26 low subprocess import/call heuristics
  and one medium file-mode heuristic. Each call site was reviewed: fixed
  executable/argument arrays, no shell interpolation, validated targets, and
  credentials supplied on stdin. The medium result is the existing CLI launcher's
  intentional 0755 mode; it contains only launcher code/path information, no
  secrets, and is not writable by other users. Private state and socket modes
  remain 0700/0600. These heuristics were triaged, not suppressed or described
  as a zero-warning scan.
- **364 Python tests, 99 Qt cases**, Ruff 0.16.5, ty 0.0.78, bytecode compilation,
  Omarchy manifest validation, and whitespace checks pass. Qt totals include
  fixture setup/cleanup. Keyboard integration runs actual Qt input events against
  the plugin and installed Omarchy controls in an offscreen window with an inert
  broker. Real Quickshell socket recovery is tested against a delayed local server.
- GitHub CI additionally exercises Qt 6.4.2. Its focus-collection regression
  caught unsupported for-of iteration over QML child lists; indexed traversal
  now preserves the same focus order on older Qt. This was a compatibility
  failure, not an authorization change.
- Fresh distribution tests create an isolated installation and launcher, start
  and restart the real broker, check permissions and version, and clean it up;
  network and keyring access are blocked in that fixture. Earlier native
  installation/shortcut/disable/removal acceptance remains documented in
  [VERIFICATION.md](VERIFICATION.md); those unchanged installation paths were
  not all repeated interactively during this review.
- The owner reports successful live testing of job run and bookmark save/delete
  before this release review. This is user-reported acceptance; the security
  tests themselves trigger no real jobs, builds, or tenant writes.
- The root preview was refreshed from the current interface using synthetic
  jobs/account details and an inert broker. No private screenshot is published.

## Remaining limits

Rock's authorization is final. Permission checks and writes are separate server
requests. Section deletion cannot atomically prevent another client from adding
children between the last check and DELETE; the UI and --with-links flow explain
and authorize deletion of all contents. Job/build acceptance is not completion
verification. Omarchy plugins remain unsandboxed owner-local software. Marketplace
verification applies only to its approved snapshot; this update requires its own
review and does not inherit 0.26.1 verification.
