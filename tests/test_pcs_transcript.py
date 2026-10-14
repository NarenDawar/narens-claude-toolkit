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
import pcs_transcript as t  # noqa: E402


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def write(self, name, data):
        path = self.dir / name
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        return path

    def test_srt_gives_numbered_cues(self):
        cues = t.parse_file(self.write("a.srt", pcs_builder.srt(pcs_builder.sample_cues())))
        self.assertEqual(len(cues), 24)
        self.assertEqual([c["n"] for c in cues], list(range(1, 25)))
        self.assertEqual((cues[2]["start"], cues[2]["end"]), (10.0, 15.0))
        self.assertEqual(cues[2]["text"], "I once lost every customer I had in a single week.")
        self.assertIsNone(cues[2]["speaker"])

    def test_srt_with_bom_and_crlf_parses_the_same(self):
        plain = t.parse_file(self.write("a.srt", pcs_builder.srt(pcs_builder.sample_cues())))
        odd = t.parse_file(
            self.write("b.srt", pcs_builder.srt(pcs_builder.sample_cues(), crlf=True, bom=True))
        )
        self.assertEqual(plain, odd)

    def test_srt_joins_lines_strips_tags_and_unescapes(self):
        text = (
            "1\n00:00:01,000 --> 00:00:04,000\n<i>Hello</i> &amp; welcome\nto the show\n\n"
            "2\n00:00:05,500 --> 00:00:07,250\nSecond.\n"
        )
        cues = t.parse_file(self.write("a.srt", text))
        self.assertEqual(cues[0]["text"], "Hello & welcome to the show")
        self.assertEqual((cues[1]["start"], cues[1]["end"]), (5.5, 7.25))

    def test_vtt_skips_notes_reads_settings_voice_and_short_times(self):
        text = (
            "WEBVTT - demo\n\nNOTE this is a comment\nmore note\n\n"
            "intro\n00:01.000 --> 00:04.000 align:start position:0%\n<v Ana>Hello there.</v>\n\n"
            "00:00:05.000 --> 00:00:08.000\n<c.yellow>Second</c> cue.\n"
        )
        cues = t.parse_file(self.write("a.vtt", text))
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0]["speaker"], "Ana")
        self.assertEqual(cues[0]["text"], "Hello there.")
        self.assertEqual((cues[0]["start"], cues[0]["end"]), (1.0, 4.0))
        self.assertEqual(cues[1]["text"], "Second cue.")
        self.assertIsNone(cues[1]["speaker"])
        self.assertEqual(cues[1]["start"], 5.0)

    def test_json_list_and_whisper_segments_object(self):
        as_list = pcs_builder.json_segments(pcs_builder.sample_cues())
        cues = t.parse_file(self.write("a.json", as_list))
        self.assertEqual(len(cues), 24)
        self.assertEqual(cues[2]["start"], 10.0)
        wrapped = '{"text": "x", "segments": ' + as_list + "}"
        self.assertEqual(t.parse_file(self.write("b.json", wrapped)), cues)

    def test_json_keeps_a_speaker(self):
        text = '[{"start": 0, "end": 2.5, "text": " Hi there. ", "speaker": "Ben"}]'
        cue = t.parse_file(self.write("a.json", text))[0]
        self.assertEqual((cue["speaker"], cue["text"], cue["end"]), ("Ben", "Hi there.", 2.5))

    def test_format_is_sniffed_when_the_extension_says_nothing(self):
        j = t.parse_file(self.write("a.txt", '[{"start": 0, "end": 1, "text": "Hi."}]'))
        v = t.parse_file(self.write("b.txt", pcs_builder.vtt(pcs_builder.sample_cues())))
        s = t.parse_file(self.write("c.txt", pcs_builder.srt(pcs_builder.sample_cues())))
        self.assertEqual((len(j), len(v), len(s)), (1, 24, 24))

    def test_empty_text_cues_are_dropped_and_numbers_stay_consecutive(self):
        text = (
            "1\n00:00:01,000 --> 00:00:02,000\nOne.\n\n"
            "2\n00:00:02,000 --> 00:00:03,000\n<i></i>\n\n"
            "3\n00:00:03,000 --> 00:00:04,000\nThree.\n"
        )
        cues = t.parse_file(self.write("a.srt", text))
        self.assertEqual([(c["n"], c["text"]) for c in cues], [(1, "One."), (2, "Three.")])

    def test_overlapping_cues_are_kept(self):
        text = (
            "1\n00:00:01,000 --> 00:00:05,000\nOne.\n\n"
            "2\n00:00:03,000 --> 00:00:06,000\nTwo.\n"
        )
        self.assertEqual(len(t.parse_file(self.write("a.srt", text))), 2)

    def test_end_before_start_is_an_error(self):
        text = "1\n00:00:05,000 --> 00:00:02,000\nOops.\n"
        with self.assertRaisesRegex(t.TranscriptError, "before"):
            t.parse_file(self.write("a.srt", text))

    def test_a_cue_with_an_unreadable_timing_line_is_an_error_not_a_silent_drop(self):
        text = (
            "1\n00:00:00,000 --> 00:00:10,000\nOne.\n\n"
            "2\n00:00:10,000 -> 00:00:20,000\nTwo has a typo arrow.\n\n"
            "3\n00:00:30,000 --> 00:00:40,000\nThree.\n"
        )
        with self.assertRaisesRegex(t.TranscriptError, "timing"):
            t.parse_file(self.write("a.srt", text))

    def test_a_blank_line_inside_a_cue_is_an_error_not_a_silent_drop(self):
        text = (
            "1\n00:00:00,000 --> 00:00:10,000\nFirst half.\n\nSecond half.\n\n"
            "2\n00:00:10,000 --> 00:00:20,000\nTwo.\n"
        )
        with self.assertRaisesRegex(t.TranscriptError, "timing"):
            t.parse_file(self.write("a.srt", text))

    def test_times_without_milliseconds_are_read(self):
        text = "1\n00:00:20 --> 00:00:30\nNo millis.\n\n2\n00:31 --> 00:40\nShort.\n"
        cues = t.parse_file(self.write("a.srt", text))
        self.assertEqual([(c["start"], c["end"]) for c in cues], [(20.0, 30.0), (31.0, 40.0)])

    def test_a_vtt_header_with_no_blank_line_does_not_swallow_the_first_cue(self):
        text = "WEBVTT\n00:00.000 --> 00:04.000\nFirst.\n\n00:05.000 --> 00:08.000\nSecond.\n"
        cues = t.parse_file(self.write("a.vtt", text))
        self.assertEqual([c["text"] for c in cues], ["First.", "Second."])

    def test_stray_cue_numbers_and_blank_blocks_are_not_errors(self):
        text = "1\n00:00:00,000 --> 00:00:10,000\nOne.\n\n   \n\n2\n"
        self.assertEqual(len(t.parse_file(self.write("a.srt", text))), 1)

    def test_bad_json_shapes_are_errors_not_tracebacks(self):
        bad = [
            "{not json",
            '"just a string"',
            "[1, 2]",
            '[{"start": "0", "end": 1, "text": "x"}]',
            '[{"start": true, "end": 1, "text": "x"}]',
            '[{"start": 0, "end": 1}]',
            '[{"start": 2, "end": 1, "text": "x"}]',
            '[{"start": -1, "end": 1, "text": "x"}]',
            '[{"start": 0, "end": 1e999, "text": "x"}]',
        ]
        for i, text in enumerate(bad):
            with self.subTest(text=text), self.assertRaises(t.TranscriptError):
                t.parse_file(self.write(f"b{i}.json", text))

    def test_unusable_files_are_errors(self):
        with self.assertRaisesRegex(t.TranscriptError, "empty"):
            t.parse_file(self.write("a.srt", "  \n"))
        with self.assertRaisesRegex(t.TranscriptError, "no cues"):
            t.parse_file(self.write("b.txt", "hello world, no timestamps here"))
        with self.assertRaisesRegex(t.TranscriptError, "UTF-8"):
            t.parse_file(self.write("c.srt", b"\xff\xfe\x00bad"))
        with self.assertRaisesRegex(t.TranscriptError, "cannot read"):
            t.parse_file(self.dir / "missing.srt")


class FormatTests(unittest.TestCase):
    def test_fmt_time(self):
        self.assertEqual(t.fmt_time(0), "00:00:00.000")
        self.assertEqual(t.fmt_time(3661.5), "01:01:01.500")
        self.assertEqual(t.fmt_time(59.9996), "00:01:00.000")
        self.assertEqual(t.fmt_time(10.25), "00:00:10.250")


if __name__ == "__main__":
    unittest.main()
