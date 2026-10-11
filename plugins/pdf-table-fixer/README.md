# pdf-table-fixer: a Claude Code skill by Naren

> Repair table structure in already-tagged PDFs and check the result with veraPDF.

Part of [Naren's Claude Toolkit](https://github.com/NarenDawar/narens-claude-toolkit).

## When it triggers

Ask things like "fix the table headers in this PDF", "my PDF tables fail PDF/UA", or "repair the table tags". It works on PDFs that are already tagged; it does not tag untagged ones.

## What it does

It repairs only table structure: which cells are headers (and their scope), row and column spans, header links for multi-level tables, and the order of rows and cells. The flow is **inspect** (a script lists every table and the problems the file proves), **plan** (Claude reads that and writes a small JSON plan), **diff** (you see exactly what would change), **apply** (a new file is written, never the original) and **validate** (veraPDF PDF/UA-1 before and after, flagging any rule that newly fails).

Before a new file is kept, the script checks that every page's content is byte-identical and that no tagged content was lost from the structure tree. A plan that does not fit the file is refused and nothing is written.

## Requirements

- Python 3 and `pikepdf`: `python -m pip install pikepdf` (the first skill in this toolkit that is not standard-library only).
- Optional, for validation: Java and [veraPDF](https://verapdf.org/). Without them the skill says "not validated" and never claims a pass.

## Install

**Plugin marketplace (recommended)**

```text
/plugin marketplace add NarenDawar/narens-claude-toolkit
/plugin install pdf-table-fixer@narens-claude-toolkit
```

**Manual**

Copy `plugins/pdf-table-fixer/skills/pdf-table-fixer` into `~/.claude/skills/`.

## Limits

- Tagged PDFs only, and only table structure. Alt text, tagging and other fixes are out of scope.
- veraPDF PDF/UA-1 is the one judge. PAC may disagree on some rules; this makes no claim about PAC.
- The checks prove the structure is valid and consistent, not that the chosen headers are the semantically right ones. That rests on Claude's reading and your review of the diff.
- Encrypted and signed files are refused. Saving rewrites the whole file.
- Row and cell order evidence uses where text is drawn and is approximate. Text in fonts without a ToUnicode map cannot be read and is flagged.
- **Not yet run on real-world PDFs, and the veraPDF report parsing has not been run against a real veraPDF** (veraPDF was not installed when this was built; the parser is tested against report text written to match veraPDF's XML).

## Example

**Before:** a PDF's table has every cell tagged as data, so a screen reader reads "Name, Qty, Apple, 3, Pear, 5" with no headers.

**After:** the plan sets the first row as headers; the screen reader announces "Qty: 3" for the cell under it. veraPDF's table-related failures drop and nothing new fails.

---

Made by [Naren](https://github.com/NarenDawar). If this helped, star the repo.
