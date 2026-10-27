"""The five tools. Each takes (anki, arguments) and returns JSON-serializable data."""


class ToolInputError(ValueError):
    """The caller's arguments are wrong; the message tells them how to fix it."""


def _text(args, key, required=False):
    value = args.get(key)
    if value is None or value == "":
        if required:
            raise ToolInputError(f"'{key}' is required")
        return None
    if not isinstance(value, str):
        raise ToolInputError(f"'{key}' must be a string")
    return value


def _count(args, key, default, maximum):
    value = args.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ToolInputError(f"'{key}' must be an integer from 1 to {maximum}")
    return value


def _deck_filter(deck):
    return 'deck:"%s"' % deck.replace("\\", "\\\\").replace('"', '\\"')


def list_decks(anki, args):
    stats = anki("getDeckStats", decks=anki("deckNames"))
    return [
        {
            "deck": s["name"],
            "new": s["new_count"],
            "learning": s["learn_count"],
            "due": s["review_count"],
            "total": s["total_in_deck"],
        }
        for s in stats.values()
    ]


def _note(entry):
    if not isinstance(entry, dict):
        return None
    cloze, front, back = entry.get("cloze"), entry.get("front"), entry.get("back")
    if isinstance(cloze, str) and "{{c" in cloze:
        return "Cloze", {"Text": cloze}
    if isinstance(front, str) and front.strip() and isinstance(back, str) and back.strip():
        return "Basic", {"Front": front, "Back": back}
    return None


def add_cards(anki, args):
    deck = _text(args, "deck", required=True)
    entries = args.get("notes")
    if not isinstance(entries, list) or not entries:
        raise ToolInputError("'notes' must be a non-empty list")
    tags = args.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise ToolInputError("'tags' must be a list of strings")
    if deck not in anki("deckNames"):
        if args.get("create_deck") is not True:
            raise ToolInputError(
                f"deck '{deck}' does not exist; fix the name or pass create_deck=true"
            )
        anki("createDeck", deck=deck)

    built = [_note(e) for e in entries]
    valid = [
        {
            "deckName": deck,
            "modelName": model,
            "fields": fields,
            "tags": tags,
            "options": {"allowDuplicate": False, "duplicateScope": "deck"},
        }
        for model, fields in filter(None, built)
    ]
    ids = iter(anki("addNotes", notes=valid) if valid else [])
    results = []
    for index, note in enumerate(built):
        if note is None:
            results.append({"index": index, "status": "invalid: needs front+back, or cloze with {{c1::...}}"})
            continue
        note_id = next(ids)
        if note_id is None:
            results.append({"index": index, "status": "skipped: duplicate in this deck"})
        else:
            results.append({"index": index, "status": "added", "note_id": note_id})
    return results


def search_notes(anki, args):
    query = _text(args, "query", required=True)
    limit = _count(args, "limit", 20, 100)
    found = anki("findNotes", query=query)
    info = anki("notesInfo", notes=found[:limit]) if found else []
    return {
        "total_matches": len(found),
        "notes": [
            {
                "note_id": n["noteId"],
                "model": n["modelName"],
                "tags": n["tags"],
                "fields": {k: v["value"] for k, v in n["fields"].items()},
            }
            for n in info
        ],
    }


def get_due_cards(anki, args):
    deck = _text(args, "deck")
    limit = _count(args, "limit", 10, 50)
    query = "is:due" + (" " + _deck_filter(deck) if deck else "")
    found = anki("findCards", query=query)
    info = anki("cardsInfo", cards=found[:limit]) if found else []
    return {
        "total_due": len(found),
        "cards": [
            {
                "card_id": c["cardId"],
                "deck": c["deckName"],
                "fields": {k: v["value"] for k, v in c["fields"].items()},
            }
            for c in info
        ],
    }


def answer_cards(anki, args):
    answers = args.get("answers")
    if not isinstance(answers, list) or not answers:
        raise ToolInputError("'answers' must be a non-empty list")
    for a in answers:
        ok = (
            isinstance(a, dict)
            and isinstance(a.get("card_id"), int)
            and not isinstance(a.get("card_id"), bool)
            and a.get("ease") in (1, 2, 3, 4)
            and not isinstance(a.get("ease"), bool)
        )
        if not ok:
            raise ToolInputError("each answer needs an integer 'card_id' and 'ease' of 1-4")
    done = anki(
        "answerCards", answers=[{"cardId": a["card_id"], "ease": a["ease"]} for a in answers]
    )
    return [
        {"card_id": a["card_id"], "recorded": ok} for a, ok in zip(answers, done)
    ]


_NOTE = {
    "type": "object",
    "properties": {
        "front": {"type": "string", "description": "Question side. Use with 'back'."},
        "back": {"type": "string", "description": "Answer side. Use with 'front'."},
        "cloze": {
            "type": "string",
            "description": "Cloze text such as 'Paris is the capital of {{c1::France}}'. Use instead of front/back.",
        },
    },
}

TOOLS = [
    (
        "list_decks",
        "List every Anki deck with its new, learning, due and total card counts.",
        {"type": "object", "properties": {}},
        list_decks,
    ),
    (
        "add_cards",
        "Add flashcards to a deck. Each note is a front/back pair or a cloze. Duplicates in the "
        "deck are skipped, and the result says per note whether it was added, skipped or invalid.",
        {
            "type": "object",
            "properties": {
                "deck": {"type": "string", "description": "Exact deck name."},
                "notes": {"type": "array", "items": _NOTE, "description": "Cards to add."},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags for every note."},
                "create_deck": {"type": "boolean", "description": "Create the deck if it does not exist. Default false."},
            },
            "required": ["deck", "notes"],
        },
        add_cards,
    ),
    (
        "search_notes",
        "Search notes with Anki's search syntax (for example 'deck:French tag:leech' or 'added:7'). "
        "Returns the matching notes' fields and tags, and the total match count.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Anki search query."},
                "limit": {"type": "integer", "description": "Max notes to return, 1-100. Default 20."},
            },
            "required": ["query"],
        },
        search_notes,
    ),
    (
        "get_due_cards",
        "Get cards due for review now, with their fields (the answer is included, so hide it "
        "until the user has tried). Pair with answer_cards to run a study session.",
        {
            "type": "object",
            "properties": {
                "deck": {"type": "string", "description": "Only this deck (and its subdecks). Default all decks."},
                "limit": {"type": "integer", "description": "Max cards to return, 1-50. Default 10."},
            },
        },
        get_due_cards,
    ),
    (
        "answer_cards",
        "Record review results, which changes the cards' schedule. Ease: 1 again, 2 hard, "
        "3 good, 4 easy. Only call this for cards the user actually answered.",
        {
            "type": "object",
            "properties": {
                "answers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "card_id": {"type": "integer", "description": "card_id from get_due_cards."},
                            "ease": {"type": "integer", "enum": [1, 2, 3, 4]},
                        },
                        "required": ["card_id", "ease"],
                    },
                }
            },
            "required": ["answers"],
        },
        answer_cards,
    ),
]
