import subprocess
import unittest
from unittest.mock import patch

from rock_lens_broker.clipboard import copy_to_clipboard


class ClipboardTests(unittest.TestCase):
    @patch("rock_lens_broker.clipboard.subprocess.run")
    @patch("pathlib.Path.is_file", return_value=True)
    def test_value_is_passed_only_on_stdin(self, _exists, run):
        run.return_value = subprocess.CompletedProcess(["/usr/bin/wl-copy"], 0)

        self.assertTrue(copy_to_clipboard("private Magnus content"))

        args, kwargs = run.call_args
        self.assertEqual(args[0], ["/usr/bin/wl-copy"])
        self.assertEqual(kwargs["input"], b"private Magnus content")
        self.assertNotIn("private Magnus content", args[0])


if __name__ == "__main__":
    unittest.main()
