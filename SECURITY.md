# Security policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub's security
advisory interface for this repository. Do not include Rock credentials,
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
text. Rock permissions remain the authorization boundary for tenant data and
the mobile-app build action. Rock Arch probes only its eight fixed read
endpoints after login, hides denied categories, and independently enforces the
detected allowlist in the broker before search requests are issued.

Update checks are limited to the canonical Git-managed Rock Arch installation.
They first require `origin` to be the canonical ONE&ALL Church repository, fetch
its public `HEAD`, refuse local tracked changes or diverged history, validate
the remote plugin ID and version, and expose only bounded status codes to QML.
Installation always delegates to Omarchy's fixed plugin updater so its
fast-forward, validation, rollback, and rescan safeguards remain authoritative.
Automatic installation is disabled by default.

The supported CLI uses the same owner-only broker and emits a versioned,
bounded JSON contract. Private search input can be read from stdin so person
names do not need to appear in process arguments. Confirmed actions have a
side-effect-free dry-run path, and diagnostics omit tenant identity, local
paths, queries, and secrets. Native UI handoffs store query text only in broker
memory, consume it once, and erase an unclaimed handoff after 30 seconds.

Magnus build tracking records only that the action endpoint accepted a request.
Receipts are profile-scoped, owner-only local files without endpoint URLs and
never claim server-side completion. Rock Arch does not synthesize deployment
status when Magnus does not expose a dependable status endpoint.

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
