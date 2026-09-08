# Security policy

## Reporting a vulnerability

Please report suspected vulnerabilities through the repository's
[private vulnerability reporting form](https://github.com/ONE-ALL-Church/rock-arch-omarchy/security/advisories/new).
Do not include Rock credentials,
cookies, tenant records, or other production data in a report. A minimal local
reproduction using synthetic data is preferred.

## Supported boundary

Rock Arch is an owner-local Omarchy plugin. Its Unix socket and state files are
designed to protect against other local users, malformed server responses, and
untrusted paths or URLs returned by Rock or Magnus. The broker exposes fixed,
bounded operations and stable public errors; it does not provide a generic HTTP
or command-execution surface.

The plugin and broker run with the desktop user's authority. They do not claim
to isolate against arbitrary code already executing as that same user, a
compromised Quickshell process, a compromised Python runtime, or a malicious
Rock server that returns semantically deceptive but structurally valid display
text. Rock permissions remain the authorization boundary for tenant data,
Personal Link creation and deletion, scheduled jobs, and the mobile-app build action. Rock Arch probes only
its nine fixed entity read endpoints after login, hides denied categories, and independently enforces the
detected allowlist in the broker before search requests are issued.

Update checks are limited to the canonical Git-managed Rock Arch installation.
They first require `origin` to be the canonical ONE&ALL Church repository, fetch
its public `HEAD`, refuse local tracked changes or diverged history, validate
the remote plugin ID and version, and expose only bounded status codes to QML.
Installation pins the full checked commit ID unchanged through the worker. It
validates that commit in a private temporary worktree with Omarchy's static
validator, then performs an exact-ID fast-forward with Git hooks disabled. It
verifies the installed ID and clean state before requesting an Omarchy shell
restart; the worker never fetches or follows a mutable ref. Concurrent updates,
local edits, diverged history, and ignored-file collisions are refused. Failed
candidate validation leaves the installed checkout intact. Later concurrent
changes cause an error without forcing a rollback over the user's edits.
Automatic installation is disabled by default.

Magnus file previews explicitly use `TextEdit.PlainText`. Remote content is
selectable literal text and cannot request rich-text image resources. The
[0.26.1 follow-up](docs/SECURITY-REVIEW-0.26.1.md) records both marketplace fixes
and their regression evidence.

The supported CLI uses the same owner-only broker and emits a versioned,
bounded JSON contract. Private search input can be read from stdin so person
names do not need to appear in process arguments. Confirmed actions have a
side-effect-free dry-run path, and diagnostics omit tenant identity, local
paths, queries, and secrets. Native UI handoffs store query text only in broker
memory, consume it once, and erase an unclaimed handoff after 30 seconds.

CLI read access defaults on; mutations and all per-action grants default off,
including upgrades. The broker enforces the mutation gate and an explicit
allowlist for link/section creation and deletion, job runs, and Magnus builds.
Draft commits check the current grants. Section deletion uses the stored draft's
kind and scope; `--with-links` requires both deletion grants. Creating a bookmark's
first section also requires section creation permission. Builds launched from
Recent Links use the same build grant. Local settings remain editable through
the CLI, and interactive panel actions retain their own confirmation flows.
These preferences control the supported client, not other software running as
the same Unix user.

Magnus build tracking records only that the action endpoint accepted a request.
Receipts are profile-scoped, owner-only local files without endpoint URLs and
never claim server-side completion. Rock Arch does not synthesize deployment
status when Magnus does not expose a dependable status endpoint.

Job triggering uses a separate fixed-endpoint client. Read-only discovery follows
the known Obsidian Scheduled Job List type to an actual page/block pair. A bounded
initialization action verifies that exact type and page/block access; Rock Arch
also requires the block's Edit permission, even when Rock's RunNow action would
permit a viewer. The standard Jobs page is preferred, with a unique accessible
custom placement as fallback. Discovery failures and ambiguous placements disable
the action. Access caches and drafts are cleared on account/context changes.
A current Jobs search reference or an exact Scheduled Job entity reference from
the active profile's Recent Links can create a two-minute, single-use draft.
History references must match the active origin and exact job route; they do
not grant job access.
Confirmation rechecks access, placement, and the job's GUID/name before one
RunNow POST with its GUID. GET cannot trigger jobs, clients cannot supply page or
block GUIDs, and uncertain writes are never retried. The UI drops unsent job
requests on close, profile changes, and connection failure. Status is a bounded
read of the latest job record, not proof that this request completed. Permission
checks and POST are separate requests; Rock's own authorization remains final.

Personal Link additions use a separate bounded client. It derives the person
and primary alias from the authenticated session, offers only non-shared
sections owned by that alias, and rechecks both account and section at Save.
Clients cannot choose a raw owner or record ID. The URL must resolve to the
active HTTPS Rock origin. Single-use drafts expire after ten minutes and are
cleared on account/context changes and sign-out. Expiry is checked again after
validation reads and before writes. Saves are read back before
success is reported; ambiguous outcomes are not retried automatically. Explicit
section creation accepts only a name and fixes the authenticated owner and
`IsShared: false`. It checks for a matching private section before creating one,
and verifies the returned section's ID, name, ownership, and private status.
Link and section drafts cannot be used interchangeably. A first private Links
section can also be created as part of an explicit bookmark save.

Deletion uses separate opaque per-record references and expiring, single-use
confirmation drafts. Navigation IDs, raw record IDs, shared items, and foreign
owners cannot delete. Before DELETE the broker rechecks the account, exact
record fields, and private section ownership. Section confirmation counts all
children rather than relying on displayed counts, and retains only their IDs in
the in-memory draft. Invalid counts or more than 10,000 children block deletion.
The UI explicitly authorizes the section and all its contents; the CLI requires
`--with-links --confirm` for populated sections. This scope cannot change between
preparation and confirmation. Changed child IDs require a fresh review, even if
the count stays the same. The fixed delete client
accepts only positive integer IDs under the two Personal Links endpoints and
verifies absence afterward, including child absence for section deletion.
Uncertain responses are never retried automatically.
Rock's section DELETE cascades to children and has no conditional empty-only
operation. The UI and flagged CLI authorize all contents, and the reported count
is the last verified count, not an atomic server receipt. Without `--with-links`,
the CLI checks emptiness immediately before deletion, but a concurrent addition
after that check remains a server-side race. Rock Arch cannot make the separate
read and DELETE atomic.

## Secret handling

Rock profile usernames and passwords are stored in desktop Secret Service. The
Rock session cookie is held only in broker memory and expires after 15 idle
minutes. Secret values are passed to `secret-tool` through stdin, never argv.
The broker invokes the fixed `/usr/bin/secret-tool` binary and rejects invalid
or oversized secret output. Sign-out reports an error if Secret Service does
not confirm deletion. The removed experimental OAuth subsystem and its legacy
records are not read.

Do not attach a live tenant or retrieve production credentials when testing a
security report. The unit suite uses synthetic stores, cookies, responses, and
local Unix sockets.

The [0.27.0 release audit](docs/SECURITY-REVIEW-0.27.0.md) covers the new mutation
features, Recent Link actions, UI boundaries, and release verification.
