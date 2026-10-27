# anki-mcp: run Anki study sessions from Claude

> Lets Claude quiz you on your due Anki cards, record your answers, and add flashcards without creating duplicates.

Part of [Naren's Claude Toolkit](https://github.com/NarenDawar/narens-claude-toolkit). Other Anki MCP servers mostly wrap card create, read, update and delete. This one is built around a study session: pull what is due, quiz you, write your grades back so Anki reschedules the cards, and turn a conversation into new cards without double-adding.

## Tools

| Tool | What it does |
| --- | --- |
| `list_decks` | Every deck with new, learning, due and total counts. |
| `get_due_cards` | Cards due now (optionally one deck), with their fields. Max 50 per call. |
| `answer_cards` | Records grades (1 again, 2 hard, 3 good, 4 easy). This changes the schedule. |
| `add_cards` | Adds front/back or cloze notes. Skips duplicates in the deck and reports each note as added, skipped or invalid. An unknown deck is an error unless `create_deck` is true. |
| `search_notes` | Anki search syntax (`deck:French tag:leech`, `added:7`). Returns fields, tags and the total match count. |

There is deliberately no delete or edit tool: nothing here can destroy cards. `answer_cards` is the one tool that changes existing cards, and its description tells Claude to call it only for cards you actually answered.

## Use it

You need Anki running on the same computer with the [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on (code `2055492159`) installed. Anki may ask you to approve the first connection.

Python 3.9 or newer, standard library only. From the repository root:

Add it to your project's `.mcp.json`, with `PYTHONPATH` pointing at `servers/anki-mcp/src` (use an absolute path if Claude is not started from the repository root):

```json
{
  "mcpServers": {
    "anki": {
      "command": "python",
      "args": ["-m", "anki_mcp"],
      "env": { "PYTHONPATH": "servers/anki-mcp/src" }
    }
  }
}
```

Set `ANKI_CONNECT_URL` if AnkiConnect is not on the default `http://127.0.0.1:8765`. The folder has a `pyproject.toml` with an `anki-mcp` console script, but installing it with `pip` is not verified or published yet.

Then try: "Quiz me on my due French cards, one at a time" or "Make cloze cards from this paragraph in my Biology deck".

## What is tested

Tests run against a fake AnkiConnect, including one real stdio round trip. They have **not** been run against a real Anki install, and the note types are assumed to be Anki's stock `Basic` (Front, Back) and `Cloze` (Text). If you renamed them or use another language's names, `add_cards` will report an error from Anki.

```text
cd servers/anki-mcp/tests
python -m unittest -v test_server
```
