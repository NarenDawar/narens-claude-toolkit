# news-source-reader: a Claude Code skill by Naren

> Use when the user shares a news article (link, saved page or pasted text) and asks how reliable or well sourced it is, who is behind the outlet, whether its claims hold up, or what it leaves out (for example 'is this article trustworthy?', 'where does this claim come from?', 'what's missing from this story?').

Part of [Naren's Claude Toolkit](https://github.com/NarenDawar/narens-claude-toolkit).

## When it triggers

You paste or link a news story and ask "how well sourced is this?", "who owns this outlet?" or "what is it leaving out?".

## What it does

A script reads the saved page and lists what the article points at: where its links go (government, court and journal pages count as primary), how many sources are named or anonymous, how many direct quotes it has, and which figures appear with no attribution or link. Claude then opens the primary links and checks each central claim against them, traces the unattributed figures, reads the outlet's own ownership and funding page, and compares the story with other outlets' coverage of the same event. The report says how many links were opened out of how many, and lists everything not checked.

It does not tell you what to think, it does not label an outlet or a writer as left or right, and it does not rate an article by whether it agrees with you.

## Install

**Plugin marketplace (recommended)**

```text
/plugin marketplace add NarenDawar/narens-claude-toolkit
/plugin install news-source-reader@narens-claude-toolkit
```

**Manual**

Copy `plugins/news-source-reader/skills/news-source-reader` into `~/.claude/skills/`.

Needs Python 3.9 or newer. No other packages. Opening links needs Claude's web tools.

## Limits

- **The script finds what to check, not whether it is true.** It matches patterns: link domains, phrases such as "people familiar with", and sentences with numbers and no attribution. It will miss sourcing that is described in words with no link, and flag figures that are fine.
- **Primary is a short list.** Government, court, journal and some dataset domains are treated as primary; a company's own filing or an NGO's report counts as "other".
- **Paywalled and blocked pages cannot be opened.** The report says which, and ownership is then marked `unverified` rather than filled in from memory.
- **Plain Claude was already good at this.** On one Guardian article it gave a thorough, honest report, but it gave ownership from memory (the about page was blocked), called the outlet "left-of-centre", and opened 2 of about 11 links. With the skill it opened the primary links first, reported ownership as unverified instead of guessing, gave no slant label, and listed what was not checked; the evidence it could actually reach was not much larger, because of blocked pages. One article, one run each.
- **Links that need a browser load blank.** In the test, two government database pages returned only a header, so those claims stayed unchecked and were reported that way.
- Only English-language pages were tested.

## Example

**Before:** "Ownership: the Guardian is owned by the Scott Trust (from background knowledge, not verified). The outlet is generally read as left-of-centre."

**After** (the skill's run on the same article, with a budget of 8 pages): "Rating: partly sourced. Opened 4 of 18 links; 2 of the 4 primary links loaded blank (the database pages need a browser). 21 named attributions, none anonymous, 4 figures with no attribution. The headline numbers rest on one tracker's data and could not be traced to it. Ownership: unverified, the about page did not load."

---

Made by [Naren](https://github.com/NarenDawar). If this helped, star the repo.
