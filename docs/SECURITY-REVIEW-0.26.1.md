# Marketplace security review follow-up — 0.26.1

Prepared on 2026-09-06 in response to the
[Omarchy marketplace review](https://github.com/omacom/omarchy-plugin-marketplace/issues/5075#issuecomment-5562310599)
of commit `3f900909d0e5af2ebb3efe139adf99a69f6ab252`. This patch addresses both
findings on the submitted release; unreleased development features are excluded.
Marketplace approval remains a separate maintainer decision.

## Checked update revision

The previous worker invoked Omarchy's updater, which fetched remote HEAD again.
The commit installed could therefore differ from the commit checked by Rock Arch.

`UpdateManager` now resolves and validates a full 40-character commit ID and uses
that ID for history and manifest checks. Both manual and automatic paths pass
it unchanged as the worker's required `--expected-revision` argument.

The worker accepts only the canonical installed checkout and origin. With a
private advisory lock held, it creates an exact-commit temporary worktree and
uses the fixed Omarchy static validator there before changing the live install.
It rechecks the current checkout, then fast-forwards to the immutable ID with
Git hooks disabled and ignored-file overwrites refused. It verifies the installed
ID, clean state, and plugin validation before requesting a shell restart, and
checks the ID again before reporting success. It does not fetch, follow
FETCH_HEAD, or invoke Omarchy's mutable-target plugin updater.

Invalid targets, diverged history, local changes, validation failures, concurrent
workers, or revision mismatches return errors. Candidate validation failure
leaves the installed checkout intact. A later concurrent modification is preserved
and reported; the worker does not force a rollback over someone else's changes.
A failed shell restart reports an error even when the checked commit is installed.

Regression evidence in `tests/test_update_worker.py` uses real local Git repos:
check commit B, advance remote HEAD and local FETCH_HEAD to C, then install through
both manual and automatic paths. The installed checkout, activation spy, and
success state all identify only B. Other cases cover malformed/missing targets,
foreign origins, tracked/untracked changes, ignored-file collisions, divergence,
failed validation, concurrent edits and workers, restart failure, and a forced
post-install identity mismatch. `tests/test_updates.py` checks argument pinning
and refusal to launch with an invalid checked revision.

## Magnus literal text

The Magnus preview now explicitly sets `textFormat: TextEdit.PlainText` and uses
the small production `RockArchPlainTextArea` control, which also declares that
boundary. Remote file text remains read-only, selectable, and unwrapped.

`tests/test_magnus_text.py` instantiates that production control under Qt with
HTML containing HTTP and local-file image URLs. It verifies that selection returns
the complete literal markup. A loopback HTTP server and Linux inotify watches on
harmless temporary images detect no resource requests from the plain-text control.
An independent AutoText control loads its own HTTP and local image fixtures,
proving both observers work.

Qt documents PlainText as TextEdit's default, and the original implicit-default
preview did not reproduce resource loading on the local Qt 6.11.2 environment.
The explicit mode removes dependence on that default and is now protected by a
resource-loading regression test; this is not a claim that the original exploit
was reproduced on every supported Qt version.

## Verification and limits

- 242 Python tests pass, including the real Git race and Qt resource-boundary
  tests. The separate Qt suite passes 43 cases (35 behavioral tests plus setup
  and cleanup).
- Ruff, ty, bytecode compilation, Omarchy manifest validation, whitespace checks,
  and a redacted Gitleaks working-directory scan pass. Standalone QML lint exits
  zero; unresolved Omarchy imports produce the existing standalone warnings.
- A supplementary local run repeats both real Git race paths with the actual
  Omarchy static validator: all four candidate/live validations pass. Shell
  activation is observed through a test spy, not performed by that fixture.
- Tests use synthetic data. They do not retrieve production credentials, trigger
  Magnus builds, or claim a new independent audit of the complete application.
  The prior desktop lifecycle evidence remains in `VERIFICATION.md`.

The desktop Unix account remains the trust boundary. Git commit pinning prevents
a changed remote target from replacing the selected commit; it does not certify
that a selected commit is trustworthy or prevent another same-user process from
modifying files outside the updater's control.
