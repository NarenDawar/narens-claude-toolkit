# Podcast Clip Scout: design

Status: approved
Date: 2026-10-13

## Purpose

Read a timestamped podcast transcript and produce a ranked list of short-form clip candidates, each with a start time, an end time, a hook score with reasons, and a caption, ready to hand to a cutter.

The skill picks and describes moments. It never touches audio or video. Its output feeds `podcast-use`, `skill-caption-clip` or plain `ffmpeg`.

## What is and is not validated

- The scoring is Claude's judgment. There is no test set of human-picked clips behind it, and the README says so.
- The helper script checks that the picks are consistent (real cues, in-range lengths, no overlaps, correct arithmetic). It does not check that a hook is a good hook.

## Decisions (made with the owner)

1. No test set. The scoring is unvalidated and documented as such.
2. A rubric plus a small stdlib-only Python helper.
3. One configurable length range, default 20 to 60 seconds, overridden with `--min` and `--max`. No platform presets, because their limits change and cannot be verified from here.
4. A weighted rubric of five dimensions, not one holistic score and not two passes.

## Layout

```
plugins/podcast-clip-scout/
  .claude-plugin/plugin.json
  README.md
  skills/podcast-clip-scout/
    SKILL.md
    scripts/pcs_transcript.py
    scripts/pcs_picks.py
    scripts/pcs_export.py
    scripts/clips.py
tests/pcs_builder.py, test_pcs_transcript.py, test_pcs_picks.py, test_pcs_export.py, test_pcs_cli.py
```

Plus a marketplace entry, a CHANGELOG entry and the regenerated `README.md` and `llms.txt`. No CI dependency change.

## Flow

1. The user gives Claude a transcript file.
2. Claude runs `clips.py cues FILE`, which prints numbered cues with timestamps.
3. Claude reads the text and writes `picks.json`, citing cue numbers only. Claude never types a timestamp.
4. Claude runs `clips.py check FILE --picks picks.json`, fixes every error, and repeats.
5. Claude runs `clips.py export FILE --picks picks.json --out DIR`, which writes ranked CSV and JSON.
6. Claude reports the ranked table and states what is unverified.

Long episodes: Claude reads the cues in cue-range chunks, collects candidates from each, and ranks across all of them. The helper sees only the final list.

## pcs_transcript.py (parser)

Parses to a list of cues `{n, start, end, text, speaker}`; `n` is 1-based.

- SRT and VTT, including VTT cue settings, `<v Speaker>` tags and inline tags, a BOM, and CRLF line endings.
- JSON: a list of `{start, end, text}` segments (seconds as numbers), optionally with `speaker`, or an object with that list under `"segments"` (the shape Whisper writes).
- Errors raise `TranscriptError` with a one-line message: unreadable file, empty file, no cues found, an end time before a start time.
- Overlapping cues are kept as they are.

## clips.py (CLI) and pcs_picks.py / pcs_export.py (check and export logic)

`cues FILE [--from N] [--to M]` prints `n  HH:MM:SS.mmm  text` per cue, optionally only cues N to M inclusive (a range past the end is clipped; the long-episode chunks use this).

`check FILE --picks picks.json [--min 20] [--max 60] [--max-caption 150]` reports every problem, not only the first.

Errors:
- A cue number does not exist, or `start_cue > end_cue`.
- The duration (end time of `end_cue` minus start time of `start_cue`) is outside `--min` to `--max`.
- Two clips overlap in time.
- A score is not an integer from 0 to 3, or one of the five dimensions is missing.
- `total` is not the sum of the scores.
- The list is not in ranked order (total descending; ties by `hook`, then `standalone`).
- The caption is empty or longer than `--max-caption` characters (my own cap, not a platform rule).
- A reason is missing for a dimension.

Warnings (do not change the exit code):
- The start cue does not begin a sentence, or the end cue does not end one (previous cue's text does not end in `.?!` or this cue's text does not).
- A gap longer than 5 seconds between consecutive cues inside a clip.

`export FILE --picks picks.json --out DIR` runs the same checks, refuses to write on errors, then writes `clips.csv` and `clips.json` with times formatted `HH:MM:SS.mmm`.

Exit codes: 0 clean, 1 picks invalid, 2 unreadable input or bad arguments.

## Rubric

Five dimensions, each an integer from 0 to 3, total 0 to 15.

| Dimension | 0 | 3 |
|---|---|---|
| hook | Opens on filler | First sentence grabs: a claim, question, surprise or conflict |
| standalone | Needs earlier context | A stranger understands it cold |
| emotion | Flat | Laughter, anger, vulnerability or real surprise |
| payoff | Trails off or cuts mid-thought | A clear punchline, conclusion or takeaway lands at the end |
| quotable | Nothing worth repeating | A line someone would screenshot or caption |

`SKILL.md` carries short anchors for scores 1 and 2. Ranking is by total; ties break by `hook`, then `standalone`.

## picks.json

```json
{"clips": [{"start_cue": 41, "end_cue": 58,
  "scores": {"hook": 3, "standalone": 2, "emotion": 2, "payoff": 3, "quotable": 1},
  "total": 11,
  "reasons": {"hook": "...", "standalone": "...", "emotion": "...", "payoff": "...", "quotable": "..."},
  "caption": "..."}]}
```

## SKILL.md behaviour

- Run `cues` first and read the whole transcript. Pick only from cue numbers it can see.
- Aim for the requested number of clips (default 5). If the episode lacks that many good moments, return fewer and say so.
- Write picks, run `check`, fix every error, then `export`.
- End with the ranked table and a plain statement that the scores are unvalidated judgment.
- Ask when input is ambiguous (for example missing speaker labels); do not guess.

## Tests

`unittest`, fixtures built in code, no network, no third-party packages.

- Parser: SRT, VTT (settings, voice tags), JSON, malformed input, empty file, overlapping cues, BOM, CRLF.
- Check: one test per rule above, a clean pass, and an all-errors case.
- Export: CSV and JSON round-trip, time formatting, refusal on errors.
- CLI: exit codes 0, 1 and 2.
- A fixture transcript with a hand-built ideal `picks.json` that must pass cleanly. It proves the pipeline, not the quality of the picks.

## Limits (stated in the README)

- The scoring is unvalidated against human picks.
- Text only: tone of voice, laughter not in the transcript and visuals are invisible.
- Transcript quality caps the result: bad timestamps or speaker labels give bad clips.
- No claim about what performs on any platform.
- The line with `podcast-use` reels is close. This skill chooses moments; it does not cut them.

## Out of scope

Cutting, burned-in captions, audio processing, show notes, platform presets, engagement prediction, ffmpeg export.
