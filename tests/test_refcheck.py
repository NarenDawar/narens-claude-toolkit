import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers

sys.path.insert(
    0,
    str(helpers.REPO_ROOT / "plugins" / "citation-verifier" / "skills" / "citation-verifier" / "scripts"),
)
import refcheck as rc  # noqa: E402


def work(title, authors, year, doi="10.1/x", venue="Nature", years=None, source="crossref"):
    return {"source": source, "title": title, "authors": [rc.surname(a) for a in authors], "year": year,
            "years": years or [year], "doi": doi, "venue": venue, "url": "https://example.org/" + doi}


WATSON = work("Molecular Structure of Nucleic Acids: A Structure for Deoxyribose Nucleic Acid",
              ["Watson", "Crick"], 1953, "10.1038/171737a0")
REF = {"id": "w", "title": "Molecular structure of nucleic acids: a structure for deoxyribose nucleic acid",
       "authors": ["Watson, J. D.", "Crick, F. H. C."], "year": 1953}


class TextTests(unittest.TestCase):
    def test_surnames_agree_across_formats(self):
        for name in ("van Assen, M.", "Marcel van Assen", "Assen", "VAN ASSEN"):
            self.assertEqual(rc.surname(name), "assen", name)

    def test_title_similarity(self):
        self.assertEqual(rc.title_similarity("Deep Residual Learning!", "deep residual learning"), 1.0)
        self.assertLess(rc.title_similarity("Deep residual learning", "Molecular structure of nucleic acids"), 0.5)
        self.assertEqual(rc.title_similarity("", "x"), 0.0)

    def test_a_subtitle_is_not_a_different_title(self):
        self.assertGreaterEqual(rc.title_similarity("Prospect theory", "Prospect theory: an analysis of decision"), 0.9)

    def test_two_different_subtitles_are_different_works(self):
        self.assertLess(rc.title_similarity("Deep learning: a review", "Deep learning: methods and tools"), 0.9)
        self.assertLess(rc.title_similarity("Deep learning: a review", "Deep learning"), 0.9)


class CompareTests(unittest.TestCase):
    def test_clean_match_has_no_issues(self):
        self.assertEqual(rc.compare(REF, WATSON), ([], []))

    def test_wrong_first_author_and_unknown_author(self):
        issues, _ = rc.compare({**REF, "authors": ["Smith, J."]}, WATSON)
        self.assertIn("first author", issues[0])
        issues, _ = rc.compare({**REF, "authors": ["Watson", "Franklin"]}, WATSON)
        self.assertIn("franklin", issues[0])

    def test_year_is_fine_within_one_and_against_any_year_the_record_holds(self):
        self.assertEqual(rc.compare({**REF, "year": 1954}, WATSON)[0], [])
        old = work("T", ["Watson"], 2000, years=[2000, 1979])  # a digitised record that is dated later
        self.assertEqual(rc.compare({**REF, "authors": ["Watson"], "year": 1979}, old)[0], [])
        self.assertIn("year", rc.compare({**REF, "year": 1963}, WATSON)[0][0])

    def test_a_different_venue_is_only_a_note(self):
        issues, notes = rc.compare({**REF, "venue": "Science"}, WATSON)
        self.assertEqual(issues, [])
        self.assertIn("venue", notes[0])
        self.assertEqual(rc.compare({**REF, "venue": "Nature Reviews"}, WATSON)[1], [])


class CheckOneTests(unittest.TestCase):
    def run_check(self, ref, doi_result=None, found=()):
        return rc.check_one(ref, lookup_doi=lambda doi: doi_result, lookup_search=lambda r: list(found))

    def test_verified_by_doi(self):
        out = self.run_check({**REF, "doi": "10.1038/171737a0"}, WATSON)
        self.assertEqual((out["status"], out["issues"]), ("verified", []))

    def test_a_doi_that_belongs_to_another_work_is_a_mismatch_not_a_pass(self):
        other = work("Deep Residual Learning for Image Recognition", ["He"], 2016, "10.1109/x")
        out = self.run_check({**REF, "doi": "10.1109/x"}, other)
        self.assertEqual(out["status"], "doi-mismatch")
        self.assertEqual(out["doi_belongs_to"]["title"], other["title"])

    def test_a_doi_with_no_record_falls_back_to_a_title_search(self):
        out = self.run_check({**REF, "doi": "10.1/none"}, None, [WATSON])
        self.assertEqual(out["status"], "verified")

    def test_a_doi_with_no_record_and_no_title_match_says_so(self):
        out = self.run_check({**REF, "doi": "10.1/none"}, None, [])
        self.assertEqual(out["status"], "doi-not-found")

    def test_verified_by_title_search(self):
        self.assertEqual(self.run_check(REF, found=[WATSON])["status"], "verified")

    def test_wrong_year_is_reported_with_what_was_found(self):
        out = self.run_check({**REF, "year": 1963}, found=[WATSON])
        self.assertEqual(out["status"], "metadata-mismatch")
        self.assertIn("1953", out["issues"][0])

    def test_among_records_with_one_title_the_best_fit_wins(self):
        reprint = work(WATSON["title"], ["Watson", "Crick"], 1974, "10.1/reprint")
        out = self.run_check(REF, found=[reprint, WATSON])
        self.assertEqual(out["matched"]["doi"], "10.1038/171737a0")

    def test_no_match_is_not_found_with_the_closest_record_shown(self):
        near = work("Loss aversion in politics", ["Smith"], 2019)
        out = self.run_check({"id": "x", "title": "Loss aversion in sequential gambles"}, found=[near])
        self.assertEqual(out["status"], "not-found")
        self.assertEqual(out["closest"]["title"], "Loss aversion in politics")

    def test_nothing_to_check_and_lookup_failures_are_errors_not_crashes(self):
        self.assertEqual(rc.check_one({"id": "x"})["status"], "error")

        def boom(ref):
            raise rc.LookupError_("network down")

        out = rc.check_one(REF, lookup_search=boom)
        self.assertEqual((out["status"], out["issues"]), ("error", ["network down"]))

    def test_the_title_match_alone_never_passes_a_wrong_first_author(self):
        out = self.run_check({**REF, "authors": ["Smith, J."]}, found=[WATSON])
        self.assertEqual(out["status"], "metadata-mismatch")


class SearchTests(unittest.TestCase):
    def test_openalex_failure_degrades_to_crossref_with_a_note(self):
        crossref = {"message": {"items": [{"title": ["T"], "DOI": "10.1/a", "author": [{"family": "Smith"}],
                                          "issued": {"date-parts": [[2019]]}}]}}

        def fake(url, tries=2):
            if "crossref" in url:
                return crossref
            raise rc.LookupError_("HTTP 429")

        ref = {"title": "T", "authors": ["Smith"]}
        with mock.patch.object(rc, "get_json", fake):
            found = rc.search(ref)
        self.assertEqual(len(found), 1)
        self.assertIn("OpenAlex unavailable", ref["_notes"][0])

    def test_both_sources_failing_raises(self):
        with mock.patch.object(rc, "get_json", side_effect=rc.LookupError_("down")):
            with self.assertRaises(rc.LookupError_):
                rc.search({"title": "T"})


class QuoteTests(unittest.TestCase):
    SOURCE = "We found that a single session 10% longer than the longest run\nin the prior 30 days raised risk."

    def test_statuses(self):
        out = rc.quote_check(self.SOURCE, [
            {"id": "a", "quote": "a single session 10% longer than the longest run in the prior 30 days"},
            {"id": "b", "quote": "a single session 30% longer than the longest run in the prior 30 days"},
            {"id": "c", "quote": "raised risk"},
        ])
        self.assertEqual([r["status"] for r in out], ["ok", "not-found", "too-short"])


class AbstractTests(unittest.TestCase):
    def test_the_inverted_index_is_put_back_in_order(self):
        reply = {"abstract_inverted_index": {"world": [1], "Hello": [0], "again": [2]}}
        with mock.patch.object(rc, "openalex_get", return_value=reply):
            self.assertEqual(rc.abstract_of("10.1/x"), "Hello world again")
        with mock.patch.object(rc, "openalex_get", return_value=None):
            self.assertIsNone(rc.abstract_of("10.1/x"))


class CliTests(unittest.TestCase):
    def cli(self, argv, stdin=""):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.object(sys, "stdin", io.StringIO(stdin)):
            try:
                code = rc.main(argv)
            except SystemExit as exit_:
                code = exit_.code
        return code, out.getvalue(), err.getvalue()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def path(self, name, text):
        p = Path(self.tmp.name) / name
        p.write_text(text, encoding="utf-8")
        return str(p)

    def test_check_prints_a_summary(self):
        refs = self.path("r.json", json.dumps([REF]))
        with mock.patch.object(rc, "search", return_value=[WATSON]):
            code, out, _ = self.cli(["check", refs])
        self.assertEqual((code, json.loads(out)["summary"]), (0, {"verified": 1}))

    def test_quote_exit_codes(self):
        src = self.path("s.txt", QuoteTests.SOURCE)
        good = json.dumps([{"id": "a", "quote": "the longest run in the prior 30 days raised risk"}])
        bad = json.dumps([{"id": "a", "quote": "this sentence is not in the source at all"}])
        self.assertEqual(self.cli(["quote", src], good)[0], 0)
        self.assertEqual(self.cli(["quote", src], bad)[0], 1)

    def test_bad_input_is_a_usage_error(self):
        self.assertEqual(self.cli(["check", self.path("r.json", "not json")])[0], 2)
        self.assertEqual(self.cli(["check", self.path("r.json", "{}")])[0], 2)
        self.assertEqual(self.cli(["check", str(Path(self.tmp.name) / "none.json")])[0], 2)
        self.assertEqual(self.cli(["quote", self.path("s.txt", "x")], "nope")[0], 2)

    def test_a_dead_network_is_reported_not_a_traceback(self):
        with mock.patch.object(rc, "abstract_of", side_effect=rc.LookupError_("offline")):
            code, _, err = self.cli(["abstract", "10.1/x"])
        self.assertEqual(code, 2)
        self.assertIn("lookup failed", err)


if __name__ == "__main__":
    unittest.main()
