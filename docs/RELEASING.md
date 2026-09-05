# Releasing Rock Arch

Omarchy installs this repository directly. A release therefore needs a valid
root manifest, a passing test suite, a fast-forwardable default branch, and a
matching annotated version tag. No generated package or external CLI bundle is
required.

## Prepare

1. Update the version in `rock_arch_broker/version.py`, `manifest.json`,
   `pyproject.toml`, and `currentVersion` in `RockArch.qml` (Settings uses that
   controller value).
2. Add the user-visible changes to `CHANGELOG.md`.
3. Run the release checks:

   ```bash
   python3 -m unittest discover -s tests -v
   scripts/check-qml
   uvx --from ruff==0.16.5 ruff check rock_arch_broker tests
   uvx --from ty==0.0.78 ty check rock_arch_broker
   python3 -m compileall -q rock_arch_broker
   omarchy plugin validate .
   ```

4. Confirm the repository contains no tenant data or secrets before publishing.
5. Test a fresh plugin installation on Omarchy: open it from the icon and shell
   command, close with Escape, configure and test an optional shortcut, disable,
   re-enable, restart the shell, and remove using the README instructions.
   The automated distribution test covers an isolated launcher, broker startup,
   restart, and file cleanup; it does not replace this interactive shell check.

The release-contract test deliberately fails when versions drift, the manifest
entry point disappears, or a second nested manifest is introduced.

## Publish

Push `main`, wait for GitHub Actions to pass, then create and push the matching
`v<version>` tag and GitHub release using the relevant changelog entry.

For the first Omarchy Marketplace listing, follow the
[publishing guide](https://plugins.omarchy.org/publish.html) and open the
[submission form](https://github.com/omacom/omarchy-plugin-marketplace/issues/new?template=submit-plugin.yml).
Use category **Productivity** and tags **Bar**, **Launcher**, **Quickshell**.
Include the full commit SHA and explain the Python broker, Secret Service login,
optional confirmed Magnus builds, and opt-in self-updates in maintainer notes.
Check for an existing submission before creating another one. The marketplace
scans the exact commit and requires maintainer approval; a GitHub release alone
does not list the plugin. Keep the submitted commit stable while it is reviewed.

## Update an installation

Users with a Git-managed installation update from the default branch:

```bash
omarchy plugin update oneall.rock-arch
```

Omarchy uses a fast-forward-only merge, validates the result, and rolls back a
failed validation. The general `omarchy update` command does not update
third-party plugins.
