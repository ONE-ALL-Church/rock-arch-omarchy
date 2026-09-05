# Architecture and privacy boundary

## Components

1. `plugin/oneall.rock-arch`: a Quickshell panel controller composed from
   focused Login, Search, Personal Links, Magnus, Settings, and navigation QML
   components. Shared key handling and selection chrome remain independent
   primitives. `RockArchBroker.qml` owns the Python process and Unix socket;
   `RockArchConnection.qml` owns request coalescing, credential-queue cleanup,
   and retries. `RockArchResponses.js` preserves response ordering and delegates
   account, search/Knowledge/links, and Magnus updates to focused modules with
   explicit controller and UI dependencies.
2. `rock_arch_broker`: an allowlist-based local broker using an owner-only Unix
   socket (`0700` directory, `0600` socket).
3. `rock-arch`: an owner-local, JSON-producing terminal and agent client for
   the same broker. It adds no independent HTTP or credential implementation.
4. `RockSessionProvider`: native per-profile Rock login, Secret Service
   credential storage, and a validated memory-only `.ROCK` cookie.
5. `SecretToolStore`: the small Secret Service adapter used only for
   per-profile Rock usernames and passwords.
6. `MockAdapter`: deterministic, synthetic records for People, Groups, Group
   Types, Workflow Types, Jobs, Pages, Content Channel Types, and Content
   Channel Items.
7. `MagnusReadOnlyAdapter`: optional native capability probe plus descriptor-
   driven browsing, bounded previews/downloads, clipboard values, hashes,
   same-origin view links, and confirmed mobile app builds on the selected Rock
   origin. It reuses `RockSessionProvider`; no external CLI is launched.
8. `RockRestReadOnlyAdapter`: eight fixed Rock REST v1 entity GETs plus the fixed
   current-user Personal Links action, authenticated by the native Rock session.
9. `RockKbReadOnlyAdapter`: explicit public Knowledge search and exact-result
   reads through a fixed, credentialless HTTPS origin, with bounded response
   transformation, short in-memory caches, and opaque result/source IDs.
10. `QuickReturnStore`: same-origin launcher and accepted-build shortcuts,
   deduplicated and capped at 20 in an owner-only JSON file. Build entries are
   executed only through the Magnus validator and require confirmation again.
11. `BuildReceiptStore`: profile-scoped, owner-only Magnus acceptance receipts
    with persistent opaque build IDs. Receipts explicitly cannot verify server
    completion.
12. `BrokerOperations`: the explicit operation-name router and request handlers;
   broker construction, state ownership, and lifecycle transitions remain in
   `Broker`.
13. `http_security`: shared redirect refusal, authenticated cookie-header
    validation, and bounded JSON decoding used by every Rock HTTP client.
14. `UpdateManager`: daily public-Git revision checks plus a fixed detached
    worker that delegates installation, validation, rollback, and shell restart
    to Omarchy. Automatic installation is an explicit preference and defaults
   to off.
15. `ShortcutManager`: optional owner-local Lua shortcut edits. The UI model
    and shared setup controls live in `RockArchShortcut.qml` and
    `RockArchShortcutSettings.qml`. `shortcut_keymap.py` resolves physical
    bindings through Hyprland's reported XKB layouts and its existing
    libxkbcommon runtime library.

Shortcut operations use fixed names (`shortcut_status`, `shortcut_install`,
`shortcut_remove`) and a fixed Rock Arch summon command. Mutations require
explicit confirmation, an installed plugin, PROD context, a fresh revision of
the config and active bindings, and an unoccupied combination. The broker
refuses symlinks, unsafe ownership/permissions, changed managed blocks, and
unknown configuration/keymap shapes. It serializes its writers, preserves
unrelated bytes, keeps an owner-only backup, atomically replaces the file,
reloads Hyprland and verifies activation. Failed reloads roll back only if no
concurrent file edit would be overwritten. The UI reports the configured
binding and offers Change/Remove for managed shortcuts. Shortcut responses
never reset Rock login/onboarding state.

The broker module's legacy login/status aliases forward to the supported CLI.
Retired raw-path diagnostic commands return migration guidance before creating
a client. There is one supported command path for profile and session changes.

## Trust boundary

QML handles a password only while the user types and submits an explicit login
request. It clears the password field immediately; if the broker remains
unavailable, it purges the queued credential request on panel close or after the
18-second connection timeout. Credentials are never returned from the broker.
QML never receives cookies, SQL, raw entity response bodies, raw URLs/record
IDs, internal exception text, or fields outside the typed display contract.
The content exceptions are a bounded UTF-8 Magnus file preview explicitly
selected by the user and the bounded public body of an explicitly selected
Rock Knowledge result. Both cross typed, size-limited contracts.
Requests and responses are newline-delimited JSON with a 16 KiB request limit.
Search text is sent through the socket, not argv. The broker emits no request or
response logging.

At startup, the broker requires the socket directory to be an actual directory
owned by the current user and forces mode `0700`. It will never unlink a regular
file, symlink, foreign socket, or group/world-accessible socket at the expected
path. A stale socket is removed only after its device, inode, owner, type, and
permissions are rechecked; a live private socket is treated as an already
running broker. QML launches the broker through `/usr/bin/python3`, avoiding a
PATH-selected executable at this credential boundary.

The supported terminal client validates the owner and permissions of the same
socket and its directory, bounds responses to 5 MiB, and adds an explicit
official-client marker. The broker refuses marked Rock requests when the
default-on `terminalAccess` preference is disabled. Owner-local settings and
shortcut management remain available for configuration and recovery; settings
reads return no profile identities or Rock data. This preference is a
supported-client control, not a sandbox against hostile software already
running as the same Unix account. The Unix account remains the OS security
boundary.

When the broker runs from the canonical Git-managed plugin installation,
`TerminalAccessManager` atomically installs a small `~/.local/bin/rock-arch`
Python launcher pointing at that installation. It refuses source-checkout
repointing, symlinks, foreign or unsafe paths, and any unrelated existing
command. The launcher contains no credentials or profile data. CLI login reads
the password from a masked terminal prompt and never accepts it in argv.
Commands produce versioned, bounded JSON and use process-local opaque IDs; IDs
expire when the broker restarts. Private searches can read stdin, `doctor`
returns redacted diagnostics, and `describe` plus `--dry-run` inspect an action
without executing it. Browser, clipboard, download, history deletion, sign-out,
profile removal, update installation, and mobile builds require `--confirm`.
Omarchy panel handoff stages a one-time payload in broker memory, invokes the
fixed plugin IPC method without putting the query in argv, and erases an
unclaimed payload after 30 seconds.

The updater is active only when the running repository is the canonical
Git-managed `oneall.rock-arch` installation. It also requires `origin` to match
the canonical ONE&ALL Church repository before it fetches `origin HEAD`,
compares revisions, and validates the remote root manifest's plugin ID and
semantic version. It will not install over tracked changes or diverged history.
Both the manual and optional automatic path launch a detached fixed module that
accepts only the canonical install directory and calls Omarchy's plugin updater.
Omarchy remains responsible for the fast-forward merge, plugin validation, and
rollback; Rock Arch then requests a full shell restart so new IPC methods are
registered. Updater state is bounded, owner-only JSON and
contains no Git output, credentials, cookies, or Rock data.

Person Quick Look exposes only `displayName`, `subtitle`, `campus`, and an
opaque `safeId`. Live search deliberately reports campus as `Not requested`.
No contact details, notes, addresses, dates of birth, family relationships,
photos, raw record IDs, or authentication identifiers are in the contract.

## Native Rock session boundary

Each profile stores only its display name, stable random ID, and strict HTTPS
origin in owner-only JSON. Username and password are stored under that profile
ID in desktop Secret Service. `RockSessionProvider` verifies new credentials
with a redirect-free `POST /api/Auth/Login` before replacing a saved login. It
accepts only a bounded `.ROCK` cookie from `Set-Cookie` and retains that cookie
only in process memory with a sliding 15-minute idle timeout.

Profiles created by earlier Rock Arch releases automatically migrate their
`magnus_username` and `magnus_password` Secret Service records into neutral
`rock_username` and `rock_password` records, then remove the obsolete keys.
Authentication failure, sign-out, profile change, or a failed authenticated
request clears the cached cookie.
Sign-out and profile removal are successful only when Secret Service reports
that every targeted record was cleared. A deletion failure clears the in-memory
cookie but returns `secure_storage_failed` instead of claiming that stored
credentials are gone.

Version 0.14 removed the unused experimental OpenID manager and its public
broker operations. Legacy `oidc.json`, client-secret, and token records are not
read. They remain user-owned and are not silently deleted during an upgrade.

## Explicit context

Context is a broker-owned enum: `DEV` or `PROD`. Normal startup is forced to
PROD, including migration of a previously persisted DEV value. The QML omits
the context control, and the broker rejects requests to enter DEV. Synthetic
DEV data is available only when the broker process starts with the exact
`ROCK_ARCH_DEVELOPER_MODE=1` flag; values such as `true` or `yes` fail closed.
When enabled, an authorized local developer request may select either context;
the panel still renders no context badge or end-user switch. DEV provides
deterministic fixtures across Search, Personal Links, Recent Links, Knowledge,
and Magnus. The Magnus fixture preserves the content-family, application,
page/block, and file hierarchy and exposes Deploy only on the parent mobile-app
listing. Its open, download, clipboard, source-open, history-clear, and build
operations are explicit no-ops. PROD never falls back to fixture data, and only
PROD can perform the narrowly gated Magnus mobile app build action.

## Live REST boundary

Live data is available only in explicit PROD context and only after a Rock
profile login is configured. The bare domain is normalized to an HTTPS origin
and rejected if it contains credentials, a path, query, fragment, or non-443
port. The broker attaches the validated memory-only `.ROCK` cookie only to
exact-origin HTTPS requests. Core REST reads do not check for Magnus and remain
available when the plugin is absent or the account lacks Magnus permission.

The client cannot choose an endpoint. These are Rock's established REST v1
controller/OData routes, not `/api/v2`. Search is limited to `People`, `Groups`,
`GroupTypes`, `WorkflowTypes`, `ServiceJobs`, `Pages`, `ContentChannelTypes`,
and `ContentChannelItems`, with fixed `$select`, `$orderby`, `$top=3`, and
generated `startswith` filters. The eight fixed reads share one native Rock
session cookie and start in
parallel; results are still transformed in a deterministic category order.
After login, a separate bounded capability pass sends `$select=Id&$top=1` to
those same eight endpoints in parallel. A successful list response marks a
category searchable even when it contains no rows; authorization and missing-
endpoint responses mark only that category unavailable. Transient failures make
the access check fail closed instead of guessing. The result is cached in broker
memory for five minutes and cleared on profile, origin, credential, or context
changes.
The Groups projection also expands only `GroupType.Name` for its subtitle.
People project age, Giving Group, marital/connection/record status, then perform
at most one bounded Groups read for the returned family IDs. That second read
projects only campus plus member names, roles, and archive flags; the in-memory
result is cached by family ID. A spouse label requires a married record and
exactly one other non-archived Adult family member, avoiding guesses for
multi-adult households. Contact details, addresses, and full birth dates are
never requested.
Recognized leading entity prefixes are parsed into one canonical category and
the remaining text; a scoped search runs only that category's existing fixed
specification. Bare prefixes omit `$filter` but retain the fixed projection,
ordering, and `$top=3`. Unknown prefixes stay in the search text and cannot
select an API path.
Personal Links use only `PersonalLinks/GetPersonalLinksData`. Responses are
capped at 2 MiB, transformed immediately into display allowlists, and cached in
memory for five minutes. Unscoped search matches the allowlisted title and
section locally, ranks Personal Links before entity results, and never exposes
their URLs. Opening the panel force-refreshes that cache; scoped entity searches
do not include Personal Links. A failed category is reported as unavailable;
PROD never falls back to mock data. There is no raw HTTP, generic entity, SQL,
mutation, job execution, or Run Now operation.

The cookie authenticates the actor but does not override Rock authorization.
The broker intersects saved category preferences with the detected account
capabilities before every search. QML receives only the category names, hides
unavailable choices and shortcuts, and cannot make a scoped or unscoped request
reach an unavailable endpoint. Rock controller/action permissions remain the
authoritative server-side boundary.

## Public Rock Knowledge boundary

Public Knowledge search is a separate trust path from live Rock search. A
dedicated Knowledge workspace and `Ctrl+3` (default order) own the external query flow. The
leading `kb:` and `knowledge:` prefixes remain quiet main-Search transitions:
QML moves their remainder into Knowledge before dispatch, so normal unscoped
and entity-prefixed Rock text can never reach the external service.

`RockKbHttpClient` performs only redirect-free GET requests to the exact
`https://rock-agent-kb.oneandall.church` origin. It attaches the Rock Arch user
agent and JSON accept header only. The client has no reference to the Rock
session or profile stores, so it cannot attach a cookie, credential, instance
domain, profile identifier, Personal Link, Recent Link, or Rock entity result.
Generic, issue, idea, and recipe search requires at least three characters;
local Model Map, Lava-context, and concept filtering accepts two. Each area
returns at most ten rows. The redirect-free client uses only fixed GET routes
for generic search, exact results, Model Map, Lava contexts, issues, ideas, and
concept guides. Search responses are capped at 512 KiB, bounded collections at
3 MiB, and exact details at 2 MiB; only 20,000 characters of plain body text
cross QML.

Both service schemas are checked before use. Result IDs and source URLs remain
inside an in-process HMAC registry; QML receives only `kb-` opaque IDs, bounded
titles/snippets, trust labels, version status, public body text, attribution,
a source hostname, and bounded related-item rows. Related result IDs, Model Map
slugs, Lava roots, and concept IDs are registered behind the same opaque-ID
boundary; QML cannot provide an endpoint or raw target. Opening a source requires a separately selected detail,
an explicit action, and an HTTPS URL with no credentials, custom port, local
hostname, IP literal, control character, or redirect. Knowledge results never
enter profile-scoped Recent Links. Search and exact details are cached only in
broker memory for five minutes.

The hosted KB may return official, reviewed-community, or unreviewed routing
material. Rock Arch preserves authority labels and marks community issue and
idea reports as unreviewed rather than presenting them as established Rock
behavior. Displayed material is attributed to Rock Agent Knowledge Base,
ONE&ALL Church. The integration uses the service's plain HTTPS projection and
does not install or invoke Rock KB MCP or CLI tooling.

## Optional Magnus boundary

Magnus is an optional server capability, not an identity provider. After a
normal Rock login the broker probes only
`/api/TriumphTech/Magnus/GetServer`. Success enables the Magnus view; 403 or 404
marks it unavailable for that profile without affecting search or links.

The native adapter accepts only the configured Rock origin, permits only tree
paths under `api/TriumphTech/Magnus/GetTreeItems/` and content paths under
`/FileContent/`, and rejects alternate origins, redirects, query strings,
fragments, control characters, backslashes, and traversal segments after
repeated percent-decoding. This rejects encoded and multiply encoded traversal
before any network request. The HTTP layer independently permits only the
probe, tree, file-content, and numeric mobile-app build route families. Tree
rows and files cross QML only as process-local opaque IDs. Text previews are
explicit user actions, UTF-8 only, reject NUL bytes, and are capped at 64 KiB;
file reads are capped at 4 MiB and tree responses at 2 MiB.

Descriptors become capabilities only after validation. Files expose bounded
download, content/hash copy, and an optional same-origin view target. Folders
expose build only when Magnus supplies the exact numeric mobile app build path.
Delete, upload, new-file, new-folder, broader build, arbitrary HTTP, and raw URL
operations are discarded. Build uses the Magnus CLI-compatible POST contract,
has no automatic retry, and requires confirmation in QML before the broker is
called. The action response proves acceptance only. Rock Arch records that
state in an owner-only receipt, sends an acceptance notification, and does not
invent completion or deployment timestamps that Magnus does not expose.

## Navigation, Personal Links, and Recent Links

Search results and Personal Links cross the socket with process-local HMAC IDs.
Only the broker can resolve those IDs. Every search category maps to a fixed
Rock route: Person (`/Person/{Id}`), Group (`/Group/{Id}`), Workflow Type
configuration (`/admin/general/workflows?WorkflowTypeId={Id}`), Scheduled Job
detail (`/admin/system/jobs/{Id}`), Page (`/page/{Id}`), and Content Channel
Item (`/ContentChannelItem/{Id}`). Personal Link targets may be relative but
must resolve to HTTPS on the selected Rock origin; external and malformed
links are omitted.

Successful user-requested opens and accepted mobile app build requests are
shown as Recent Links. The underlying Quick Return store keeps the title, type,
order, target, and timestamp locally, but
returns only another process-local opaque ID, title, and type to QML. Its
directory is `0700`, its file is `0600`, writes are atomic, entries are
validated on every read, and the oldest entries are removed beyond 20. The
public list is sorted globally by its last-used timestamp, newest first, rather
than grouping items by entity type. Each origin receives a separate store, and
DEV returns a separate, deterministic and non-persistent Recent Links fixture;
its clear and activation operations are no-ops. PROD never receives those
fixtures. A Magnus Build entry cannot be opened as a URL; activation routes it
back through the build-path validator after another UI confirmation. The broker
serves this local list independently from Personal Links,
so showing the empty Search state never performs a Rock network request. This
intentionally emulates Rock's useful return list without importing browser-local
Rock history.

Build acceptance history is stored separately from Recent Links, capped at 50,
and keyed by stable random `build-` IDs. The store contains title, acceptance
time, fixed acceptance copy, local status provenance, and the explicit fact
that completion is unverifiable; it contains no build URI or Rock origin.
