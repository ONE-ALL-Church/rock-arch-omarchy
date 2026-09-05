import json
import tempfile
import unittest
from pathlib import Path

from rock_arch_broker.instance import InstanceStore
from rock_arch_broker.origin import OriginError, validate_rock_origin


class InstanceTests(unittest.TestCase):
    def test_bare_domain_is_normalized_to_https_origin(self):
        self.assertEqual(
            validate_rock_origin("Rock.Example.org/"),
            "https://rock.example.org",
        )

    def test_origin_rejects_insecure_or_non_origin_values(self):
        for value in (
            "http://rock.example.org",
            "https://user:pass@rock.example.org",
            "https://rock.example.org/api",
            "https://rock.example.org:8443",
            "https://rock.example.org?next=bad",
            "https://rock.example.org.attacker.example\\@rock.example.org",
            "*.example.org",
        ):
            with self.subTest(value=value), self.assertRaises(OriginError):
                validate_rock_origin(value)

    def test_instance_store_is_owner_only_and_rejects_permissive_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config" / "instance.json"
            store = InstanceStore(path)
            self.assertEqual(store.set("rock.example.org"), "https://rock.example.org")
            self.assertEqual(store.get(), "https://rock.example.org")
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.chmod(0o644)
            self.assertIsNone(store.get())

    def test_invalid_instance_record_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "instance.json"
            path.write_text(json.dumps({"origin": "http://bad.example"}))
            path.chmod(0o600)
            self.assertIsNone(InstanceStore(path).get())

    def test_deep_instance_json_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "instance.json"
            path.write_bytes(b"[" * 1_500 + b"]" * 1_500)
            path.chmod(0o600)
            self.assertIsNone(InstanceStore(path).get())


if __name__ == "__main__":
    unittest.main()
