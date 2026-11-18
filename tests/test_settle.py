import contextlib
import io
import itertools
import json
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

import helpers

sys.path.insert(
    0,
    str(helpers.REPO_ROOT / "plugins" / "trip-expense-settler" / "skills" / "trip-expense-settler" / "scripts"),
)
import settle as st  # noqa: E402

PEOPLE = ["Ana", "Ben", "Cy", "Dee"]


def ledger(*entries, **extra):
    return {"base": "EUR", "people": PEOPLE, "entries": list(entries), **extra}


def equal(eid, payer, amount, names=PEOPLE, **extra):
    return {"id": eid, "payer": payer, "amount": amount, "split": {"equal": list(names)}, **extra}


class MoneyTests(unittest.TestCase):
    def test_cents_and_formatting(self):
        self.assertEqual(st.cents(Decimal("41.405")), 4140)  # half to even
        self.assertEqual(st.cents(Decimal("41.415")), 4142)
        self.assertEqual((st.fmt(5), st.fmt(-1234), st.fmt(100)), ("0.05", "-12.34", "1.00"))

    def test_shares_always_add_to_the_total(self):
        for total, weights in [(10000, {"a": 1, "b": 1, "c": 1}), (9650, {"a": 1, "b": 1, "c": 1}),
                               (1, {"a": 1, "b": 1}), (11000, {"a": 40, "b": 30, "c": 40})]:
            with self.subTest(total=total):
                self.assertEqual(sum(st.allocate(total, weights).values()), total)

    def test_the_extra_cent_goes_to_the_earlier_name(self):
        self.assertEqual(st.allocate(100, {"a": 1, "b": 1, "c": 1}), {"a": 34, "b": 33, "c": 33})


class EntryTests(unittest.TestCase):
    def shares(self, entry, rate=Decimal(1)):
        return st.entry_shares(entry, rate, PEOPLE)

    def test_equal_split(self):
        total, parts = self.shares(equal("d", "Ben", "96.50", ["Ben", "Ana", "Cy"]))
        self.assertEqual((total, parts), (9650, {"Ben": 3217, "Ana": 3217, "Cy": 3216}))

    def test_unequal_shares(self):
        _, parts = self.shares({"id": "b", "payer": "Ben", "amount": "110", "split": {"shares": {"Ben": 40, "Cy": 30, "Dee": 40}}})
        self.assertEqual(parts, {"Ben": 4000, "Cy": 3000, "Dee": 4000})

    def test_decimal_shares(self):
        _, parts = self.shares({"id": "b", "payer": "Ben", "amount": "10", "split": {"shares": {"Ben": "1.5", "Cy": "0.5"}}})
        self.assertEqual(parts, {"Ben": 750, "Cy": 250})

    def test_exact_amounts_must_add_up(self):
        _, parts = self.shares({"id": "m", "payer": "Ana", "amount": "18", "split": {"exact": {"Ben": "18"}}})
        self.assertEqual(parts, {"Ben": 1800})
        with self.assertRaises(st.LedgerError):
            self.shares({"id": "m", "payer": "Ana", "amount": "18", "split": {"exact": {"Ben": "10", "Cy": "5"}}})

    def test_a_refund_flips_every_sign(self):
        total, parts = self.shares(equal("r", "Ana", "-40"))
        self.assertEqual((total, sum(parts.values())), (-4000, -4000))

    def test_foreign_currency_is_converted_once(self):
        total, parts = self.shares(equal("t", "Dee", "45", ["Dee", "Ben"]), Decimal("0.92"))
        self.assertEqual((total, parts), (4140, {"Dee": 2070, "Ben": 2070}))

    def test_bad_entries_are_refused(self):
        for entry in (equal("z", "Ana", "0"), equal("x", "Ana", "abc"), equal("u", "Ana", "10", ["Ana", "Zed"]),
                      {"id": "n", "payer": "Ana", "amount": "5", "split": {}},
                      {"id": "s", "payer": "Ana", "amount": "5", "split": {"shares": {"Ana": 0}}}):
            with self.subTest(entry=entry), self.assertRaises(st.LedgerError):
                self.shares(entry)


class SettleTests(unittest.TestCase):
    TRIP = ledger(
        equal("airbnb", "Ana", "480"), equal("refund", "Ana", "-40"),
        equal("dinner", "Ben", "96.50", ["Ben", "Ana", "Cy"]), equal("groceries", "Cy", "62.30"),
        equal("taxi", "Dee", "45", ["Dee", "Ben"], currency="USD"),
        {"id": "museum", "payer": "Ana", "amount": "18", "split": {"exact": {"Ben": "18"}}},
        {"id": "boat", "payer": "Ben", "amount": "110", "split": {"shares": {"Ben": 40, "Cy": 30, "Dee": 40}}},
        rates={"USD": "0.92"},
    )

    def test_the_trip(self):
        out = st.settle(self.TRIP)
        self.assertEqual(out["balances"], {"Ana": "300.25", "Ben": "-29.95", "Cy": "-125.43", "Dee": "-144.87"})
        self.assertEqual(out["checks"], {"balances_sum_to_zero": True, "payments_clear_every_balance": True, "payment_count": 3})
        self.assertEqual({p["to"] for p in out["payments"]}, {"Ana"})

    def test_a_missing_rate_payer_or_entries_is_an_error(self):
        with self.assertRaises(st.LedgerError):
            st.settle(ledger(equal("t", "Dee", "45", currency="USD")))
        with self.assertRaises(st.LedgerError):
            st.settle(ledger(equal("t", "Zed", "45")))
        with self.assertRaises(st.LedgerError):
            st.settle({"people": PEOPLE, "entries": []})
        with self.assertRaises(st.LedgerError):
            st.settle({"people": ["a", "a"], "entries": [equal("x", "a", "1", ["a"])]})
        with self.assertRaises(st.LedgerError):
            st.settle(ledger(equal("t", "Dee", "45", currency="USD"), rates={"USD": "0"}))

    def test_a_self_paid_expense_needs_no_payment(self):
        out = st.settle(ledger(equal("solo", "Ana", "20", ["Ana"])))
        self.assertEqual((out["payments"], out["balances"]["Ana"]), ([], "0.00"))


class FewestPaymentsTests(unittest.TestCase):
    def count(self, balances):
        payments = st.fewest_payments(balances)
        left = dict(balances)
        for a, b, c in payments:
            left[a] += c
            left[b] -= c
        self.assertTrue(all(v == 0 for v in left.values()), left)
        return len(payments)

    def test_independent_groups_are_settled_separately(self):
        balances = {"Ana": 8240, "Ben": -3115, "Cy": -5125, "Dee": 12000, "Eli": -6430, "Fay": -5570, "Gus": 4000, "Hal": -4000}
        self.assertEqual(self.count(balances), 5)  # 8 people in 3 groups that each net to zero

    def test_matches_brute_force_on_small_cases(self):
        cases = [{"a": 5, "b": -2, "c": -3}, {"a": 4, "b": 6, "c": -7, "d": -3}, {"a": 10, "b": -4, "c": 3, "d": -9}]
        for balances in cases:
            with self.subTest(balances=balances):
                self.assertEqual(self.count(balances), self.brute(balances))

    def brute(self, balances):
        names = [n for n, v in balances.items() if v]
        best = len(names) - 1
        # the most zero-sum groups: try every labelling of people into k groups
        for k in range(len(names), 0, -1):
            for labels in itertools.product(range(k), repeat=len(names)):
                if len(set(labels)) == k and all(sum(balances[n] for n, g in zip(names, labels) if g == i) == 0 for i in range(k)):
                    return len(names) - k
        return best

    def test_nobody_owing_means_no_payments(self):
        self.assertEqual(st.fewest_payments({"a": 0, "b": 0}), [])

    def test_a_big_group_still_returns_a_valid_answer(self):
        balances = {f"p{i}": (100 if i % 2 else -100) for i in range(14)}
        self.assertEqual(self.count(balances), 7)  # falls back to the greedy match, which is also minimal here


class CliTests(unittest.TestCase):
    def cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = st.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_prints_json_and_reports_bad_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            good, bad, broken = (Path(tmp) / n for n in ("g.json", "b.json", "x.json"))
            good.write_text(json.dumps(ledger(equal("a", "Ana", "40"))), encoding="utf-8")
            bad.write_text(json.dumps(ledger(equal("a", "Zed", "40"))), encoding="utf-8")
            broken.write_text("not json", encoding="utf-8")
            code, out, _ = self.cli([str(good)])
            self.assertEqual((code, json.loads(out)["balances"]["Ana"]), (0, "30.00"))
            for path in (bad, broken, Path(tmp) / "none.json"):
                self.assertEqual(self.cli([str(path)])[0], 2)
            self.assertEqual(self.cli([])[0], 2)


if __name__ == "__main__":
    unittest.main()
