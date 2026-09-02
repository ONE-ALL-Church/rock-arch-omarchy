# Architecture and privacy boundary

## Components

1. `plugin/oneall.rock-lens`: a thin Quickshell bar indicator and launcher.
2. `rock_lens_broker`: an allowlist-based local broker using an owner-only Unix
   socket (`0700` directory, `0600` socket).
3. `RockSessionProvider`: native per-profile Rock login, Secret Service
   credential storage, and a validated memory-only `.ROCK` cookie.
4. `OAuthManager`: optional Rock OpenID Connect authorization-code support for
   future bearer-token capabilities; core login does not require it.
5. `MockAdapter`: deterministic, synthetic records for People, Groups,
   Workflow Types, Jobs, Pages, and Content Channel Items.
6. `MagnusReadOnlyAdapter`: optional native capability probe plus descriptor-
   driven tree browsing, bounded text previews, and hashes on the selected Rock
   origin. It reuses `RockSessionProvider`; no external CLI is launched.
7. `RockRestReadOnlyAdapter`: six fixed Rock REST v1 entity GETs plus the fixed
   current-user Personal Links action, authenticated by the native Rock session.
8. `QuickReturnStore`: same-origin launcher history, deduplicated and capped at
   20 in an owner-only JSON file.

## Trust boundary

The QML side never receives credentials, cookies, SQL, raw entity response
bodies, raw URLs/record IDs, internal exception text, or fields outside the
typed display contract. The sole content exception is a bounded UTF-8 Magnus
file preview explicitly selected by the user.
Requests and responses are newline-delimited JSON with a 16 KiB request limit.
Search text is sent through the socket, not argv. The broker emits no request or
response logging.

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

Profiles created by earlier Rock Lens releases automatically migrate their
`magnus_username` and `magnus_password` Secret Service records into neutral
`rock_username` and `rock_password` records, then remove the obsolete keys.
Authentication failure, sign-out, profile change, or a failed authenticated
request clears the cached cookie.

## Optional Rock OAuth boundary

Rock is the OpenID Provider. The broker loads owner-only issuer/client metadata,
retrieves Rock's standard discovery document, and accepts only HTTPS
authorization and token endpoints on the issuer's origin. The registered
callback must be an exact unprivileged `127.0.0.1` HTTP URI. Authorization uses
`response_type=code`, a random state and nonce, and S256 PKCE. Public Rock
clients have no secret; confidential-client secrets are read from Secret
Service only for the token exchange.

Authorization codes live only in broker memory. Stored token records contain
the bearer token, optional refresh token, type, scope string, and expiry and are
written only to Secret Service. Identity-token claims are not persisted or
sent to QML. The public socket contract exposes only a fixed state/label and a
configured boolean. Detailed HTTP errors and response bodies are discarded.

Authentication states are `unconfigured`, `signed_out`, `starting`, `waiting`,
`refreshing`, `authenticated`, `expired`, and `failed`. Refresh failure deletes
the unusable token set and fails closed. Disconnect deletes only the local token
set. Gated DEV and PROD use separate configuration and keyring records.

## Explicit context

Context is a broker-owned enum: `DEV` or `PROD`. Normal startup is forced to
PROD, including migration of a previously persisted DEV value. The QML omits
the context control, and the broker rejects requests to enter DEV. Synthetic
DEV data is available only when the broker process starts with the exact
`ROCK_LENS_DEVELOPER_MODE=1` flag; values such as `true` or `yes` fail closed.
When enabled, the UI restores the visibly labeled context control and explicit
`set_context` requests may select either context. Both contexts remain
read-only, and PROD never falls back to synthetic data.

## Live REST boundary

Live data is available only in explicit PROD context and only after a Rock
profile login is configured. The bare domain is normalized to an HTTPS origin
and rejected if it contains credentials, a path, query, fragment, or non-443
port. The broker attaches the validated memory-only `.ROCK` cookie only to
exact-origin HTTPS requests. Core REST reads do not check for Magnus and remain
available when the plugin is absent or the account lacks Magnus permission.

The client cannot choose an endpoint. These are Rock's established REST v1
controller/OData routes, not `/api/v2`. Search is limited to `People`, `Groups`,
`WorkflowTypes`, `ServiceJobs`, `Pages`, and `ContentChannelItems`, with fixed
`$select`, `$orderby`, `$top=3`, and generated `startswith` filters. The six
fixed reads share one native Rock session cookie and start in
parallel; results are still transformed in a deterministic category order.
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
capped at 2 MiB and transformed immediately into display allowlists. A failed
category is reported as unavailable; PROD never falls back to mock data. There
is no raw HTTP, generic entity, SQL, mutation, job execution, or Run Now
operation.

The cookie authenticates the actor but does not override Rock authorization.
Rock controller/action permissions still apply; endpoints that enforce entity
security continue to do so for the signed-in Rock account.

## Optional Magnus boundary

Magnus is an optional server capability, not an identity provider. After a
normal Rock login the broker probes only
`/api/TriumphTech/Magnus/GetServer`. Success enables the Magnus view; 403 or 404
marks it unavailable for that profile without affecting search or links.

The native adapter accepts only the configured Rock origin, permits only tree
paths under `api/TriumphTech/Magnus/GetTreeItems/` and content paths under
`/FileContent/`, and rejects alternate origins, redirects, query strings,
fragments, control characters, backslashes, and traversal segments. Tree rows
and files cross QML only as process-local opaque IDs. Text previews are explicit
user actions, UTF-8 only, reject NUL bytes, and are capped at 64 KiB; file reads
are capped at 4 MiB and tree responses at 2 MiB.

Descriptors are sanitized into `build`, `delete`, `upload`, `newFile`, and
`newFolder` availability labels only when their URI is same-origin and has the
expected Magnus action prefix. Those labels do not grant an operation: this
release exposes only browse, preview, and hash. There are no write, remove,
upload, create, build, deployment, arbitrary HTTP, or raw URL operations.

## Navigation, Personal Links, and Recent Links

Search results and Personal Links cross the socket with process-local HMAC IDs.
Only the broker can resolve those IDs. Every search category maps to a fixed
Rock route: Person (`/Person/{Id}`), Group (`/Group/{Id}`), Workflow Type
configuration (`/admin/general/workflows?WorkflowTypeId={Id}`), Scheduled Job
detail (`/admin/system/jobs/{Id}`), Page (`/page/{Id}`), and Content Channel
Item (`/ContentChannelItem/{Id}`). Personal Link targets may be relative but
must resolve to HTTPS on the selected Rock origin; external and malformed
links are omitted.

Successful user-requested opens are shown as Recent Links. The underlying Quick
Return store keeps the title, type, order, target, and timestamp locally, but
returns only another process-local opaque ID, title, and type to QML. Its
directory is `0700`, its file is `0600`, writes are atomic, entries are
validated on every read, and the oldest entries are removed beyond 20. Each
origin receives a separate store, and Recent Links are omitted from DEV
responses. The broker serves this local list independently from Personal Links,
so showing the empty Search state never performs a Rock network request. This
intentionally emulates Rock's useful return list without importing browser-local
Rock history.
