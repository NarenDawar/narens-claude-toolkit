# PDF Table Fixer: design

Date: 2026-10-11. Status: approved.

## Purpose

A skill that does one job: repair the table structure (header cells, scope, row and column spans, reading order) inside PDFs that are already tagged, then check the result with veraPDF. It exists because an existing PDF remediation skill states that complex tables are not fixed automatically. It does not tag untagged PDFs, write alt text or fix anything outside tables.

Brief the user gave: "rebuild table structure (headers, spans, reading order) in already-tagged PDFs and validate with veraPDF", choosing one validator because PAC and veraPDF disagree on some rules.

Decisions taken with the user:

- **Dependency:** `pikepdf` is allowed and required. This is the one skill in the toolkit that is not standard-library only.
- **Approach (B):** evidence, then a plan, then a safe apply. A script inspects and reports evidence; Claude reads it and writes a fix plan; a script validates the plan and applies it to a new file; veraPDF re-checks.
- **Validator:** veraPDF, PDF/UA-1 profile only. PAC is Windows-only and closed, so it cannot be scripted or run in CI. Reports always name the profile, and the README says PAC may disagree.

## Layout

`plugins/pdf-table-fixer/skills/pdf-table-fixer/` with `SKILL.md`, `scripts/tables.py`, `scripts/validate.py`, and a plugin README. Tests live in the repo's `tests/` (`test_tables.py`, `test_validate.py`). The plugin is added to the marketplace, CHANGELOG, generated README and `llms.txt` like the others.

## Scripts

All Python 3. Third-party import: `pikepdf` only. Each script checks its dependencies at startup and names what is missing and how to install it.

- `tables.py inspect IN.pdf [--json]`: read-only. For each `Table` in the structure tree prints a stable table id, the page, the rows and cells as they are (element type, text, `RowSpan`, `ColSpan`, `Scope`, `ID`/`Headers`) and the problems it can prove. A PDF with no structure tree is reported as untagged and out of scope, and the script stops.
- `tables.py plan-diff IN.pdf --plan PLAN.json`: validates the plan and shows, per table, what would change. Writes nothing.
- `tables.py apply IN.pdf --plan PLAN.json --out OUT.pdf`: runs the same validation, then writes a new PDF. Refuses `--out` equal to `IN`.
- `validate.py FILE.pdf [--against BEFORE.pdf]`: runs veraPDF (PDF/UA-1). Reports the failed-rule count and the table-related rules (those about `Table`, `TH`, `TD`, headers and spans). With `--against` it shows before and after side by side and flags any rule that fails after but not before as a regression, even when the total fell. If Java or veraPDF is missing it says "not validated" and never claims a pass.

## Plan file

JSON, keyed by table id from `inspect`. Per table: `header_rows` and `header_cols` (counts from top and left), `spans` (list of `{row, col, rowspan, colspan}`), and optionally `headers` (a map from a data cell to the header cell ids it falls under) for irregular tables. Nothing outside tables can appear in it.

## What apply may change

Only inside table structure elements:

- `TD` to `TH` for header cells, and `Scope` (`Row`, `Column`, `Both`) on each `TH`.
- `RowSpan` and `ColSpan` in the cell's table attribute object.
- `ID` on header cells and `Headers` on dependent data cells, for tables a simple scope cannot describe (two or more header levels, irregular spans).
- Reading order: reorders `TR` and cell children into row-major order. A table with `THead`/`TBody`/`TFoot` keeps that layout; rows move within their section.

It never changes text, page content streams, fonts, links, other tags or metadata. Cell text is read only.

## Safety rules

1. Output is a new file; the output is written to a temporary file and moved into place only after every check below passes.
2. The plan is validated against the file before any write: it names existing table ids; spans fit the grid with no overlap or overrun; header counts do not exceed the table size. Otherwise nothing is written, exit code 2, one line per problem.
3. Encrypted PDFs, PDFs with no structure tree and PDFs that cannot be opened are refused with the reason.
4. After writing, the output is reopened: page count is unchanged and every marked-content reference present before is still in the structure tree after. A failure here discards the output.
5. A summary lists each applied table: id, what changed, cells touched.
6. Exit codes: 0 success, 1 validation regression, 2 bad input, bad plan or missing dependency, 3 output failed the post-write check (nothing written).

Honest limit (README): the checks prove the structure is valid and consistent, not that the chosen headers are the semantically right ones. That rests on Claude's reading of the evidence and the user's review of the diff.

## Process in SKILL.md

1. Run `inspect`; if untagged, stop and say so.
2. Read the problem lists; ask the user only where the evidence does not decide.
3. Write the plan.
4. Show `plan-diff`; wait for a yes.
5. `apply`.
6. `validate --against`; report before and after, any regression, and "not validated" if veraPDF is absent.

Never quote document text beyond what a table row needs to be identified; never claim PAC compliance.

## Testing

- Tagged PDFs are generated in the tests by pikepdf; no binary fixtures are committed. Faults covered: header row in `TD`, missing `Scope`, span past the grid, ragged rows, rows out of order, a two-level header, an untagged PDF.
- Every problem `inspect` claims to prove has a test with a file that has the fault and one that does not.
- `apply`: a test per refusal rule; page content streams byte-identical; the marked-content check fails on a deliberately broken plan; failed apply leaves no output file.
- `validate.py` is tested against a stub veraPDF that prints its XML report; one live test runs real veraPDF and is skipped when it is absent.
- Tests skip cleanly when pikepdf is absent. The hosted CI installs nothing today; adding `pip install pikepdf` to the workflow is a change to `.github/workflows` and is to be confirmed with the owner before any push.

## Out of scope for v1

Untagged PDFs, alt text, scanned or image-only tables, forms, geometry-based table detection, PAC, PDF/UA-2.

## Unverified until the user tries it

Real-world PDFs from Word, InDesign, Acrobat and LaTeX each tag tables differently. The first live check is the user running the skill on a document they care about. veraPDF is not installed on the development machine, so the live veraPDF test cannot run here until it is.
