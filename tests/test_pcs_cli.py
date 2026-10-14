import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import helpers
import pcs_builder

SCRIPT = (
    helpers.REPO_ROOT / "plugins" / "podcast-clip-scout" / "skills" / "podcast-clip-scout" / "scripts" / "clips.py"
)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.srt = self.write("ep.srt", pcs_builder.srt(pcs_builder.sample_cues()))
        self.picks = self.write("picks.json", json.dumps(pcs_builder.ideal_picks()))

    def write(self, name, text):
        path = self.dir / name
        path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
        return path

    def run_cli(self, *args):
        r = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True)
        return r.returncode, r.stdout.decode("utf-8"), r.stderr.decode("utf-8")

    def test_cues_prints_numbered_timestamped_lines(self):
        code, out, _ = self.run_cli("cues", self.srt)
        lines = out.splitlines()
        self.assertEqual(code, 0)
        self.assertEqual(len(lines), 24)
        self.assertEqual(lines[2], "    3  00:00:10.000  I once lost every customer I had in a single week.")

    def test_cues_range_and_clipping(self):
        code, out, _ = self.run_cli("cues", self.srt, "--from", "3", "--to", "4")
        self.assertEqual((code, len(out.splitlines())), (0, 2))
        code, out, _ = self.run_cli("cues", self.srt, "--from", "23", "--to", "99")
        self.assertEqual((code, len(out.splitlines())), (0, 2))
        for bad in (("--from", "0"), ("--from", "30"), ("--from", "5", "--to", "2")):
            code, _, err = self.run_cli("cues", self.srt, *bad)
            self.assertEqual(code, 2, bad)
            self.assertIn("error:", err)

    def test_cues_shows_speakers_and_survives_non_ascii_text(self):
        vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n<v Ana>café — 日本語</v>\n"
        code, out, _ = self.run_cli("cues", self.write("a.vtt", vtt))
        self.assertEqual(code, 0)
        self.assertIn("[Ana] café — 日本語", out)

    def test_unreadable_transcripts_exit_2(self):
        for name, data in (("e.srt", ""), ("b.srt", b"\xff\xfe\x00"), ("n.txt", "no timestamps")):
            code, _, err = self.run_cli("cues", self.write(name, data))
            self.assertEqual(code, 2, name)
            self.assertIn("error:", err)
        code, _, err = self.run_cli("cues", self.dir / "missing.srt")
        self.assertEqual(code, 2)

    def test_check_passes_the_ideal_picks_with_no_warnings(self):
        code, out, _ = self.run_cli("check", self.srt, "--picks", self.picks)
        self.assertEqual(code, 0)
        self.assertIn("ok: 2 clips (0 warning(s))", out)
        self.assertNotIn("WARN", out)

    def test_check_exits_1_and_lists_every_problem(self):
        bad = pcs_builder.ideal_picks()
        bad["clips"][0]["total"] = 99
        bad["clips"][1]["caption"] = ""
        code, out, _ = self.run_cli("check", self.srt, "--picks", self.write("bad.json", json.dumps(bad)))
        self.assertEqual(code, 1)
        self.assertIn("ERROR clip 1: total is 99", out)
        self.assertIn("ERROR clip 2: caption is missing", out)
        self.assertIn("2 error(s), 0 warning(s)", out)

    def test_check_prints_warnings_but_exits_0(self):
        picks = pcs_builder.ideal_picks()
        picks["clips"] = [dict(picks["clips"][0], start_cue=6, end_cue=11)]
        code, out, _ = self.run_cli("check", self.srt, "--picks", self.write("w.json", json.dumps(picks)))
        self.assertEqual(code, 0)
        self.assertIn("WARN clip 1: starts mid-sentence", out)

    def test_check_length_options(self):
        code, _, _ = self.run_cli("check", self.srt, "--picks", self.picks, "--min", "40")
        self.assertEqual(code, 1)
        code, _, _ = self.run_cli("check", self.srt, "--picks", self.picks, "--min", "10", "--max", "30")
        self.assertEqual(code, 0)

    def test_bad_arguments_and_bad_picks_files_exit_2(self):
        cases = [
            ("check", self.srt, "--picks", self.dir / "missing.json"),
            ("check", self.srt, "--picks", self.write("junk.json", "{nope")),
            ("check", self.srt, "--picks", self.write("list.json", "[1]")),
            ("check", self.srt, "--picks", self.picks, "--min", "50", "--max", "10"),
            ("check", self.srt, "--picks", self.picks, "--min", "-1"),
            ("check", self.srt, "--picks", self.picks, "--max-caption", "0"),
            ("check", self.srt),
            ("nonsense",),
            (),
        ]
        for args in cases:
            code, _, _ = self.run_cli(*args)
            self.assertEqual(code, 2, args)

    def test_export_writes_both_files_after_a_clean_check(self):
        out_dir = self.dir / "out" / "deep"
        code, out, _ = self.run_cli("export", self.srt, "--picks", self.picks, "--out", out_dir)
        self.assertEqual(code, 0)
        self.assertTrue((out_dir / "clips.csv").is_file())
        self.assertTrue((out_dir / "clips.json").is_file())
        self.assertIn("wrote", out)

    def test_export_of_invalid_picks_writes_nothing_and_creates_no_folder(self):
        bad = pcs_builder.ideal_picks()
        bad["clips"][0]["scores"]["hook"] = 9
        out_dir = self.dir / "never"
        code, out, _ = self.run_cli(
            "export", self.srt, "--picks", self.write("bad.json", json.dumps(bad)), "--out", out_dir
        )
        self.assertEqual(code, 1)
        self.assertIn("ERROR", out)
        self.assertFalse(out_dir.exists())

    def test_export_to_a_path_that_is_a_file_exits_2(self):
        blocker = self.write("blocker.txt", "x")
        code, _, err = self.run_cli("export", self.srt, "--picks", self.picks, "--out", blocker)
        self.assertEqual(code, 2)
        self.assertIn("error:", err)

    def test_the_whole_flow_works_from_vtt_and_json_transcripts_too(self):
        vtt = self.write("ep.vtt", pcs_builder.vtt(pcs_builder.sample_cues()))
        js = self.write("ep.json", pcs_builder.json_segments(pcs_builder.sample_cues()))
        for source in (vtt, js):
            code, out, _ = self.run_cli("check", source, "--picks", self.picks)
            self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
