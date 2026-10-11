import sys
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401  (puts scripts/ on sys.path)
import pdf_builder

SCRIPTS = helpers.REPO_ROOT / "plugins" / "pdf-table-fixer" / "skills" / "pdf-table-fixer" / "scripts"


@unittest.skipUnless(pdf_builder.HAVE_PIKEPDF, "pikepdf not installed")
class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "t.pdf"

    def test_tagged_table_has_rows_and_cells(self):
        import pikepdf
        pdf_builder.make_pdf(self.path, [[["Name", "Qty"], ["Apple", "3"]]])
        pdf = pikepdf.open(self.path)
        table = pdf.Root.StructTreeRoot.K.K[0]
        self.assertEqual(str(table.S), "/Table")
        self.assertEqual(len(table.K), 2)
        self.assertEqual(str(table.K[0].K[0].S), "/TD")
        self.assertEqual(len(pdf.pages), 1)

    def test_untagged_has_no_structure_tree(self):
        import pikepdf
        pdf_builder.make_pdf(self.path, [[["a"]]], tagged=False)
        pdf = pikepdf.open(self.path)
        self.assertNotIn("/StructTreeRoot", pdf.Root)

    def test_encrypted_needs_a_password(self):
        import pikepdf
        pdf_builder.make_pdf(self.path, [[["a"]]], encrypt=True)
        with self.assertRaises(pikepdf.PasswordError):
            pikepdf.open(self.path)

    def test_span_scope_and_headers_are_written(self):
        import pikepdf
        pdf_builder.make_pdf(self.path, [[[{"text": "H", "tag": "TH", "scope": "Column", "colspan": 2, "id": "h1"}],
                                          [{"text": "x", "headers": ["h1"]}]]])
        pdf = pikepdf.open(self.path)
        th = pdf.Root.StructTreeRoot.K.K[0].K[0].K[0]
        self.assertEqual(str(th.A.Scope), "/Column")
        self.assertEqual(int(th.A.ColSpan), 2)
        self.assertEqual(str(th.ID), "h1")
        td = pdf.Root.StructTreeRoot.K.K[0].K[1].K[0]
        self.assertEqual([str(h) for h in td.A.Headers], ["h1"])


if __name__ == "__main__":
    unittest.main()
