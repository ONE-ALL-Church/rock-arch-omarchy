import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rock_lens_broker.update_worker import run_update
from rock_lens_broker.updates import OMARCHY, PLUGIN_ID


class UpdateWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.home = Path(self.temporary.name)
        self.root = self.home / ".config" / "omarchy" / "plugins" / PLUGIN_ID
        (self.root / ".git").mkdir(parents=True)
        self.state = self.home / "state" / "updates.json"

    def tearDown(self):
        self.temporary.cleanup()

    def test_successful_update_restarts_shell_before_reporting_success(self):
        completed = subprocess.CompletedProcess([], 0)
        with (
            patch("rock_lens_broker.update_worker.Path.home", return_value=self.home),
            patch("rock_lens_broker.update_worker._validated_version", return_value="0.24.1"),
            patch("rock_lens_broker.update_worker._origin_is_canonical", return_value=True),
            patch("rock_lens_broker.update_worker._revision", return_value="a" * 40),
            patch("rock_lens_broker.update_worker.subprocess.run", side_effect=[completed, completed]) as runner,
            patch("rock_lens_broker.update_worker._notify"),
            patch("rock_lens_broker.update_worker._terminate_broker") as terminate,
        ):
            result = run_update(self.state, self.root, 4242)

        self.assertEqual(result, 0)
        self.assertEqual(
            runner.call_args_list[0].args[0],
            [str(OMARCHY), "plugin", "update", PLUGIN_ID, "--yes"],
        )
        self.assertEqual(
            runner.call_args_list[1].args[0],
            [str(OMARCHY), "restart", "shell"],
        )
        self.assertEqual(json.loads(self.state.read_text())["state"], "updated")
        terminate.assert_called_once_with(4242)

    def test_shell_restart_failure_is_reported_and_recycles_broker(self):
        success = subprocess.CompletedProcess([], 0)
        failure = subprocess.CompletedProcess([], 1)
        with (
            patch("rock_lens_broker.update_worker.Path.home", return_value=self.home),
            patch("rock_lens_broker.update_worker._validated_version", return_value="0.24.1"),
            patch("rock_lens_broker.update_worker._origin_is_canonical", return_value=True),
            patch("rock_lens_broker.update_worker.subprocess.run", side_effect=[success, failure]),
            patch("rock_lens_broker.update_worker._notify"),
            patch("rock_lens_broker.update_worker._terminate_broker") as terminate,
        ):
            result = run_update(self.state, self.root, 4242)

        state = json.loads(self.state.read_text())
        self.assertEqual(result, 1)
        self.assertEqual(state["state"], "error")
        self.assertEqual(state["error"], "update_failed")
        terminate.assert_called_once_with(4242)

    def test_noncanonical_origin_is_rejected_before_omarchy_runs(self):
        with (
            patch("rock_lens_broker.update_worker.Path.home", return_value=self.home),
            patch("rock_lens_broker.update_worker._validated_version", return_value="0.25.2"),
            patch("rock_lens_broker.update_worker._origin_is_canonical", return_value=False),
            patch("rock_lens_broker.update_worker.subprocess.run") as runner,
        ):
            result = run_update(self.state, self.root, 4242)

        self.assertEqual(result, 1)
        self.assertEqual(
            json.loads(self.state.read_text())["error"],
            "update_source_not_allowed",
        )
        runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
