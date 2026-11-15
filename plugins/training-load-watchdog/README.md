# training-load-watchdog: a Claude Code skill by Naren

> Use when a runner shares a Strava, Garmin or other activity export (CSV) and wants to know if their recent training looks risky, if they are ramping up too fast, or what the next weeks of running should be (for example 'check my training for injury risk', 'am I doing too much?', 'plan my next two weeks from my Strava export').

Part of [Naren's Claude Toolkit](https://github.com/NarenDawar/narens-claude-toolkit).

## When it triggers

Give Claude your activity export and ask whether your training looks risky or what to run next: "check my Strava export for injury risk", "plan my next two weeks".

## What it does

A script reads your CSV (Strava `activities.csv`, Garmin Connect export, or any file with a date, a type and a distance) and checks each recent run against the longest run of the 30 days before it. A run more than 10% longer is a small spike, more than 30% moderate, more than 100% large. Claude reports the spikes with the numbers, then, if you ask, plans two weeks and checks every planned run with the same script so the plan does not contain a spike.

It is built on the single-session finding of [Frandsen et al., Br J Sports Med 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12421110) (5,205 runners). The same study found no link between week-to-week change and injury and a negative one for the acute:chronic workload ratio, so those popular rules are deliberately not used as warnings.

## Install

**Plugin marketplace (recommended)**

```text
/plugin marketplace add NarenDawar/narens-claude-toolkit
/plugin install training-load-watchdog@narens-claude-toolkit
```

**Manual**

Copy `plugins/training-load-watchdog/skills/training-load-watchdog` into `~/.claude/skills/`.

Needs Python 3.9 or newer. No other packages.

## Limits

- **Not medical advice.** The evidence is observational and about groups; a spike is a reason to look, not a prediction for you. Lasting pain goes to a physiotherapist or doctor.
- **Running only.** The study covered running sessions. Other sports are described, not judged.
- **Distance only.** It does not see pace, heart rate, sleep or how hard a run was, so it cannot say whether a run was easy.
- **Only what is in the file.** A run missing from the export looks like rest.
- Tested on one real public Strava export (24 unique runs, 59 rows with every activity doubled, which the script now drops) and on built test files in Strava and Garmin layouts. Real exports from other watches and languages may have date formats it does not know; it says how many rows it skipped.
- In two comparisons on the same file, plain Claude gave sensible plans but leaned on week-to-week jumps and the acute:chronic ratio (one answer called a ratio "fine", another called 1.46 "borderline"; the study found no link for either), quoted thresholds it said were from memory, and never measured a run against the 30-day longest. The skill gave the exact figure (the marathon was 44.7% over the previous longest) and sourced it. Plans were equally cautious; the gain is the evidence and the numbers, not safer plans.

## Example

**Before:** "Last week +26% on the week before, over the 10% rule. Acute:chronic ratio 0.96, in the sweet spot."

**After:** "No spikes in the last 28 days. Longest run in the last 30 days is 9.63 km, so the ceiling for a single run is 10.59 km. Planned 12 km on Jan 18 is a small spike (+24.6%)."

---

Made by [Naren](https://github.com/NarenDawar). If this helped, star the repo.
