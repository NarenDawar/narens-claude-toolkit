# podcast-clip-scout: a Claude Code skill by Naren

> Pick ranked short-form clip candidates from a timestamped transcript.

Part of [Naren's Claude Toolkit](https://github.com/NarenDawar/narens-claude-toolkit).

## When it triggers

Ask things like "find the best clips in this episode", "which moments would work as shorts", or "pick reel candidates from this transcript", and give it an SRT, VTT or JSON transcript with timestamps.

## What it does

Claude reads the numbered, timestamped cues and scores candidate moments on five dimensions, each 0 to 3: `hook` (does the first sentence grab), `standalone` (does it make sense cold), `emotion`, `payoff` (does it end on a conclusion or punchline) and `quotable`. It writes its picks as cue numbers, never typed timestamps. A small helper script then derives the start and end times from the cues, checks the picks, and exports a ranked `clips.csv` and `clips.json` with start, end, scores, reasons and a caption for each clip.

It chooses and describes moments only. It does not cut audio or video, burn in captions, process audio or write show notes; use the times it writes with `podcast-use`, `ffmpeg` or your editor.

## Requirements

Python 3, standard library only. Nothing to install.

## Install

**Plugin marketplace (recommended)**

```text
/plugin marketplace add NarenDawar/narens-claude-toolkit
/plugin install podcast-clip-scout@narens-claude-toolkit
```

**Manual**

Copy `plugins/podcast-clip-scout/skills/podcast-clip-scout` into `~/.claude/skills/`.

## Limits

- **The scoring is unvalidated.** It is Claude's judgment against a stated rubric. It has not been compared with clips a person picked, and nobody has measured whether the clips it ranks high do better anywhere. The first real test is to hand-pick clips from a few episodes and see whether its ranking agrees.
- The helper checks that the list is consistent: cue numbers exist, lengths are in range (default 20 to 60 seconds, change with `--min` and `--max`), clips do not overlap, totals add up, the order is by rank, captions are present and under 150 characters (this tool's own default, not a platform rule). It cannot tell a strong hook from a weak one.
- Text only. Tone of voice, laughter that is not in the transcript and visuals are invisible to it.
- Transcript quality caps the result: wrong timestamps or missing speaker labels give wrong clips.
- No claim about what performs on any platform, and no platform presets.
- Warnings, not errors: a clip that starts or ends mid-sentence, or has a gap of more than 5 seconds between cues.

## Example

**Input:** a 24-cue transcript of a founder interview.

**Output** (`clips.csv`, abridged):

```text
rank,start,end,duration_seconds,start_cue,end_cue,total,...,caption
1,00:00:10.000,00:00:40.000,30.0,3,8,12,...,He lost every customer in a week. Here is what he learned about runway.
2,00:00:55.000,00:01:25.000,30.0,12,17,10,...,Stop guessing. Call ten users a week and shut up.
```
