import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from rock_arch_broker import legacy_cli
from rock_arch_broker.__main__ import main
from rock_arch_broker.cli import CliError


class LegacyCliTests(unittest.TestCase):
    def test_aliases_use_the_supported_broker_client(self):
        cases = (
            ("rock", "status", ["status"]),
            ("rock", "login", ["login"]),
            ("magnus", "status", ["magnus", "status"]),
            ("magnus", "configure", ["login"]),
        )
        for group, command, target in cases:
            with (
                self.subTest(group=group, command=command),
                patch("rock_arch_broker.cli.run", return_value=3) as run,
                redirect_stderr(io.StringIO()) as output,
            ):
                self.assertEqual(legacy_cli.run(group, [command]), 3)
                run.assert_called_once_with(target)
                self.assertIn("Deprecated alias", output.getvalue())

    def test_module_entry_point_preserves_client_exit_status(self):
        with (
            patch("sys.argv", ["rock_arch_broker", "rock", "status"]),
            patch("rock_arch_broker.cli.run", return_value=4),
            redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as result,
        ):
            main()
        self.assertEqual(result.exception.code, 4)

    def test_retired_paths_do_not_start_a_client_or_echo_private_paths(self):
        for command in ("ls", "cat", "hash"):
            with (
                self.subTest(command=command),
                patch("rock_arch_broker.cli.run") as run,
                redirect_stderr(io.StringIO()) as output,
                self.assertRaises(SystemExit) as result,
            ):
                legacy_cli.run("magnus", [command, "/FileContent/private-fixture"])
            self.assertEqual(result.exception.code, 2)
            run.assert_not_called()
            self.assertNotIn("private-fixture", output.getvalue())
            self.assertIn("rock-arch magnus browse", output.getvalue())

    def test_alias_obeys_terminal_access_refusal(self):
        with (
            patch(
                "rock_arch_broker.cli.BrokerClient.request",
                side_effect=CliError("terminal_access_disabled", 3),
            ),
            redirect_stderr(io.StringIO()) as error,
            redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(legacy_cli.run("rock", ["status"]), 3)
        self.assertEqual(output.getvalue(), "")
        self.assertIn('"error":"terminal_access_disabled"', error.getvalue())


if __name__ == "__main__":
    unittest.main()
