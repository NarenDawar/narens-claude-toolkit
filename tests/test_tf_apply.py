import json
import sys
import tempfile
import unittest
from pathlib import Path

import helpers
import pdf_builder

sys.path.insert(0, str(helpers.REPO_ROOT / "plugins" / "pdf-table-fixer" / "skills" / "pdf-table-fixer" / "scripts"))
if pdf_builder.HAVE_PIKEPDF:
    import pikepdf
    import tf_apply
    import tf_plan
    import tf_struct


@unittest.skipUnless(pdf_builder.HAVE_PIKEPDF, "pikepdf not installed")
class ApplyTests(unittest.TestCase):
    GRID = [["Name", "Qty"], ["Apple", "3"], ["Pear", "5"]]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = Path(self.tmp.name)
        self.src, self.out, self.plan = d / "in.pdf", d / "out.pdf", d / "plan.json"

    def write_plan(self, tp):
        self.plan.write_text(json.dumps({"tables": {"t1": tp}}), encoding="utf-8")

    def run_apply(self, tp):
        self.write_plan(tp)
        return tf_apply.run_apply(self.src, self.plan, self.out)

    def cells(self, path=None):
        pdf = tf_struct.open_checked(path or self.out)
        try:
            t = tf_struct.read_tables(pdf)[0]
        finally:
            pdf.close()
        return t, [[c for c in r["cells"]] for r in t["rows"]]

    def snap(self, path):
        with pikepdf.open(path) as pdf:
            return tf_apply.snapshot(pdf)

    def test_header_row_is_written_and_input_untouched(self):
        pdf_builder.make_pdf(self.src, [self.GRID])
        before = self.src.read_bytes()
        lines = self.run_apply({"header_rows": 1})
        self.assertEqual(self.src.read_bytes(), before)
        _, cells = self.cells()
        self.assertEqual([(c["tag"], c["scope"]) for c in cells[0]], [("TH", "Column")] * 2)
        self.assertEqual([c["tag"] for c in cells[1]], ["TD", "TD"])
        self.assertTrue(any("t1" in l for l in lines))

    def test_span_scope_row_and_both(self):
        pdf_builder.make_pdf(self.src, [[["Title"], ["a", "b"]]])
        self.run_apply({"header_rows": 1, "header_cols": 0, "spans": [{"row": 0, "cell": 0, "colspan": 2}]})
        _, cells = self.cells()
        self.assertEqual(cells[0][0]["colspan"], 2)
        self.run_apply({"header_rows": 1, "header_cols": 1, "spans": [{"row": 0, "cell": 0, "colspan": 2}]})
        _, cells = self.cells()
        self.assertEqual((cells[0][0]["scope"], cells[1][0]["scope"]), ("Both", "Row"))

    def test_td_span_one_removes_span_keys(self):
        pdf_builder.make_pdf(self.src, [[[{"text": "x", "colspan": 2}, "y"], ["a", "b", "c"]]])
        self.run_apply({"spans": [{"row": 0, "cell": 0, "colspan": 1}, {"row": 0, "cell": 1, "colspan": 2}]})
        _, cells = self.cells()
        self.assertEqual((cells[0][0]["colspan"], cells[0][1]["colspan"]), (1, 2))

    def test_row_and_cell_reorder(self):
        pdf_builder.make_pdf(self.src, [self.GRID])
        self.run_apply({"row_order": [0, 2, 1], "cell_order": {"1": [1, 0]}})
        _, cells = self.cells()
        self.assertEqual([[c["text"] for c in r] for r in cells], [["Name", "Qty"], ["Pear", "5"], ["3", "Apple"]])

    def test_sections_keep_their_layout_when_rows_move_inside_a_section(self):
        pdf_builder.make_pdf(self.src, [[["H"], ["a"], ["b"]]], sections=True)
        self.run_apply({"row_order": [0, 2, 1]})
        t, cells = self.cells()
        self.assertEqual([r["section"] for r in t["rows"]], ["THead", "TBody", "TBody"])
        self.assertEqual([r[0]["text"] for r in cells], ["H", "b", "a"])

    def test_linked_headers_are_written(self):
        pdf_builder.make_pdf(self.src, [[["A", "B"], ["x", "y"]]])
        self.run_apply({"header_rows": 1, "headers": {"1.0": ["0.0"]}})
        _, cells = self.cells()
        self.assertEqual(cells[0][0]["id"], "t1-h0-0")
        self.assertEqual(cells[1][0]["headers"], ["t1-h0-0"])

    def test_page_content_is_byte_identical_and_marked_refs_preserved(self):
        pdf_builder.make_pdf(self.src, [self.GRID])
        a = self.snap(self.src)
        self.run_apply({"header_rows": 1, "row_order": [0, 2, 1]})
        b = self.snap(self.out)
        self.assertEqual(a["content"], b["content"])
        self.assertEqual(a["refs"], b["refs"])
        self.assertEqual(a["pages"], b["pages"])

    def test_check_after_catches_lost_refs_and_changed_content(self):
        pdf_builder.make_pdf(self.src, [self.GRID])
        pdf = pikepdf.open(self.src)
        self.addCleanup(pdf.close)
        before = tf_apply.snapshot(pdf)
        t = tf_struct.read_tables(pdf)[0]
        t["rows"][0]["_obj"].K = pikepdf.Array([])          # drop a row's cells from the tree
        pdf.pages[0].Contents = pdf.make_stream(b"q Q")      # and change the page content
        problems = tf_apply.check_after(before, pdf)
        self.assertTrue(any("marked-content" in p for p in problems))
        self.assertTrue(any("content" in p for p in problems))

    def test_failed_post_check_writes_nothing(self):
        pdf_builder.make_pdf(self.src, [self.GRID])
        orig = tf_apply.apply_layout

        def sabotage(table, layout):
            orig(table, layout)
            table["rows"][0]["_obj"].K = pikepdf.Array([])

        tf_apply.apply_layout = sabotage
        self.addCleanup(setattr, tf_apply, "apply_layout", orig)
        with self.assertRaises(tf_apply.PostCheckFailed):
            self.run_apply({"header_rows": 1})
        self.assertFalse(self.out.exists())
        self.assertEqual([p.name for p in Path(self.tmp.name).iterdir() if p.suffix == ".tmp"], [])

    def test_bad_plan_writes_nothing(self):
        pdf_builder.make_pdf(self.src, [self.GRID])
        with self.assertRaises(tf_struct.Refusal):
            self.run_apply({"header_rows": 9})
        self.assertFalse(self.out.exists())

    def test_out_equal_to_input_is_refused(self):
        pdf_builder.make_pdf(self.src, [self.GRID])
        self.write_plan({"header_rows": 1})
        before = self.src.read_bytes()
        with self.assertRaisesRegex(tf_struct.Refusal, "overwrite"):
            tf_apply.run_apply(self.src, self.plan, self.src)
        self.assertEqual(self.src.read_bytes(), before)

    def test_untagged_and_encrypted_are_refused(self):
        for kw in ({"tagged": False}, {"encrypt": True}):
            pdf_builder.make_pdf(self.src, [self.GRID], **kw)
            with self.assertRaises(tf_struct.Refusal):
                self.run_apply({"header_rows": 1})
            self.assertFalse(self.out.exists())

    def test_signed_is_refused(self):
        pdf_builder.make_pdf(self.src, [self.GRID])
        with pikepdf.open(self.src, allow_overwriting_input=True) as pdf:
            pdf.Root.AcroForm = pikepdf.Dictionary(SigFlags=3, Fields=pikepdf.Array([]))
            pdf.save(self.src)
        with self.assertRaisesRegex(tf_struct.Refusal, "signed"):
            self.run_apply({"header_rows": 1})
        self.assertFalse(self.out.exists())

    def test_nested_table_in_cell_gets_its_own_id(self):
        pdf_builder.make_pdf(self.src, [self.GRID])
        with pikepdf.open(self.src, allow_overwriting_input=True) as pdf:
            outer = tf_struct.read_tables(pdf)[0]
            cell = outer["rows"][1]["cells"][0]["_obj"]
            mk = lambda **kw: pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.StructElem, **kw))
            inner = mk(S=pikepdf.Name.Table, P=cell)
            tr = mk(S=pikepdf.Name.TR, P=inner)
            td = mk(S=pikepdf.Name.TD, P=tr, K=0)
            tr.K, inner.K = pikepdf.Array([td]), pikepdf.Array([tr])
            cell.K = pikepdf.Array([cell.K, inner])
            pdf.save(self.src)
        pdf = tf_struct.open_checked(self.src)
        self.addCleanup(pdf.close)
        self.assertEqual([t["id"] for t in tf_struct.read_tables(pdf)], ["t1", "t2"])


if __name__ == "__main__":
    unittest.main()
