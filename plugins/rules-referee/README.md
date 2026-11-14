# rules-referee: a Claude Code skill by Naren

> Use when the user has a board game, card game or tabletop RPG rulebook (PDF or text) and wants a rules question or dispute settled, or asks what the rulebook actually says (for example 'does the rulebook let me do this?', 'we're arguing about a rule', 'settle this using the rulebook').

Part of [Naren's Claude Toolkit](https://github.com/NarenDawar/narens-claude-toolkit).

## When it triggers

Give Claude a rulebook and a rules argument: "does the rulebook let me draw a second card after a locomotive?", "we're arguing about the end of the game", "what does the rulebook say about this?".

## What it does

Claude finds the passages that bear on the question using a small script, reads the surrounding pages for exceptions, and returns one of four verdicts: ANSWERED (a passage states it), COMBINED (it follows from several passages), AMBIGUOUS (two readings fit) or SILENT (the rulebook does not cover it). Every quote comes with a PDF page number, and a script checks each quote against the PDF text before the answer is shown, so an invented or misquoted rule is caught. Where the rulebook is silent or ambiguous, Claude says so instead of guessing, and only looks at the publisher's FAQ or errata if you ask, labeled as outside the rulebook.

It does not invent rules, and it does not decide house rules for you.

## Install

**Plugin marketplace (recommended)**

```text
/plugin marketplace add NarenDawar/narens-claude-toolkit
/plugin install rules-referee@narens-claude-toolkit
```

**Manual**

Copy `plugins/rules-referee/skills/rules-referee` into `~/.claude/skills/`.

Needs Python 3.9 or newer and either the `pypdf` package (`pip install pypdf`) or the `pdftotext` program from poppler.

## Limits

- **Plain Claude's answers on a clean rulebook are usually right; the difference is evidence.** In tests on two official English rulebooks (4 and 16 pages), Claude without this skill gave correct answers but cited no page numbers, and 3 of the 8 quotes it gave on the longer rulebook were reworded inside quotation marks (for example "select" for the rulebook's "choose"). With the skill, every quote was verbatim and paged. Only two rulebooks were tested, both in English, both with a text layer.
- **Scanned PDFs have no text to check.** Pages without a text layer are listed, and anything read from an image is marked unverified.
- Multi-column layouts and drop-caps can scramble extracted text. Quotes are matched ignoring spacing, case and punctuation, but the words must match exactly.
- The check proves a quote is in the PDF, not that Claude understood it correctly. Reading and judging the rule is still Claude's job.
- It does not look up errata unless you ask, and forum answers are never treated as the rulebook.

## Example

**Before:** "Can I take a second card after a face-up locomotive?" gets a confident answer, a paraphrase of the rule, and no page number.

**After:** "ANSWERED: no. Page 3: 'it must be the first train card you draw this turn and you cannot then draw a second card.' A locomotive drawn blind from the deck is an exception, quoted on the same page."

---

Made by [Naren](https://github.com/NarenDawar). If this helped, star the repo.
