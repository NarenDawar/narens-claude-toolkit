import time
import unittest

import support  # noqa: F401
from mcp_fixer import bench_prompts as bp

TOOLS = [
    {
        "name": "search_items",
        "description": "Search the\n  catalog by keyword.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "Keyword"},
                "order": {"type": "string", "enum": ["asc", "desc"]},
            },
            "required": ["q"],
        },
    },
    {"name": "get_item", "description": "Fetch one item."},
    "junk",
    {"name": ""},
    {"description": "no name"},
]
NAMES = {"search_items", "get_item"}


class RenderTests(unittest.TestCase):
    def test_tools_are_rendered_compactly(self):
        text = bp.render_tools(TOOLS)
        self.assertIn("- search_items: Search the catalog by keyword.", text)
        self.assertIn("    - q (string; required): Keyword", text)
        self.assertIn("    - order (string; one of asc, desc)", text)
        self.assertIn("- get_item: Fetch one item.", text)
        self.assertNotIn("junk", text)
        self.assertNotIn("no name", text)

    def test_odd_schemas_do_not_crash(self):
        odd = [
            {"name": "a", "description": 5, "inputSchema": {"properties": {"x": {"type": ["string", "null"]}, "y": 5}, "required": [["x"], "y"]}},
            {"name": "b", "inputSchema": {"properties": "nope"}},
            {"name": "c", "inputSchema": []},
        ]
        text = bp.render_tools(odd)
        self.assertIn("- a", text)
        self.assertIn("x (string|null)", text)
        self.assertIn("y (required)", text)

    def test_the_trial_prompt_has_the_tools_the_request_and_the_format(self):
        prompt = bp.trial_prompt(TOOLS, "find me stuff {with} braces")
        for name in NAMES:
            self.assertIn(name, prompt)
        self.assertIn("User request: find me stuff {with} braces", prompt)
        self.assertIn('{"tool": "<tool name>"}', prompt)

    def test_the_tasks_prompt_names_the_target_and_the_count(self):
        prompt = bp.tasks_prompt(TOOLS, "get_item", 3)
        self.assertIn('need the tool "get_item"', prompt)
        self.assertIn("3 different requests", prompt)
        self.assertIn("search_items", prompt)


class ParseChoiceTests(unittest.TestCase):
    def test_accepted_replies(self):
        cases = [
            ('{"tool": "get_item"}', "get_item"),
            ('```json\n{"tool": "get_item"}\n```', "get_item"),
            ('I would pick this one: {"tool": "search_items"} because it fits.', "search_items"),
            ('{"tool": "get_item"} {"tool": "search_items"}', "search_items"),
            ('{"other": 1} {"tool": "get_item"}', "get_item"),
        ]
        for text, expected in cases:
            with self.subTest(text):
                self.assertEqual(bp.parse_choice(text, NAMES), expected)

    def test_rejected_replies_are_none(self):
        cases = [
            '{"tool": "ghost"}',
            '{"tool": 5}',
            '{"tool": ["get_item"]}',
            '{"tool": " get_item "}',
            '[{"tool": "get_item"}]',
            "",
            "no json here",
            '{"tool": "get_item"',
        ]
        for text in cases:
            with self.subTest(text):
                self.assertIsNone(bp.parse_choice(text, NAMES))

    def test_quoted_description_does_not_override_the_final_choice(self):
        text = 'The description says {"tool":"search_items"}. I pick {"tool":"get_item"}.'
        self.assertEqual(bp.parse_choice(text, NAMES), "get_item")

    def test_unknown_final_choice_does_not_fall_back_to_a_quoted_tool(self):
        self.assertIsNone(bp.parse_choice(
            '{"tool":"get_item"} but my answer is {"tool":"ghost"}', NAMES
        ))

    def test_pathological_replies_are_fast_and_none(self):
        started = time.monotonic()
        self.assertIsNone(bp.parse_choice("[" * 5000, NAMES))
        self.assertIsNone(bp.parse_choice("{" * 1000000, NAMES))
        self.assertLess(time.monotonic() - started, 20)

    def test_a_valid_answer_after_the_cap_is_ignored(self):
        text = " " * (bp.MAX_REPLY_CHARS + 10) + '{"tool": "get_item"}'
        self.assertIsNone(bp.parse_choice(text, NAMES))


class ParseTaskListTests(unittest.TestCase):
    def test_lists(self):
        self.assertEqual(bp.parse_task_list('["a b", "c d"]'), ["a b", "c d"])
        self.assertEqual(bp.parse_task_list('```json\n["a b"]\n```'), ["a b"])
        self.assertEqual(bp.parse_task_list('Here you go: ["a b"] enjoy'), ["a b"])
        self.assertEqual(bp.parse_task_list('["a", 5, "", "  ", " b "]'), ["a", "b"])
        self.assertEqual(bp.parse_task_list('["x"] ["y"]'), ["x"])
        self.assertEqual(bp.parse_task_list("[1, 2]"), [])

    def test_no_list_is_none(self):
        for text in ("no", "", '{"a": 1}', '["unterminated'):
            with self.subTest(text):
                self.assertIsNone(bp.parse_task_list(text))


class MentionsNameTests(unittest.TestCase):
    def test_whole_word_matches_with_name_variants(self):
        self.assertTrue(bp.mentions_name("please get item 5", "get_item"))
        self.assertTrue(bp.mentions_name("use GET_ITEM now", "get_item"))
        self.assertTrue(bp.mentions_name("use get-item now", "get-item"))
        self.assertTrue(bp.mentions_name("run it", "run"))
        self.assertFalse(bp.mentions_name("show me the running totals", "run"))
        self.assertFalse(bp.mentions_name("find stuff", "get_item"))


if __name__ == "__main__":
    unittest.main()
