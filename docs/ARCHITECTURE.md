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
    worker that pins installation to the full checked commit, validates it with
    Omarchy, and requests a shell restart after exact-ID verification. Automatic
    installation is an explicit preference and defaults to off.
15. `ShortcutManager`: optional owner-local Lua shortcut edits. The UI model
    and shared setup controls live in `RockArchShortcut.qml` and
    `RockArchShortcutSettings.qml`. `shortcut_keymap.py` resolves physical
    bindings through Hyprland's reported XKB layouts and its existing
    libxkbcommon runtime library.

16. `PersonalLinkManager`: private link/section catalogs and confirmed creation
    and deletion through fixed endpoints, with expiring, single-use drafts.
17. `JobManager`: bounded Scheduled Job List discovery, authorization checks,
    short-lived job drafts, confirmed RunNow requests, and latest-record status.
18. `cli_permissions`: explicit grants for the six supported remote mutation
    actions, enforced in the broker independently of interactive panel controls.

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
The Personal Link editor receives its explicitly selected, validated same-origin
URL so the user can review and edit the bookmark.
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
default-on `terminalAccess` read preference is disabled. Remote mutations also
require the default-off `terminalMutationAccess` gate and explicit membership in
`terminalMutationActions` (empty by default). Draft commits re-evaluate grants;
section deletion derives its action from the stored draft, and `--with-links`
also requires delete permission for links. Implicit first-section creation and
Recent Links build triggers enforce their corresponding grants. Owner-local settings and
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
Both the manual and optional automatic path pass the same full 40-character
checked commit to a detached fixed module. It accepts only the canonical install
directory and serializes workers with a private advisory lock. The worker
validates an exact-commit temporary worktree with Omarchy's static validator,
rechecks the live checkout, and uses a hook-disabled fast-forward to that immutable
ID. It never fetches or invokes Omarchy's mutable-target plugin updater. Local
changes, untracked files, and ignored-file collisions are preserved. After
verifying installed identity, version, and clean state, it requests a full shell
restart so new IPC methods are registered. Candidate validation failure leaves
the existing installation intact; later concurrent changes cause a failure
without forcibly reverting someone else's changes. Updater state is bounded, owner-only JSON and
contains no Git output, credentials, cookies, or Rock data.

Person Quick Look exposes only `displayName`, `subtitle`, `campus`, and an
opaque `safeId`. Optional person context includes age, conservatively inferred
spouse, family campus, and connection status. Contact details, notes, addresses,
full birth dates, photos, raw record IDs, and authentication identifiers are
excluded. The bounded family read is described below.

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
generated prefix filters (contains-style matching for Workflow Types). The eight fixed reads share one native Rock
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
Personal Link listing uses `PersonalLinks/GetPersonalLinksData`. Responses are
capped at 2 MiB, transformed immediately into display allowlists, and cached in
memory for five minutes. Unscoped search matches the allowlisted title and
section locally, ranks Personal Links before entity results, and never exposes
their URLs. Opening the panel force-refreshes that cache; scoped entity searches
do not include Personal Links. A failed category is reported as unavailable;
PROD never falls back to mock data. This search client exposes no write or
generic HTTP operation. Personal Link changes and job triggering use separate
fixed-endpoint clients described below; there is no arbitrary entity mutation
or SQL interface.

### Personal Link additions

`PersonalLinkManager` owns in-memory, ten-minute, single-use drafts, typed for
either link or section creation. The Search
source is resolved through the existing opaque registry; the UI receives the
validated same-origin URL only for this explicit editor. Profile switches,
credential changes, sign-out, and context changes clear drafts. UI request IDs
discard late responses, and closing or interrupting the form drops queued
unsent preparations and saves.

A separate `PersonalLinkHttpClient` leaves the search client's GET-only contract
intact. It reads `People/GetCurrentPerson`, discards all fields except the
person ID and primary alias ID, and projects `Id,Name,IsShared,PersonAliasId`
from `PersonalLinkSections`. The section query uses the primary alias directly:
some Rock versions do not expose the PersonAlias navigation field to OData.
Only sections attached to that alias are offered; shared sections are rejected.
Raw owner and section IDs never cross the UI/CLI boundary.

Save rechecks the authenticated identity and section ownership. The fixed
`POST /api/PersonalLinks` payload contains only Name, Url, PersonAliasId,
SectionId, and Order. If no personal sections exist, the explicit Save can first
create a non-shared Links section through `POST /api/PersonalLinkSections` with
the authenticated owner. Explicit section creation uses the same private endpoint
with only Name, PersonAliasId, and IsShared fixed to false. The supplied name is
checked against existing private sections without case sensitivity, then a new
section is read back to verify ID, name, owner, and privacy. At most 100 private
sections are supported; the limit is checked before creating another section.
Each endpoint remains subject to Rock's REST action
permissions. Names obey Rock's 100 UTF-16-unit limit; URLs are bounded,
canonicalized HTTPS targets on the active origin. No shared-link writes, edits,
or arbitrary entity writes are exposed.

Before creating a link, an exact section/owner/URL query detects duplicates.
After creation, a bounded read-back checks the returned ID, owner, section,
name, and URL. The draft is consumed before a POST. An ambiguous response never
causes a POST retry; a subsequent explicit attempt repeats the duplicate check.
Successful saves invalidate the existing Personal Links cache.

Deletion uses a separate bounded mapping of opaque `deleteId`s to the exact
personal bookmark record. It never resolves a navigation URL into a delete
target, so same-URL bookmarks remain distinct. The map clears on profile changes
and link-cache invalidation. Section targets use the owned catalog's `safeId`.
Prepare reads the exact record, derives the current account and private section,
and stores a separate single-use draft with a snapshot of the reviewed
fields. Confirmation repeats those checks, rejects changes, consumes the draft,
sends one fixed DELETE, and reads back absence. A previously removed record is
reported as already deleted without sending DELETE.

Section preparation queries `PersonalLinks` by SectionId with `$select=Id,SectionId`,
`$orderby=Id`, and `$top=10001`, without owner or URL filtering. Invalid rows,
duplicate IDs, and more than 10,000 children block deletion. The sorted IDs stay
in the in-memory draft; the UI and CLI receive only `linkCount` and `withLinks`.
The strictly typed `withLinks` scope must match at preparation and confirmation.
The UI authorizes all contents; the CLI requires `--with-links` for that scope.
Confirmation compares the full child ID set and requires a fresh review if it
changed, even when the count is unchanged. Without this flag, preparation refuses
populated sections and confirmation rechecks emptiness with `$top=1`.

Deletion sends one section DELETE and verifies both the section and its children
are absent. It never loops over child DELETEs. The result's count is the last
verified count, not an atomic server receipt. These queries include links hidden
by URL validation or panel limits. Rock's standard
[`ApiController.Delete`](https://github.com/SparkDevNetwork/Rock/blob/a51094b052a501983dfb746c45d441b59b67d2bb/Rock.Rest/ApiController.cs)
does not provide a conditional delete or transaction spanning these requests;
the Personal Link model enables cascade deletion. The UI and flagged CLI explicitly
authorize the section and all its contents. For the default empty-only CLI path,
an addition by another client between the final check and DELETE could still be
cascaded. Atomic empty-only deletion would require a corresponding Rock server
endpoint.

`RockArchLinkView.qml` derives section headers, expanded child rows, and a flat
alphabetical list from the allowlisted links and an owned-section catalog. Rock's
Personal Links endpoint omits empty sections, so refreshing Links also reads the
current identity and private sections. The catalog exposes only name, opaque
creation and display IDs, and private status. If that optional read is denied,
the existing authorized bookmarks remain available. Expanded empty sections
offer Add a link with the section preselected. It keeps the selected record
through reordering and expands the containing section after a save. Group display
IDs are deterministic HMAC references scoped to the profile's random local ID,
the Rock origin, and the section ID; they do not enter the navigation registry
and are not action tokens. Only these references and view preferences persist in
the owner-only profile store, not section names or bookmark URLs. Same-named
sections stay distinct. Expansion settings are removed when a profile is deleted.
Creating a section switches to Sections, opens it, and selects its heading.
No creation-date metadata is requested or stored.

The contract was checked against the official Rock source at
[`a51094b`](https://github.com/SparkDevNetwork/Rock/tree/a51094b052a501983dfb746c45d441b59b67d2bb):
[`ApiController.Post`](https://github.com/SparkDevNetwork/Rock/blob/a51094b052a501983dfb746c45d441b59b67d2bb/Rock.Rest/ApiController.cs),
[`GetCurrentPerson`](https://github.com/SparkDevNetwork/Rock/blob/a51094b052a501983dfb746c45d441b59b67d2bb/Rock.Rest/Controllers/PeopleController.Partial.cs),
the [Personal Link model](https://github.com/SparkDevNetwork/Rock/blob/a51094b052a501983dfb746c45d441b59b67d2bb/Rock/Model/CMS/PersonalLink/PersonalLink.cs),
and the [Personal Link Section model](https://github.com/SparkDevNetwork/Rock/blob/a51094b052a501983dfb746c45d441b59b67d2bb/Rock/Model/CMS/PersonalLinkSection/PersonalLinkSection.cs).

The cookie authenticates the actor but does not override Rock authorization.
The broker intersects saved category preferences with the detected account
capabilities before every search. QML receives only the category names, hides
unavailable choices and shortcuts, and cannot make a scoped or unscoped request
reach an unavailable endpoint. Rock controller/action permissions remain the
authoritative server-side boundary.

### Scheduled jobs

`JobManager` discovers the modern Obsidian Scheduled Job List type through bounded
`BlockTypes`, `Blocks`, and `Pages` reads. Its fixed
`RefreshObsidianBlockInitialization` action verifies the discovered page/block pair,
block type, and page access. Both add and delete capability flags must be true,
which requires block Edit access. The standard Jobs page is preferred; otherwise
exactly one accessible custom placement is required. Discovery is cached for
60 seconds and cleared on account, credentials, origin, or context changes.

Only a current Jobs search reference can prepare a two-minute, single-use draft.
Confirmation refreshes discovery and rechecks job identity, name, placement, and
expiry before one `RunNow` POST containing the job GUID. The client accepts only
these two exact block actions under the discovered page/block path. Clients cannot
provide their own route or use GET to trigger execution. Uncertain writes are
never retried. Status reads the latest recorded job state; acceptance and an old
Success record do not prove this request completed.

The Search panel presents Run only after access succeeds and opens confirmation
in the same panel with Cancel initially focused. CLI execution additionally
requires the `runJobs` grant; discovery and previews remain read operations.

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
Rock route:

| Entity | Rock route |
|---|---|
| Person | `/Person/{id}` |
| Group | `/Group/{id}` |
| Group Type | `/admin/general/group-types/{id}` |
| Workflow Type | `/admin/general/workflows?WorkflowTypeId={id}` |
| Scheduled Job | `/admin/system/jobs/{id}` |
| Page | `/page/{id}` |
| Content Channel Type | `/admin/cms/content-channel-type?ContentChannelTypeId={id}` |
| Content Channel Item | `/ContentChannelItem/{id}` |

Personal Link targets may be relative but must resolve to HTTPS on the selected Rock origin; external and malformed
links are omitted.

Successful user-requested opens and accepted mobile app build requests are
shown as Recent Links. The underlying Quick Return store keeps the title, type,
order, target, and timestamp locally, but
returns only another process-local opaque ID, title, and type to QML. Its
directory is `0700`, its file is `0600`, writes are atomic, entries are
validated on every read, and the oldest entries are removed beyond 20. The
public list is sorted globally by its last-used timestamp, newest first, rather
than grouping items by entity type. Each profile receives a separate store, and
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
