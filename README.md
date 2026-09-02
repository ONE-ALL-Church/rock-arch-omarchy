# Rock Lens

Rock Lens is a read-only Omarchy 4.0.2+ launcher for Rock RMS discovery. The
current search slice runs against public-safe mock data, and Rock login uses
Rock's OpenID Connect server. QML is only a view: search terms and sanitized
authentication state travel over an owner-only local Unix socket, while
credentials and tokens remain inside the Python broker and desktop keyring.

![Rock Lens mock launcher](outputs/rock-lens-mvp.png)

## Run the MVP

```bash
python3 -m unittest discover -s tests -v
python3 -m rock_lens_broker --socket /tmp/rock-lens-demo.sock
```

The installed Omarchy integration uses `$XDG_RUNTIME_DIR/rock-lens/broker.sock`
and starts the broker without passing queries or credentials as arguments.
Summon it with `Super+R` or click the explicit `DEV` / `PROD` bar indicator.

## Configure Rock login

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
the loopback URI, and leave the secret blank for a public client. Then open
Rock Lens and choose **Sign in**. The broker discovers Rock's endpoints, opens
Rock's sign-in/consent page, validates the callback state, exchanges the code,
and renews expiring sessions with the refresh token.

The client metadata file is owner-only at
`$XDG_CONFIG_HOME/rock-lens/oidc.json` (normally
`~/.config/rock-lens/oidc.json`). Client secrets and tokens are stored by the
desktop Secret Service. The launcher receives only `configured`, state, and a
fixed display label.

## Safety guarantees

- Context is stored explicitly as `DEV` or `PROD`; it is never inferred from a
  path, host name, URL, or response.
- Rock login uses authorization code flow, S256 PKCE, exact callback state
  validation, HTTPS discovery, and same-origin authorization/token endpoints.
- Client secrets and access/refresh tokens use Secret Service and never enter
  QML, argv, repository files, logs, notifications, or screenshots.
- Disconnect removes the context's local token set; it does not claim to end
  the user's browser-wide Rock session.
- The mock adapter remains the only enabled data adapter in this slice. Login
  establishes the identity boundary but does not silently enable live reads.
- Live adapters are capability-detected and fail closed.
- There is no mutation transport, SQL execution, job trigger, or Run Now UI.
- Broker errors are reduced to stable public codes. Response bodies, tokens,
  cookies, SQL, PII, and exceptions are not logged or forwarded to QML.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[docs/VERIFICATION.md](docs/VERIFICATION.md).
