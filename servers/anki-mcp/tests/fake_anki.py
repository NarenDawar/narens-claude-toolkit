"""A tiny in-memory AnkiConnect, served over HTTP on a free local port."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class FakeAnki:
    def __init__(self):
        self.decks = {"French": 1, "Default": 2}
        self.notes = {}  # id -> {"deck", "model", "fields", "tags"}
        self.answered = []
        self.calls = []
        self._next_id = 100
        self.due_card_ids = []
        self._server = HTTPServer(("127.0.0.1", 0), self._handler())
        self.url = "http://127.0.0.1:%d" % self._server.server_port
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def close(self):
        self._server.shutdown()
        self._server.server_close()

    def _handler(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.calls.append(request)
                try:
                    reply = {"result": fake.dispatch(request["action"], request["params"]), "error": None}
                except Exception as exc:  # reported to the client like AnkiConnect does
                    reply = {"result": None, "error": str(exc)}
                body = json.dumps(reply).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler

    def dispatch(self, action, params):
        return getattr(self, "do_" + action)(**params)

    def do_deckNames(self):
        return list(self.decks)

    def do_createDeck(self, deck):
        return self.decks.setdefault(deck, len(self.decks) + 1)

    def do_getDeckStats(self, decks):
        return {
            str(self.decks[d]): {
                "name": d, "new_count": 2, "learn_count": 1, "review_count": 3,
                "total_in_deck": sum(1 for n in self.notes.values() if n["deck"] == d),
            }
            for d in decks
        }

    def do_addNotes(self, notes):
        ids = []
        for note in notes:
            first = next(iter(note["fields"].values()))
            if any(n["deck"] == note["deckName"] and next(iter(n["fields"].values())) == first
                   for n in self.notes.values()):
                ids.append(None)
                continue
            self._next_id += 1
            self.notes[self._next_id] = {
                "deck": note["deckName"], "model": note["modelName"],
                "fields": note["fields"], "tags": note["tags"],
            }
            ids.append(self._next_id)
        return ids

    def do_findNotes(self, query):
        return [i for i, n in self.notes.items() if query in n["tags"] or query == "*"]

    def do_notesInfo(self, notes):
        return [
            {"noteId": i, "modelName": self.notes[i]["model"], "tags": self.notes[i]["tags"],
             "fields": {k: {"value": v, "order": 0} for k, v in self.notes[i]["fields"].items()}}
            for i in notes
        ]

    def do_findCards(self, query):
        return list(self.due_card_ids)

    def do_cardsInfo(self, cards):
        return [
            {"cardId": c, "deckName": "French", "fields": {"Front": {"value": "q%d" % c}, "Back": {"value": "a%d" % c}}}
            for c in cards
        ]

    def do_answerCards(self, answers):
        self.answered.extend(answers)
        return [True for _ in answers]
