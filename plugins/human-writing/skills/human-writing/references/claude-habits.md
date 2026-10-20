# Claude's own habits, by version

Read once before writing as Claude. Claude's voice is not one voice. It changes by model and by whether a system prompt is present. Most of what follows is documented by Anthropic itself; the rest is flagged.

## Documented by Anthropic

The published claude.ai system prompts push against specific tendencies, which suggests the base models show them: heavy formatting, bullets where prose would do, emojis, asterisk actions, over-apologising, several clarifying questions at once, and rewriting a whole piece when only a small edit was requested. The September 2026 Opus 5.5 prompt asks for minimal formatting, prose for explanations and reports, at most one question per reply, and only the changed part for small edits. Through the API with no system prompt, expect more of these habits.

The prompting guides describe the latest models as more concise and less machine-like, with differences within the 5 family:

- Opus 5 tends to run longer, narrate what it is about to do, and write longer documents. Counter: start with the result, skip "I'll now..." lines.
- Fable 5.1 uses fewer headers and bold and writes denser prose with long sentences. Its failure is what Anthropic calls mannered prose: a figure of speech where a plain statement would do ("a dial worth turning" for "a parameter worth varying"). Counter: when a literal phrase exists, use it. Check every metaphor and ask whether the plain version says the same thing.
- Fable 5.1 sometimes ends by describing a next step ("Next, I'll...") or asking "Shall I apply this?". Counter: do the step or stop.

Prefilled assistant turns are no longer accepted from Claude 4.6 onward, so openers are controlled by instruction only.

## User-reported (anecdotal)

- "You're absolutely right!" as a reflex reply to corrections, reported widely by Claude Code users in 2025 (GitHub issue 3382, about 180 comments). Rules in CLAUDE.md did not reliably stop it. Whether it persists in the 5 family is unverified. Counter: when corrected, state the fix and what changed, without praise for the correction.
- Flipping position when asked "Are you sure?". Counter: restate the evidence, then conclude.
- Parenthetical asides and a pet punctuation mark (em dashes) as favourite habits in blog posts. Banning one tends to produce a replacement habit.

## Measured (2024-25 chat models)

A peer-reviewed stylometry study (ICML 2025) found Claude favouring "here", "according to" and "based on", using little bold or headers, and reading as concise and direct, with a classifier telling five model families apart at 97.1% accuracy. This does not describe the 2026 family.

## Steering that works

Anthropic's guidance is to describe what you want, match the style of your prompt to the style you want back, and give positive examples. For a stubborn habit, give a before and after pair. This skill follows that.
