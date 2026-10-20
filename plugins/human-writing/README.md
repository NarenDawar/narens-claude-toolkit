# human-writing: a Claude Code skill by Naren

> Write and edit prose so it reads like one specific person wrote it, not like a language model.

Part of [Naren's Claude Toolkit](https://github.com/NarenDawar/narens-claude-toolkit).

## When it triggers

Ask things like "write a Slack message announcing the office is closed, keep it casual", "make this sound like me" with a pasted sample of your writing, or "this reads like ChatGPT wrote it, can you fix it". It also applies as a last pass on anything Claude drafted that you will send or publish under your own name.

It stays out of code, translation, proofreading-only requests, legal text, and anything whose exact wording must not change.

## What it does

People who spot machine-made prose are mostly reacting to genericness: no particular reader, no position, no real detail, no voice. So the skill works on the cause instead of swapping banned words.

- **Write mode.** Asks for the reader, the one point, the real details (names, numbers, what happened) and two or three samples of your own writing, then drafts with plain habits. It never invents facts, quotes, numbers or feelings; where a fact is missing it leaves a visible placeholder.
- **Edit mode.** Marks problems in order of how much they matter (missing specifics, structural tells, assistant residue, then vocabulary), fixes the cause rather than the string, keeps every fact, and changes as little as possible in formal writing.
- **Lint script.** `scripts/lint.py` counts patterns per 1,000 words (dashes, "not just X but Y", trailing -ing clauses, word triads, bold-label bullets), sentence-length spread, and leaked artifacts. With `--sample` it compares against your own writing; with `--original` it reports numbers, quotes and names that were dropped or added; with `--clean` it removes leaked citation markers, tracking parameters and stray invisible characters.

The reference files hold a structure-first catalog of tells, a dated vocabulary list, Claude's habits by model version, genre notes, a voice-profile procedure, and the research behind all of it.

## What it does not do

It does not promise to pass AI detectors and it does not remove watermarks. The research behind it found detector scores say nothing about quality, and text watermarks are statistical signals that character cleanup cannot touch. If your school, employer or publisher requires disclosure of AI help, follow that rule.

## Requirements

Python 3, standard library only, for the optional lint script.

## Install

**Plugin marketplace (recommended)**

```text
/plugin marketplace add NarenDawar/narens-claude-toolkit
/plugin install human-writing@narens-claude-toolkit
```

**Manual**

Copy `plugins/human-writing/skills/human-writing` into `~/.claude/skills/`.

## Limits

- **Lightly tested.** In a blind comparison on 8 prompts, judged by Claude models (two judges per prompt, shuffled labels), it ranked first on average rank (1.94) against `blader/humanizer` (2.00), `stop-slop` (2.69) and plain Claude (3.38). The gap to `blader/humanizer` is not meaningful at this sample size, the judges are the same model family as the writers, and no human raters were used. Every skill beat plain Claude mainly by not inventing facts.
- The tell catalog is English-tuned. For other languages only the principles apply.
- The vocabulary list is dated and goes stale with each model release. Refresh `references/tells-lexical.md` when a new model ships.
- Several facts in the references (provider watermark announcements, EU AI Act timing) came from secondary sources. Verify before quoting them.
- Claude often handles short writing requests without calling any skill. If it does not fire, say "use the human-writing skill".

## Example

From the test runs: a LinkedIn post that sounded like a chatbot wrote it, edited with the skill.

**Before** (the pasted draft):

> I'm thrilled to announce that I've officially embarked on an exciting new chapter in my career! This Monday, I joined Kestrel Studio as a Gameplay Engineer. After three incredible years at a mobile studio, where I had the privilege of shipping two titles, I'm eager to leverage my skills in a new and dynamic environment. I'll be working on a co-op shooter alongside a talented team of 14 passionate individuals. It's not just a job, it's an opportunity to grow, learn, and make a lasting impact. Here's to new beginnings! #gamedev #newjob #grateful

**After** (the skill's output, which also asks for one or two of your own posts and a real detail instead of making one up):

> Started at Kestrel Studio on Monday as a gameplay engineer.
>
> I spent the last three years at a mobile studio and shipped two titles there. Now I'm on a co-op shooter with a team of 14.
>
> #gamedev #newjob

---

Made by [Naren](https://github.com/NarenDawar). If this helped, star the repo.
