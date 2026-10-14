import copy
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
import pcs_picks as p  # noqa: E402


def good(index=0, **over):
    clip = copy.deepcopy(pcs_builder.ideal_picks()["clips"][index])
    clip.update(over)
    return clip


def run(clips, cues=None, **kw):
    return p.check(cues or pcs_builder.cue_dicts(), {"clips": clips}, **kw)


class CheckTests(unittest.TestCase):
    def assertOneError(self, clips, fragment, **kw):
        errors, _ = run(clips, **kw)
        self.assertTrue(any(fragment in e for e in errors), errors)

    def test_ideal_picks_pass_with_no_errors_or_warnings(self):
        errors, warnings = p.check(pcs_builder.cue_dicts(), pcs_builder.ideal_picks())
        self.assertEqual((errors, warnings), ([], []))

    def test_cue_numbers_must_exist_and_be_in_order(self):
        self.assertOneError([good(end_cue=99)], "cue 99 does not exist")
        self.assertOneError([good(start_cue=0)], "cue 0 does not exist")
        self.assertOneError([good(start_cue=8, end_cue=3)], "start_cue 8 is after end_cue 3")
        self.assertOneError([good(start_cue="3")], "whole cue numbers")
        self.assertOneError([good(start_cue=True)], "whole cue numbers")
        self.assertOneError([good(end_cue=None)], "whole cue numbers")

    def test_duration_must_sit_in_the_range(self):
        self.assertOneError([good(start_cue=3, end_cue=4)], "lasts 10s, outside 20-60s")
        self.assertOneError([good(start_cue=3, end_cue=16)], "lasts 70s, outside 20-60s")
        errors, _ = run([good(start_cue=3, end_cue=4)], min_seconds=5, max_seconds=100)
        self.assertEqual(errors, [])

    def test_clips_may_not_overlap(self):
        clips = [good(0), good(1, start_cue=8, end_cue=13)]
        self.assertOneError(clips, "clip 1 and clip 2 overlap")

    def test_scores_must_be_whole_numbers_from_0_to_3(self):
        for bad in (4, -1, "3", 2.0, None, True):
            clip = good()
            clip["scores"]["hook"] = bad
            self.assertOneError([clip], "score 'hook' must be a whole number from 0 to 3")

    def test_missing_and_unknown_dimensions(self):
        clip = good()
        del clip["scores"]["emotion"]
        self.assertOneError([clip], "scores is missing 'emotion'")
        clip = good()
        clip["scores"]["charm"] = 2
        self.assertOneError([clip], "unknown score dimension 'charm'")
        self.assertOneError([good(scores=5)], "scores must be an object")

    def test_total_must_equal_the_sum(self):
        self.assertOneError([good(total=13)], "total is 13 but the scores add up to 12")
        self.assertOneError([good(total="12")], "total is '12' but the scores add up to 12")

    def test_every_dimension_needs_a_reason(self):
        clip = good()
        clip["reasons"]["payoff"] = "  "
        self.assertOneError([clip], "reasons is missing a line for 'payoff'")
        self.assertOneError([good(reasons=[])], "reasons must be an object")

    def test_caption_is_required_and_capped(self):
        self.assertOneError([good(caption="")], "caption is missing")
        self.assertOneError([good(caption=5)], "caption is missing")
        self.assertOneError([good(caption="x" * 151)], "caption is 151 characters, over 150")
        errors, _ = run([good(caption="x" * 150)])
        self.assertEqual(errors, [])
        errors, _ = run([good(caption="x" * 151)], max_caption=200)
        self.assertEqual(errors, [])

    def test_list_must_be_in_ranked_order(self):
        clips = [good(1), good(0)]
        self.assertOneError(clips, "clip 2 should come before clip 1")

    def test_ties_break_by_hook_then_standalone(self):
        a = good(0, total=11)
        a["scores"] = {"hook": 2, "standalone": 3, "emotion": 2, "payoff": 2, "quotable": 2}
        b = good(1, total=11)
        b["scores"] = {"hook": 3, "standalone": 2, "emotion": 2, "payoff": 2, "quotable": 2}
        self.assertOneError([a, b], "clip 2 should come before clip 1")
        errors, _ = run([b, a])
        self.assertEqual(errors, [])

    def test_every_problem_is_reported_not_just_the_first(self):
        errors, _ = run([good(end_cue=99, caption=""), good(1, total=0)])
        self.assertGreaterEqual(len(errors), 3)

    def test_mid_sentence_boundaries_warn_but_do_not_fail(self):
        errors, warnings = run([good(start_cue=6, end_cue=11)])
        self.assertEqual(errors, [])
        self.assertTrue(any("starts mid-sentence (cue 5" in w for w in warnings), warnings)
        errors, warnings = run([good(start_cue=9, end_cue=14)])
        self.assertEqual(errors, [])
        self.assertTrue(any("ends mid-sentence (cue 14" in w for w in warnings), warnings)

    def test_a_long_gap_inside_a_clip_warns(self):
        cues = pcs_builder.cue_dicts()
        cues[4]["start"] += 7
        cues[4]["end"] += 7
        errors, warnings = run([good()], cues=cues)
        self.assertEqual(errors, [])
        self.assertTrue(any("7s gap between cues 4 and 5" in w for w in warnings), warnings)

    def test_wrong_json_types_give_errors_never_a_traceback(self):
        garbage = [
            None,
            [],
            "text",
            {},
            {"clips": "x"},
            {"clips": []},
            {"clips": [1, "a", None, []]},
            {"clips": [{}]},
            {"clips": [{"start_cue": "1", "end_cue": [2], "scores": 5, "reasons": [], "caption": 5, "total": "x"}]},
            {"clips": [{"start_cue": 1, "end_cue": 2, "scores": {"hook": {}}, "reasons": {"hook": 3}}]},
        ]
        for picks in garbage:
            with self.subTest(picks=picks):
                errors, _ = p.check(pcs_builder.cue_dicts(), picks)
                self.assertTrue(errors)

    def test_odd_cues_do_not_crash(self):
        cues = [
            {"n": 1, "start": 5.0, "end": 5.0, "text": "Zero length", "speaker": None},
            {"n": 2, "start": 1.0, "end": 9.0, "text": "Out of order.", "speaker": None},
        ]
        errors, _ = p.check(cues, {"clips": [good(start_cue=1, end_cue=2)]})
        self.assertTrue(errors)


class LoadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def write(self, data):
        path = self.dir / "picks.json"
        path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        return path

    def test_loads_an_object_with_a_utf8_bom(self):
        path = self.write("﻿" + json.dumps(pcs_builder.ideal_picks()))
        self.assertEqual(p.load_picks(path), pcs_builder.ideal_picks())

    def test_unreadable_files_raise_picks_error(self):
        for data in (b"\xff\xfe\x00", "{not json", "[1]", '"s"'):
            with self.subTest(data=data), self.assertRaises(p.PicksError):
                p.load_picks(self.write(data))
        with self.assertRaises(p.PicksError):
            p.load_picks(self.dir / "missing.json")


if __name__ == "__main__":
    unittest.main()
