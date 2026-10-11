import json
import sys
import tempfile
import unittest
from pathlib import Path

import helpers
import pdf_builder

sys.path.insert(0, str(helpers.REPO_ROOT / "plugins" / "pdf-table-fixer" / "skills" / "pdf-table-fixer" / "scripts"))
if pdf_builder.HAVE_PIKEPDF:
    import tf_plan
    import tf_struct


@unittest.skipUnless(pdf_builder.HAVE_PIKEPDF, "pikepdf not installed")
class PlanTests(unittest.TestCase):
    GRID = [["Name", "Qty"], ["Apple", "3"], ["Pear", "5"]]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "t.pdf"
        self._open = []
        self.addCleanup(self._close_all)

    def _close_all(self):
        for p in self._open:
            p.close()
        self._open = []

    def tables(self, rows, **kw):
        self._close_all()  # an open handle blocks rewriting the file on Windows
        pdf_builder.make_pdf(self.path, [rows], **kw)
        pdf = tf_struct.open_checked(self.path)
        self._open.append(pdf)
        return tf_struct.read_tables(pdf)

    def check(self, rows, tplan, **kw):
        ts = self.tables(rows, **kw)
        if "expect" not in tplan:  # expect is required; tests that are not about it get the right one
            t = ts[0]
            tplan = dict(tplan, expect={"rows": len(t["rows"]), "cells": sum(len(r["cells"]) for r in t["rows"])})
        layouts, errors = tf_plan.check_plan({"tables": {"t1": tplan}}, ts)
        return ts, layouts, errors

    def test_header_row_makes_th_with_column_scope(self):
        ts, layouts, errors = self.check(self.GRID, {"header_rows": 1})
        self.assertEqual(errors, [])
        a = layouts["t1"]["attrs"]
        self.assertEqual((a[(0, 0)]["tag"], a[(0, 0)]["scope"]), ("TH", "Column"))
        self.assertEqual((a[(1, 0)]["tag"], a[(1, 0)]["scope"]), ("TD", None))

    def test_header_row_and_column_give_row_and_both_scope(self):
        _, layouts, errors = self.check(self.GRID, {"header_rows": 1, "header_cols": 1})
        a = layouts["t1"]["attrs"]
        self.assertEqual(a[(0, 0)]["scope"], "Both")
        self.assertEqual(a[(0, 1)]["scope"], "Column")
        self.assertEqual(a[(1, 0)]["scope"], "Row")
        self.assertEqual(a[(1, 1)]["tag"], "TD")

    def test_no_header_keys_leaves_header_kinds_alone(self):
        rows = [[{"text": "Name", "tag": "TH", "scope": "Column"}, "Qty"], ["a", "b"]]
        _, layouts, errors = self.check(rows, {})
        self.assertEqual(errors, [])
        a = layouts["t1"]["attrs"]
        self.assertEqual((a[(0, 0)]["tag"], a[(0, 0)]["scope"], a[(0, 1)]["tag"]), ("TH", "Column", "TD"))

    def test_span_applied_then_grid_checked(self):
        rows = [["Title"], ["a", "b"]]
        _, layouts, errors = self.check(rows, {"spans": [{"row": 0, "cell": 0, "colspan": 2}]})
        self.assertEqual(errors, [])
        self.assertEqual(layouts["t1"]["attrs"][(0, 0)]["colspan"], 2)
        _, _, errors = self.check(rows, {})  # without the span the table is ragged, and a plan may not leave it so
        self.assertTrue(any("ragged_rows" in e for e in errors))

    def test_span_that_overruns_is_an_error(self):
        _, _, errors = self.check(self.GRID, {"spans": [{"row": 2, "cell": 0, "rowspan": 3}]})
        self.assertTrue(any("span_overrun" in e for e in errors))

    def test_bad_span_address_and_values(self):
        _, _, errors = self.check(self.GRID, {"spans": [{"row": 9, "cell": 0, "colspan": 2}]})
        self.assertTrue(any("row 9" in e for e in errors))
        _, _, errors = self.check(self.GRID, {"spans": [{"row": 0, "cell": 0, "colspan": 0}]})
        self.assertTrue(errors)

    def test_header_counts_too_big(self):
        _, _, errors = self.check(self.GRID, {"header_rows": 4})
        self.assertTrue(any("header_rows" in e for e in errors))
        _, _, errors = self.check(self.GRID, {"header_cols": 3})
        self.assertTrue(any("header_cols" in e for e in errors))

    def test_unknown_table_and_unknown_keys(self):
        ts = self.tables(self.GRID)
        _, errors = tf_plan.check_plan({"tables": {"t9": {}}}, ts)
        self.assertTrue(any("t9" in e for e in errors))
        _, errors = tf_plan.check_plan({"tables": {"t1": {"header_row": 1}}}, ts)
        self.assertTrue(any("header_row" in e for e in errors))
        _, errors = tf_plan.check_plan({"stuff": 1}, ts)
        self.assertTrue(errors)

    def test_expect_counts_guard_against_a_plan_for_another_file(self):
        _, _, errors = self.check(self.GRID, {"expect": {"rows": 5, "cells": 10}})
        self.assertTrue(any("expect" in e for e in errors))
        _, _, errors = self.check(self.GRID, {"expect": {"rows": 3, "cells": 6}})
        self.assertEqual(errors, [])

    def test_row_order_must_be_a_permutation_and_keep_sections(self):
        _, _, errors = self.check(self.GRID, {"row_order": [0, 0, 1]})
        self.assertTrue(any("row_order" in e for e in errors))
        _, layouts, errors = self.check(self.GRID, {"row_order": [0, 2, 1]})
        self.assertEqual(errors, [])
        self.assertEqual([r[0] for r in layouts["t1"]["arranged"]], [(0, 0), (2, 0), (1, 0)])
        _, _, errors = self.check(self.GRID, {"row_order": [1, 0, 2]}, sections=True)
        self.assertTrue(any("section" in e for e in errors))

    def test_cell_order_reorders_within_a_row(self):
        _, layouts, errors = self.check(self.GRID, {"cell_order": {"1": [1, 0]}})
        self.assertEqual(errors, [])
        self.assertEqual(layouts["t1"]["arranged"][1], [(1, 1), (1, 0)])

    def test_linked_headers_get_ids_and_dependents_get_headers(self):
        rows = [["A", "B"], ["x", "y"]]
        _, layouts, errors = self.check(rows, {"header_rows": 1, "headers": {"1.0": ["0.0"], "1.1": ["0.1"]}})
        self.assertEqual(errors, [])
        a = layouts["t1"]["attrs"]
        self.assertEqual(a[(0, 0)]["id"], "t1-h0-0")
        self.assertEqual(a[(1, 0)]["headers"], ["t1-h0-0"])

    def test_linked_header_must_be_a_header_cell(self):
        _, _, errors = self.check([["A", "B"], ["x", "y"]], {"header_rows": 1, "headers": {"1.0": ["1.1"]}})
        self.assertTrue(any("not a header" in e for e in errors))

    def test_diff_lists_changes_and_is_empty_when_nothing_changes(self):
        ts, layouts, _ = self.check(self.GRID, {"header_rows": 1})
        lines = tf_plan.diff(ts[0], layouts["t1"])
        self.assertTrue(any("row 0 cell 0" in l and "TD->TH" in l and "Column" in l for l in lines))
        ts, layouts, _ = self.check(self.GRID, {})
        self.assertEqual(tf_plan.diff(ts[0], layouts["t1"]), [])

    def test_expect_is_required(self):
        ts = self.tables(self.GRID)
        _, errors = tf_plan.check_plan({"tables": {"t1": {"header_rows": 1}}}, ts)
        self.assertTrue(any("expect is required" in e for e in errors))

    def test_row_order_across_two_tbody_elements_is_refused(self):
        import pikepdf
        pdf_builder.make_pdf(self.path, [[["H"], ["a"], ["b"]]], sections=True)
        with pikepdf.open(self.path, allow_overwriting_input=True) as pdf:
            table = pdf.Root.StructTreeRoot.K.K[0]
            thead, tbody = table.K[0], table.K[1]
            tr_b = tbody.K[1]
            tbody2 = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.StructElem, S=pikepdf.Name.TBody,
                                                          P=table, K=pikepdf.Array([tr_b])))
            tr_b.P = tbody2
            tbody.K = pikepdf.Array([tbody.K[0]])
            table.K = pikepdf.Array([thead, tbody, tbody2])
            pdf.save(self.path)
        self._close_all()
        pdf = tf_struct.open_checked(self.path)
        self._open.append(pdf)
        ts = tf_struct.read_tables(pdf)
        base = {"expect": {"rows": 3, "cells": 3}}
        _, errors = tf_plan.check_plan({"tables": {"t1": dict(base, row_order=[0, 2, 1])}}, ts)
        self.assertTrue(any("section" in e for e in errors))
        _, errors = tf_plan.check_plan({"tables": {"t1": dict(base, row_order=[0, 1, 2])}}, ts)
        self.assertEqual(errors, [])

    def test_minted_ids_avoid_ids_already_in_the_document(self):
        ts = self.tables([["A", "B"], ["x", "y"]])
        plan = {"tables": {"t1": {"expect": {"rows": 2, "cells": 4}, "header_rows": 1, "headers": {"1.0": ["0.0"]}}}}
        layouts, errors = tf_plan.check_plan(plan, ts, taken={"t1-h0-0"})
        self.assertEqual(errors, [])
        minted = layouts["t1"]["attrs"][(0, 0)]["id"]
        self.assertNotEqual(minted, "t1-h0-0")
        self.assertEqual(layouts["t1"]["attrs"][(1, 0)]["headers"], [minted])

    def test_headers_left_pointing_at_a_demoted_cell_is_an_error_and_can_be_cleared(self):
        rows = [[{"text": "R1", "tag": "TH", "id": "rh1"}, "a"],
                [{"text": "R2", "tag": "TH", "id": "rh2"}, {"text": "b", "headers": ["rh2"]}]]
        _, _, errors = self.check(rows, {"header_rows": 1})
        self.assertTrue(any("no longer" in e and "1.1" in e for e in errors))
        _, _, errors = self.check(rows, {"header_rows": 1, "headers": {"1.1": []}})
        self.assertEqual(errors, [])

    def test_load_plan_rejects_bad_json(self):
        p = Path(self.tmp.name) / "p.json"
        p.write_text("{nope", encoding="utf-8")
        with self.assertRaises(tf_struct.Refusal):
            tf_plan.load_plan(p)
        p.write_text(json.dumps([1]), encoding="utf-8")
        with self.assertRaises(tf_struct.Refusal):
            tf_plan.load_plan(p)


if __name__ == "__main__":
    unittest.main()
