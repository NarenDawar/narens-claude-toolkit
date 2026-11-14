import json
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone

import helpers

sys.path.insert(
    0,
    str(helpers.REPO_ROOT / "plugins" / "oss-issue-matcher" / "skills" / "oss-issue-matcher" / "scripts"),
)
import repo_pulse as rp  # noqa: E402

NOW = datetime(2026, 11, 13, tzinfo=timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def reply(hours, login="maint", assoc="MEMBER", typename="User"):
    return {
        "createdAt": iso(NOW - timedelta(days=60) + timedelta(hours=hours)),
        "authorAssociation": assoc,
        "author": {"login": login, "__typename": typename},
    }


def pr(state="MERGED", age_days=60, assoc="FIRST_TIME_CONTRIBUTOR", comments=(), reviews=(), author="dev"):
    created = NOW - timedelta(days=age_days)
    closed = None if state == "OPEN" else iso(created + timedelta(days=3))
    return {
        "createdAt": iso(created),
        "closedAt": closed,
        "mergedAt": closed if state == "MERGED" else None,
        "state": state,
        "authorAssociation": assoc,
        "author": {"login": author, "__typename": "User"},
        "comments": {"nodes": list(comments)},
        "reviews": {"nodes": list(reviews)},
    }


def repo(prs, archived=False, commit_days_ago=5):
    return {
        "isArchived": archived,
        "defaultBranchRef": {"target": {"committedDate": iso(NOW - timedelta(days=commit_days_ago))}},
        "pullRequests": {"nodes": prs},
    }


def healthy(n=10):
    return [pr(comments=[reply(5)]) for _ in range(n)]


def run(prs, **kw):
    return rp.analyze("o/r", repo(prs, **kw), NOW)


class GradeTests(unittest.TestCase):
    def test_a_fast_merging_repo_is_responsive(self):
        result = run(healthy())
        self.assertEqual(result["grade"], "responsive")
        self.assertEqual(result["median_hours_to_first_reply"], 5.0)
        self.assertEqual(result["merge_rate"], 1.0)
        self.assertEqual(result["ignored_share"], 0.0)

    def test_a_repo_that_ignores_outside_prs_is_avoided(self):
        result = run([pr(state="CLOSED") for _ in range(10)])
        self.assertEqual(result["grade"], "avoid")
        self.assertEqual(result["ignored_share"], 1.0)
        self.assertEqual(result["merge_rate"], 0.0)

    def test_slow_replies_are_slow_not_avoid(self):
        result = run([pr(comments=[reply(200)]) for _ in range(10)])
        self.assertEqual(result["grade"], "slow")

    def test_too_few_outside_prs_are_not_scored(self):
        self.assertEqual(run(healthy(7))["grade"], "insufficient-data")

    def test_new_open_prs_do_not_count_toward_the_sample(self):
        result = run(healthy(7) + [pr(state="OPEN", age_days=2) for _ in range(20)])
        self.assertEqual(result["external_prs"], 27)
        self.assertEqual(result["grade"], "insufficient-data")

    def test_archived_repo(self):
        self.assertEqual(run(healthy(), archived=True)["grade"], "archived")

    def test_an_old_last_commit_is_avoided(self):
        result = run(healthy(), commit_days_ago=400)
        self.assertEqual(result["grade"], "avoid")
        self.assertTrue(any("400 days" in why for why in result["why"]))

    def test_a_low_merge_rate_is_avoided(self):
        prs = [pr(state="CLOSED", comments=[reply(5)]) for _ in range(9)] + [pr(comments=[reply(5)])]
        result = run(prs)
        self.assertEqual(result["grade"], "avoid")
        self.assertEqual(result["merge_rate"], 0.1)


class ReplyTests(unittest.TestCase):
    def outcome(self, comment):
        return run([pr(state="CLOSED", comments=[comment]) for _ in range(10)])

    def test_a_bot_reply_does_not_count(self):
        result = self.outcome(reply(1, login="triage[bot]", assoc="MEMBER"))
        self.assertEqual(result["ignored_share"], 1.0)
        result = self.outcome(reply(1, login="triage", assoc="MEMBER", typename="Bot"))
        self.assertEqual(result["ignored_share"], 1.0)

    def test_another_contributor_is_not_a_maintainer(self):
        self.assertEqual(self.outcome(reply(1, assoc="CONTRIBUTOR"))["ignored_share"], 1.0)

    def test_the_author_replying_to_themselves_does_not_count(self):
        self.assertEqual(self.outcome(reply(1, login="dev"))["ignored_share"], 1.0)

    def test_a_maintainer_review_counts_as_a_reply(self):
        result = run([pr(reviews=[reply(2)]) for _ in range(10)])
        self.assertEqual(result["ignored_share"], 0.0)
        self.assertEqual(result["median_hours_to_first_reply"], 2.0)

    def test_the_earliest_maintainer_reply_is_used(self):
        result = run([pr(comments=[reply(30)], reviews=[reply(4)]) for _ in range(10)])
        self.assertEqual(result["median_hours_to_first_reply"], 4.0)


class SampleTests(unittest.TestCase):
    def test_team_prs_and_deleted_authors_are_left_out(self):
        team = [pr(assoc="MEMBER") for _ in range(5)]
        ghost = dict(pr(), author=None)
        result = run(healthy(8) + team + [ghost])
        self.assertEqual(result["external_prs"], 8)

    def test_an_old_open_pr_without_a_reply_is_ignored_but_a_new_one_is_not(self):
        old = [pr(state="OPEN", age_days=20) for _ in range(2)]
        new = [pr(state="OPEN", age_days=3) for _ in range(2)]
        result = run(healthy(6) + old + new)
        self.assertEqual(result["judged_prs"], 8)
        self.assertEqual(result["ignored_share"], 0.25)

    def test_stale_open_prs_are_counted(self):
        result = run(healthy(8) + [pr(state="OPEN", age_days=45, comments=[reply(5)])])
        self.assertEqual(result["stale_open_external_prs"], 1)

    def test_an_old_draft_is_not_waiting_for_review(self):
        draft = dict(pr(state="OPEN", age_days=40), isDraft=True)
        result = run(healthy(8) + [draft])
        self.assertEqual(result["judged_prs"], 8)
        self.assertEqual(result["ignored_share"], 0.0)

    def test_a_merge_without_a_comment_is_not_ignored(self):
        result = run([pr() for _ in range(10)])
        self.assertEqual(result["ignored_share"], 0.0)
        self.assertIsNone(result["median_hours_to_first_reply"])

    def test_the_merge_rate_needs_enough_closed_prs(self):
        prs = [pr(comments=[reply(5)]) for _ in range(4)] + [pr(state="OPEN", comments=[reply(5)]) for _ in range(6)]
        self.assertIsNone(run(prs)["merge_rate"])


class FetchTests(unittest.TestCase):
    def fake(self, payload):
        calls = []

        def runner(owner, name, n):
            calls.append((owner, name, n))
            return json.dumps(payload)

        return runner, calls

    def test_pulse_reads_and_grades_a_repo(self):
        runner, calls = self.fake({"data": {"repository": repo(healthy())}})
        result = rp.pulse("octo/cat", 30, run=runner)
        self.assertEqual(calls, [("octo", "cat", 30)])
        self.assertEqual(result["repo"], "octo/cat")
        self.assertIn(result["grade"], {"responsive", "slow", "avoid", "insufficient-data"})

    def test_a_missing_repository_is_an_error_entry(self):
        runner, _ = self.fake({"data": {"repository": None}, "errors": [{"message": "Could not resolve"}]})
        self.assertIn("not found", rp.pulse("octo/none", run=runner)["error"])

    def test_gh_failure_is_an_error_entry(self):
        def runner(owner, name, n):
            raise subprocess.CalledProcessError(1, "gh", stderr="HTTP 401: Bad credentials")

        self.assertIn("401", rp.pulse("octo/cat", run=runner)["error"])

    def test_a_bad_name_is_rejected_before_any_call(self):
        runner, calls = self.fake({})
        for bad in ("octo", "octo/cat; rm -rf", "a/b/c", "octo cat/x"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                rp.pulse(bad, run=runner)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
