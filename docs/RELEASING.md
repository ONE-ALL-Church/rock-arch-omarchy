# Releasing Rock Lens

Omarchy installs this repository directly. A release therefore needs a valid
root manifest, a passing test suite, a fast-forwardable default branch, and a
matching annotated version tag. No generated package or external CLI bundle is
required.

## Prepare

1. Update the version in `rock_lens_broker/version.py`, `manifest.json`,
   `pyproject.toml`, and the Rock Lens footer in `RockLensSettingsPanel.qml`.
2. Add the user-visible changes to `CHANGELOG.md`.
3. Run the release checks:

   ```bash
   python3 -m unittest discover -s tests -v
   uvx --from ruff==0.16.5 ruff check rock_lens_broker tests
   uvx --from ty==0.0.78 ty check rock_lens_broker
   python3 -m compileall -q rock_lens_broker
   omarchy plugin validate .
   ```

4. Confirm the repository contains no tenant data or secrets before publishing.

The release-contract test deliberately fails when versions drift, the manifest
entry point disappears, or a second nested manifest is introduced.

## Publish

Push `main`, wait for GitHub Actions to pass, then create and push the matching
`v<version>` tag and GitHub release using the relevant changelog entry.

## Update an installation

Users with a Git-managed installation update from the default branch:

```bash
omarchy plugin update oneall.rock-lens
```

Omarchy uses a fast-forward-only merge, validates the result, and rolls back a
failed validation. The general `omarchy update` command does not update
third-party plugins.
