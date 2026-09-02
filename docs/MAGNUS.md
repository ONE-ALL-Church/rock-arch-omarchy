# Optional native Magnus boundary

Rock Lens talks to the server-side TriumphTech Magnus API directly. The Node
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

## Read-only functionality

Authorized profiles receive a **Magnus** tab with:

- descriptor-driven folder browsing;
- explicit UTF-8 text preview capped at 64 KiB;
- SHA-256 for every preview;
- same-origin validation for tree, content, and advertised action URIs.

The terminal interface uses the same native adapter:

```bash
python3 -m rock_lens_broker magnus status
python3 -m rock_lens_broker magnus ls
python3 -m rock_lens_broker magnus ls \
  api/TriumphTech/Magnus/GetTreeItems/mobileapps/app/14
python3 -m rock_lens_broker magnus cat \
  /FileContent/block-handler/5350/content.lava
python3 -m rock_lens_broker magnus hash \
  /FileContent/block-handler/5350/content.lava
```

Tree paths must begin with
`api/TriumphTech/Magnus/GetTreeItems/`. Content paths must begin with
`/FileContent/`; the full `/api/TriumphTech/Magnus/FileContent/` form is safely
normalized. Alternate origins, redirects, URL credentials, queries, fragments,
backslashes, control characters, and traversal segments are rejected. Tree
responses are capped at 2 MiB/500 items and content reads at 4 MiB.

QML never receives these paths. The broker registers each folder and file under
a process-local HMAC identifier. Item descriptors may advertise `build`,
`delete`, `upload`, `newFile`, or `newFolder`; Rock Lens emits only the validated
action name as informational UI and discards the URI.

## Authentication and migration

Profile credentials live in desktop Secret Service under the stable random
profile ID. New credentials are verified before replacing a saved login. The
validated `.ROCK` cookie is never written by Rock Lens and remains only in
broker memory with a sliding 15-minute idle timeout.

Version 0.10 migrates profile-scoped `magnus_username` and `magnus_password`
records written by earlier releases to neutral `rock_username` and
`rock_password` keys, then removes the obsolete records. Sign-out clears both
new and legacy keys as well as the in-memory cookie.

## Mutation and promotion policy

This release does not expose Magnus `write`, `build`, `rm`, `mkdir`, `touch`, or
`upload` through QML, the broker socket, or its Python adapter. A future authoring
workspace must preserve the descriptor-derived URI internally and add, in
order:

1. a mode-`0600` rollback copy and before/after hash;
2. a local diff and explicit confirmation;
3. QA/test deployment before production;
4. read-back verification;
5. Android MAUI and iOS old-shell rendering checks where mobile content is
   involved;
6. a separate production-promotion approval.

Rock entity, relationship, REST, and SQL operations are not Magnus file
operations and must remain behind their own reviewed allowlists.
