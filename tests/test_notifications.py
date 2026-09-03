import subprocess
import unittest
from unittest.mock import patch

from rock_lens_broker.notifications import notify_build_accepted


class NotificationTests(unittest.TestCase):
    def test_notification_uses_fixed_program_and_contains_no_target_data(self):
        with (
            patch("rock_lens_broker.notifications.NOTIFY_SEND") as executable,
            patch(
                "rock_lens_broker.notifications.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0),
            ) as runner,
        ):
            executable.is_file.return_value = True
            executable.__str__.return_value = "/usr/bin/notify-send"
            self.assertTrue(notify_build_accepted())

        command = runner.call_args.args[0]
        self.assertEqual(command[0], "/usr/bin/notify-send")
        self.assertNotIn("http", " ".join(command).lower())
        self.assertNotIn("mobileapps", " ".join(command).lower())


if __name__ == "__main__":
    unittest.main()
