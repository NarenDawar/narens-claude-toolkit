import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import helpers
import pdf_builder

sys.path.insert(0, str(helpers.REPO_ROOT / "plugins" / "pdf-table-fixer" / "skills" / "pdf-table-fixer" / "scripts"))
if pdf_builder.HAVE_PIKEPDF:
    import tables


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = tables.main(argv)
    return code, out.getvalue(), err.getvalue()


@unittest.skipUnless(pdf_builder.HAVE_PIKEPDF, "pikepdf not installed")
class InspectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "t.pdf"

    def test_text_output_lists_tables_rows_cells_and_problems(self):
        pdf_builder.make_pdf(self.path, [[["Name", "Qty"], ["Apple", "3"]]])
        code, out, _ = run(["inspect", str(self.path)])
        self.assertEqual(code, 0)
        self.assertIn("t1  page 1  2 rows, 4 cells", out)
        self.assertIn('0: TD "Name"', out)
        self.assertIn("no_header", out)

    def test_json_output_has_counts_and_no_private_keys(self):
        pdf_builder.make_pdf(self.path, [[["Name", "Qty"], ["Apple", "3"]]])
        code, out, _ = run(["inspect", str(self.path), "--json"])
        data = json.loads(out)
        t = data["tables"][0]
        self.assertEqual((t["id"], t["rows_count"], t["cells_count"]), ("t1", 2, 4))
        self.assertEqual(t["problems"][0]["code"], "no_header")
        self.assertNotIn("_obj", json.dumps(data))

    def test_long_cell_text_is_cut(self):
        pdf_builder.make_pdf(self.path, [[["x" * 100]]])
        _, out, _ = run(["inspect", str(self.path)])
        self.assertIn("x" * 59 + "…", out)
        self.assertNotIn("x" * 61, out)

    def test_untagged_is_refused_with_exit_2(self):
        pdf_builder.make_pdf(self.path, [[["a"]]], tagged=False)
        code, out, err = run(["inspect", str(self.path)])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("untagged", err)

    def test_pdf_with_no_tables_says_so(self):
        pdf_builder.make_pdf(self.path, [])
        code, out, _ = run(["inspect", str(self.path)])
        self.assertEqual(code, 0)
        self.assertIn("no tables", out)


if __name__ == "__main__":
    unittest.main()
