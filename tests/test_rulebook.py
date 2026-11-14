import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers

sys.path.insert(
    0,
    str(helpers.REPO_ROOT / "plugins" / "rules-referee" / "skills" / "rules-referee" / "scripts"),
)
import rulebook as rb  # noqa: E402

PAGES = [
    "Components\n1 rules booklet\n110 train cards",
    "If you want to draw a face up locomotive, it must be the first train card you draw this turn\n"
    "and you cannot then draw a second card.",
    "4.Shufflethetraincardsanddealastartinghandof4cardstoeach player .",
    "",
]


def pdf_bytes(pages):
    """A small valid PDF with one line of text per page."""
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", None, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for text in pages:
        page_id = len(objs) + 1
        kids.append(f"{page_id} 0 R")
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 72 700 Td ({safe}) Tj ET".encode("latin-1")
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {page_id + 1} 0 R >>".encode()
        )
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>".encode()
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


class CompactTests(unittest.TestCase):
    def test_spacing_case_punctuation_and_hyphens_do_not_matter(self):
        self.assertEqual(rb.compact("Draw a  “face-up”\nlocomotive."), rb.compact("draw a face up locomotive"))

    def test_words_still_have_to_match(self):
        self.assertNotEqual(rb.compact("draw two cards"), rb.compact("draw three cards"))


class InfoTests(unittest.TestCase):
    def test_pages_without_a_text_layer_are_listed(self):
        report = rb.info(PAGES)
        self.assertEqual(report["pages"], 4)
        self.assertEqual(report["pages_without_text"], [4])
        self.assertEqual(len(report["characters_per_page"]), 4)


class FindTests(unittest.TestCase):
    def test_pages_with_more_terms_rank_first(self):
        hits = rb.find(PAGES, ["locomotive", "second card"])
        self.assertEqual([h["page"] for h in hits], [2])
        self.assertEqual(hits[0]["matched"], 2)
        self.assertIn("first train card", hits[0]["terms"]["locomotive"])

    def test_a_term_on_a_page_that_lost_its_spaces_is_still_found(self):
        hit = rb.find(PAGES, ["train cards"])[0] if rb.find(PAGES, ["train cards"])[0]["page"] == 1 else None
        pages = {h["page"]: h for h in rb.find(PAGES, ["shuffle the train cards"])}
        self.assertIsNone(pages[3]["terms"]["shuffle the train cards"])
        self.assertIsNotNone(hit)

    def test_no_match_returns_nothing(self):
        self.assertEqual(rb.find(PAGES, ["castle"]), [])


class VerifyTests(unittest.TestCase):
    QUOTE = "it must be the first train card you draw this turn and you cannot then draw a second card"

    def status(self, page, quote):
        return rb.verify(PAGES, [{"page": page, "quote": quote}])[0]

    def test_a_real_quote_on_the_cited_page_is_ok(self):
        self.assertEqual(self.status(2, self.QUOTE)["status"], "ok")

    def test_a_quote_cited_to_the_wrong_page_says_where_it_is(self):
        result = self.status(1, self.QUOTE)
        self.assertEqual((result["status"], result["found_on"]), ("wrong-page", [2]))

    def test_a_quote_that_is_not_in_the_book_is_not_found(self):
        self.assertEqual(self.status(2, "you may then draw a third card from the deck")["status"], "not-found")

    def test_a_reworded_quote_is_not_found(self):
        self.assertEqual(self.status(2, self.QUOTE.replace("cannot", "may not"))["status"], "not-found")

    def test_a_very_short_quote_proves_nothing(self):
        self.assertEqual(self.status(2, "draw a second card")["status"], "too-short")

    def test_a_page_out_of_range_is_searched_everywhere(self):
        self.assertEqual(self.status(99, self.QUOTE)["status"], "no-page")
        self.assertEqual(self.status(99, self.QUOTE)["found_on"], [2])

    def test_a_quote_with_no_page_says_where_it_is_but_is_not_ok(self):
        result = self.status(None, self.QUOTE)
        self.assertEqual((result["status"], result["found_on"]), ("no-page", [2]))


class CliTests(unittest.TestCase):
    def run_cli(self, argv, stdin=""):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.object(sys, "stdin", io.StringIO(stdin)), \
                mock.patch.object(rb, "load_pages", return_value=PAGES):
            try:
                code = rb.main(argv)
            except SystemExit as exit_:
                code = exit_.code
        return code, out.getvalue(), err.getvalue()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.book = Path(self.tmp.name) / "book.pdf"
        self.book.write_bytes(b"%PDF-1.4")

    def tearDown(self):
        self.tmp.cleanup()

    def test_verify_exits_0_when_every_quote_is_ok(self):
        body = json.dumps([{"page": 2, "quote": VerifyTests.QUOTE}])
        code, out, _ = self.run_cli(["verify", str(self.book)], body)
        self.assertEqual((code, json.loads(out)[0]["status"]), (0, "ok"))

    def test_verify_exits_1_when_a_quote_fails(self):
        body = json.dumps([{"page": 2, "quote": "an invented rule that is nowhere in the book"}])
        code, out, _ = self.run_cli(["verify", str(self.book)], body)
        self.assertEqual((code, json.loads(out)[0]["status"]), (1, "not-found"))

    def test_bad_json_on_stdin_is_a_usage_error(self):
        code, _, err = self.run_cli(["verify", str(self.book)], "not json")
        self.assertEqual(code, 2)
        self.assertIn("JSON list", err)

    def test_a_missing_file_is_a_usage_error(self):
        code, _, err = self.run_cli(["info", str(Path(self.tmp.name) / "none.pdf")])
        self.assertEqual(code, 2)
        self.assertIn("no such file", err)

    def test_find_needs_a_term(self):
        self.assertEqual(self.run_cli(["find", str(self.book)])[0], 2)

    def test_page_prints_the_text_of_the_pages_asked_for(self):
        code, out, _ = self.run_cli(["page", str(self.book), "2", "1"])
        self.assertEqual(code, 0)
        self.assertLess(out.index("=== page 2 ==="), out.index("=== page 1 ==="))
        self.assertIn("you cannot then draw a second card", out)

    def test_page_rejects_numbers_outside_the_book(self):
        for bad in (["0"], ["5"], ["two"], ["2", "9"]):
            with self.subTest(bad=bad):
                self.assertEqual(self.run_cli(["page", str(self.book), *bad])[0], 2)
        self.assertEqual(self.run_cli(["page", str(self.book)])[0], 2)


@unittest.skipUnless(
    shutil.which("pdftotext") or __import__("importlib").util.find_spec("pypdf"), "no PDF text reader installed"
)
class RealPdfTests(unittest.TestCase):
    def test_pages_are_read_in_order_and_quotes_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = Path(tmp) / "book.pdf"
            book.write_bytes(pdf_bytes(["Setup: deal four cards to each player and place the deck in the middle", "Players may never trade cards with anyone"]))
            pages = rb.load_pages(str(book))
            self.assertEqual(len(pages), 2)
            result = rb.verify(pages, [{"page": 2, "quote": "Players may never trade cards with anyone"}])
            self.assertEqual(result[0]["status"], "ok")
            self.assertEqual(rb.info(pages)["pages_without_text"], [])


if __name__ == "__main__":
    unittest.main()
