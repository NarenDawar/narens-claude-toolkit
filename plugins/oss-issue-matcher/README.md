# oss-issue-matcher: a Claude Code skill by Naren

> Use when the user wants to find an open-source issue or project to contribute to, a good first issue, or help picking a repo whose maintainers will actually review and merge outside pull requests (for example 'find me a first open-source contribution', 'good first issues for Rust', 'is this repo worth contributing to').

Part of [Naren's Claude Toolkit](https://github.com/NarenDawar/narens-claude-toolkit).

## When it triggers

Ask for a first open-source contribution, good first issues in a language, or whether a repo is worth contributing to.

## What it does

Claude searches GitHub for open, unassigned issues labeled "good first issue" or "help wanted", then scores each candidate repo on how it has treated outside pull requests, using a small script that reads the last 100 PRs through the `gh` CLI. For outside contributors only, it measures the merge rate, the median time to a maintainer's first reply, the share of PRs left unanswered, and how recently the repo was committed to. Repos that ignore outside PRs are dropped before any issue is considered. For the issues in the repos that remain, it checks that nobody has claimed them, that no open PR already covers them, that a maintainer wants them, and what the contributing guide requires. You get the best three, each with its numbers.

It is read-only. It never comments on an issue, forks, or opens a PR for you.

## Install

**Plugin marketplace (recommended)**

```text
/plugin marketplace add NarenDawar/narens-claude-toolkit
/plugin install oss-issue-matcher@narens-claude-toolkit
```

**Manual**

Copy `plugins/oss-issue-matcher/skills/oss-issue-matcher` into `~/.claude/skills/`.

Needs the [GitHub CLI](https://cli.github.com) installed and logged in (`gh auth login`), and Python 3.9 or newer.

## Limits

- **The grades are a heuristic.** The thresholds (for example a reply within 72 hours) are judgment calls, not research findings. The script prints the raw numbers beside the grade so you can disagree.
- It samples the last 100 PRs. A maintainer reply buried deep in a long thread can be missed, so slow answers are slightly under-counted.
- A repo graded `avoid` may simply close unsolicited PRs unless an issue was agreed first. The skill says so when CONTRIBUTING makes it clear.
- A maintainer whose organisation membership is private appears as an outside contributor, which makes a repo look friendlier than it is.
- It cannot tell whether an issue is easy. It checks scope against your hours and skills from the issue text.
- GitHub API rate limits apply when scoring many repos.

## Example

**Before:** "Find me a first Python contribution" gets a repo with a "good first issue" label, picked from a search result, with no sign anyone reviews outside PRs.

**After:** three issues from repos that merged most outside PRs recently, each with its merge rate, median first-reply time and share left unanswered, plus a list of repos that were rejected and why.

---

Made by [Naren](https://github.com/NarenDawar). If this helped, star the repo.
