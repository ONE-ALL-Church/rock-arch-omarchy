import json
import subprocess
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from rock_lens_broker.updates import (
    CANONICAL_REPOSITORY_URLS,
    PLUGIN_ID,
    PYTHON,
    UpdateError,
    UpdateManager,
    write_update_state,
)


class FakeGit:
    def __init__(
        self,
        *,
        dirty=False,
        current="a" * 40,
        available="b" * 40,
        remote="https://github.com/ONE-ALL-Church/rock-arch-omarchy.git",
    ):
        self.dirty = dirty
        self.current = current
        self.available = available
        self.remote = remote
        self.commands = []

    def __call__(self, command, timeout):
        self.commands.append((command, timeout))
        arguments = command[3:]
        if arguments == ["remote", "get-url", "origin"]:
            return self._result(command, self.remote + "\n")
        if arguments[:2] == ["status", "--porcelain"]:
            return self._result(command, "tracked change\n" if self.dirty else "")
        if arguments == ["rev-parse", "HEAD"]:
            return self._result(command, self.current + "\n")
        if arguments == ["fetch", "--quiet", "origin", "HEAD"]:
            return self._result(command)
        if arguments == ["rev-parse", "FETCH_HEAD"]:
            return self._result(command, self.available + "\n")
        if arguments == ["merge-base", "--is-ancestor", "HEAD", "FETCH_HEAD"]:
            return self._result(command)
        if arguments == ["show", "FETCH_HEAD:manifest.json"]:
            return self._result(
                command,
                json.dumps({"id": PLUGIN_ID, "version": "0.16.0"}),
            )
        raise AssertionError(f"unexpected command: {command}")

    @staticmethod
    def _result(command, stdout="", returncode=0):
        return subprocess.CompletedProcess(command, returncode, stdout, "")


class UpdateManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "plugin"
        self.root.mkdir()
        self.state_file = Path(self.temporary.name) / "state" / "updates.json"
        self.now = datetime(2026, 9, 2, 12, 30, tzinfo=UTC)

    def tearDown(self):
        self.temporary.cleanup()

    def manager(self, git, launcher=None):
        manager = UpdateManager(
            self.state_file,
            plugin_root=self.root,
            installed_root=self.root,
            command_runner=git,
            process_launcher=launcher,
            clock=lambda: self.now,
        )
        manager._managed = True
        return manager

    def test_available_revision_reports_remote_version(self):
        manager = self.manager(FakeGit())
        state = manager._check_once()

        self.assertEqual(state["state"], "available")
        self.assertEqual(state["availableVersion"], "0.16.0")
        self.assertTrue(state["updateAvailable"])
        self.assertEqual(state["lastCheckedAt"], "2026-09-02T12:30:00Z")

    def test_only_canonical_origin_can_check_or_install_updates(self):
        git = FakeGit(remote="https://attacker.example/rock-arch.git")
        manager = self.manager(git)

        with self.assertRaisesRegex(UpdateError, "update_source_not_allowed"):
            manager._check_once()

        manager._state.update(state="available", updateAvailable=True)
        with self.assertRaisesRegex(UpdateError, "update_source_not_allowed"):
            manager.start_update()
        self.assertEqual(manager._state["error"], "update_source_not_allowed")
        self.assertFalse(
            any("fetch" in command for command, _timeout in git.commands)
        )

        self.assertIn(
            "git@github.com:ONE-ALL-Church/rock-arch-omarchy.git",
            CANONICAL_REPOSITORY_URLS,
        )

    def test_current_revision_is_up_to_date_without_reading_remote_manifest(self):
        revision = "a" * 40
        git = FakeGit(current=revision, available=revision)
        state = self.manager(git)._check_once()

        self.assertEqual(state["state"], "current")
        self.assertFalse(state["updateAvailable"])
        self.assertFalse(any(command[-2:] == ["show", "FETCH_HEAD:manifest.json"] for command, _ in git.commands))

    def test_local_tracked_changes_block_check_and_install(self):
        manager = self.manager(FakeGit(dirty=True))
        checked = manager._check_once()
        self.assertEqual(checked["state"], "modified")
        self.assertEqual(checked["error"], "local_changes_prevent_update")

        manager._state.update(state="available", updateAvailable=True)
        with self.assertRaisesRegex(UpdateError, "local_changes_prevent_update"):
            manager.start_update()

    def test_start_update_launches_fixed_detached_worker_and_writes_private_state(self):
        launched = []

        def launcher(command, working_directory):
            launched.append((command, working_directory))

        manager = self.manager(FakeGit(), launcher)
        manager._state.update(state="available", updateAvailable=True)
        status = manager.start_update()

        self.assertEqual(status["state"], "updating")
        self.assertEqual(len(launched), 1)
        command, working_directory = launched[0]
        self.assertEqual(command[:3], [str(PYTHON), "-m", "rock_lens_broker.update_worker"])
        self.assertEqual(working_directory, self.root)
        self.assertEqual(self.state_file.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.state_file.parent.stat().st_mode & 0o777, 0o700)

    def test_state_loader_rejects_permissive_file(self):
        write_update_state(
            self.state_file,
            {
                "state": "available",
                "availableVersion": "9.9.9",
                "currentRevision": "a" * 40,
                "availableRevision": "b" * 40,
                "lastCheckedAt": "2026-09-02T12:30:00Z",
                "lastUpdatedAt": "",
                "operationStartedAt": "",
                "updateAvailable": True,
                "error": "",
            },
        )
        self.state_file.chmod(0o644)
        manager = self.manager(FakeGit())
        self.assertFalse(manager._state["updateAvailable"])
        self.assertEqual(manager._state["state"], "idle")

    def test_remote_manifest_must_match_plugin_id_and_semver(self):
        for manifest in (
            {"id": "someone.else", "version": "0.16.0"},
            {"id": PLUGIN_ID, "version": "next"},
        ):
            result = subprocess.CompletedProcess([], 0, json.dumps(manifest), "")
            with self.subTest(manifest=manifest), self.assertRaisesRegex(
                UpdateError, "update_check_failed"
            ):
                UpdateManager._manifest_version(result)


if __name__ == "__main__":
    unittest.main()
