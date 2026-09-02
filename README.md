# Rock Lens

Rock Lens is a read-only Omarchy 4.0.2+ launcher for Rock RMS discovery. DEV
uses public-safe synthetic data. PROD uses the `.ROCK` session created by
Magnus to search six fixed Rock REST v1 resources and load the current person's
Personal Links. Group results include their Rock Group Type. The six category
reads run concurrently, and a brief memory-only Magnus session cache keeps
successive searches responsive without persisting the cookie. QML is only a
view: search terms and opaque navigation IDs
travel over an owner-only local Unix socket, while credentials, cookies, raw
record IDs, URLs, and response bodies remain inside the Python broker.

For privileged Rock file inspection, Rock Lens also includes a hardened,
read-only Magnus adapter. Setup first records the selected Rock instance's
strict HTTPS origin, keeps that origin's credentials in Secret Service, and
gives each command an ephemeral Magnus profile that is deleted immediately
afterward.

Rock Lens also emulates Rock's Quick Return behavior. It remembers only
same-origin records or Personal Links that were opened from the launcher,
deduplicates them, caps the list at 20, and stores private target data in an
owner-only local file. It does not read or follow browser history.

![Rock Lens mock launcher](outputs/rock-lens-mvp.png)

## Run the MVP

```bash
python3 -m unittest discover -s tests -v
python3 -m rock_lens_broker --socket /tmp/rock-lens-demo.sock
```

The installed Omarchy integration uses `$XDG_RUNTIME_DIR/rock-lens/broker.sock`
and starts the broker without passing queries or credentials as arguments.
Summon it with `Super+R` or click the explicit `DEV` / `PROD` bar indicator.

## Optional OpenID Connect client

In Rock, create a dedicated client under `Admin Tools > Settings > OpenID
Connect Clients`. Register this exact loopback redirect URI:

```text
http://127.0.0.1:41397/oauth/callback
```

Allow the minimum scopes Rock Lens requests: `openid` and `offline_access`.
Rock's current source supports a public client with no secret and requires S256
PKCE for that client type. For an installed version or confidential client that
requires a secret, generate one; Rock Lens stores it in Secret Service, never
in the repository or command line.

These settings follow Rock's official [OpenID Connect
documentation](https://community.rockrms.com/documentation/BookContent/9#openid-connect)
and the [current Rock authorization-provider
source](https://github.com/SparkDevNetwork/Rock/blob/f0917ef9799aa433d8be7b648666ecd5239550b1/Rock.Oidc/Authorization/AuthorizationProvider.cs).

Run the owner-local interactive setup separately for each configured context:

```bash
python3 -m rock_lens_broker configure --context DEV
python3 -m rock_lens_broker configure --context PROD
```

Enter Rock's Public Application Root as the issuer, copy the client ID, accept
the loopback URI, and leave the secret blank for a public client. The broker
includes this standards-based end-user login boundary, but the current live
search and Personal Links path does not use it. Those reads use the ephemeral
local Magnus session described below. The OpenID client remains available for
future user-facing capabilities that should not use an admin cookie.

The client metadata file is owner-only at
`$XDG_CONFIG_HOME/rock-lens/oidc.json` (normally
`~/.config/rock-lens/oidc.json`). Client secrets and tokens are stored by the
desktop Secret Service. The launcher receives only `configured`, state, and a
fixed display label.

The selected Rock origin is non-secret metadata stored owner-only at
`$XDG_CONFIG_HOME/rock-lens/instance.json`. Usernames and passwords are not
stored there; Secret Service keys are separated by a hash of that origin.

## Configure Magnus

Magnus is deliberately separate from end-user OpenID Connect login. In Rock
Lens, switch to **PROD** and enter the Rock credentials in the displayed masked
form. The broker sends them only over its owner-only socket and
stores them in Secret Service. The equivalent terminal setup remains available:

```bash
python3 -m rock_lens_broker magnus configure
python3 -m rock_lens_broker magnus status
```

The same ephemeral session can then perform the fixed, bounded search and
Personal Links reads. Its temporary profile is removed immediately; only the
validated cookie is retained in broker memory with a 15-minute idle timeout.
The adapter still exposes only bounded `ls`, `cat`, and
`hash` file operations; it does not expose a generic REST client. See
[docs/MAGNUS.md](docs/MAGNUS.md) for its exact restrictions.

In the launcher, PROD search starts only after at least one character is typed.
The **Links** tab loads Personal Links and local Quick Returns. **Open** is
offered for every search category: People, Groups, Workflow Types, Scheduled
Jobs, Pages, and Content Channel Items. Each target uses a fixed Rock route and
must resolve to the exact configured Rock origin; Personal Links have the same
origin restriction. Personal Links are fetched only when the Links tab is
opened, so they cannot delay the initial Search view.

Start a query with an entity prefix to search only that Rock category. A bare
prefix such as `g:` lists the first three items in that category.

| Category | Short prefix | Full aliases | Shortcut |
|---|---|---|---|
| People | `p:` | `person:`, `people:` | `Alt+P` |
| Groups | `g:` | `group:`, `groups:` | `Alt+G` |
| Workflows | `w:` | `workflow:`, `workflows:` | `Alt+W` |
| Jobs | `j:` | `job:`, `jobs:` | `Alt+J` |
| Pages | `pg:` | `page:`, `pages:` | `Alt+Shift+P` |
| Content Channel Items | `c:` | `content:`, `item:`, `items:` | `Alt+C` |

For example, `g: youth` calls only the Groups endpoint. The active scope appears
as a badge beside the search field. `Esc` clears the scope before closing the
panel, and `Alt+0` clears it directly. Unknown prefixes remain ordinary search
text; no slash-command mode is required.

The search field keeps native editing behavior. Up and Down move through results
and across the Search/Links boundary, Tab cycles search input, results, and
links (Shift+Tab reverses), and Enter or Space opens the selected live target.
Backspace on a highlighted item returns to the search field and deletes at the
search cursor, so narrowing can continue without an extra navigation step.

People results include compact duplicate-name context when Rock provides it:
age, conservatively identified spouse, family campus, and connection status.
Spouse is shown only for a married person with exactly one other active Adult
in the family group. Email, phone, address, and full birth date are not fetched.
DEV never opens a target and does not display the PROD Quick Return history.

## Safety guarantees

- Context is stored explicitly as `DEV` or `PROD`; it is never inferred from a
  path, host name, URL, or response.
- Rock login uses authorization code flow, S256 PKCE, exact callback state
  validation, HTTPS discovery, and same-origin authorization/token endpoints.
- Client secrets and access/refresh tokens use Secret Service and never enter
  QML, argv, repository files, logs, notifications, or screenshots.
- Disconnect removes the context's local token set; it does not claim to end
  the user's browser-wide Rock session.
- PROD never falls back to synthetic results. Without configured Magnus
  credentials or with a failed endpoint, the affected live category is empty.
- Live reads are fixed REST v1 GET operations with bounded responses and field-level
  output allowlists. QML cannot supply a URL, API path, OData field, or filter
  expression.
- Personal Links are read-only, restricted to same-origin HTTPS targets, and
  represented outside the broker by opaque IDs.
- Quick Returns contain only launcher-opened targets, are capped at 20, are
  visible only in PROD, and are stored under `$XDG_STATE_HOME/rock-lens` with
  owner-only permissions.
- There is no mutation transport, SQL execution, job trigger, or Run Now UI.
- Magnus accepts only the configured HTTPS Rock origin, rejects cross-origin
  and traversal paths, uses per-origin Secret Service records, and exposes no
  mutation operation.
- Broker errors are reduced to stable public codes. Response bodies, tokens,
  cookies, SQL, unselected PII, URLs, and exceptions are not logged or
  forwarded to QML.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[docs/VERIFICATION.md](docs/VERIFICATION.md).
