"""Runs the real veraPDF on generated PDFs. Skipped unless veraPDF, Java and pikepdf are all installed."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers
import pdf_builder

sys.path.insert(0, str(helpers.REPO_ROOT / "plugins" / "pdf-table-fixer" / "skills" / "pdf-table-fixer" / "scripts"))
import verapdf_check as v  # noqa: E402

EXE, JAVA = v.find_tools()
READY = bool(EXE and JAVA and pdf_builder.HAVE_PIKEPDF)
if READY:
    import tf_apply


def real_runner(path):
    return subprocess.run([EXE, "--flavour", v.FLAVOUR, "--format", "xml", str(path)],
                          capture_output=True, timeout=300).stdout.decode("utf-8", "replace")


@unittest.skipUnless(READY, "veraPDF, Java or pikepdf not installed")
class LiveVeraPdfTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)

    def table_rules(self, path):
        rep = v.parse_report(real_runner(path))
        return {k for k, r in rep["rules"].items() if r["table"]}

    def test_th_without_scope_is_flagged_and_apply_fixes_it(self):
        src, plan, out = self.d / "in.pdf", self.d / "plan.json", self.d / "out.pdf"
        th = lambda s: {"text": s, "tag": "TH"}
        pdf_builder.make_pdf(src, [[[th("A"), th("B")], ["1", "2"]]])
        self.assertEqual(self.table_rules(src), {("7.5", "1")})
        plan.write_text(json.dumps({"tables": {"t1": {"expect": {"rows": 2, "cells": 4}, "header_rows": 1}}}),
                        encoding="utf-8")
        tf_apply.run_apply(src, plan, out)
        self.assertEqual(self.table_rules(out), set())

    def test_ragged_rows_are_flagged_and_a_span_fixes_them(self):
        src, plan, out = self.d / "in.pdf", self.d / "plan.json", self.d / "out.pdf"
        th = lambda s: {"text": s, "tag": "TH", "scope": "Column"}
        pdf_builder.make_pdf(src, [[[th("A"), th("B")], ["1", "2"], ["3"]]])
        self.assertEqual(self.table_rules(src), {("7.2", "43")})
        plan.write_text(json.dumps({"tables": {"t1": {"expect": {"rows": 3, "cells": 5},
                                                      "spans": [{"row": 2, "cell": 0, "colspan": 2}]}}}),
                        encoding="utf-8")
        tf_apply.run_apply(src, plan, out)
        self.assertEqual(self.table_rules(out), set())

    def test_main_reports_a_real_regression_with_exit_1(self):
        before, after = self.d / "b.pdf", self.d / "a.pdf"
        th = lambda s, **k: dict({"text": s, "tag": "TH"}, **k)
        pdf_builder.make_pdf(before, [[[th("A", scope="Column")], ["1"]]])
        pdf_builder.make_pdf(after, [[[th("A")], ["1"]]])  # the scope is gone
        self.assertEqual(v.main([str(after), "--against", str(before)], runner=real_runner), 1)


if __name__ == "__main__":
    unittest.main()
