# citation-verifier: a Claude Code skill by Naren

> Use when the user has a manuscript, bibliography, reference list or AI-written text with citations and wants to know whether the references are real and correctly cited, or whether the cited works actually say what the text claims (for example 'check my references', 'are these citations hallucinated?', 'does this paper really say that?').

Part of [Naren's Claude Toolkit](https://github.com/NarenDawar/narens-claude-toolkit).

## When it triggers

You have a draft, a bibliography or text a model wrote, with citations, and you ask "are these real?", "check my references" or "does the paper really say that?".

## What it does

A free script looks every reference up in Crossref and OpenAlex and compares title, first author and year with the record it finds. Each reference gets one status: `verified`, `metadata-mismatch` (it exists, but the year or author differs), `doi-mismatch` (the DOI is a different work, with what it actually is), `doi-not-found`, `not-found` or `error`. Then, for the claims your text makes about a cited paper, Claude pulls the abstract or open-access full text, finds the passage that bears on the claim, and a second script confirms the quote is really in the source. A claim is reported as supported, partly supported, not supported or not checked.

It never calls a reference "fake" or "hallucinated". A reference with no match is reported as "no match found", with the searches that were run, because the databases are weak on books, theses and non-English work. Only titles, author surnames and DOIs leave your machine, never the manuscript.

It is a free alternative to paid reference-checking services.

## Install

**Plugin marketplace (recommended)**

```text
/plugin marketplace add NarenDawar/narens-claude-toolkit
/plugin install citation-verifier@narens-claude-toolkit
```

**Manual**

Copy `plugins/citation-verifier/skills/citation-verifier` into `~/.claude/skills/`.

Needs Python 3.9 or newer and a network connection. No other packages. OpenAlex has a small shared free quota; set `OPENALEX_API_KEY` to use your own.

## Limits

- **Plain Claude with web tools was already good on a short list.** On 10 references (6 real, 2 invented, 1 real title with another paper's DOI, 1 with the wrong year and journal), Claude without the skill found all four problems. Its answer called the invented ones "likely fabricated", gave one verdict from memory, and did not check any claim against a paper. With the skill the same four were found, with the database record shown for each, the unmatched ones were worded as "no match found", and two claims were checked against the abstract of the cited paper (one supported, one reported as contradicting the abstract and left open until the full text is read). One test list, one run each.
- **Rate limits.** OpenAlex answered 429 (too many requests) during testing. The script then checks Crossref only and says so. In that run a famous 2017 conference paper that has no Crossref record was matched to a 2025 record and flagged `metadata-mismatch`, which is right to flag and wrong to conclude from. Confirm those against the publisher or OpenAlex.
- **Databases have gaps.** `not-found` is not proof that a work does not exist. Books, theses, preprints, small journals and non-English works are weakly covered.
- **Claims are only as good as the text it can open.** Paywalled papers are reported as not checked, and an abstract can support a claim but cannot rule one out.
- **It checks that a reference exists and matches, not that it is a good source.**

## Example

**Before:** "Reference 8, Kahneman and Tversky 1981, is likely fabricated. Remove it."

**After:** "Reference 8: no match in Crossref, OpenAlex or a web search for the exact title. The Kahneman and Tversky paper in Econometrica is the 1979 one, already reference 4. Confirm the intended source before removing it."

---

Made by [Naren](https://github.com/NarenDawar). If this helped, star the repo.
