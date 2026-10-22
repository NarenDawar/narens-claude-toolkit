"""Write the ranked clip list as CSV and JSON. Standard library only."""
import csv
import json
from pathlib import Path

from pcs_picks import DIMENSIONS, cue_bounds
from pcs_transcript import fmt_time

CSV_COLUMNS = [
    "rank", "start", "end", "duration_seconds", "start_cue", "end_cue", "total",
    *DIMENSIONS, "caption",
]


def build_rows(cues, picks):
    """picks must already have passed pcs_picks.check; times come from the cues."""
    rows = []
    for rank, clip in enumerate(picks["clips"], 1):
        first, last = clip["start_cue"], clip["end_cue"]
        start, end = cue_bounds(cues, first, last)
        rows.append({
            "rank": rank,
            "start": fmt_time(start),
            "end": fmt_time(end),
            "duration_seconds": round(end - start, 3),
            "start_cue": first,
            "end_cue": last,
            "total": clip["total"],
            "scores": dict(clip["scores"]),
            "reasons": dict(clip["reasons"]),
            "caption": clip["caption"].strip(),
        })
    return rows


def _csv_safe(text):
    """A spreadsheet reads a leading = + - @ as a formula; a leading apostrophe stops that."""
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def write_export(cues, picks, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = build_rows(cues, picks)
    json_path = out_dir / "clips.json"
    with open(json_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"clips": rows}, indent=2, ensure_ascii=False) + "\n")
    csv_path = out_dir / "clips.csv"
    # A UTF-8 BOM makes Excel on Windows read the file as UTF-8, not the local code page.
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_COLUMNS)
        for r in rows:
            writer.writerow([
                r["rank"], r["start"], r["end"], r["duration_seconds"], r["start_cue"],
                r["end_cue"], r["total"], *[r["scores"][d] for d in DIMENSIONS],
                _csv_safe(r["caption"]),
            ])
    return csv_path, json_path
