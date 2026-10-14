import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

import helpers
import pcs_builder

sys.path.insert(
    0,
    str(helpers.REPO_ROOT / "plugins" / "podcast-clip-scout" / "skills" / "podcast-clip-scout" / "scripts"),
)
import pcs_export as x  # noqa: E402


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.cues = pcs_builder.cue_dicts()

    def test_rows_carry_times_derived_from_the_cues(self):
        rows = x.build_rows(self.cues, pcs_builder.ideal_picks())
        self.assertEqual([r["rank"] for r in rows], [1, 2])
        self.assertEqual((rows[0]["start"], rows[0]["end"]), ("00:00:10.000", "00:00:40.000"))
        self.assertEqual(rows[0]["duration_seconds"], 30.0)
        self.assertEqual((rows[1]["start_cue"], rows[1]["end_cue"]), (12, 17))
        self.assertEqual(rows[1]["scores"]["hook"], 2)

    def test_writes_csv_and_json_into_a_new_nested_folder(self):
        out = self.dir / "a" / "b"
        csv_path, json_path = x.write_export(self.cues, pcs_builder.ideal_picks(), out)
        self.assertEqual((csv_path.name, json_path.name), ("clips.csv", "clips.json"))
        with open(csv_path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(list(rows[0]), x.CSV_COLUMNS)
        self.assertEqual(rows[0]["start"], "00:00:10.000")
        self.assertEqual(rows[0]["total"], "12")
        self.assertEqual(rows[1]["caption"], "Stop guessing. Call ten users a week and shut up.")
        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(data["clips"][0]["reasons"]["hook"], "first: hook")

    def test_csv_starts_with_a_utf8_bom_so_excel_reads_non_ascii_captions(self):
        csv_path, json_path = x.write_export(self.cues, pcs_builder.ideal_picks(), self.dir)
        self.assertTrue(csv_path.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertFalse(json_path.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_json_uses_lf_line_endings(self):
        _, json_path = x.write_export(self.cues, pcs_builder.ideal_picks(), self.dir)
        self.assertNotIn(b"\r\n", json_path.read_bytes())

    def test_a_caption_cannot_become_a_spreadsheet_formula(self):
        picks = pcs_builder.ideal_picks()
        picks["clips"][0]["caption"] = "=HYPERLINK(\"http://example.com\")"
        picks["clips"][1]["caption"] = "-1+1"
        csv_path, json_path = x.write_export(self.cues, picks, self.dir)
        with open(csv_path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        self.assertTrue(rows[0]["caption"].startswith("'="))
        self.assertTrue(rows[1]["caption"].startswith("'-"))
        self.assertEqual(
            json.loads(json_path.read_text(encoding="utf-8"))["clips"][0]["caption"],
            "=HYPERLINK(\"http://example.com\")",
        )

    def test_non_ascii_captions_survive(self):
        picks = pcs_builder.ideal_picks()
        picks["clips"][0]["caption"] = "café — 日本語"
        csv_path, _ = x.write_export(self.cues, picks, self.dir)
        with open(csv_path, newline="", encoding="utf-8-sig") as fh:
            self.assertEqual(list(csv.DictReader(fh))[0]["caption"], "café — 日本語")

    def test_an_output_path_that_is_a_file_raises_oserror(self):
        blocker = self.dir / "file.txt"
        blocker.write_text("x", encoding="utf-8")
        with self.assertRaises(OSError):
            x.write_export(self.cues, pcs_builder.ideal_picks(), blocker)


if __name__ == "__main__":
    unittest.main()
