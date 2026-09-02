# Hardened Magnus boundary

Rock Lens uses the installed `rock-magnus-cli` only through
`MagnusReadOnlyAdapter`. The adapter is intentionally smaller than the raw CLI:

- the only allowed server is `https://rock.example.org`;
- HTTP, alternate hosts, URL credentials, queries, fragments, and cross-origin
  action URLs are rejected;
- tree paths must begin with
  `api/TriumphTech/Magnus/GetTreeItems/`;
- file paths must begin with `/FileContent/`;
- traversal, URL-shaped paths, control characters, and oversized responses are
  rejected;
- only `status`, `ls`, `cat`, and SHA-256 `hash` operations are exposed;
- Rock credentials are stored in Secret Service, never the Magnus plaintext
  configuration;
- each invocation creates an isolated mode-`0700` temporary configuration,
  hardens temporary files to `0600`, and destroys it afterward;
- raw stderr and Rock response bodies do not cross the adapter boundary.

Rock's `/api/Auth/Login` returns a tenant session cookie that may be accepted by
other same-origin Rock endpoints when the account is authorized. Rock Lens does
not treat that as permission to expose arbitrary REST calls: the cookie exists
only inside one ephemeral Magnus invocation and cannot be supplied with a raw
URL. General entity/API reads remain a separate, explicitly allowlisted V3/MCP
capability.

Configure credentials through a hidden local prompt:

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

Never use Magnus for Rock entity, relationship, REST, or SQL reads. Those
belong to the read-only Rock RMS MCP V3 surface.
