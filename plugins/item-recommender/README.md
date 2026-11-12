# item-recommender: a Claude Code skill by Naren

> Use when the user asks Claude to find, pick, compare or recommend a product to buy (for example 'find me the best toothbrush', 'which laptop should I get', 'best budget vacuum', 'X vs Y, which one?', 'what's worth buying for ...').

Part of [Naren's Claude Toolkit](https://github.com/NarenDawar/narens-claude-toolkit).

## When it triggers

Ask for the best of anything you would buy: "find me the best toothbrush", "which laptop should I get", "best budget vacuum", "X vs Y, which one?".

## What it does

Claude fixes the criteria that matter for the category before reading any ranking, then opens sources in tiers: independent labs that buy and measure first, then practitioner communities, then owner reviews with the failure modes. Affiliate "best of" pages are used only to find model names, never as evidence. A pick needs at least three opened sources, two of them independent. Finalists are searched for known failures, and the exact current model and price are checked and dated. The answer gives one pick, a cheaper option, who should choose differently, an evidence ledger, and what could change the pick. If the category barely matters, it says so instead of crowning a winner.

It does not buy anything, track prices over time, or promise a pick suits you. It does not rank services or places.

## Install

**Plugin marketplace (recommended)**

```text
/plugin marketplace add NarenDawar/narens-claude-toolkit
/plugin install item-recommender@narens-claude-toolkit
```

**Manual**

Copy `plugins/item-recommender/skills/item-recommender` into `~/.claude/skills/`.

## Limits

- **Not yet tested against many categories.** It was written after one baseline run, a plain "best toothbrush" lookup that ran one search, opened no pages and leaned on promotional pages.
- It sees only what web search and public pages show. Paywalled lab results and blocked forums are listed as unchecked.
- Prices change daily; each one is dated and should be re-checked at purchase.
- Needs web search. Without it, it should say so and stop, since it will not recommend from memory.

## Example

**Before:** "Find me the best toothbrush" gets one search, a list from snippets of promotional pages, and a note that prices were not checked.

**After:** one pick for your budget with a dated price, a cheaper alternative, the criteria, an evidence ledger with each source's tier, known failure modes, and what would change the answer.

---

Made by [Naren](https://github.com/NarenDawar). If this helped, star the repo.
