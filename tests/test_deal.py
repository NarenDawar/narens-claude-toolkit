import contextlib
import io
import json
import sys
import unittest

import helpers

sys.path.insert(
    0,
    str(helpers.REPO_ROOT / "plugins" / "deal-sparring-partner" / "skills" / "deal-sparring-partner" / "scripts"),
)
import deal  # noqa: E402


class LadderTests(unittest.TestCase):
    def offers(self, *args, **kwargs):
        return [r["offer"] for r in deal.ladder(*args, **kwargs)["rungs"]]

    def test_a_seller_ladder_falls_from_opening_to_reservation_in_shrinking_steps(self):
        offers = self.offers("buyer", 14500, 13800, 12800)
        self.assertEqual((offers[0], offers[-1]), (14500, 12800))
        steps = [a - b for a, b in zip(offers, offers[1:])]
        self.assertTrue(all(x > y for x, y in zip(steps, steps[1:])), steps)

    def test_a_buyer_ladder_rises_and_never_passes_the_reservation(self):
        offers = self.offers("seller", 10000, 11000, 12000, rungs=5)
        self.assertEqual(offers, sorted(offers))
        self.assertEqual((offers[0], offers[-1], max(offers)), (10000, 12000, 12000))

    def test_the_target_rung_is_marked(self):
        rungs = deal.ladder("buyer", 14500, 13400, 12800)["rungs"]
        self.assertEqual([r["at_or_past_target"] for r in rungs][:3], [False, False, True])

    def test_misordered_numbers_and_too_few_rungs_are_refused(self):
        with self.assertRaises(ValueError):
            deal.ladder("buyer", 12000, 13000, 12800)
        with self.assertRaises(ValueError):
            deal.ladder("seller", 12000, 11000, 10000)
        with self.assertRaises(ValueError):
            deal.ladder("buyer", 14500, 13800, 12800, rungs=1)


class ScoreTests(unittest.TestCase):
    def test_share_of_the_zone_the_user_kept(self):
        out = deal.score("buyer", 13500, 12800, 12900)
        self.assertEqual((out["outcome"], out["user_share_of_zone_pct"], out["zone_width"]), ("deal", 85.7, 700))

    def test_seller_side(self):
        out = deal.score("seller", 12000, 13000, 12500)
        self.assertEqual((out["zone"], out["user_share_of_zone_pct"]), ([12000, 13000], 50.0))

    def test_the_other_sides_best_and_worst_outcomes(self):
        self.assertEqual(deal.score("buyer", 13500, 12800, 12800)["user_share_of_zone_pct"], 100.0)
        self.assertEqual(deal.score("buyer", 13500, 12800, 13500)["user_share_of_zone_pct"], 0.0)

    def test_agreeing_past_your_own_walkaway_is_flagged(self):
        self.assertEqual(deal.score("buyer", 13500, 12800, 13900)["outcome"], "worse-than-walkaway")
        self.assertEqual(deal.score("seller", 12000, 11000, 11500)["outcome"], "worse-than-walkaway")

    def test_walking_away_when_a_deal_was_possible_is_a_missed_deal(self):
        self.assertIn("missed deal", deal.score("buyer", 13500, 12800)["verdict"])

    def test_walking_away_when_no_deal_was_possible_is_correct(self):
        out = deal.score("buyer", 12000, 12800)
        self.assertEqual((out["zone_exists"], out["verdict"]), (False, "no deal was possible"))

    def test_a_deal_with_no_zone_means_the_scenario_was_wrong(self):
        self.assertEqual(deal.score("buyer", 12700, 12800, 12700)["outcome"], "deal-outside-zone")
        self.assertEqual(deal.score("buyer", 12700, 12800, 12600)["outcome"], "deal-outside-zone")

    def test_a_zero_width_zone_does_not_divide_by_zero(self):
        self.assertEqual(deal.score("buyer", 12800, 12800, 12800)["user_share_of_zone_pct"], 100.0)


class CliTests(unittest.TestCase):
    def cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = deal.main(argv)
            except SystemExit as exit_:
                code = exit_.code
        return code, out.getvalue(), err.getvalue()

    def test_ladder_and_score_print_json(self):
        code, out, _ = self.cli(["ladder", "--side", "buyer", "--opening", "14500", "--target", "13800", "--reservation", "12800"])
        self.assertEqual((code, json.loads(out)["never_cross"]), (0, 12800))
        code, out, _ = self.cli(["score", "--side", "buyer", "--walkaway", "13500", "--reservation", "12800", "--no-deal"])
        self.assertEqual((code, json.loads(out)["outcome"]), (0, "no-deal"))

    def test_bad_numbers_and_missing_outcome_are_usage_errors(self):
        self.assertEqual(self.cli(["ladder", "--side", "buyer", "--opening", "1", "--target", "2", "--reservation", "3"])[0], 2)
        self.assertEqual(self.cli(["score", "--side", "buyer", "--walkaway", "1", "--reservation", "2"])[0], 2)
        self.assertEqual(self.cli(["score", "--side", "buyer", "--walkaway", "1", "--reservation", "2", "--final", "1", "--no-deal"])[0], 2)


if __name__ == "__main__":
    unittest.main()
