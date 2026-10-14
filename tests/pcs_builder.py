"""Builds small transcripts and picks for the podcast-clip-scout tests."""
import json

TEXTS = [
    "Welcome back to the show.",
    "Today we are talking about failure.",
    "I once lost every customer I had in a single week.",
    "Nobody tells you how quiet that feels.",
    "I kept refreshing the dashboard, hoping it was a bug,",
    "and it was not a bug.",
    "That was the day I learned what a runway really is.",
    "You do not run out of money, you run out of time.",
    "Anyway, let us take a quick break.",
    "We are back.",
    "So what did you change afterwards?",
    "Everything, honestly.",
    "I stopped building features nobody asked for.",
    "I started calling ten users a week, and",
    "the second call told me more than a year of guessing.",
    "People will tell you what they need if you shut up.",
    "That is the whole secret, and it is boring.",
    "Okay, so what about hiring?",
    "Hire slowly.",
    "Fire quickly.",
    "That is also boring advice.",
    "But it works.",
    "Thanks for listening.",
    "See you next week.",
]


def sample_cues():
    """24 cues of 5 seconds each, as (start, end, text)."""
    return [(i * 5.0, (i + 1) * 5.0, text) for i, text in enumerate(TEXTS)]


def cue_dicts():
    return [
        {"n": i, "start": s, "end": e, "text": t, "speaker": None}
        for i, (s, e, t) in enumerate(sample_cues(), 1)
    ]


def _stamp(seconds, sep):
    ms = round(seconds * 1000)
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def srt(cues, crlf=False, bom=False):
    blocks = [
        f"{i}\n{_stamp(s, ',')} --> {_stamp(e, ',')}\n{t}"
        for i, (s, e, t) in enumerate(cues, 1)
    ]
    text = "\n\n".join(blocks) + "\n"
    if crlf:
        text = text.replace("\n", "\r\n")
    return ("﻿" if bom else "") + text


def vtt(cues):
    blocks = [f"{_stamp(s, '.')} --> {_stamp(e, '.')}\n{t}" for s, e, t in cues]
    return "WEBVTT\n\n" + "\n\n".join(blocks) + "\n"


def json_segments(cues):
    return json.dumps([{"start": s, "end": e, "text": t} for s, e, t in cues])


def ideal_picks():
    """Two clips that pass `check` with no errors and no warnings on sample_cues()."""
    def reasons(tag):
        return {d: f"{tag}: {d}" for d in ("hook", "standalone", "emotion", "payoff", "quotable")}

    return {
        "clips": [
            {
                "start_cue": 3,
                "end_cue": 8,
                "scores": {"hook": 3, "standalone": 3, "emotion": 2, "payoff": 2, "quotable": 2},
                "total": 12,
                "reasons": reasons("first"),
                "caption": "He lost every customer in a week. Here is what he learned about runway.",
            },
            {
                "start_cue": 12,
                "end_cue": 17,
                "scores": {"hook": 2, "standalone": 3, "emotion": 1, "payoff": 2, "quotable": 2},
                "total": 10,
                "reasons": reasons("second"),
                "caption": "Stop guessing. Call ten users a week and shut up.",
            },
        ]
    }
