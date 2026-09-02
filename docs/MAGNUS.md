# Hardened Magnus boundary

Rock Lens uses the installed `rock-magnus-cli` only through
`MagnusReadOnlyAdapter`. The adapter is intentionally smaller than the raw CLI:

- setup requires the Rock instance domain before credentials;
- the domain is normalized to an HTTPS origin; HTTP, non-443 ports, URL
  credentials, paths, queries, fragments, and cross-origin action URLs are
  rejected;
- tree paths must begin with
  `api/TriumphTech/Magnus/GetTreeItems/`;
- file paths must begin with `/FileContent/`;
- traversal, URL-shaped paths, control characters, and oversized responses are
  rejected;
- only `status`, `ls`, `cat`, and SHA-256 `hash` operations are exposed;
- Rock credentials are stored in Secret Service under a stable random profile
  ID, so different instances and multiple accounts on one instance do not share
  credentials;
- each login creates an isolated mode-`0700` temporary configuration, hardens
  temporary files to `0600`, and destroys it afterward;
- the validated cookie may be reused from broker memory with a 15-minute idle
  timeout and is cleared on a timer, domain or credential change, authentication
  failure, or broker restart;
- raw stderr and Rock response bodies do not cross the adapter boundary.

Rock's `/api/Auth/Login` returns a tenant session cookie that may be accepted by
other same-origin Rock endpoints when the account is authorized. Rock Lens
validates the `.ROCK` value from the ephemeral Magnus profile and can yield it
in memory to the separate `RockRestReadOnlyAdapter`. It cannot be supplied with
a raw URL. The profile is destroyed immediately, while the validated cookie may
remain only in broker memory with a 15-minute idle timeout.

The REST adapter permits only fixed REST v1 GETs for People, Groups, Workflow
Types, Service Jobs, Pages, Content Channel Items, and current-user Personal
Links. It does not call `/api/v2`. Filters, selects, ordering, and row limits
are generated in code; QML supplies only a sanitized search string. Rock's own
controller/action and entity authorization still determine what the logged-in
account can see.

Magnus 0.1.0 reads its password prompt character by character. Rock Lens waits
for that prompt and writes one character at a time over stdin; the password is
never placed in argv. Cookie records are then selected by their exact
`serverUrl`, independent of the nested JSON layout produced by Magnus's `Conf`
dependency.

Configure credentials through the masked form in Rock Lens **Settings**.
The profile name and domain come first. The QML form clears its password
immediately after serializing the owner-local request, the broker stores the
origin in an owner-only configuration and both credentials in Secret Service,
and neither credential is returned over the socket. The equivalent hidden
terminal prompt is:

```bash
python3 -m rock_lens_broker magnus configure
```

Use bounded read-only operations:

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

`cat --output` creates a new owner-only file and refuses to overwrite an
existing path or follow its final symlink.

## Mutation and promotion policy

Rock Lens does not expose Magnus `write`, `build`, `rm`, `mkdir`, `touch`, or
`upload`. Production mutation therefore cannot happen through the broker or its
socket protocol.

When a future content task explicitly requires promotion, use the raw Magnus
CLI as a separate, reviewed operation:

1. Read the current production file and save a mode-`0600` rollback copy.
2. Hash the rollback copy and local candidate.
3. Write only to the identified QA/test target.
4. Read it back and verify the expected hash and markers.
5. Verify both Android MAUI and the iOS old shell.
6. Wait for explicit production-promotion approval.
7. Write production, read it back, and verify again.

Do not use the raw Magnus file commands for Rock entities, relationships, REST,
or SQL. Entity and Personal Link reads belong to the fixed read-only REST
adapter; broader API access still requires a separately reviewed allowlist.
