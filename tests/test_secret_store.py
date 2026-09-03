import unittest
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


if __name__ == "__main__":
    unittest.main()
