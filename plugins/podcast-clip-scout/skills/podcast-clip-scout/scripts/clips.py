#!/usr/bin/env python3
"""Podcast Clip Scout helper: cues | check | export. Standard library only.

Exit codes: 0 ok; 1 the picks are invalid; 2 unreadable input, bad arguments or an
output that cannot be written. Nothing is written unless the picks pass the check.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pcs_export  # noqa: E402
import pcs_picks  # noqa: E402
import pcs_transcript  # noqa: E402


def build_parser():
    parser = argparse.ArgumentParser(
        prog="clips.py", description="Check and export podcast clip picks against a transcript."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    cues = sub.add_parser("cues", help="print numbered, timestamped cues")
    cues.add_argument("transcript")
    cues.add_argument("--from", dest="first", type=int, default=1, help="first cue to print")
    cues.add_argument("--to", dest="last", type=int, default=None, help="last cue to print")

    for name, helptext in (("check", "validate picks.json"), ("export", "write ranked CSV and JSON")):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("transcript")
        sp.add_argument("--picks", required=True)
        sp.add_argument("--min", dest="min_seconds", type=float, default=20.0)
        sp.add_argument("--max", dest="max_seconds", type=float, default=60.0)
        sp.add_argument("--max-caption", dest="max_caption", type=int, default=150)
        if name == "export":
            sp.add_argument("--out", required=True)
    return parser


def cmd_cues(args):
    cues = pcs_transcript.parse_file(args.transcript)
    first = args.first
    last = len(cues) if args.last is None else min(args.last, len(cues))
    if first < 1 or first > len(cues) or last < first:
        print(f"error: cue range {first}-{args.last} is not inside 1-{len(cues)}", file=sys.stderr)
        return 2
    for cue in cues[first - 1:last]:
        who = f"[{cue['speaker']}] " if cue["speaker"] else ""
        print(f"{cue['n']:>5}  {pcs_transcript.fmt_time(cue['start'])}  {who}{cue['text']}")
    return 0


def _checked(args):
    """Returns (cues, picks, errors, warnings) after printing the report, or None for exit 2."""
    if args.min_seconds < 0 or args.max_seconds < args.min_seconds or args.max_caption < 1:
        print("error: --min must be 0 or more, --max at least --min, --max-caption at least 1", file=sys.stderr)
        return None
    cues = pcs_transcript.parse_file(args.transcript)
    picks = pcs_picks.load_picks(args.picks)
    errors, warnings = pcs_picks.check(
        cues, picks, args.min_seconds, args.max_seconds, args.max_caption
    )
    for line in errors:
        print(f"ERROR {line}")
    for line in warnings:
        print(f"WARN {line}")
    return cues, picks, errors, warnings


def cmd_check(args):
    result = _checked(args)
    if result is None:
        return 2
    _, picks, errors, warnings = result
    if errors:
        print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"ok: {len(picks['clips'])} clips ({len(warnings)} warning(s))")
    return 0


def cmd_export(args):
    result = _checked(args)
    if result is None:
        return 2
    cues, picks, errors, warnings = result
    if errors:
        print(f"{len(errors)} error(s), {len(warnings)} warning(s); nothing written")
        return 1
    try:
        csv_path, json_path = pcs_export.write_export(cues, picks, args.out)
    except OSError as exc:
        print(f"error: cannot write to {args.out}: {exc.strerror or exc}", file=sys.stderr)
        return 2
    print(f"wrote {csv_path}")
    print(f"wrote {json_path}")
    return 0


COMMANDS = {"cues": cmd_cues, "check": cmd_check, "export": cmd_export}


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    try:
        return COMMANDS[args.command](args)
    except (pcs_transcript.TranscriptError, pcs_picks.PicksError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _utf8_streams():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


if __name__ == "__main__":
    _utf8_streams()
    sys.exit(main())
