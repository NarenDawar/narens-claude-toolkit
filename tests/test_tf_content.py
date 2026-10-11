import sys
import tempfile
import unittest
from pathlib import Path

import helpers
import pdf_builder

sys.path.insert(0, str(helpers.REPO_ROOT / "plugins" / "pdf-table-fixer" / "skills" / "pdf-table-fixer" / "scripts"))
if pdf_builder.HAVE_PIKEPDF:
    import pikepdf
    import tf_content


def _page_with(contents, font=None):
    pdf = pikepdf.new()
    page = pdf.add_blank_page(page_size=(612, 792))
    font = font or pdf.make_indirect(pikepdf.Dictionary(
        Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica))
    page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font))
    page.Contents = pdf.make_stream(contents)
    return pdf, page


@unittest.skipUnless(pdf_builder.HAVE_PIKEPDF, "pikepdf not installed")
class ContentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "t.pdf"

    def test_text_and_position_per_mcid(self):
        pdf_builder.make_pdf(self.path, [[["Name", "Qty"], ["Apple", "3"]]])
        pdf = pikepdf.open(self.path)
        got = tf_content.page_text(pdf.pages[0])
        self.assertEqual(got[0]["text"], "Name")
        self.assertEqual(got[0]["pos"], (72.0, 740.0))
        self.assertEqual(got[3]["text"], "3")
        self.assertEqual(got[3]["pos"], (192.0, 720.0))

    def test_cm_translation_moves_position(self):
        pdf, page = _page_with(
            b"q 1 0 0 1 100 200 cm /P << /MCID 7 >> BDC BT /F1 12 Tf 10 20 Td (Hi) Tj ET EMC Q")
        got = tf_content.page_text(page)
        self.assertEqual(got[7], {"text": "Hi", "pos": (110.0, 220.0)})

    def test_tj_array_joins_strings_and_big_kerns_become_spaces(self):
        pdf, page = _page_with(b"/P << /MCID 0 >> BDC BT /F1 12 Tf [(A) -30 (B) -400 (C)] TJ ET EMC")
        self.assertEqual(tf_content.page_text(page)[0]["text"], "AB C")

    def test_tounicode_bfchar_and_bfrange(self):
        cmap = (b"beginbfchar <0001> <0048> endbfchar\n"
                b"beginbfrange <0002> <0004> <0061> endbfrange")
        got = tf_content.parse_tounicode(cmap)
        self.assertEqual(got[1], "H")
        self.assertEqual([got[2], got[3], got[4]], ["a", "b", "c"])

    def test_undecodable_font_gives_replacement_characters_not_a_crash(self):
        pdf = pikepdf.new()
        font = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type0, BaseFont=pikepdf.Name.X,
            Encoding=pikepdf.Name("/Identity-H")))
        page = pdf.add_blank_page(page_size=(612, 792))
        page.Resources = pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font))
        page.Contents = pdf.make_stream(b"/P << /MCID 0 >> BDC BT /F1 12 Tf <00410042> Tj ET EMC")
        self.assertEqual(tf_content.page_text(page)[0]["text"], "��")


if __name__ == "__main__":
    unittest.main()
