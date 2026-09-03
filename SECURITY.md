# Security policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub's security
advisory interface for this repository. Do not include Rock credentials,
cookies, tenant records, or other production data in a report. A minimal local
reproduction using synthetic data is preferred.

## Supported boundary

Rock Lens is an owner-local Omarchy plugin. Its Unix socket and state files are
designed to protect against other local users, malformed server responses, and
untrusted paths or URLs returned by Rock or Magnus. The broker exposes fixed,
bounded operations and stable public errors; it does not provide a generic HTTP
or command-execution surface.

The plugin and broker run with the desktop user's authority. They do not claim
to isolate against arbitrary code already executing as that same user, a
compromised Quickshell process, a compromised Python runtime, or a malicious
Rock server that returns semantically deceptive but structurally valid display
text. Rock permissions remain the authorization boundary for tenant data and
the mobile-app build action.

## Secret handling

Rock profile usernames and passwords are stored in desktop Secret Service. The
Rock session cookie is held only in broker memory and expires after 15 idle
minutes. Secret values are passed to `secret-tool` through stdin, never argv.
Sign-out reports an error if Secret Service does not confirm deletion. The
removed experimental OAuth subsystem and its legacy records are not read.

Do not attach a live tenant or retrieve production credentials when testing a
security report. The unit suite uses synthetic stores, cookies, responses, and
local Unix sockets.
