# platform-opportunity-scout: a Claude Code skill by Naren

> Use when the user names a platform or medium (Roblox, YouTube, Instagram, TikTok, Twitch, Etsy, Substack and the like) and wants business ideas built on or around it, or asks what to make, sell or build there (for example 'business ideas for Roblox', 'what could I build around YouTube creators', 'find me a niche on Instagram').

Part of [Naren's Claude Toolkit](https://github.com/NarenDawar/narens-claude-toolkit).

## When it triggers

Name a platform and ask what to build there: "business ideas for Roblox", "what could I build around YouTube creators", "find me a niche on Instagram". It works for any medium with an audience or marketplace: Roblox, YouTube, TikTok, Twitch, Etsy, Substack and so on.

## What it does

Claude searches for how money moves on the platform, generates 10 to 15 candidate ideas across three kinds (native, picks-and-shovels, arbitrage), gathers evidence for each, and cuts to 3 to 5. Every survivor then goes through a verification pass: each claim is opened at its source and dated, numbers need a second independent source, a real payer must exist, competitors are searched three ways, and the platform's current terms are read for the part the idea depends on. The report ranks survivors with an evidence ledger, lists the ideas that were killed and why, and says what could not be checked.

It does not build the business, write code, or promise that an idea will make money.

## Install

**Plugin marketplace (recommended)**

```text
/plugin marketplace add NarenDawar/narens-claude-toolkit
/plugin install platform-opportunity-scout@narens-claude-toolkit
```

**Manual**

Copy `plugins/platform-opportunity-scout/skills/platform-opportunity-scout` into `~/.claude/skills/`.

## Limits

- **Untested against real outcomes.** Nobody has checked whether ideas that survive its verification do better than ones that do not. It reduces unsourced claims; it does not predict success.
- It sees only what web search and public pages show. Private communities, paywalled data and platform dashboards are listed as unchecked, not guessed.
- Platform economics and policies change, so a result is only as fresh as the sources it cites. Each source is dated in the report.
- Needs web search. Without it, it should say so and stop, since it will not report facts from memory.

## Example

**Before:** "Business ideas for Roblox?" gets a list of ten generic ideas (make a popular game, sell UGC items) with payout figures recalled from memory.

**After:** a ranked shortlist of a few ideas, each with sourced evidence of who pays, competitors found, platform risk, a one-week test under $100, and a short list of ideas it killed and why.

---

Made by [Naren](https://github.com/NarenDawar). If this helped, star the repo.
