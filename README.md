# Rock Lens

Rock Lens is an Omarchy 4.0.2+ launcher for Rock RMS discovery. Every
user signs in directly to their Rock instance through the native Python broker;
Magnus is not the login provider and neither the Magnus CLI nor Rock MCP is a
runtime dependency. The resulting `.ROCK` cookie is retained only in broker
memory with a 15-minute idle timeout and authenticates six fixed Rock REST v1
search resources plus the current person's Personal Links.

After login, Rock Lens probes the optional server-side Magnus API. Users whose
account and Rock instance expose it receive a separate **Magnus** tab for
filesystem-style browsing, bounded text preview, download, clipboard copy,
SHA-256 verification, same-origin viewing, and controlled mobile app builds.
Everyone else keeps the complete search, Personal Links, and Recent Links
experience without an error or empty core UI. Magnus item descriptors determine
which server actions exist. Only exact descriptor-provided mobile-app build
endpoints can be triggered, and every build requires an explicit production
confirmation. Write, upload, create, and delete remain disabled.

A compact Settings view supports multiple Rock instances or accounts,
connection testing, sign-out, profile removal, per-profile Recent Links,
category controls, person-context visibility, and close-after-open behavior
(enabled by default).
Search terms and opaque navigation or Magnus IDs travel over an owner-only local
Unix socket. Credentials, cookies, raw Rock record IDs, and raw server URLs do
not cross that boundary; only a user-requested bounded Magnus text preview is
returned to the panel.

Rock Lens also emulates Rock's Quick Return behavior as **Recent Links**. It
remembers only same-origin records or Personal Links that were opened from the
launcher, deduplicates them, caps the list at 20, and stores private target data
in an owner-only local file. It does not read or follow browser history.

![Rock Lens mock launcher](outputs/rock-lens-mvp.png)

## Install or run locally

```bash
python3 -m unittest discover -s tests -v
python3 -m rock_lens_broker --socket /tmp/rock-lens-demo.sock
```

The repository itself is a valid Omarchy plugin: its root `manifest.json`
points to the QML entry point and includes the Python broker. A published copy
can therefore be installed directly without Node.js, npm, Magnus CLI, or Rock
MCP:

```bash
omarchy plugin add https://github.com/OWNER/rock-lens-omarchy.git --enable
```

For a standalone broker command outside Omarchy, install the same dependency-free
Python package with `uv tool install .`.

The installed Omarchy integration uses `$XDG_RUNTIME_DIR/rock-lens/broker.sock`
and starts the broker without passing queries or credentials as arguments.
Summon it with `Super+R` or click the Rock bar indicator.

## Developer mode

Synthetic preview data remains available for UI development and privacy-safe
testing, but it is not exposed during normal use. The broker accepts DEV only
when its process starts with this exact flag:

```bash
ROCK_LENS_DEVELOPER_MODE=1 python3 -m rock_lens_broker
```

The installed shell must receive the same environment flag before it starts.
When enabled, the DEV/PROD badge and switch reappear. Without the flag, startup
forces PROD, rewrites a previously saved DEV context to PROD, hides the switch,
and rejects direct socket requests to enter DEV. Values such as `true` or `yes`
do not enable it.

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

Run the owner-local interactive setup for production:

```bash
python3 -m rock_lens_broker configure
```

Developer-mode OAuth metadata can still be configured with
`ROCK_LENS_DEVELOPER_MODE=1` and `--context DEV`.

Enter Rock's Public Application Root as the issuer, copy the client ID, accept
the loopback URI, and leave the secret blank for a public client. This OIDC
client remains available for future token-based capabilities. Current search,
links, and Magnus reads use the native per-profile Rock session login below and
do not require an administrator to register an OAuth client.

The client metadata file is owner-only at
`$XDG_CONFIG_HOME/rock-lens/oidc.json` (normally
`~/.config/rock-lens/oidc.json`). Client secrets and tokens are stored by the
desktop Secret Service. The launcher receives only `configured`, state, and a
fixed display label.

Rock profile names, strict origins, the active profile ID, and allowlisted
preferences are non-secret metadata stored owner-only at
`$XDG_CONFIG_HOME/rock-lens/profiles.json`. Usernames and passwords are never
stored there; Secret Service keys use stable random profile IDs, so two accounts
on the same Rock instance remain separate. Existing single-instance setup and
Recent Links migrate automatically, with the old history retained as rollback.
Successful mobile app builds are also added as **Magnus Build** Recent Links so
they can be re-triggered quickly; re-triggering always displays the production
confirmation again.

## Configure a Rock profile

Open **Settings** (or press `Ctrl+,`) and enter the Rock domain, username, and
password in the masked form. The broker first verifies the login directly at
the selected origin, then stores the credentials in Secret Service. The
equivalent terminal setup remains available:

```bash
python3 -m rock_lens_broker rock login
python3 -m rock_lens_broker rock status
```

The native login performs the fixed, bounded search and Personal Links reads.
It then probes Magnus independently. A successful probe enables the panel's
Magnus tab and the bounded `ls`, `cat`, and `hash` terminal operations. A 403 or
404 marks Magnus unavailable for only that profile; it never disables normal
Rock functionality. See [docs/MAGNUS.md](docs/MAGNUS.md) for the exact boundary.

**Sign out** clears the selected profile's password, username, and in-memory
cookie while keeping its profile metadata and local Recent Links. **Remove**
also deletes that profile's local metadata and Recent Links. Both actions
require a second click in the launcher and never modify the Rock server.

In the launcher, an empty **Search** view shows local **Recent Links**, with a
confirmed **Clear** action in the section header. Typing immediately replaces
them with search results. **Personal Links** has its own tab and is fetched only
when that tab is opened, so its Rock network read cannot delay Search or Recent
Links. **Open** is offered for every search category:
People, Groups, Workflow Types, Scheduled Jobs, Pages, and Content Channel
Items. Each target uses a fixed Rock route and must resolve to the exact
configured Rock origin; Personal Links have the same origin restriction.

Start a query with an entity prefix to search only that Rock category. A bare
prefix such as `g:` lists the first three items in that category.

| Category | Short prefix | Full aliases | Shortcut |
|---|---|---|---|
| People | `p:` | `person:`, `people:` | `Alt+P` |
| Groups | `g:` | `group:`, `groups:` | `Alt+G` |
| Workflow Types | `w:` or `wt:` | `workflow:`, `workflowtype:`, `workflowtypes:` | `Alt+W` |
| Jobs | `j:` | `job:`, `jobs:` | `Alt+J` |
| Pages | `pg:` | `page:`, `pages:` | `Alt+Shift+P` |
| Content Channel Items | `c:` | `content:`, `item:`, `items:` | `Alt+C` |

For example, `g: youth` calls only the Groups endpoint. Every scope also accepts
an exact Rock ID or GUID, such as `g: 42` or `p: a81b7c6d-1234-4abc-9876-0123456789ab`.
A GUID entered without a prefix is checked across all enabled categories. A bare
numeric ID is not searched across categories because Rock IDs overlap between
entity types; add the appropriate prefix instead. The active scope appears as a
badge beside the search field. `Esc` clears the scope before closing the panel,
and `Alt+0` clears it directly. Unknown prefixes remain ordinary search text;
no slash-command mode is required.

The search field keeps native editing behavior. Up and Down move through Recent
Links or results and across the Search/Personal Links boundary. Tab cycles the
search input, its displayed items, and Personal Links (Shift+Tab reverses), and
Enter or Space opens the selected live target. Backspace on a highlighted item
returns to the search field and deletes at the search cursor, so narrowing can
continue without an extra navigation step.

People results include compact duplicate-name context when Rock provides it:
age, conservatively identified spouse, family campus, and connection status.
Spouse is shown only for a married person with exactly one other active Adult
in the family group. Email, phone, address, and full birth date are not fetched.
Gated DEV never opens a target and does not display the PROD Recent Link
history.

## Safety guarantees

- Normal use is locked to PROD. DEV requires the exact process-level developer
  flag and remains visibly labeled while enabled.
- Native Rock login sends credentials only in a same-origin HTTPS request body,
  rejects redirects, validates the `.ROCK` cookie, and saves credentials only
  after a successful login. The optional OIDC implementation retains its S256
  PKCE and exact-origin protections.
- Passwords, client secrets, cookies, and access/refresh tokens never enter
  argv, repository files, logs, notifications, or screenshots.
- PROD never falls back to synthetic results. Without a configured Rock login
  the affected live category is empty; missing Magnus access affects only the
  Magnus tab.
- Live reads are fixed REST v1 GET operations with bounded responses and field-level
  output allowlists. QML cannot supply a URL, API path, OData field, or filter
  expression.
- Personal Links are read-only, restricted to same-origin HTTPS targets, and
  represented outside the broker by opaque IDs.
- Recent Links (the local Quick Return store) contain only launcher-opened
  targets and successfully triggered mobile app builds, are capped at 20, are
  visible only in PROD, and are stored under
  `$XDG_STATE_HOME/rock-lens` with owner-only permissions.
- Magnus mobile-app rows show the time of the last successful deployment that
  Rock Lens initiated for the active profile. Magnus does not provide a global
  deployment timestamp, so builds started elsewhere are not represented.
- There is no general mutation transport, SQL execution, job trigger, or Run
  Now UI. The sole server-side action is an explicitly confirmed mobile app
  build advertised by the selected Magnus descriptor.
- Magnus accepts only the configured HTTPS Rock origin, rejects cross-origin
  and traversal paths, uses the same authenticated Rock session, and does not
  expose write, upload, create, or delete operations.
- Broker errors are reduced to stable public codes. Response bodies, tokens,
  cookies, SQL, unselected PII, URLs, and exceptions are not logged or
  forwarded to QML.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[docs/VERIFICATION.md](docs/VERIFICATION.md).
