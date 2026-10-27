import json
import os
import subprocess
import sys
import unittest

import support
from anki_mcp import server
from anki_mcp.client import AnkiConnect
from fake_anki import FakeAnki


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeAnki()
        self.addCleanup(self.fake.close)
        self.anki = AnkiConnect(self.fake.url, timeout=2)

    def call(self, name, arguments=None):
        reply = server.handle(self.anki, {
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        })
        result = reply["result"]
        text = result["content"][0]["text"]
        return result.get("isError", False), (text if result.get("isError") else json.loads(text))

    def test_initialize_and_tool_list(self):
        init = server.handle(self.anki, {"id": 1, "method": "initialize", "params": {}})
        self.assertEqual(init["result"]["serverInfo"]["name"], "anki-mcp")
        tools = server.handle(self.anki, {"id": 2, "method": "tools/list"})["result"]["tools"]
        self.assertEqual(
            [t["name"] for t in tools],
            ["list_decks", "add_cards", "search_notes", "get_due_cards", "answer_cards"],
        )
        self.assertIsNone(server.handle(self.anki, {"method": "notifications/initialized"}))

    def test_unknown_tool_and_method(self):
        reply = server.handle(self.anki, {"id": 1, "method": "tools/call", "params": {"name": "nope"}})
        self.assertEqual(reply["error"]["code"], -32602)
        self.assertEqual(server.handle(self.anki, {"id": 2, "method": "x"})["error"]["code"], -32601)

    def test_list_decks(self):
        error, decks = self.call("list_decks")
        self.assertFalse(error)
        self.assertEqual({d["deck"] for d in decks}, {"French", "Default"})
        self.assertEqual(decks[0]["due"], 3)

    def test_add_cards_reports_each_note(self):
        notes = [
            {"front": "chat", "back": "cat"},
            {"cloze": "Paris is in {{c1::France}}"},
            {"front": "chat", "back": "cat"},
            {"front": "only front"},
        ]
        error, results = self.call("add_cards", {"deck": "French", "notes": notes, "tags": ["t"]})
        self.assertFalse(error)
        self.assertEqual([r["status"].split(":")[0] for r in results],
                         ["added", "added", "skipped", "invalid"])
        models = sorted(n["model"] for n in self.fake.notes.values())
        self.assertEqual(models, ["Basic", "Cloze"])

    def test_add_cards_unknown_deck_needs_create_flag(self):
        notes = [{"front": "a", "back": "b"}]
        error, message = self.call("add_cards", {"deck": "Spanish", "notes": notes})
        self.assertTrue(error)
        self.assertIn("create_deck", message)
        self.assertNotIn("Spanish", self.fake.decks)
        error, results = self.call("add_cards", {"deck": "Spanish", "notes": notes, "create_deck": True})
        self.assertFalse(error)
        self.assertEqual(results[0]["status"], "added")

    def test_search_notes_respects_limit(self):
        self.call("add_cards", {"deck": "French", "notes": [
            {"front": "a", "back": "1"}, {"front": "b", "back": "2"}], "tags": ["leech"]})
        error, found = self.call("search_notes", {"query": "leech", "limit": 1})
        self.assertFalse(error)
        self.assertEqual(found["total_matches"], 2)
        self.assertEqual(len(found["notes"]), 1)
        self.assertEqual(found["notes"][0]["tags"], ["leech"])

    def test_search_notes_rejects_bad_limit(self):
        error, message = self.call("search_notes", {"query": "x", "limit": 0})
        self.assertTrue(error)
        self.assertIn("limit", message)

    def test_due_cards_then_answer(self):
        self.fake.due_card_ids = [7, 8, 9]
        error, due = self.call("get_due_cards", {"deck": 'Fr"ench', "limit": 2})
        self.assertFalse(error)
        self.assertEqual(due["total_due"], 3)
        self.assertEqual([c["card_id"] for c in due["cards"]], [7, 8])
        self.assertEqual(due["cards"][0]["fields"], {"Front": "q7", "Back": "a7"})
        query = next(c for c in self.fake.calls if c["action"] == "findCards")["params"]["query"]
        self.assertEqual(query, 'is:due deck:"Fr\\"ench"')
        error, done = self.call("answer_cards", {"answers": [{"card_id": 7, "ease": 3}]})
        self.assertFalse(error)
        self.assertEqual(done, [{"card_id": 7, "recorded": True}])
        self.assertEqual(self.fake.answered, [{"cardId": 7, "ease": 3}])

    def test_answer_cards_validates_before_touching_anki(self):
        for bad in ([{"card_id": 7, "ease": 5}], [{"card_id": "7", "ease": 3}], [{"card_id": 7}], []):
            error, _ = self.call("answer_cards", {"answers": bad})
            self.assertTrue(error)
        self.assertEqual(self.fake.answered, [])

    def test_unreachable_anki_is_a_tool_error(self):
        self.fake.close()
        error, message = self.call("list_decks")
        self.assertTrue(error)
        self.assertIn("AnkiConnect", message)


class StdioTest(unittest.TestCase):
    def test_real_process_round_trip(self):
        fake = FakeAnki()
        self.addCleanup(fake.close)
        lines = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_decks"}},
        ]
        env = dict(os.environ, ANKI_CONNECT_URL=fake.url, PYTHONPATH=str(support.SRC))
        proc = subprocess.run(
            [sys.executable, "-m", "anki_mcp"],
            input="\n".join(json.dumps(m) for m in lines) + "\nnot json\n",
            capture_output=True, text=True, env=env, timeout=20,
        )
        replies = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual([r.get("id") for r in replies], [1, 2, None])
        self.assertEqual(replies[2]["error"]["code"], -32700)
        self.assertIn("French", replies[1]["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
