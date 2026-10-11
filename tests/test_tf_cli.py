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


@unittest.skipUnless(pdf_builder.HAVE_PIKEPDF, "pikepdf not installed")
class PlanDiffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "t.pdf"
        self.plan = Path(self.tmp.name) / "plan.json"
        pdf_builder.make_pdf(self.path, [[["Name", "Qty"], ["Apple", "3"]]])

    def test_plan_diff_prints_changes_and_writes_nothing(self):
        before = self.path.read_bytes()
        self.plan.write_text(json.dumps({"tables": {"t1": {"header_rows": 1}}}), encoding="utf-8")
        code, out, _ = run(["plan-diff", str(self.path), "--plan", str(self.plan)])
        self.assertEqual(code, 0)
        self.assertIn("t1", out)
        self.assertIn("TD->TH", out)
        self.assertEqual(self.path.read_bytes(), before)

    def test_bad_plan_exits_2_with_one_line_per_error(self):
        self.plan.write_text(json.dumps({"tables": {"t7": {}}}), encoding="utf-8")
        code, out, err = run(["plan-diff", str(self.path), "--plan", str(self.plan)])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("t7", err)


if __name__ == "__main__":
    unittest.main()
