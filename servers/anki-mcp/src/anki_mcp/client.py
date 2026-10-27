"""Minimal AnkiConnect client: one JSON POST per call, standard library only."""
import json
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8765"


class AnkiError(Exception):
    """AnkiConnect is unreachable or rejected a request."""


class AnkiConnect:
    def __init__(self, url=DEFAULT_URL, timeout=10):
        self.url = url
        self.timeout = timeout

    def __call__(self, action, **params):
        body = json.dumps({"action": action, "version": 6, "params": params}).encode()
        request = urllib.request.Request(
            self.url, body, {"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                reply = json.load(response)
        except (OSError, ValueError) as exc:
            raise AnkiError(
                f"Cannot reach AnkiConnect at {self.url} ({exc}). Anki must be running "
                "with the AnkiConnect add-on installed (add-on code 2055492159)."
            ) from exc
        if reply.get("error"):
            raise AnkiError(str(reply["error"]))
        return reply.get("result")
