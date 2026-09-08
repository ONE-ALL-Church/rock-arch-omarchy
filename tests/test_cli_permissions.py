import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from test_broker import FakeLive, FakeMagnus, FakeSession
from test_personal_links import ORIGIN, FakeRock

from rock_arch_broker.agent_protocol import settings_schema
from rock_arch_broker.broker import Broker
from rock_arch_broker.cli_permissions import MUTATION_ACTIONS
from rock_arch_broker.contracts import Context
from rock_arch_broker.instance import InstanceStore
from rock_arch_broker.jobs import JobRunOutcome
from rock_arch_broker.navigation import NavigationTarget
from rock_arch_broker.personal_links import PersonalLinkManager
from rock_arch_broker.profiles import ProfileError, ProfileStore
from rock_arch_broker.terminal_access import CLI_CLIENT


class CliPermissionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        instance = self.root / "instance.json"
        InstanceStore(instance).set(ORIGIN)
        self.rock = FakeRock()
        self.session = FakeSession(True)
        self.links = PersonalLinkManager(self.session, self.rock)
        self.magnus = FakeMagnus(True)
        self.jobs = Mock()
        self.jobs.run.return_value = JobRunOutcome(
            NavigationTarget("Synthetic job", "Scheduled Job", 40, ORIGIN + "/admin/system/jobs/7")
        )
        live = FakeLive()
        live.invalidate_personal_links = Mock()
        self.broker = Broker(self.root / "context", instance_file=instance,
                             session=self.session, live=live, magnus=self.magnus,
                             personal_links=self.links, jobs=self.jobs,
                             build_notifier=lambda: True)
        self.broker._context = Context.PROD
        self.store = self.broker._profile_store

    def request(self, op, **values):
        return self.broker.handle({"op": op, "client": CLI_CLIENT, **values})

    def grant(self, *actions):
        self.store.update_preferences({"terminalMutationAccess": True,
                                       "terminalMutationActions": list(actions)})

    def test_new_and_existing_preferences_default_off_and_roundtrip(self):
        preferences = self.store.preferences()
        self.assertTrue(preferences["terminalAccess"])
        self.assertFalse(preferences["terminalMutationAccess"])
        self.assertEqual(preferences["terminalMutationActions"], [])
        legacy = json.loads(self.store.path.read_text())
        legacy["preferences"].pop("terminalMutationAccess", None)
        legacy["preferences"].pop("terminalMutationActions", None)
        self.store.path.write_text(json.dumps(legacy))
        self.assertFalse(self.store.preferences()["terminalMutationAccess"])
        self.grant("runJobs", "addLinks")
        reloaded = ProfileStore(self.store.path, InstanceStore(self.root / "instance.json"))
        self.assertEqual(reloaded.preferences()["terminalMutationActions"], ["addLinks", "runJobs"])
        self.assertEqual(settings_schema()["fields"]["terminalMutationActions"]["items"], list(MUTATION_ACTIONS))

    def test_permission_updates_are_strict_atomic_and_available_with_read_off(self):
        for value in (True, "runJobs", ["unknown"], [1], ["runJobs", "runJobs"], [{}]):
            with self.subTest(value=value), self.assertRaises(ProfileError):
                self.store.update_preferences({"terminalMutationAccess": True, "terminalMutationActions": value})
            self.assertFalse(self.store.preferences()["terminalMutationAccess"])
        self.assertFalse(self.request("settings_update", settings={"terminalMutationAccess": "true"})["ok"])
        self.assertTrue(self.request("settings_update", settings={"terminalAccess": False})["ok"])
        self.assertTrue(self.request("settings_status")["ok"])
        self.assertTrue(self.request("settings_update", settings={"terminalAccess": True})["ok"])

    def test_default_blocks_every_write_without_io_but_allows_reads_and_previews(self):
        for op in ("personal_link_save", "personal_section_save", "personal_delete_commit", "job_run", "magnus_build"):
            with self.subTest(op=op):
                self.assertEqual(self.request(op, confirmed=True)["error"], "terminal_mutations_disabled")
        self.assertEqual(self.rock.calls, [])
        self.assertEqual(self.magnus.build_calls, [])
        self.jobs.run.assert_not_called()
        self.assertTrue(self.request("personal_link_prepare", name="Page", url="/page/42")["ok"])
        self.assertTrue(self.request("personal_section_prepare", name="Section")["ok"])
        self.assertEqual(self.rock.writes, [])

    def test_granting_one_action_does_not_allow_another_and_revocation_is_immediate(self):
        self.grant("runJobs")
        self.assertTrue(self.request("job_run", confirmed=True, draftId="synthetic")["ok"])
        self.assertEqual(self.request("magnus_build", confirmed=True)["requiredAction"], "buildMagnus")
        self.store.update_preferences({"terminalMutationActions": []})
        self.assertEqual(self.request("job_run", confirmed=True)["requiredAction"], "runJobs")
        self.jobs.run.assert_called_once()
        self.store.update_preferences({"terminalMutationAccess": False})
        self.assertEqual(self.request("job_run", confirmed=True)["error"], "terminal_mutations_disabled")
        self.assertTrue(self.broker.handle({"op": "job_run", "confirmed": True})["ok"])
        self.assertEqual(self.jobs.run.call_count, 2)

    def test_link_and_implicit_first_section_have_separate_grants(self):
        self.rock.sections = []
        draft = self.request("personal_link_prepare", name="Page", url="/page/42")["personalLink"]
        save = {"draftId": draft["draftId"], "name": draft["name"], "url": draft["url"], "confirmed": True}
        self.grant("addLinks")
        self.assertEqual(self.request("personal_link_save", **save)["requiredAction"], "addSections")
        self.assertEqual(self.rock.writes, [])
        self.grant("addSections")
        self.assertEqual(self.request("personal_link_save", **save)["requiredAction"], "addLinks")
        self.assertEqual(self.rock.writes, [])
        self.grant("addLinks", "addSections")
        self.assertTrue(self.request("personal_link_save", **save)["personalLink"]["saved"])
        self.assertEqual(len(self.rock.writes), 2)

    def test_section_creation_grant_is_independent_and_checked_after_preview(self):
        draft = self.request("personal_section_prepare", name="Private")["personalSection"]
        save = {"draftId": draft["draftId"], "name": "Private", "confirmed": True}
        self.grant("addLinks")
        self.assertEqual(self.request("personal_section_save", **save)["requiredAction"], "addSections")
        self.assertEqual(self.rock.writes, [])
        self.grant("addSections")
        self.assertTrue(self.request("personal_section_save", **save)["ok"])

    def test_delete_scope_comes_from_draft_and_with_links_needs_both_grants(self):
        self.rock.links = [{"Id": 100, "Name": "Page", "Url": ORIGIN + "/page/42", "SectionId": 7, "PersonAliasId": 420}]
        section = self.links.list_sections()[0]["safeId"]
        draft = self.request("personal_delete_prepare", kind="section", targetId=section, withLinks=True)["personalDelete"]
        commit = {"draftId": draft["draftId"], "withLinks": True, "confirmed": True, "kind": "link"}
        self.grant("deleteLinks")
        self.assertEqual(self.request("personal_delete_commit", **commit)["requiredAction"], "deleteSections")
        self.grant("deleteSections")
        self.assertEqual(self.request("personal_delete_commit", **commit)["requiredAction"], "deleteLinks")
        self.assertEqual(self.rock.writes, [])
        self.grant("deleteSections", "deleteLinks")
        self.assertTrue(self.request("personal_delete_commit", **commit)["ok"])
        self.assertEqual(self.rock.links, [])

    def test_empty_section_delete_without_contents_needs_only_section_grant(self):
        section = self.links.list_sections()[0]["safeId"]
        draft = self.request("personal_delete_prepare", kind="section", targetId=section)["personalDelete"]
        self.grant("deleteSections")
        self.assertTrue(self.request("personal_delete_commit", draftId=draft["draftId"], confirmed=True)["ok"])

    def test_link_delete_requires_its_own_grant_and_rechecks_revocation(self):
        self.rock.links = [{"Id": 100, "Name": "Page", "Url": ORIGIN + "/page/42", "SectionId": 7, "PersonAliasId": 420}]
        draft = self.links.prepare_delete("link", 100)
        commit = {"draftId": draft["draftId"], "confirmed": True, "kind": "section"}
        self.grant("deleteLinks")
        self.store.update_preferences({"terminalMutationActions": ["deleteSections"]})
        self.assertEqual(self.request("personal_delete_commit", **commit)["requiredAction"], "deleteLinks")
        self.assertEqual(self.rock.writes, [])
        self.grant("deleteLinks")
        self.assertTrue(self.request("personal_delete_commit", **commit)["ok"])
        self.assertEqual(len(self.rock.writes), 1)

    def test_master_enable_alone_grants_nothing_and_read_disable_blocks_writes(self):
        self.grant()
        self.assertEqual(self.request("job_run", confirmed=True)["requiredAction"], "runJobs")
        self.grant("runJobs")
        self.store.update_preferences({"terminalAccess": False})
        self.assertEqual(self.request("job_run", confirmed=True)["error"], "terminal_access_disabled")
        self.jobs.run.assert_not_called()
        self.assertTrue(self.request("settings_status")["settings"]["terminalMutationAccess"])
        self.assertEqual(self.request("settings_status")["settings"]["terminalMutationActions"], ["runJobs"])

    def test_recent_build_cannot_bypass_the_build_grant(self):
        built = self.broker.handle({"op": "magnus_build", "safeId": "opaque-mobile-app", "confirmed": True})
        recent_id = built["quickReturns"][0]["safeId"]
        self.assertEqual(self.request("activate_recent", safeId=recent_id, confirmed=True)["error"], "terminal_mutations_disabled")
        self.grant("runJobs")
        self.assertEqual(self.request("activate_recent", safeId=recent_id, confirmed=True)["requiredAction"], "buildMagnus")
        self.assertEqual(len(self.magnus.build_calls), 1)
        self.grant("buildMagnus")
        self.assertTrue(self.request("activate_recent", safeId=recent_id, confirmed=True)["ok"])
        self.assertEqual(len(self.magnus.build_calls), 2)
