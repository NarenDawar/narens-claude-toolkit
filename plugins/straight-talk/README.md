# straight-talk: a Claude Code skill by Naren

> Use when giving an assessment, review or verdict on something the user made or decided, or when the user pushes back, shows hurt, or cites others' approval of work you rated lower.

Part of [Naren's Claude Toolkit](https://github.com/NarenDawar/narens-claude-toolkit).

## When it triggers

You ask for a verdict on something you made or decided, then push back: "my mentor said it was strong", "this is kind of crushing", "the deadline is tonight", "just confirm it's fine". It also applies when you direct a choice Claude disagrees with.

## What it does

A short, always-cheap posture: no subagents and no multi-advisor council. Claude states its verdict in the first sentence, gives reasons tied to the work, credits only specific strengths, says "I haven't seen X" for anything it wasn't shown, and labels each pushback as new evidence, a new argument, or the same position restated. Its position changes only for the first two. If the choice is yours, Claude does it and raises the risk once.

## Limits

- **Tested narrowly.** In fresh single-turn runs without the skill, Claude held its verdict under pressure; what slipped was tone: unearned praise, vouching for work it had not seen, cushioning before the verdict. The skill targets that. It has not been tested on long sessions, where agreement may drift over many turns.
- It does not make Claude right, only stops it softening a verdict because you are invested.

## Install

**Plugin marketplace (recommended)**

```text
/plugin marketplace add NarenDawar/narens-claude-toolkit
/plugin install straight-talk@narens-claude-toolkit
```

**Manual**

Copy `plugins/straight-talk/skills/straight-talk` into `~/.claude/skills/`.

## Example

**Before:** "Your mentor and the three readers aren't wrong. The line is clear, sincere and well-written... everything else stays as it is." (never saw the essay)

**After:** "Same position restated. No, I don't think it's a strong thesis... I haven't seen the essay, so I can't say what your readers responded to." Then the fastest fix.

---

Made by [Naren](https://github.com/NarenDawar). If this helped, star the repo.
