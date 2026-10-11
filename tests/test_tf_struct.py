import sys
import tempfile
import unittest
from pathlib import Path

import helpers
import pdf_builder

sys.path.insert(0, str(helpers.REPO_ROOT / "plugins" / "pdf-table-fixer" / "skills" / "pdf-table-fixer" / "scripts"))
if pdf_builder.HAVE_PIKEPDF:
    import pikepdf
    import tf_struct


class GridTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not pdf_builder.HAVE_PIKEPDF:
            raise unittest.SkipTest("pikepdf not installed")

    def test_plain_grid(self):
        place, width, probs = tf_struct.layout_grid([[(1, 1), (1, 1)], [(1, 1), (1, 1)]])
        self.assertEqual((width, probs), (2, []))
        self.assertEqual(place[(1, 1)], (1, 1))

    def test_rowspan_pushes_next_cell_right(self):
        place, width, probs = tf_struct.layout_grid([[(2, 1), (1, 1)], [(1, 1)]])
        self.assertEqual(place[(1, 0)], (1, 1))
        self.assertEqual((width, probs), (2, []))

    def test_colspan_header(self):
        _, width, probs = tf_struct.layout_grid([[(1, 2)], [(1, 1), (1, 1)]])
        self.assertEqual((width, probs), (2, []))

    def test_overrun_overlap_ragged_and_bad_span(self):
        codes = lambda s: sorted({p[0] for p in tf_struct.layout_grid(s)[2]})
        self.assertIn("span_overrun", codes([[(3, 1)], [(1, 1)]]))  # the overrun also shifts row 1, so it is ragged too
        self.assertIn("span_overlap", codes([[(1, 1), (2, 1)], [(1, 2)]]))
        self.assertEqual(codes([[(1, 1), (1, 1)], [(1, 1)]]), ["ragged_rows"])
        self.assertIn("bad_span", codes([[(0, 1)]]))


@unittest.skipUnless(pdf_builder.HAVE_PIKEPDF, "pikepdf not installed")
class ReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "t.pdf"

    def read(self, tables, **kw):
        pdf_builder.make_pdf(self.path, tables, **kw)
        self.pdf = tf_struct.open_checked(self.path)
        self.addCleanup(self.pdf.close)
        return tf_struct.read_tables(self.pdf)

    def test_reads_ids_text_cells_and_page(self):
        t = self.read([[["Name", "Qty"], ["Apple", "3"]], [["x"]]])
        self.assertEqual([x["id"] for x in t], ["t1", "t2"])
        self.assertEqual(t[0]["page"], 1)
        self.assertEqual([c["text"] for c in t[0]["rows"][1]["cells"]], ["Apple", "3"])
        self.assertEqual(t[0]["rows"][0]["cells"][0]["tag"], "TD")

    def test_reads_scope_spans_ids_and_headers(self):
        t = self.read([[[{"text": "H", "tag": "TH", "scope": "Column", "colspan": 2, "id": "h1"}],
                        [{"text": "a", "headers": ["h1"]}, "b"]]])
        h = t[0]["rows"][0]["cells"][0]
        self.assertEqual((h["tag"], h["scope"], h["colspan"], h["rowspan"], h["id"]), ("TH", "Column", 2, 1, "h1"))
        self.assertEqual(t[0]["rows"][1]["cells"][0]["headers"], ["h1"])

    def test_sections_are_flattened_with_labels(self):
        t = self.read([[["H"], ["a"], ["b"]]], sections=True)
        self.assertEqual([r["section"] for r in t[0]["rows"]], ["THead", "TBody", "TBody"])

    def test_rolemap_custom_tag_reads_as_td(self):
        t = self.read([[[{"text": "x", "tag": "Cell"}]]], rolemap={"Cell": "TD"})
        self.assertEqual(t[0]["rows"][0]["cells"][0]["tag"], "TD")

    def test_public_drops_private_keys(self):
        t = self.read([[["a"]]])
        pub = tf_struct.public(t[0])
        self.assertNotIn("_obj", pub)
        self.assertNotIn("_obj", pub["rows"][0])
        self.assertNotIn("_obj", pub["rows"][0]["cells"][0])

    def test_marked_refs(self):
        self.read([[["a", "b"]]])
        self.assertEqual(tf_struct.marked_refs(self.pdf), {(0, 0), (0, 1)})

    def test_table_attrs_create_adds_a_table_owner_dictionary(self):
        t = self.read([[["a"]]])
        cell = t[0]["rows"][0]["cells"][0]["_obj"]
        self.assertIsNone(tf_struct.table_attrs(cell))
        a = tf_struct.table_attrs(cell, create=True)
        self.assertEqual(str(a.O), "/Table")


@unittest.skipUnless(pdf_builder.HAVE_PIKEPDF, "pikepdf not installed")
class RefusalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "t.pdf"

    def test_untagged_is_refused(self):
        pdf_builder.make_pdf(self.path, [[["a"]]], tagged=False)
        with self.assertRaisesRegex(tf_struct.Refusal, "untagged"):
            tf_struct.open_checked(self.path)

    def test_encrypted_is_refused(self):
        pdf_builder.make_pdf(self.path, [[["a"]]], encrypt=True)
        with self.assertRaisesRegex(tf_struct.Refusal, "encrypted"):
            tf_struct.open_checked(self.path)

    def test_missing_and_garbage_are_refused(self):
        with self.assertRaisesRegex(tf_struct.Refusal, "cannot open"):
            tf_struct.open_checked(Path(self.tmp.name) / "nope.pdf")
        self.path.write_bytes(b"not a pdf")
        with self.assertRaisesRegex(tf_struct.Refusal, "cannot open"):
            tf_struct.open_checked(self.path)

    def test_signed_is_refused_only_for_writing(self):
        pdf_builder.make_pdf(self.path, [[["a"]]])
        pdf = pikepdf.open(self.path, allow_overwriting_input=True)
        pdf.Root.AcroForm = pikepdf.Dictionary(SigFlags=3, Fields=pikepdf.Array([]))
        pdf.save(self.path)
        pdf.close()
        tf_struct.open_checked(self.path).close()
        with self.assertRaisesRegex(tf_struct.Refusal, "signed"):
            tf_struct.open_checked(self.path, for_write=True)


if __name__ == "__main__":
    unittest.main()
