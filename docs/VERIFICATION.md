# Verification record

This record describes the current `0.15.0` release boundary. Historical feature
changes belong in [CHANGELOG.md](../CHANGELOG.md), not in this acceptance record.

## Automated checks

Run from the repository root:

```bash
python3 -m unittest discover -s tests -v
uvx --from ruff==0.16.5 ruff check rock_lens_broker tests
uvx --from ty==0.0.78 ty check rock_lens_broker
python3 -m compileall -q rock_lens_broker
omarchy plugin validate .
/usr/lib/qt6/bin/qmllint plugin/oneall.rock-arch/*.qml
git diff --check
```

The suite contains 121 passing tests. Release-contract coverage keeps
the manifest, package, network user-agent, and displayed version synchronized;
verifies the composed QML entry point and focused panel files; and prevents the
obsolete OpenID implementation or nested plugin manifest from returning.
Updater coverage verifies remote revision detection, manifest identity and
version validation, local-change refusal, fixed worker launch arguments, private
state permissions, broker routing, and the opt-in automatic-update preference.

GitHub Actions runs the unit tests, Ruff, ty, and bytecode compilation on every
push to `main` and on pull requests.

## Authentication boundary

- Rock Arch has one authentication path: a redirect-free HTTPS
  `POST /api/Auth/Login` to the selected, validated Rock origin.
- Only a bounded `.ROCK` cookie is accepted from `Set-Cookie`. It remains in
  broker memory and expires after 15 idle minutes.
- Profile usernames and passwords are stored by Secret Service. A subprocess
  contract test verifies that secret values are supplied to `secret-tool` only
  on stdin, never in argv.
- The experimental OpenID client, loopback callback server, bearer-token store,
  CLI configuration path, and broker operations are absent from the release.
  Legacy `auth_status`, `auth_login`, and `auth_disconnect` requests return
  `unsupported_operation`.
- Old user-owned `oidc.json` and keyring records are ignored and are not silently
  deleted during upgrade.

## Data and navigation boundary

- The QML process receives no credentials, cookies, raw Rock IDs, raw server
  URLs, response bodies, or exception text. A user-selected bounded Magnus text
  preview is the sole content exception.
- Search uses six fixed Rock REST v1 resources with fixed projections, bounded
  results, and exact-origin navigation targets. It exposes no generic HTTP,
  REST v2, SQL, mutation, job-run, or Run Now transport.
- Personal Links are same-origin and represented outside the broker by opaque
  IDs. Recent Links are owner-only, profile-scoped, deduplicated, and capped at
  20 entries.
- Person context is limited to age, conservatively inferred spouse, family
  campus, and connection status. Contact details, addresses, and full birth
  dates are not fetched.

## Magnus boundary

- Magnus is optional and reuses the native Rock session. A missing plugin or
  403/404 authorization response does not disable Search or links.
- Tree, file, view, and mobile-app build paths are validated against fixed
  same-origin prefixes and represented in QML by process-local opaque IDs.
- Previews, downloads, and tree responses are size-bounded. Cross-origin URLs,
  redirects, traversal, query strings, fragments, and control characters are
  rejected.
- Only a descriptor-advertised numeric mobile-app build endpoint can mutate the
  server, and every first or repeated build requires an explicit confirmation.
  No build is triggered by the automated suite.

## Update boundary

- Update checks run only for the exact Git-managed
  `oneall.rock-arch` installation and fetch the public remote without prompting
  for credentials.
- Remote metadata must contain the same plugin ID and a bounded semantic
  version. A non-fast-forward history or local tracked changes disables the
  install action and leaves the checkout untouched.
- Automatic installation is a persisted boolean preference that defaults to
  off. Manual and automatic installs both invoke Omarchy's fixed plugin updater,
  which performs its own fast-forward merge, validation, rollback, and rescan.
- The detached worker accepts only the canonical installed plugin directory and
  writes only owner-readable status. It never includes profile credentials,
  cookies, tenant data, or command output in its state or notifications.

## UI evidence

The README uses the current selection and deployment-confirmation UI:

- [`02-search-results.png`](../outputs/keyboard-audit/02-search-results.png)
  contains only deterministic DEV search data.
- [`05-magnus-confirmation.png`](../outputs/keyboard-audit/05-magnus-confirmation.png)
  shows the bounded `Test` confirmation and does not trigger a deployment.

Both images are cropped to the Rock Arch panel and contain no desktop, tenant,
credential, or live record data. See [KEYBOARD-AUDIT.md](KEYBOARD-AUDIT.md) for
the interaction coverage represented by these captures.

## Local acceptance

- Target shell: Omarchy 4.0.2 or newer.
- The root repository passes Omarchy plugin validation and contains no Rock MCP,
  Magnus CLI, Node.js, npm, pip, or uv runtime dependency.
- Standalone `qmllint` may report expected unresolved Omarchy import warnings;
  it must report no QML syntax error.
- `hyprctl reload` must succeed and `hyprctl configerrors` must be empty after
  updating the installed plugin.
- Full OS logout/login and a live Magnus deployment are intentionally outside
  this release check.

No telemetry, live search, profile change, credential change, file mutation,
or production build is performed by these verification steps.
