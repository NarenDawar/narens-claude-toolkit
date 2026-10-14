"""Parse SRT, VTT and JSON transcripts into numbered cues. Standard library only."""
import html
import json
import math
import re
from pathlib import Path


class TranscriptError(Exception):
    """A transcript that cannot be read; the message is one line for the user."""


_TIME = r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})"
_TIMING = re.compile(rf"^\s*{_TIME}\s*-->\s*{_TIME}(?:\s.*)?$")
_TAG = re.compile(r"<[^>]*>")
_VOICE = re.compile(r"<v(?:\.[^\s>]*)?\s+([^>]+)>")
_SKIP_BLOCK = re.compile(r"^(WEBVTT|NOTE|STYLE|REGION)(\s|$)")


def _ms(hours, minutes, seconds, fraction):
    whole = (int(hours or 0) * 60 + int(minutes)) * 60 + int(seconds)
    return whole * 1000 + int(fraction.ljust(3, "0"))


def _cue(n, start_ms, end_ms, text, speaker):
    return {"n": n, "start": start_ms / 1000, "end": end_ms / 1000, "text": text, "speaker": speaker}


def _parse_blocks(text):
    """SRT and VTT share one shape: blocks separated by blank lines, a timing line, then text."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    found = []
    for block in re.split(r"\n\s*\n", text):
        lines = block.strip("\n").split("\n")
        if not lines or _SKIP_BLOCK.match(lines[0].strip()):
            continue
        timing_at = next((i for i, line in enumerate(lines) if _TIMING.match(line)), None)
        if timing_at is None:
            continue
        g = _TIMING.match(lines[timing_at]).groups()
        start_ms, end_ms = _ms(*g[:4]), _ms(*g[4:])
        if end_ms < start_ms:
            raise TranscriptError(f"a cue ends before it starts: {lines[timing_at].strip()}")
        raw = " ".join(lines[timing_at + 1:])
        voice = _VOICE.search(raw)
        speaker = voice.group(1).strip() if voice else None
        clean = " ".join(html.unescape(_TAG.sub("", raw)).split())
        if clean:
            found.append((start_ms, end_ms, clean, speaker))
    return found


def _number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _parse_json(text):
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise TranscriptError(f"invalid JSON: {exc}")
    if isinstance(data, dict) and isinstance(data.get("segments"), list):
        data = data["segments"]
    if not isinstance(data, list):
        raise TranscriptError("JSON must be a list of {start, end, text} segments")
    found = []
    for i, seg in enumerate(data, 1):
        if not isinstance(seg, dict):
            raise TranscriptError(f"segment {i} is not an object")
        start, end, words = seg.get("start"), seg.get("end"), seg.get("text")
        if not _number(start) or not _number(end):
            raise TranscriptError(f"segment {i} needs numeric start and end seconds")
        if not isinstance(words, str):
            raise TranscriptError(f"segment {i} needs a text string")
        if end < start:
            raise TranscriptError(f"segment {i} ends before it starts")
        speaker = seg.get("speaker")
        speaker = speaker.strip() if isinstance(speaker, str) and speaker.strip() else None
        clean = " ".join(words.split())
        if clean:
            found.append((round(start * 1000), round(end * 1000), clean, speaker))
    return found


def _is_json(path, text):
    if path.suffix.lower() == ".json":
        return True
    if path.suffix.lower() in (".srt", ".vtt"):
        return False
    return text.lstrip()[:1] in ("[", "{")


def parse_file(path):
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise TranscriptError(f"cannot read {path}: {exc.strerror or exc}")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise TranscriptError(f"{path} is not valid UTF-8 text")
    if not text.strip():
        raise TranscriptError(f"{path} is empty")
    found = _parse_json(text) if _is_json(path, text) else _parse_blocks(text)
    if not found:
        raise TranscriptError(f"no cues found in {path}")
    return [_cue(n, *item[:3], item[3]) for n, item in enumerate(found, 1)]


def fmt_time(seconds):
    ms = round(seconds * 1000)
    hours, rem = divmod(ms, 3600000)
    minutes, rem = divmod(rem, 60000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"
