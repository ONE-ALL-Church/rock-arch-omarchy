# Architecture and privacy boundary

## Components

1. `plugin/oneall.rock-lens`: a thin Quickshell bar indicator and launcher.
2. `rock_lens_broker`: an allowlist-based local broker using an owner-only Unix
   socket (`0700` directory, `0600` socket).
3. `OAuthManager`: Rock OpenID Connect authorization-code login with S256 PKCE,
   a loopback callback, refresh-token renewal, and Secret Service persistence.
4. `MockAdapter`: deterministic, synthetic records for People, Groups,
   Workflows, Jobs, Pages, and Content Channel Items.
5. `MagnusReadOnlyAdapter`: privileged, bounded file inspection against the
   user-selected, validated Rock origin, with per-origin credentials held in
   Secret Service and raw Magnus state confined to an ephemeral owner-only
   directory.
6. `RockRestReadOnlyAdapter`: six fixed Rock REST v1 entity GETs plus the fixed
   current-user Personal Links action, authenticated by a validated cookie
   obtained inside the ephemeral Magnus session.
7. `QuickReturnStore`: same-origin launcher history, deduplicated and capped at
   20 in an owner-only JSON file.

## Trust boundary

The QML side never receives credentials, cookies, SQL, raw private response
bodies, raw URLs/record IDs, internal exception text, or fields outside the
typed display contract.
Requests and responses are newline-delimited JSON with a 16 KiB request limit.
Search text is sent through the socket, not argv. The broker emits no request or
response logging.

Person Quick Look exposes only `displayName`, `subtitle`, `campus`, and an
opaque `safeId`. Live search deliberately reports campus as `Not requested`.
No contact details, notes, addresses, dates of birth, family relationships,
photos, raw record IDs, or authentication identifiers are in the contract.

## Rock OAuth boundary

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
set. DEV and PROD use separate configuration and keyring records.

## Explicit context

Context is a broker-owned enum: `DEV` or `PROD`. Startup defaults to `DEV`.
Changing context requires an explicit `set_context` request; no environmental
signal may change it. `PROD` is a visual safety context only and grants no new
capabilities. Both contexts remain read-only.

## Live REST boundary

Live data is available only in explicit PROD context and only after a Rock
domain and its Magnus credentials are configured. The bare domain is normalized
to an HTTPS origin and rejected if it contains credentials, a path, query,
fragment, or non-443 port. One Magnus login yields a validated `.ROCK` cookie in
an ephemeral directory. The broker attaches it only to that exact-origin HTTPS
GET and destroys the directory after the operation. The validated cookie may
remain only in broker memory with a 15-minute idle timeout, avoiding a full
Magnus login for each active search session without creating a persistent file.

The client cannot choose an endpoint. These are Rock's established REST v1
controller/OData routes, not `/api/v2`. Search is limited to `People`, `Groups`,
`WorkflowTypes`, `ServiceJobs`, `Pages`, and `ContentChannelItems`, with fixed
`$select`, `$orderby`, `$top=3`, and generated `startswith` filters. The six
fixed reads share one ephemeral Magnus-authenticated cookie and start in
parallel; results are still transformed in a deterministic category order.
The Groups projection also expands only `GroupType.Name` for its subtitle.
Personal Links use only `PersonalLinks/GetPersonalLinksData`. Responses are
capped at 2 MiB and transformed immediately into display allowlists. A failed
category is reported as unavailable; PROD never falls back to mock data. There
is no raw HTTP, generic entity, SQL, mutation, job execution, or Run Now
operation.

The cookie authenticates the actor but does not override Rock authorization.
Rock controller/action permissions still apply; endpoints that enforce entity
security continue to do so for the Magnus account.

## Magnus boundary

Magnus is not an identity provider and does not replace Rock OpenID Connect for
end users. The adapter accepts only the configured Rock origin, permits only
Magnus tree paths under `api/TriumphTech/Magnus/GetTreeItems/` and content paths
under `/FileContent/`, and rejects alternate origins, query strings, fragments,
control characters, backslashes, and traversal segments.

Credentials are retrieved from Secret Service and the password is sent to the
Magnus login process through its stdin prompt, one character at a time to match
Magnus 0.1.0's interactive reader. Magnus receives an ephemeral `XDG_CONFIG_HOME`
with owner-only permissions; its plaintext cookie/config artifacts are removed
when the command exits. Output is size-bounded and sanitized. The public broker
socket exposes Magnus status only. There are no write, remove, upload, create,
build, or deployment operations in the adapter or CLI.

The cookie is yielded only inside the broker and is never persisted by Rock
Lens. It is not exposed on the socket and there is no generic HTTP/URL
operation.

## Navigation, Personal Links, and Quick Returns

Search results and Personal Links cross the socket with process-local HMAC IDs.
Only the broker can resolve those IDs. Every search category maps to a fixed
Rock route: Person (`/Person/{Id}`), Group (`/Group/{Id}`), Workflow Type
configuration (`/admin/general/workflows?WorkflowTypeId={Id}`), Scheduled Job
detail (`/admin/system/jobs/{Id}`), Page (`/page/{Id}`), and Content Channel
Item (`/ContentChannelItem/{Id}`). Personal Link targets may be relative but
must resolve to HTTPS on the selected Rock origin; external and malformed
links are omitted.

Successful user-requested opens are added to Quick Returns. The store keeps the
title, type, order, target, and timestamp locally, but returns only another
process-local opaque ID, title, and type to QML. Its directory is `0700`, its
file is `0600`, writes are atomic, entries are validated on every read, and the
oldest entries are removed beyond 20. Each origin receives a separate store,
and Quick Returns are omitted from DEV responses. This intentionally emulates
Rock's useful return list without importing browser-local Rock history.
