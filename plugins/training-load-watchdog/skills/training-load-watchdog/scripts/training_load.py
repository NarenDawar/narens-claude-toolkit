#!/usr/bin/env python3
"""Find single-session distance spikes in a running log, and check a planned schedule against them.

Usage:
  python training_load.py analyze LOG.csv [--as-of YYYY-MM-DD] [--days 28] [--types REGEX]
  python training_load.py check   LOG.csv [--as-of YYYY-MM-DD] [--types REGEX] < plan.json
        plan.json: [{"date": "2024-01-17", "distance": 8.0}, ...]  (distance in the log's own unit)

The log is a Strava (activities.csv), Garmin Connect or similar CSV with a date, an activity type
and a distance column. A spike is a session longer than the longest session in the 30 days before
it: small >10-30%, moderate >30-100%, large >100%. Distances are only ever compared with each
other, so the unit (km or miles) does not matter. Read-only; prints JSON.
"""
import argparse
import csv
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

WINDOW_DAYS = 30
CATEGORIES = [(1.0, "large"), (0.3, "moderate"), (0.1, "small")]  # growth above the longest run
DATE_COLUMNS = ["activity date", "start_date", "start date", "start time", "date"]
TYPE_COLUMNS = ["activity type", "type", "sport"]
DISTANCE_COLUMNS = ["distance"]
TIME_COLUMNS = ["moving time", "moving_time", "elapsed time", "elapsed_time", "time", "duration"]
DATE_FORMATS = ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
                "%b %d, %Y, %I:%M:%S %p", "%b %d, %Y", "%d %b %Y, %H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y"]


class LogError(Exception):
    pass


def parse_when(text):
    text = text.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    raise ValueError(text)


def parse_seconds(text):
    """Seconds from '5552', '1:32:32' or '45:12'; None when it is not a duration."""
    text = text.strip()
    try:
        return float(text.replace(",", ""))
    except ValueError:
        pass
    parts = text.split(":")
    if len(parts) in (2, 3) and all(p.replace(".", "", 1).isdigit() for p in parts):
        total = 0.0
        for part in parts:
            total = total * 60 + float(part)
        return total
    return None


def column(header, names):
    """Index of the first column whose name matches, in the order of names (a Strava export
    repeats some names; the first is used)."""
    lowered = [h.strip().lower() for h in header]
    for name in names:
        if name in lowered:
            return lowered.index(name)
    return None


def load_runs(path, types="run"):
    """(runs, notes): runs are {"start": datetime, "distance": float, "minutes": float|None},
    oldest first, only for activity types matching the regex."""
    with open(path, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        raise LogError("the file is empty")
    header, body = rows[0], rows[1:]
    c_date, c_dist = column(header, DATE_COLUMNS), column(header, DISTANCE_COLUMNS)
    c_type, c_time = column(header, TYPE_COLUMNS), column(header, TIME_COLUMNS)
    if c_date is None or c_dist is None:
        raise LogError(f"need a date column and a distance column; the file has: {', '.join(header)}")
    wanted = re.compile(types, re.I)
    runs, skipped, other = [], 0, 0
    for row in body:
        if len(row) <= max(c_date, c_dist):
            skipped += 1
            continue
        if c_type is not None and c_type < len(row) and not wanted.search(row[c_type]):
            other += 1
            continue
        try:
            start = parse_when(row[c_date])
            distance = float(row[c_dist].replace(",", ""))
        except ValueError:
            skipped += 1
            continue
        if distance <= 0:
            skipped += 1
            continue
        seconds = parse_seconds(row[c_time]) if c_time is not None and c_time < len(row) else None
        runs.append({"start": start, "distance": distance, "minutes": None if seconds is None else seconds / 60})
    runs.sort(key=lambda r: r["start"])
    unique = {(r["start"], r["distance"]): r for r in runs}  # the same activity synced twice
    duplicates = len(runs) - len(unique)
    runs = sorted(unique.values(), key=lambda r: r["start"])
    notes = []
    if duplicates:
        notes.append(f"{duplicates} duplicate rows (same start time and distance) were dropped")
    if skipped:
        notes.append(f"{skipped} rows had no usable date or distance and were skipped")
    if other:
        notes.append(f"{other} rows of other activity types were ignored (types matching '{types}' are kept)")
    if not runs:
        raise LogError("no activities of the wanted type with a distance were found")
    return runs, notes


def category(growth):
    growth = round(growth, 6)  # 13 / 10 - 1 is 0.30000000000000004: exactly 30% is not "moderate"
    for floor, name in CATEGORIES:
        if growth > floor:
            return name
    return "none"


def spike(session, history):
    """The session against the longest of the sessions in the 30 days before it. None when
    there is nothing to compare with."""
    since = session["start"] - timedelta(days=WINDOW_DAYS)
    prior = [r["distance"] for r in history if since <= r["start"] < session["start"]]
    if not prior:
        return None
    longest = max(prior)
    growth = session["distance"] / longest - 1
    return {
        "date": session["start"].date().isoformat(),
        "distance": round(session["distance"], 2),
        "longest_prior_30d": round(longest, 2),
        "growth_pct": round(growth * 100, 1),
        "category": category(growth),
    }


def analyze(runs, as_of, days=28):
    end = datetime.combine(as_of, datetime.min.time()) + timedelta(days=1)
    runs = [r for r in runs if r["start"] < end]
    if not runs:
        return {"error": "no runs on or before the as-of date"}
    first = runs[0]["start"].date()
    recent_from = end - timedelta(days=days)
    sessions = []
    for run in runs:
        if run["start"] >= recent_from:
            found = spike(run, runs)
            if found is not None:
                found["history_covers_30d"] = (run["start"].date() - first).days >= WINDOW_DAYS
                sessions.append(found)
    last30 = [r["distance"] for r in runs if r["start"] >= end - timedelta(days=WINDOW_DAYS)]
    longest = max(last30) if last30 else None
    run_days = sorted({r["start"].date() for r in runs})
    streak, day = 0, run_days[-1]
    while day in run_days:
        streak, day = streak + 1, day - timedelta(days=1)
    this_monday = as_of - timedelta(days=as_of.weekday())
    weeks = {}
    for back in range(6):  # empty weeks count: a week with no runs is information
        monday = this_monday - timedelta(weeks=back)
        weeks[monday] = {"week_of": monday.isoformat(), "runs": 0, "distance": 0.0}
    for run in runs:
        monday = run["start"].date() - timedelta(days=run["start"].weekday())
        if monday in weeks:
            weeks[monday]["runs"] += 1
            weeks[monday]["distance"] = round(weeks[monday]["distance"] + run["distance"], 2)
    return {
        "as_of": as_of.isoformat(),
        "first_run_in_log": first.isoformat(),
        "last_run": run_days[-1].isoformat(),
        "days_since_last_run": (as_of - run_days[-1]).days,
        "runs_in_window": len(sessions),
        "spikes": [s for s in sessions if s["category"] != "none"],
        "longest_run_last_30d": None if longest is None else round(longest, 2),
        "cap_no_spike": None if longest is None else round(longest * 1.1, 2),
        "consecutive_run_days_ending_last_run": streak,
        "recent_weeks": sorted(weeks.values(), key=lambda w: w["week_of"]),
        "history_shorter_than_30d": (as_of - first).days < WINDOW_DAYS,
    }


def check(runs, plan, as_of):
    """Each planned run against the longest run in the 30 days before it, counting the log and
    the earlier planned runs."""
    planned = []
    for entry in plan:
        planned.append({
            "start": datetime.combine(parse_when(str(entry["date"])).date(), datetime.min.time().replace(hour=12)),
            "distance": float(entry["distance"]),
        })
    planned.sort(key=lambda r: r["start"])
    history = [r for r in runs if r["start"].date() <= as_of] + planned
    history.sort(key=lambda r: r["start"])
    out = []
    for session in planned:
        found = spike(session, history)
        out.append(found if found is not None else {"date": session["start"].date().isoformat(),
                                                   "distance": session["distance"], "category": "no-prior-run"})
    return out


def main(argv=None):
    for stream in (sys.stdout, sys.stdin):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["analyze", "check"])
    parser.add_argument("log")
    parser.add_argument("--as-of", default=None, help="YYYY-MM-DD, default today")
    parser.add_argument("--days", type=int, default=28, help="how far back to list sessions")
    parser.add_argument("--types", default="run", help="regex of activity types to keep, default 'run'")
    args = parser.parse_args(argv)
    if not os.path.isfile(args.log):
        print(f"no such file: {args.log}", file=sys.stderr)
        return 2
    try:
        as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
        re.compile(args.types)
    except (ValueError, re.error) as error:
        print(f"bad argument: {error}", file=sys.stderr)
        return 2
    try:
        runs, notes = load_runs(args.log, args.types)
    except (LogError, OSError, UnicodeDecodeError) as error:
        print(f"could not read the log: {error}", file=sys.stderr)
        return 2
    if args.command == "analyze":
        result = analyze(runs, as_of, args.days)
    else:
        try:
            plan = json.load(sys.stdin)
            assert isinstance(plan, list) and plan
            result = check(runs, plan, as_of)
        except (ValueError, AssertionError, KeyError, TypeError):
            print('stdin must be a JSON list like [{"date": "2024-01-17", "distance": 8}]', file=sys.stderr)
            return 2
    print(json.dumps({"notes": notes, "result": result}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
