import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rock_arch_broker.update_worker import _install_lock, run_update
from rock_arch_broker.updates import GIT, OMARCHY, PLUGIN_ID, UpdateManager

REAL_RUN = subprocess.run


class UpdateWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.fake_home = Path(self.temporary.name)
        self.remote = self.fake_home / "remote"
        self.root = self.fake_home / ".config/omarchy/plugins" / PLUGIN_ID
        self.state = self.fake_home / "state/updates.json"
        self.git(self.fake_home, "init", "--initial-branch=main", str(self.remote))
        self.git(self.remote, "config", "user.email", "test@example.invalid")
        self.git(self.remote, "config", "user.name", "Test")
        self.first = self.commit("A")
        self.git(self.fake_home, "clone", str(self.remote), str(self.root))
        self.expected = self.commit("B")
        self.git(self.root, "fetch", "origin", "HEAD")
        self.calls = []
        self.activated = []
        self.on_validate = lambda: None
        self.fail_validation = False
        self.fail_restart = False
        self.canonical = True

    def git(self, root, *arguments):
        result = REAL_RUN([str(GIT), "-C", str(root), *arguments], capture_output=True, text=True, timeout=10, check=False)
        if result.returncode:
            self.fail(result.stderr)
        return result.stdout.strip()

    def commit(self, marker):
        manifest = {"schemaVersion": 1, "id": PLUGIN_ID, "name": "Test", "version": "0.26.1",
                    "kinds": ["bar-widget"], "entryPoints": {"barWidget": "Main.qml"}}
        (self.remote / "manifest.json").write_text(json.dumps(manifest))
        (self.remote / "Main.qml").write_text('import QtQuick\nItem { property string marker: "' + marker + '" }\n')
        self.git(self.remote, "add", ".")
        self.git(self.remote, "commit", "-m", marker)
        return self.git(self.remote, "rev-parse", "HEAD")

    def runner(self, command, **kwargs):
        self.calls.append(command)
        if command[0] == str(GIT) and command[-3:] == ["remote", "get-url", "origin"]:
            return subprocess.CompletedProcess(command, 0,
                "https://github.com/ONE-ALL-Church/rock-arch-omarchy.git\n" if self.canonical else "https://example.invalid/foreign.git\n", "")
        if command[:3] == [str(OMARCHY), "plugin", "validate"]:
            candidate = Path(command[3])
            self.on_validate()
            # Static validator substitute; no candidate code runs in this test.
            valid = ((candidate / "manifest.json").is_file() and (candidate / "Main.qml").is_file()
                     and not any(p.is_symlink() for p in candidate.rglob("*") if ".git" not in p.parts))
            return subprocess.CompletedProcess(command, int(self.fail_validation or not valid))
        if command == [str(OMARCHY), "restart", "shell"]:
            self.activated.append((self.git(self.root, "rev-parse", "HEAD"), (self.root / "Main.qml").read_text()))
            return subprocess.CompletedProcess(command, int(self.fail_restart))
        if command[0] != str(GIT):
            self.fail(f"unexpected command {command}")
        return REAL_RUN(command, **kwargs)

    def run_worker(self, target=None):
        with (patch("rock_arch_broker.update_worker.Path.home", return_value=self.fake_home),
              patch("rock_arch_broker.update_worker.subprocess.run", side_effect=self.runner),
              patch("rock_arch_broker.update_worker._notify"),
              patch("rock_arch_broker.update_worker._terminate_broker")):
            code = run_update(self.state, self.root, 0, self.expected if target is None else target)
        return code, json.loads(self.state.read_text())

    def test_remote_head_and_fetch_head_move_after_check_but_only_checked_commit_installs(self):
        for automatic in (False, True):
            with self.subTest(automatic=automatic):
                self.git(self.root, "reset", "--hard", self.first)
                self.git(self.remote, "reset", "--hard", self.expected)
                launched = []
                manager = UpdateManager(self.state, plugin_root=self.root, installed_root=self.root,
                    command_runner=lambda c, t: self.runner(c, timeout=t, capture_output=True, text=True),
                    process_launcher=lambda c, p, captured=launched: captured.append(c))
                manager._managed = True
                manager._state = manager._check_once()
                self.assertEqual(manager._state["availableRevision"], self.expected)
                later = self.commit("C")
                self.git(self.root, "fetch", "origin", "HEAD")
                self.assertEqual(self.git(self.root, "rev-parse", "FETCH_HEAD"), later)
                if automatic:
                    manager.status(automatic_install=True)
                else:
                    manager.start_update()
                target = launched[0][launched[0].index("--expected-revision") + 1]
                self.assertEqual(target, self.expected)
                code, state = self.run_worker(target)
                self.assertEqual(code, 0)
                self.assertEqual(state["currentRevision"], self.expected)
                self.assertEqual(self.git(self.root, "rev-parse", "HEAD"), self.expected)
                self.assertEqual(self.activated[-1][0], self.expected)
                self.assertIn('marker: "B"', self.activated[-1][1])
                self.assertNotIn('marker: "C"', (self.root / "Main.qml").read_text())
        self.assertFalse(any(c[:3] == [str(OMARCHY), "plugin", "update"] for c in self.calls))

    def test_bad_or_missing_target_never_changes_checkout(self):
        for target in ("", "HEAD", "FETCH_HEAD", "b" * 7, "A" * 40, "-" * 40, "f" * 40):
            with self.subTest(target=target):
                code, state = self.run_worker(target)
                self.assertEqual(code, 1)
                self.assertEqual(state["state"], "error")
                self.assertEqual(self.git(self.root, "rev-parse", "HEAD"), self.first)
                self.assertEqual(self.activated, [])

    def test_noncanonical_source_refuses_before_validation(self):
        self.canonical = False
        code, state = self.run_worker()
        self.assertEqual(code, 1)
        self.assertEqual(state["error"], "update_source_not_allowed")
        self.assertFalse(any(c[0] == str(OMARCHY) for c in self.calls))

    def test_tracked_and_untracked_changes_are_preserved(self):
        for filename in ("Main.qml", "private.txt"):
            with self.subTest(filename=filename):
                path = self.root / filename
                before = path.read_text() if path.exists() else None
                path.write_text("keep this user data")
                code, state = self.run_worker()
                self.assertEqual(code, 1)
                self.assertEqual(state["error"], "local_changes_prevent_update")
                self.assertEqual(path.read_text(), "keep this user data")
                self.assertEqual(self.activated, [])
                if before is None:
                    path.unlink()
                else:
                    path.write_text(before)

    def test_ignored_user_file_is_not_overwritten_by_new_tracked_file(self):
        (self.root / ".git/info/exclude").write_text("private.txt\n")
        (self.root / "private.txt").write_text("keep private content")
        (self.remote / "private.txt").write_text("new tracked content")
        self.expected = self.commit("D")
        self.git(self.root, "fetch", "origin", "HEAD")
        code, state = self.run_worker()
        self.assertEqual(code, 1)
        self.assertEqual(state["state"], "error")
        self.assertEqual((self.root / "private.txt").read_text(), "keep private content")
        self.assertEqual(self.git(self.root, "rev-parse", "HEAD"), self.first)
        self.assertEqual(self.activated, [])

    def test_failed_candidate_validation_never_touches_installed_code(self):
        self.fail_validation = True
        code, state = self.run_worker()
        self.assertEqual((code, state["error"]), (1, "update_validation_failed"))
        self.assertEqual(self.git(self.root, "rev-parse", "HEAD"), self.first)
        self.assertEqual(self.activated, [])
        self.assertEqual(self.git(self.root, "worktree", "list", "--porcelain").count("worktree "), 1)

    def test_checkout_change_during_validation_is_preserved_and_not_activated(self):
        def change():
            (self.root / "Main.qml").write_text("concurrent edit")
        self.on_validate = change
        code, state = self.run_worker()
        self.assertEqual((code, state["error"]), (1, "update_checkout_changed"))
        self.assertEqual((self.root / "Main.qml").read_text(), "concurrent edit")
        self.assertEqual(self.activated, [])

    def test_diverged_history_is_not_replaced(self):
        self.git(self.root, "config", "user.email", "test@example.invalid")
        self.git(self.root, "config", "user.name", "Test")
        (self.root / "Main.qml").write_text("local commit")
        self.git(self.root, "commit", "-am", "local")
        before = self.git(self.root, "rev-parse", "HEAD")
        code, state = self.run_worker()
        self.assertEqual((code, state["error"]), (1, "update_history_diverged"))
        self.assertEqual(self.git(self.root, "rev-parse", "HEAD"), before)
        self.assertEqual(self.activated, [])

    def test_restart_failure_never_reports_success(self):
        self.fail_restart = True
        code, state = self.run_worker()
        self.assertEqual((code, state["error"]), (1, "update_restart_failed"))
        self.assertEqual(state["state"], "error")
        self.assertEqual(self.git(self.root, "rev-parse", "HEAD"), self.expected)

    def test_install_lock_prevents_second_worker(self):
        with _install_lock(self.root):
            code, state = self.run_worker()
        self.assertEqual((code, state["error"]), (1, "update_already_running"))
        self.assertEqual(self.git(self.root, "rev-parse", "HEAD"), self.first)

    def test_post_merge_mismatch_prevents_restart(self):
        original_runner = self.runner
        def replace_after_merge(command, **kwargs):
            result = original_runner(command, **kwargs)
            if "merge" in command and "--ff-only" in command:
                self.git(self.root, "reset", "--hard", self.first)
            return result
        with (patch("rock_arch_broker.update_worker.Path.home", return_value=self.fake_home),
              patch("rock_arch_broker.update_worker.subprocess.run", side_effect=replace_after_merge),
              patch("rock_arch_broker.update_worker._notify")):
            code = run_update(self.state, self.root, 0, self.expected)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(self.state.read_text())["error"], "update_revision_mismatch")
        self.assertEqual(self.activated, [])
