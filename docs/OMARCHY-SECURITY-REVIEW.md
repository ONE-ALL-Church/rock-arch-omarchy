# Omarchy security review intake — 2026-09-06

Source: [HANCORE-linux's marketplace review](https://github.com/omacom/omarchy-plugin-marketplace/issues/5075#issuecomment-5562310599),
posted September 6, 2026 at 21:30:53 UTC on submission #5075.
The issue remains open with `needs-fixes` and `security-review-required` labels.
Automated structural validation passed, but marketplace approval is pending.

The reviewer examined submission commit
`3f900909d0e5af2ebb3efe139adf99a69f6ab252` (runtime 0.26.0).
This intake compared the findings with development commit
`8b729bc55dc096b07a01b4c7ec10aa16f3d41b08`. All five cited source files are
unchanged between those commits: `updates.py`, `update_worker.py`,
`magnus_adapter.py`, `RockArchMagnusResponses.js`, and `RockArchMagnusPanel.qml`.

## Findings and disposition

| Item | Marketplace request | Local assessment | Status |
|---|---|---|---|
| Update revision changes between check and install | Carry the full checked commit SHA into the worker, install only that commit, and verify it before and after installation; otherwise remove self-update. | Confirmed missing revision binding; a mocked worker accepted a different installed commit. | Open blocker |
| Magnus preview lacks an explicit text format | Set `textFormat: TextEdit.PlainText` and verify literal markup without resource requests. | Missing declaration confirmed. Claimed HTML-triggered loading was not reproduced on installed Qt 6.11.2; the default was PlainText. | Open reviewer requirement; explicit hardening recommended |

The earlier `package-manager` baseline flag refers to the README's manual
dependency-installation example. It is separate from these two new findings;
the maintainer's comment does not report runtime system-package installation.

## Updater evidence

`UpdateManager._check_once()` fetches `origin HEAD`, resolves `FETCH_HEAD`, and
records the available revision. `start_update()` launches the worker without an
expected revision argument. The worker invokes Omarchy's mutable-HEAD updater,
restarts the shell, and then records whatever revision is installed as success.

The installed `omarchy-plugin-update` script also fetches `origin HEAD`, merges
`FETCH_HEAD`, validates, and rescans plugins. It accepts no commit-selection
argument. A post-install comparison alone is insufficient: the wrong revision
could already have been loaded by the rescan or shell restart.

An isolated test supplied checked revision A in temporary update state and
mocked the installed revision as B. The real `run_update()` logic returned zero
and wrote `state: updated` with B. Every subprocess, notification, and broker
termination was mocked. This confirms the missing equality check; it was not a
live remote-race or installation test.

Required follow-up:

- Validate and bind the complete checked SHA through the installation path.
- Ensure only that immutable target can enter the live checkout or be loaded.
- Verify the target before activation and after installation, retaining clean
  checkout, source, fast-forward, manifest, and failure-recovery checks.
- Test remote HEAD movement between check and install, and prove no alternate
  commit is installed or activated. Include manual and automatic update paths.
- If the supported Omarchy interface cannot preserve the immutable target,
  remove Rock Arch's installer path instead of treating a later comparison as
  sufficient protection.

## Magnus evidence

Remote preview content reaches a read-only `QQC.TextArea` through
`RockArchMagnusResponses.js`. The component does not set `textFormat`.
Qt documents that [TextArea inherits TextEdit](https://doc.qt.io/qt-6/qml-qtquick-controls-textarea.html),
whose [default text format is PlainText](https://doc.qt.io/qt-6/qml-qtquick-textedit.html#textFormat-prop).

An offscreen Qt 6.11.2 test used three independent TextArea instances and an
isolated loopback HTTP listener. Each received synthetic bold/image markup:

- Default mode was PlainText; selection retained the exact markup and made
  no image request.
- Explicit PlainText retained the markup and made no image request.
- AutoText was the positive control: it interpreted the markup and requested
  the test image, proving the listener detected resource loading.

All three behavioral checks passed, plus fixture setup/cleanup. The harness
tested the same Qt control and relevant properties, not the full installed
Magnus panel. It did not probe local-file reads. It therefore does not establish
an exploitable resource-loading path in the shipped panel.

Required follow-up: explicitly declare `TextEdit.PlainText` at the actual
Magnus preview boundary, add a regression check for literal markup and no
resource loads, and report both the hardening and the default-mode evidence to
the reviewer without claiming a reproduced exploit.

## Scope and handoff

This intake changes documentation only. No runtime fixes, production writes,
plugin updates, marketplace comments, or submission changes were made.
Installed automatic updates and CLI mutations were both off when checked.
That setting does not resolve the manual updater path or either review item.

Fix and verify the submitted release boundary before requesting re-review.
The current development branch contains additional unreleased features; any
submission that includes those features must disclose the expanded scope and
the exact new commit. Neither item is closed until its remediation evidence
has been reviewed.
