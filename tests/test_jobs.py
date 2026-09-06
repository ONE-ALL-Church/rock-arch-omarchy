import copy
import io
import json
import tempfile
import unittest
import urllib.error
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from rock_arch_broker.jobs import (
    JOB_BLOCK_TYPE,
    JOBS_PAGE,
    JobError,
    JobHttpClient,
    JobManager,
    Placement,
)

ORIGIN = "https://rock.example.org"
BLOCK = "11111111-1111-4111-8111-111111111111"
CUSTOM_BLOCK = "22222222-2222-4222-8222-222222222222"
CUSTOM_PAGE = "33333333-3333-4333-8333-333333333333"
JOB = "44444444-4444-4444-8444-444444444444"


class Session:
    @contextmanager
    def authenticated_cookie(self):
        yield ".ROCK=test"


class JobHttp:
    def __init__(self):
        self.calls = []
        self.types = [{"Id": 100, "Guid": JOB_BLOCK_TYPE}]
        self.blocks = [{"Guid": BLOCK, "PageId": 102, "BlockTypeId": 100}]
        self.pages = {102: JOBS_PAGE, 103: CUSTOM_PAGE}
        self.denied = set()
        self.edit = True
        self.error = ""
        self.config_type = JOB_BLOCK_TYPE
        self.job = {"Id": 7, "Guid": JOB, "Name": "Test job", "LastStatus": "Success",
                    "LastRunDateTime": "2026-09-05T12:00:00", "LastRunDurationSeconds": 4}
        self.write_error = ""

    def request(self, origin, path, params, cookie, body=None):
        self.calls.append((origin, path, params, body))
        if body is not None:
            if self.write_error:
                raise JobError(self.write_error)
            return None
        if path == "/api/BlockTypes":
            return copy.deepcopy(self.types)
        if path == "/api/Blocks":
            return copy.deepcopy(self.blocks)
        if path == "/api/Pages":
            number = int(params["$filter"].split()[-1])
            return [{"Id": number, "Guid": self.pages[number]}]
        if path == "/api/ServiceJobs":
            return [copy.deepcopy(self.job)] if self.job else []
        if path.endswith("/RefreshObsidianBlockInitialization"):
            if self.error:
                raise JobError(self.error)
            block = path.split("/")[-2]
            if block in self.denied:
                raise JobError("job_access_denied")
            return {"blockGuid": block, "blockTypeGuid": self.config_type,
                    "configurationValues": {"isAddEnabled": self.edit, "isDeleteEnabled": self.edit, "errorMessage": None}}
        raise AssertionError(path)


class JobManagerTests(unittest.TestCase):
    def setUp(self):
        self.http = JobHttp()
        self.jobs = JobManager(Session(), self.http)
        self.jobs.set_origin(ORIGIN)

    def writes(self):
        return [c for c in self.http.calls if c[3] is not None]

    def test_discovery_uses_type_guid_and_page_block_permission_check_then_caches(self):
        self.assertTrue(self.jobs.access()["available"])
        self.assertEqual(len(self.http.calls), 4)
        self.assertIn(JOB_BLOCK_TYPE, self.http.calls[0][2]["$filter"])
        self.assertTrue(self.http.calls[-1][1].endswith("/RefreshObsidianBlockInitialization"))
        self.assertTrue(self.jobs.access()["available"])
        self.assertEqual(len(self.http.calls), 4)
        self.assertEqual(self.writes(), [])

    def test_searchable_metadata_and_view_access_do_not_grant_run_access(self):
        for value in (False, None, "true", 1):
            self.http.edit = value
            self.assertFalse(self.jobs.access(refresh=True)["available"])
        self.http.edit = True
        self.http.denied = {BLOCK}
        self.assertFalse(self.jobs.access(refresh=True)["available"])
        self.assertEqual(self.writes(), [])

    def test_default_page_preferred_and_unique_custom_placement_supported(self):
        custom = {"Guid": CUSTOM_BLOCK, "PageId": 103, "BlockTypeId": 100}
        self.http.blocks.append(custom)
        self.assertTrue(self.jobs.access()["available"])
        self.assertEqual(self.jobs._placement, Placement(JOBS_PAGE, BLOCK))
        self.http.blocks = [custom]
        self.assertTrue(self.jobs.access(refresh=True)["available"])
        self.assertEqual(self.jobs._placement, Placement(CUSTOM_PAGE, CUSTOM_BLOCK))

    def test_ambiguous_placements_missing_type_and_unexpected_config_fail_closed(self):
        self.http.blocks.append({"Guid": CUSTOM_BLOCK, "PageId": 102, "BlockTypeId": 100})
        self.assertEqual(self.jobs.access()["error"], "job_discovery_ambiguous")
        self.http.blocks.pop()
        self.http.config_type = CUSTOM_BLOCK
        self.assertFalse(self.jobs.access(refresh=True)["available"])
        self.http.types = []
        self.assertFalse(self.jobs.access(refresh=True)["available"])

    def test_failed_refresh_does_not_retain_previous_permission(self):
        self.assertTrue(self.jobs.access()["available"])
        self.http.error = "job_access_unavailable"
        self.assertFalse(self.jobs.access(refresh=True)["available"])
        self.assertIsNone(self.jobs._placement)

    def test_preview_is_read_only_and_confirmed_run_uses_fresh_guid_once(self):
        draft = self.jobs.prepare(7)
        self.assertEqual(draft["title"], "Test job")
        self.assertEqual(self.writes(), [])
        with self.assertRaisesRegex(JobError, "confirmation_required"):
            self.jobs.run(draft["draftId"], False)
        result = self.jobs.run(draft["draftId"], True)
        self.assertEqual(result["state"], "requested")
        self.assertFalse(result["completionVerified"])
        self.assertEqual(self.writes(), [(ORIGIN, Placement(JOBS_PAGE, BLOCK).action("RunNow"), {}, {"key": JOB})])
        with self.assertRaisesRegex(JobError, "draft_expired"):
            self.jobs.run(draft["draftId"], True)

    def test_expired_confirmation_and_profile_switch_cannot_run(self):
        with patch("rock_arch_broker.jobs.time.monotonic", return_value=100):
            draft = self.jobs.prepare(7)
        with patch("rock_arch_broker.jobs.time.monotonic", return_value=221), self.assertRaisesRegex(JobError, "draft_expired"):
            self.jobs.run(draft["draftId"], True)
        draft = self.jobs.prepare(7)
        self.jobs.set_origin(ORIGIN)
        with self.assertRaisesRegex(JobError, "draft_expired"):
            self.jobs.run(draft["draftId"], True)
        self.assertEqual(self.writes(), [])

    def test_revoked_access_or_changed_placement_prevents_run(self):
        for mutation in ("permission", "placement"):
            with self.subTest(mutation=mutation):
                self.setUp()
                draft = self.jobs.prepare(7)
                if mutation == "permission":
                    self.http.edit = False
                else:
                    self.http.blocks[0]["Guid"] = CUSTOM_BLOCK
                with self.assertRaisesRegex(JobError, "access_changed"):
                    self.jobs.run(draft["draftId"], True)
                self.assertEqual(self.writes(), [])

    def test_replaced_or_renamed_job_requires_new_review(self):
        for field, value in (("Guid", CUSTOM_BLOCK), ("Name", "Another job")):
            with self.subTest(field=field):
                self.setUp()
                draft = self.jobs.prepare(7)
                self.http.job[field] = value
                with self.assertRaisesRegex(JobError, "job_changed"):
                    self.jobs.run(draft["draftId"], True)
                self.assertEqual(self.writes(), [])

    def test_uncertain_post_consumes_draft_and_is_never_retried(self):
        draft = self.jobs.prepare(7)
        self.http.write_error = "job_run_uncertain"
        with self.assertRaisesRegex(JobError, "job_run_uncertain"):
            self.jobs.run(draft["draftId"], True)
        with self.assertRaisesRegex(JobError, "job_draft_expired"):
            self.jobs.run(draft["draftId"], True)
        self.assertEqual(len(self.writes()), 1)

    def test_status_reports_latest_record_without_claiming_completion(self):
        self.http.job["LastStatusMessage"] = "Sensitive internal details"
        value = self.jobs.status(7)
        self.assertEqual(value["lastStatus"], "Success")
        self.assertFalse(value["completionVerified"])
        self.assertNotIn("Sensitive", json.dumps(value))
        self.assertEqual(self.writes(), [])

    def test_invalid_ids_and_unbounded_discovery_are_rejected(self):
        for number in (True, 0, -1, "7"):
            with self.assertRaises(JobError):
                self.jobs.status(number)
        self.http.blocks *= 9
        self.assertFalse(self.jobs.access()["available"])


class Reply:
    def __init__(self, body=b"", kind="application/json"):
        self.body = body
        self.headers = {"Content-Type": kind}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, size):
        return self.body[:size]


class Opener:
    def __init__(self, response=None):
        self.response = response or Reply()
        self.calls = []

    def open(self, request, timeout):
        self.calls.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class JobHttpTests(unittest.TestCase):
    def test_only_exact_post_and_read_endpoints_are_allowed(self):
        opener = Opener()
        client = JobHttpClient(opener)
        path = Placement(JOBS_PAGE, BLOCK).action("RunNow")
        for target, body in ((path, None), ("/api/ServiceJobs", {"key": JOB}),
                             (path, {"key": "7"}), (path, {"key": JOB, "extra": "value"}),
                             ("https://other.example/RunNow", {"key": JOB})):
            with self.subTest(target=target, body=body), self.assertRaises(JobError):
                client.request(ORIGIN, target, {}, ".ROCK=test", body)
        self.assertEqual(opener.calls, [])
        client.request(ORIGIN, path, {}, ".ROCK=test", {"key": JOB})
        self.assertEqual(opener.calls[0].get_method(), "POST")
        self.assertEqual(json.loads(opener.calls[0].data), {"key": JOB})

    def test_redirect_timeout_and_html_are_uncertain_and_never_retried(self):
        for response in (TimeoutError(), urllib.error.HTTPError(ORIGIN, 302, "redirect", {}, io.BytesIO()), Reply(b"login", "text/html")):
            opener = Opener(response)
            with self.assertRaisesRegex(JobError, "job_run_uncertain"):
                JobHttpClient(opener).request(ORIGIN, Placement(JOBS_PAGE, BLOCK).action("RunNow"), {}, ".ROCK=test", {"key": JOB})
            self.assertEqual(len(opener.calls), 1)

    def test_http_permission_denial_is_distinct_from_uncertain_outcome(self):
        opener = Opener(urllib.error.HTTPError(ORIGIN, 403, "private detail", {}, io.BytesIO(b"secret")))
        with self.assertRaisesRegex(JobError, "^job_access_denied$"):
            JobHttpClient(opener).request(ORIGIN, Placement(JOBS_PAGE, BLOCK).action("RunNow"), {}, ".ROCK=test", {"key": JOB})


class JobBrokerTests(unittest.TestCase):
    def test_only_registered_job_references_can_prepare_and_profile_changes_invalidate_drafts(self):
        from test_broker import FakeMagnus, FakeSession

        from rock_arch_broker.broker import Broker
        from rock_arch_broker.instance import InstanceStore
        from rock_arch_broker.rock_rest_adapter import RockRestReadOnlyAdapter

        http = JobHttp()

        class ReadHttp:
            def get_json(self, path, params, cookie):
                return [http.job] if path == "/api/ServiceJobs" else []

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            instance = root / "instance.json"
            InstanceStore(instance).set(ORIGIN)
            session = FakeSession(True)
            live = RockRestReadOnlyAdapter(session, ReadHttp(), ORIGIN)
            jobs = JobManager(session, http)
            broker = Broker(state_file=root / "context", session=session, live=live,
                            jobs=jobs, magnus=FakeMagnus(), instance_file=instance,
                            developer_mode=False)
            row = live.search("Test", "Jobs").results[0]
            self.assertIn("runJob", broker.handle({"op": "describe", "safeId": row["safeId"]})["description"]["actions"])
            for safe_id in ("7", JOB, "rock-made-up"):
                response = broker.handle({"op": "job_prepare", "safeId": safe_id})
                self.assertFalse(response["ok"])
                self.assertEqual(response["error"], "job_not_found")
            draft = broker.handle({"op": "job_prepare", "safeId": row["safeId"], "requestId": "ui-1"})
            self.assertEqual(draft["jobAction"]["requestId"], "ui-1")
            token = draft["jobAction"]["draftId"]
            response = broker.handle({"op": "job_run", "draftId": token})
            self.assertEqual(response["error"], "job_confirmation_required")
            broker._activate_profile(broker._profile_store.active())
            response = broker.handle({"op": "job_run", "draftId": token, "confirmed": True})
            self.assertEqual(response["error"], "job_draft_expired")
            broker._profile_store.update_preferences({"enabledCategories": ["People"]})
            self.assertFalse(broker.handle({"op": "job_access"})["jobAccess"]["available"])
            self.assertEqual([c for c in http.calls if c[3] is not None], [])
