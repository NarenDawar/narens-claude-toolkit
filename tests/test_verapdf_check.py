import contextlib
import io
import sys
import unittest

import helpers

sys.path.insert(0, str(helpers.REPO_ROOT / "plugins" / "pdf-table-fixer" / "skills" / "pdf-table-fixer" / "scripts"))
import verapdf_check as v  # noqa: E402


def report(rules, compliant="false"):
    body = "".join(
        f'<rule specification="ISO 14289-1:2014" clause="{c}" testNumber="{t}" status="failed" '
        f'failedChecks="{n}"><description>{d}</description></rule>'
        for c, t, n, d in rules)
    return (f'<?xml version="1.0"?><report><jobs><job><validationReport profileName="PDF/UA-1" '
            f'isCompliant="{compliant}"><details passedRules="10" failedRules="{len(rules)}">{body}'
            f'</details></validationReport></job></jobs></report>')


BEFORE = report([("7.5", "1", 3, "TH shall have a Scope or Headers"), ("7.1", "2", 1, "Figure alt text")])
AFTER_OK = report([("7.1", "2", 1, "Figure alt text")])
AFTER_BAD = report([("7.1", "2", 1, "Figure alt text"), ("7.5", "2", 2, "Table rows are irregular")])


def run(argv, runner):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = v.main(argv, runner=runner)
    return code, out.getvalue()


class ParseTests(unittest.TestCase):
    def test_parse_failed_rules_and_table_flag(self):
        got = v.parse_report(BEFORE)
        self.assertFalse(got["compliant"])
        self.assertEqual(got["rules"][("7.5", "1")]["count"], 3)
        self.assertTrue(got["rules"][("7.5", "1")]["table"])
        self.assertFalse(got["rules"][("7.1", "2")]["table"])

    def test_description_words_flag_table_rules_outside_clause_7_5(self):
        self.assertTrue(v.is_table_rule("7.2", "A TD cell shall belong to a TR"))
        self.assertFalse(v.is_table_rule("7.1", "Tablet-sized figure"))   # whole words only
        self.assertFalse(v.is_table_rule("7.1", "Figure alt text"))

    def test_garbage_raises_value_error(self):
        with self.assertRaises(ValueError):
            v.parse_report("not xml")
        with self.assertRaises(ValueError):
            v.parse_report("<html/>")

    def test_namespaced_report_is_read(self):
        ns = BEFORE.replace("<report>", '<report xmlns="http://www.verapdf.org/MachineReadableReport">')
        self.assertEqual(len(v.parse_report(ns)["rules"]), 2)

    def test_compare_finds_new_and_fixed(self):
        c = v.compare(v.parse_report(BEFORE), v.parse_report(AFTER_BAD))
        self.assertEqual(c["new"], [("7.5", "2")])
        self.assertEqual(c["fixed"], [("7.5", "1")])
        self.assertEqual((c["table_before"], c["table_after"]), (3, 2))


class MainTests(unittest.TestCase):
    def test_single_file_report_names_profile_and_counts(self):
        code, out = run(["a.pdf"], lambda p: BEFORE)
        self.assertEqual(code, 0)
        self.assertIn("PDF/UA-1", out)
        self.assertIn("2 failed rules", out)
        self.assertIn("7.5", out)

    def test_against_fixed_file_exits_0(self):
        results = {"b.pdf": BEFORE, "a.pdf": AFTER_OK}
        code, out = run(["a.pdf", "--against", "b.pdf"], lambda p: results[p])
        self.assertEqual(code, 0)
        self.assertIn("fixed", out)

    def test_regression_exits_1_even_when_total_fell(self):
        results = {"b.pdf": report([("7.5", "1", 5, "x"), ("7.5", "3", 5, "x")]), "a.pdf": AFTER_BAD}
        code, out = run(["a.pdf", "--against", "b.pdf"], lambda p: results[p])
        self.assertEqual(code, 1)
        self.assertIn("regression", out.lower())

    def test_missing_tools_say_not_validated_and_exit_2(self):
        orig = v.find_tools
        v.find_tools = lambda: (None, None)
        self.addCleanup(setattr, v, "find_tools", orig)
        code, out = run(["a.pdf"], None)
        self.assertEqual(code, 2)
        self.assertIn("not validated", out)
        self.assertNotIn("pass", out.lower())

    def test_unreadable_report_is_not_a_pass(self):
        code, out = run(["a.pdf"], lambda p: "boom")
        self.assertEqual(code, 2)
        self.assertIn("not validated", out)


if __name__ == "__main__":
    unittest.main()
