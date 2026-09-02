# Architecture and privacy boundary

## Components

1. `plugin/oneall.rock-lens`: a thin Quickshell bar indicator and launcher.
2. `rock_lens_broker`: an allowlist-based local broker using an owner-only Unix
   socket (`0700` directory, `0600` socket).
3. `OAuthManager`: Rock OpenID Connect authorization-code login with S256 PKCE,
   a loopback callback, refresh-token renewal, and Secret Service persistence.
4. `MockAdapter`: deterministic, synthetic records for People, Groups,
   Workflows, Jobs, Pages, and Content Channel Items.
5. Future live adapters: disabled until tenant identity, authenticated actor,
   version, and read capability are proven. Their status is one of `unknown`,
   `stale`, `failed`, or `healthy`.

## Trust boundary

The QML side never receives credentials, cookies, SQL, raw private response
bodies, internal exception text, or fields outside the typed display contract.
Requests and responses are newline-delimited JSON with a 16 KiB request limit.
Search text is sent through the socket, not argv. The broker emits no request or
response logging.

Person Quick Look exposes only `displayName`, `subtitle`, `campus`, and a
synthetic `safeId`. No contact details, notes, addresses, dates of birth, family
relationships, photos, or authentication identifiers are in the contract.

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

## Live adapter gate

A live adapter may be enabled only after all gates pass: exact tenant,
authenticated actor, Rock version, access health, and read-only capability.
Any missing or ambiguous gate returns `unknown` or `failed`; there is no fallback
to unguarded REST, SQL, or credentials. Job history is read-only. Job execution
is intentionally absent at every layer.
