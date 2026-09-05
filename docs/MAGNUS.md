# Optional native Magnus boundary

Rock Arch talks to the server-side TriumphTech Magnus API directly. The Node
`rock-magnus-cli` package is not launched or otherwise required.
Magnus is also not used for authentication: every configured profile first
logs in through Rock's same-origin `/api/Auth/Login` endpoint.

After a successful Rock login, the broker probes only:

```text
/api/TriumphTech/Magnus/GetServer
```

A valid descriptor marks Magnus available for that profile. HTTP 403 or 404
means the plugin is missing or the signed-in account is not authorized; Rock
search, Personal Links, and Recent Links continue normally. A transient network
failure is reported as a capability-check error and can be retried by reopening
the panel or testing the profile connection.

## Controlled functionality

Authorized profiles receive a **Magnus** tab with:

- descriptor-driven folder browsing;
- explicit UTF-8 text preview capped at 64 KiB;
- bounded downloads saved without overwrite and with mode `0600`;
- content and SHA-256 clipboard copy through stdin, never argv;
- SHA-256 for every selected file, including binary files;
- same-origin **Open in Rock** when the descriptor advertises a view URI;
- explicit, confirmed mobile app builds;
- same-origin validation for tree, content, and advertised action URIs.

Magnus remains a drill-down tree rather than a combined file dashboard. The
root returns content families such as Websites, Mobile Applications, Lava
Shortcodes, Lava Applications, server files, and supported application types.
Rock Arch follows each descriptor URI into its children. Mobile-app build
capability is advertised on an application row in the parent Mobile
Applications listing; it is not copied onto the app's child folders or files.

The agent-friendly terminal interface uses the running broker and opaque IDs:

```bash
rock-arch magnus status
rock-arch magnus browse
rock-arch magnus browse SAFE_FOLDER_ID
rock-arch magnus preview SAFE_FILE_ID
rock-arch magnus hash SAFE_FILE_ID
rock-arch magnus download SAFE_FILE_ID --confirm
rock-arch magnus build SAFE_APP_ID --confirm
rock-arch magnus builds
rock-arch magnus build-status BUILD_ID
```

The legacy path-oriented `python3 -m rock_arch_broker magnus ls|cat|hash`
commands are retired. They exit with migration guidance without opening a
session, reading a server path, or writing an output file. Start with
`rock-arch magnus browse`, then use the returned opaque IDs with `preview`,
`hash`, or `download --confirm` as shown above.

The legacy `rock status`, `rock login`, `magnus status`, and `magnus configure`
module commands remain deprecated aliases for the corresponding `rock-arch`
status or login commands. They use the broker's active profile, login and access
checks, JSON output, and exit status.

Tree paths must begin with
`api/TriumphTech/Magnus/GetTreeItems/`. Content paths must begin with
`/FileContent/`; the full `/api/TriumphTech/Magnus/FileContent/` form is safely
normalized. Alternate origins, redirects, URL credentials, queries, fragments,
backslashes, control characters, and traversal segments are rejected. Path
validation repeatedly percent-decodes before checking boundaries, so `%2e%2e`
and multiply encoded traversal cannot bypass the allowlist. The HTTP client
also rejects every route outside the fixed probe, tree, file-content, and
numeric mobile-app build families before opening a connection. Tree responses
are capped at 2 MiB/500 items and content reads at 4 MiB.

QML never receives these paths. The broker registers each folder and file under
a process-local HMAC identifier. The broker retains a build URI only when it is
same-origin and exactly matches
`/api/TriumphTech/Magnus/Build/mobileapps/{numeric-id}`. Delete, upload, new-file,
new-folder, and broader build URIs are discarded. Magnus uses the generic
descriptor `Uri` for both folders and files, so the broker validates it as a
tree path or content path according to the descriptor's `IsFolder` value.

## Authentication and migration

Profile credentials live in desktop Secret Service under the stable random
profile ID. New credentials are verified before replacing a saved login. The
validated `.ROCK` cookie is never written by Rock Arch and remains only in
broker memory with a sliding 15-minute idle timeout.

Version 0.10 migrates profile-scoped `magnus_username` and `magnus_password`
records written by earlier releases to neutral `rock_username` and
`rock_password` keys, then removes the obsolete records. Sign-out clears both
new and legacy keys as well as the in-memory cookie. If Secret Service does not
confirm deletion, Rock Arch clears the memory cookie but reports failure rather
than presenting the profile as safely signed out.

## Build and promotion policy

Version 0.11 exposes the Magnus CLI-compatible `POST` build action only for a
descriptor-provided mobile app URI. The first run and every Recent Link rerun
require an inline production confirmation. A build request accepted by Magnus
is stored as a profile-scoped **Magnus Build** Recent Link without exposing the
URI to QML.
Rock Arch does not retry a timed-out build because the server may already have
accepted it.

The Magnus mobile-app descriptor and action response do not provide a
dependable completion-status endpoint or deployment timestamp. Rock Arch
therefore records a separate owner-only receipt when Magnus accepts a request,
shows **Last started**, and sends a local “accepted” notification. Each receipt
has an opaque build ID, state `accepted`, `statusSource: local`, and
`completionVerifiable: false`; it never claims that deployment finished.
Recent times use compact labels such as `5 minutes ago`; older times show a
local date and time. Build receipts remain available independently of Recent
Links, while builds started outside Rock Arch cannot be inferred.

For keyboard deployment, open Magnus, select a mobile app with Up/Down, press
`B`, and press `Enter` to confirm. The confirmation's Deploy button receives
keyboard focus automatically; `Esc` cancels and returns focus to the selected
mobile app before any request is sent. Recent Link reruns behave the same way.

Magnus `write`, `rm`, `mkdir`, `touch`, and `upload` remain unavailable through
QML, the broker socket, and the Python adapter. A future authoring workspace
must add, in order:

1. a mode-`0600` rollback copy and before/after hash;
2. a local diff and explicit confirmation;
3. QA/test deployment before production;
4. read-back verification;
5. Android MAUI and iOS old-shell rendering checks where mobile content is
   involved;
6. a separate production-promotion approval.

Rock entity, relationship, REST, and SQL operations are not Magnus file
operations and must remain behind their own reviewed allowlists.
