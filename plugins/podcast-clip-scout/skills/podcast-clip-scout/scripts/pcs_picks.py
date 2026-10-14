"""Validate the clips Claude picked. Standard library only.

The checks prove the list is consistent (real cues, lengths in range, no overlaps,
arithmetic and ordering right). They do not judge whether a hook is a good hook.
"""
import json
from pathlib import Path

DIMENSIONS = ("hook", "standalone", "emotion", "payoff", "quotable")
MAX_SCORE = 3
GAP_WARN_SECONDS = 5.0
_CLOSERS = "\"')]”’»"


class PicksError(Exception):
    """A picks file that cannot be read; the message is one line for the user."""


def load_picks(path):
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PicksError(f"cannot read {path}: {exc.strerror or exc}")
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except UnicodeDecodeError:
        raise PicksError(f"{path} is not valid UTF-8 text")
    except ValueError as exc:
        raise PicksError(f"{path} is not valid JSON: {exc}")
    if not isinstance(data, dict):
        raise PicksError(f'{path} must hold a JSON object with a "clips" list')
    return data


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _ends_sentence(text):
    return text.rstrip().rstrip(_CLOSERS).endswith((".", "?", "!"))


def _check_range(tag, clip, cues, min_s, max_s, errors, warnings):
    """Returns (first_cue, last_cue, start, end) when the cue numbers are usable, else None."""
    first, last = clip.get("start_cue"), clip.get("end_cue")
    if not _is_int(first) or not _is_int(last):
        errors.append(f"{tag}: start_cue and end_cue must be whole cue numbers")
        return None
    missing = [n for n in (first, last) if not 1 <= n <= len(cues)]
    if missing:
        errors.append(f"{tag}: cue {missing[0]} does not exist (the transcript has cues 1-{len(cues)})")
        return None
    if first > last:
        errors.append(f"{tag}: start_cue {first} is after end_cue {last}")
        return None
    start, end = cues[first - 1]["start"], cues[last - 1]["end"]
    length = round(end - start, 3)
    if length < min_s or length > max_s:
        errors.append(f"{tag}: lasts {length:g}s, outside {min_s:g}-{max_s:g}s")
    if first > 1 and not _ends_sentence(cues[first - 2]["text"]):
        warnings.append(f"{tag}: starts mid-sentence (cue {first - 1} does not end a sentence)")
    if not _ends_sentence(cues[last - 1]["text"]):
        warnings.append(f"{tag}: ends mid-sentence (cue {last} does not end a sentence)")
    for k in range(first, last):
        gap = round(cues[k]["start"] - cues[k - 1]["end"], 3)
        if gap > GAP_WARN_SECONDS:
            warnings.append(f"{tag}: {gap:g}s gap between cues {k} and {k + 1}")
    return first, last, start, end


def _check_scores(tag, clip, errors):
    scores = clip.get("scores")
    if not isinstance(scores, dict):
        errors.append(f"{tag}: scores must be an object with {', '.join(DIMENSIONS)}")
        return None
    ok = True
    for dim in DIMENSIONS:
        if dim not in scores:
            errors.append(f"{tag}: scores is missing '{dim}'")
            ok = False
        elif not _is_int(scores[dim]) or not 0 <= scores[dim] <= MAX_SCORE:
            errors.append(f"{tag}: score '{dim}' must be a whole number from 0 to {MAX_SCORE}")
            ok = False
    for dim in scores:
        if dim not in DIMENSIONS:
            errors.append(f"{tag}: unknown score dimension {dim!r}")
            ok = False
    return scores if ok else None


def check(cues, picks, min_seconds=20.0, max_seconds=60.0, max_caption=150):
    """Returns (errors, warnings), two lists of one-line strings."""
    clips = picks.get("clips") if isinstance(picks, dict) else None
    if not isinstance(clips, list):
        return ['picks must be an object with a "clips" list'], []
    if not clips:
        return ["no clips: the list is empty"], []
    errors, warnings = [], []
    spans, keys = {}, {}
    for i, clip in enumerate(clips, 1):
        tag = f"clip {i}"
        if not isinstance(clip, dict):
            errors.append(f"{tag}: must be an object")
            continue
        span = _check_range(tag, clip, cues, min_seconds, max_seconds, errors, warnings)
        if span:
            spans[i] = span
        scores = _check_scores(tag, clip, errors)
        if scores is not None:
            expected = sum(scores[d] for d in DIMENSIONS)
            total = clip.get("total")
            if not _is_int(total) or total != expected:
                errors.append(f"{tag}: total is {total!r} but the scores add up to {expected}")
            keys[i] = (-expected, -scores["hook"], -scores["standalone"])
        reasons = clip.get("reasons")
        if not isinstance(reasons, dict):
            errors.append(f"{tag}: reasons must be an object with a line for each dimension")
        else:
            for dim in DIMENSIONS:
                line = reasons.get(dim)
                if not isinstance(line, str) or not line.strip():
                    errors.append(f"{tag}: reasons is missing a line for '{dim}'")
        caption = clip.get("caption")
        if not isinstance(caption, str) or not caption.strip():
            errors.append(f"{tag}: caption is missing")
        elif len(caption) > max_caption:
            errors.append(f"{tag}: caption is {len(caption)} characters, over {max_caption}")
    ids = sorted(spans)
    for pos, a in enumerate(ids):
        for b in ids[pos + 1:]:
            a_first, a_last, a_start, a_end = spans[a]
            b_first, b_last, b_start, b_end = spans[b]
            if (a_first <= b_last and b_first <= a_last) or (a_start < b_end and b_start < a_end):
                errors.append(f"clip {a} and clip {b} overlap")
    scored = sorted(keys)
    for before, after in zip(scored, scored[1:]):
        if keys[before] > keys[after]:
            errors.append(f"clips are not in ranked order: clip {after} should come before clip {before}")
    return errors, warnings
