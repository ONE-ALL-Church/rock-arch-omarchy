# Release security audit — 0.26.0

Audited on 2026-09-05 before release. This is a source review with synthetic
regression tests and local release checks, not a penetration test of a Rock
server or an independent certification.

## Scope

Reviewed the broker socket and request routing, credential input and Secret
Service storage, redirect-free HTTP clients, same-origin navigation and Magnus
routes, downloads, update consent and execution, shortcut configuration writes,
CLI settings, QML display boundaries, and the release workflow. Tests did not
retrieve production credentials or execute a Magnus build.

The desktop Unix account remains the trust boundary. Arbitrary code already
running as that user has the same desktop authority; terminal-access preferences
are not an isolation mechanism against such code.

## Fixed findings

| Finding | Effect before the fix | Resolution |
|---|---|---|
| Exhausted download filenames | If all 1,000 candidate filenames existed, failure cleanup could delete the last existing file. | Cleanup runs only after this attempt successfully creates its own file. Tests preserve all existing files and remove only a newly created partial download. |
| Stale automatic-update consent | A background check retained permission to install even after automatic updates were switched off. | Checks only discover updates; installation uses a subsequent request with the current saved preference. |
| Malformed JSON numbers | Huge integer literals or non-finite values could escape expected error handling. | Shared strict decoding rejects them and returns stable errors; malformed broker input leaves the connection usable. Local store parsers also handle integer-limit errors. |
| Malformed HTTP and navigation data | Invalid status lines or URL authorities could raise raw exceptions instead of a controlled failure. | HTTP protocol errors and URL parser failures are normalized; IPv6 navigation retains brackets. Cookie headers reject non-ASCII and DEL characters. |
| Unfinished update checks | Undecodable Git output could leave the background check in `checking`. | Encoding failures finish with `update_check_failed`; version strings are limited to 64 characters. |
| Missing private reporting channel | SECURITY.md pointed to GitHub reporting while it was disabled. | Private vulnerability reporting is enabled and SECURITY.md links the form. |

## Verification

- 232 Python tests and 35 Qt behavioral tests pass (43 Qt cases including setup
  and cleanup). Ten security regression tests cover the principal failure paths.
- Ruff, ty, bytecode compilation, Omarchy manifest validation, and whitespace
  checks pass. QML lint exits zero with no syntax errors (standalone Omarchy
  import warnings remain expected).
- Fresh plugin installation, bar click, shell open/close, Escape, real shortcut
  Add/Change/Remove, Super+R activation, disable/re-enable, shell restart, and
  removal passed on Omarchy 4.0.2. Existing user data and configuration were
  restored afterward.
- Gitleaks found no secrets in the working directory or the 69 existing commits.
- Bandit reported one medium-severity permission heuristic for the CLI launcher's
  `0755` mode. This is intentional: the launcher contains a fixed module import
  and source path, no secrets, and is writable only by its owner. Socket and
  private-data permissions are checked separately. No high-severity finding was
  reported.

The review found no remaining confirmed vulnerability in its scope. See
[VERIFICATION.md](VERIFICATION.md) for native desktop acceptance and limitations.
