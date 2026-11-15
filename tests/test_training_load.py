import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

import helpers

sys.path.insert(
    0,
    str(helpers.REPO_ROOT / "plugins" / "training-load-watchdog" / "skills" / "training-load-watchdog" / "scripts"),
)
import training_load as tl  # noqa: E402


def run(day, distance, hour=8):
    return {"start": datetime(2024, 1, day, hour), "distance": float(distance), "minutes": None}


STRAVA = (
    "Activity ID,Activity Date,Activity Name,Activity Type,Elapsed Time,Distance,Elapsed Time,Moving Time,Distance\n"
    '1,"Jan 1, 2024, 7:30:00 AM",a,Run,3000,10.0,3000,2900,10000.0\n'
    '2,"Jan 8, 2024, 7:30:00 AM",b,Ride,3000,40.0,3000,2900,40000.0\n'
    '3,"Jan 12, 2024, 7:30:00 AM",c,Run,3000,12.0,3000,2900,12000.0\n'
)
GARMIN = (
    "Activity Type,Date,Distance,Time\n"
    "Running,2024-01-01 07:30:00,5.0,00:30:00\n"
    "Trail Running,2024-01-10 07:30:00,8.0,01:05:10\n"
    "Cycling,2024-01-11 07:30:00,30.0,01:30:00\n"
)


class CategoryTests(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(tl.category(-0.5), "none")
        self.assertEqual(tl.category(0.10), "none")  # up to 10% is the reference group
        self.assertEqual(tl.category(11 / 10 - 1), "none")  # float noise: 0.10000000000000009
        self.assertEqual(tl.category(0.11), "small")
        self.assertEqual(tl.category(0.30), "small")
        self.assertEqual(tl.category(0.31), "moderate")
        self.assertEqual(tl.category(1.0), "moderate")
        self.assertEqual(tl.category(1.01), "large")


class SpikeTests(unittest.TestCase):
    def test_compares_with_the_longest_run_in_the_prior_30_days(self):
        history = [run(1, 10), run(5, 6), run(20, 13)]
        found = tl.spike(history[2], history)
        self.assertEqual((found["longest_prior_30d"], found["category"]), (10.0, "small"))
        self.assertEqual(found["growth_pct"], 30.0)

    def test_a_run_older_than_30_days_does_not_count(self):
        old = {"start": datetime(2023, 12, 1, 8), "distance": 20.0, "minutes": None}
        history = [old, run(5, 6)]
        found = tl.spike(history[1], history)
        self.assertIsNone(found)  # the 20 is 35 days earlier; nothing else to compare with

    def test_the_window_edge_is_inclusive(self):
        old = {"start": datetime(2023, 12, 6, 8), "distance": 20.0, "minutes": None}
        self.assertEqual(tl.spike(run(5, 22), [old])["longest_prior_30d"], 20.0)

    def test_same_day_earlier_run_counts_later_one_does_not(self):
        history = [run(5, 10, hour=7), run(5, 14, hour=18)]
        self.assertEqual(tl.spike(history[1], history)["longest_prior_30d"], 10.0)
        self.assertIsNone(tl.spike(history[0], history))

    def test_no_history_means_no_verdict(self):
        self.assertIsNone(tl.spike(run(5, 10), [run(5, 10)]))


class LoadTests(unittest.TestCase):
    def write(self, text):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "log.csv"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_strava_export_with_repeated_column_names(self):
        runs, notes = tl.load_runs(self.write(STRAVA))
        self.assertEqual([r["distance"] for r in runs], [10.0, 12.0])  # the Ride is ignored
        self.assertEqual(runs[0]["start"], datetime(2024, 1, 1, 7, 30))
        self.assertTrue(any("other activity types" in n for n in notes))

    def test_garmin_export_with_clock_durations(self):
        runs, _ = tl.load_runs(self.write(GARMIN))
        self.assertEqual([r["distance"] for r in runs], [5.0, 8.0])
        self.assertAlmostEqual(runs[1]["minutes"], 65 + 10 / 60)

    def test_types_can_be_changed(self):
        runs, _ = tl.load_runs(self.write(GARMIN), types="cycl")
        self.assertEqual([r["distance"] for r in runs], [30.0])

    def test_duplicate_syncs_are_dropped_once(self):
        text = "date,type,distance\n2024-01-01 08:00:00,Run,5\n2024-01-01 08:00:00,Run,5\n2024-01-02 08:00:00,Run,5\n"
        runs, notes = tl.load_runs(self.write(text))
        self.assertEqual(len(runs), 2)
        self.assertTrue(any("1 duplicate" in n for n in notes))

    def test_unusable_rows_are_counted_not_fatal(self):
        text = "date,type,distance\nnot a date,Run,5\n2024-01-01,Run,abc\n2024-01-02,Run,0\n2024-01-03,Run,5\n"
        runs, notes = tl.load_runs(self.write(text))
        self.assertEqual(len(runs), 1)
        self.assertTrue(any("3 rows" in n for n in notes))

    def test_missing_columns_and_empty_files_are_errors(self):
        for text in ("a,b\n1,2\n", "", "date,type,distance\n"):
            with self.subTest(text=text), self.assertRaises(tl.LogError):
                tl.load_runs(self.write(text))

    def test_a_file_without_a_type_column_keeps_every_row(self):
        runs, _ = tl.load_runs(self.write("date,distance\n2024-01-01,5\n"))
        self.assertEqual(len(runs), 1)


class AnalyzeTests(unittest.TestCase):
    RUNS = [run(1, 10), run(8, 6), run(15, 5), run(22, 14), run(24, 6)]

    def test_spikes_are_listed_with_the_numbers(self):
        out = tl.analyze(self.RUNS, date(2024, 1, 25), days=14)
        self.assertEqual(out["runs_in_window"], 3)
        self.assertEqual([(s["date"], s["category"]) for s in out["spikes"]], [("2024-01-22", "moderate")])
        self.assertEqual(out["longest_run_last_30d"], 14.0)
        self.assertEqual(out["cap_no_spike"], 15.4)

    def test_empty_weeks_are_reported_as_zero(self):
        out = tl.analyze([run(1, 10), run(24, 6)], date(2024, 1, 25))
        weeks = {w["week_of"]: w["runs"] for w in out["recent_weeks"]}
        self.assertEqual(weeks["2024-01-08"], 0)
        self.assertEqual(weeks["2024-01-22"], 1)
        self.assertEqual(len(weeks), 6)

    def test_runs_after_the_as_of_date_are_ignored(self):
        out = tl.analyze(self.RUNS, date(2024, 1, 16))
        self.assertEqual(out["last_run"], "2024-01-15")

    def test_days_since_last_run_and_streak(self):
        out = tl.analyze([run(1, 5), run(2, 5), run(3, 5)], date(2024, 1, 10))
        self.assertEqual((out["days_since_last_run"], out["consecutive_run_days_ending_last_run"]), (7, 3))

    def test_short_history_is_marked(self):
        self.assertTrue(tl.analyze([run(1, 5), run(10, 8)], date(2024, 1, 11))["history_shorter_than_30d"])
        found = tl.analyze([run(1, 5), run(10, 8)], date(2024, 1, 11))["spikes"][0]
        self.assertFalse(found["history_covers_30d"])

    def test_nothing_before_the_as_of_date(self):
        self.assertIn("error", tl.analyze(self.RUNS, date(2023, 1, 1)))


class CheckTests(unittest.TestCase):
    def test_planned_runs_chain_off_each_other(self):
        history = [run(1, 10)]
        plan = [{"date": "2024-01-03", "distance": 12}, {"date": "2024-01-05", "distance": 13}]
        out = tl.check(history, plan, date(2024, 1, 2))
        self.assertEqual([o["category"] for o in out], ["small", "none"])  # 13 vs the planned 12 is +8%

    def test_plan_order_does_not_matter(self):
        plan = [{"date": "2024-01-05", "distance": 13}, {"date": "2024-01-03", "distance": 12}]
        out = tl.check([run(1, 10)], plan, date(2024, 1, 2))
        self.assertEqual([o["date"] for o in out], ["2024-01-03", "2024-01-05"])

    def test_with_no_earlier_run_there_is_no_verdict(self):
        out = tl.check([], [{"date": "2024-01-03", "distance": 12}], date(2024, 1, 2))
        self.assertEqual(out[0]["category"], "no-prior-run")


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "log.csv"
        self.log.write_text("date,type,distance\n2024-01-01 08:00:00,Run,10\n2024-01-20 08:00:00,Run,14\n", encoding="utf-8")

    def cli(self, argv, stdin=""):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.object(sys, "stdin", io.StringIO(stdin)):
            try:
                code = tl.main(argv)
            except SystemExit as exit_:
                code = exit_.code
        return code, out.getvalue(), err.getvalue()

    def test_analyze_prints_json(self):
        code, out, _ = self.cli(["analyze", str(self.log), "--as-of", "2024-01-21"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["result"]["spikes"][0]["category"], "moderate")

    def test_check_reads_a_plan_from_stdin(self):
        plan = json.dumps([{"date": "2024-01-23", "distance": 16}])
        code, out, _ = self.cli(["check", str(self.log), "--as-of", "2024-01-21"], plan)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["result"][0]["category"], "small")

    def test_bad_input_is_a_usage_error(self):
        cases = [
            (["analyze", str(Path(self.tmp.name) / "none.csv")], ""),
            (["analyze", str(self.log), "--as-of", "yesterday"], ""),
            (["analyze", str(self.log), "--types", "("], ""),
            (["check", str(self.log)], "not json"),
            (["check", str(self.log)], "[]"),
            (["check", str(self.log)], '[{"date": "2024-01-23"}]'),
        ]
        for argv, stdin in cases:
            with self.subTest(argv=argv, stdin=stdin):
                self.assertEqual(self.cli(argv, stdin)[0], 2)

    def test_an_unreadable_log_is_a_usage_error(self):
        self.log.write_text("a,b\n1,2\n", encoding="utf-8")
        code, _, err = self.cli(["analyze", str(self.log)])
        self.assertEqual(code, 2)
        self.assertIn("could not read", err)


if __name__ == "__main__":
    unittest.main()
