import sys
import tempfile
import unittest
from pathlib import Path

import helpers
import pdf_builder

sys.path.insert(0, str(helpers.REPO_ROOT / "plugins" / "pdf-table-fixer" / "skills" / "pdf-table-fixer" / "scripts"))
if pdf_builder.HAVE_PIKEPDF:
    import tf_problems
    import tf_struct


@unittest.skipUnless(pdf_builder.HAVE_PIKEPDF, "pikepdf not installed")
class ProblemTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "t.pdf"

    def codes(self, table_rows, **kw):
        pdf_builder.make_pdf(self.path, [table_rows], **kw)
        pdf = tf_struct.open_checked(self.path)
        try:
            t = tf_struct.read_tables(pdf)[0]
            return sorted({p["code"] for p in tf_problems.find_problems(t)})
        finally:
            pdf.close()

    def good(self):
        th = lambda s: {"text": s, "tag": "TH", "scope": "Column"}
        return [[th("Name"), th("Qty")], ["Apple", "3"], ["Pear", "5"]]

    def test_clean_table_has_no_problems(self):
        self.assertEqual(self.codes(self.good()), [])

    def test_no_header_cells(self):
        self.assertEqual(self.codes([["Name", "Qty"], ["Apple", "3"]]), ["no_header"])

    def test_single_row_table_is_not_flagged_for_no_header(self):
        self.assertEqual(self.codes([["only", "row"]]), [])

    def test_th_without_scope(self):
        rows = self.good()
        rows[0][1] = {"text": "Qty", "tag": "TH"}
        self.assertEqual(self.codes(rows), ["th_no_scope"])

    def test_th_with_id_or_headers_links_is_not_flagged(self):
        rows = self.good()
        rows[0][1] = {"text": "Qty", "tag": "TH", "id": "q"}
        self.assertEqual(self.codes(rows), [])

    def test_span_overrun_and_ragged(self):
        rows = self.good()
        rows[1][0] = {"text": "Apple", "rowspan": 5}
        self.assertIn("span_overrun", self.codes(rows))
        rows = self.good()
        rows[2] = ["Pear"]
        self.assertEqual(self.codes(rows), ["ragged_rows"])

    def test_rows_out_of_order_by_position(self):
        rows = self.good()
        rows[1] = [{"text": "Apple", "y": 600}, {"text": "3", "y": 600}]
        self.assertIn("rows_out_of_order", self.codes(rows))

    def test_cells_out_of_order_by_position(self):
        rows = self.good()
        rows[1] = [{"text": "Apple", "x": 300}, {"text": "3", "x": 72}]
        self.assertIn("cells_out_of_order", self.codes(rows))

    def test_empty_table(self):
        self.assertEqual(self.codes([]), ["empty_table"])


if __name__ == "__main__":
    unittest.main()
