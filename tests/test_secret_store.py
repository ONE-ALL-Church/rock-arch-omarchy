import unittest
from subprocess import CompletedProcess
from unittest.mock import patch

from rock_lens_broker.contracts import Context
from rock_lens_broker.secret_store import SecretToolStore


class SecretStoreTests(unittest.TestCase):
    def test_secret_tool_passes_secret_only_on_stdin(self):
        store = SecretToolStore("/usr/bin/secret-tool")
        with patch("subprocess.run") as run:
            run.return_value.returncode = 0
            store.store(Context.PROD, "rock_password:profile:test", "never-in-argv")
        args = run.call_args.args[0]
        self.assertNotIn("never-in-argv", args)
        self.assertEqual(run.call_args.kwargs["input"], b"never-in-argv")

    def test_missing_secret_is_confirmed_as_already_cleared(self):
        store = SecretToolStore("/usr/bin/secret-tool")
        missing = CompletedProcess([], 1, stdout=b"", stderr=b"")
        with patch("subprocess.run", side_effect=[missing, missing]) as run:
            self.assertTrue(store.clear(Context.PROD, "missing"))
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[1].args[0][1], "lookup")

    def test_failed_clear_stays_failed_when_secret_remains(self):
        store = SecretToolStore("/usr/bin/secret-tool")
        failed_clear = CompletedProcess([], 1, stdout=b"", stderr=b"")
        present = CompletedProcess([], 0, stdout=b"still-present\n", stderr=b"")
        with patch("subprocess.run", side_effect=[failed_clear, present]):
            self.assertFalse(store.clear(Context.PROD, "present"))

    def test_clear_error_is_not_treated_as_missing(self):
        store = SecretToolStore("/usr/bin/secret-tool")
        failed = CompletedProcess([], 1, stdout=b"", stderr=b"keyring unavailable")
        with patch("subprocess.run", return_value=failed) as run:
            self.assertFalse(store.clear(Context.PROD, "rock_password"))
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
