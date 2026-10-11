"""Inspect, plan-diff and apply table fixes in a tagged PDF.

Usage:
    python tables.py inspect IN.pdf [--json]
    python tables.py plan-diff IN.pdf --plan PLAN.json
    python tables.py apply IN.pdf --plan PLAN.json --out OUT.pdf
Exit codes: 0 ok; 2 refusal, bad input or plan, or pikepdf missing; 3 output failed the post-write check.
"""
import argparse
import json
import sys

MISSING = "pikepdf is not installed. Install it with: python -m pip install pikepdf"


def _cut(text, n=60):
    return text if len(text) <= n else text[: n - 1] + "…"


def _inspect(path, as_json):
    import tf_problems
    import tf_struct

    pdf = tf_struct.open_checked(path)
    try:
        tables = tf_struct.read_tables(pdf)
        infos = []
        for t in tables:
            info = tf_struct.public(t)
            info["problems"] = tf_problems.find_problems(t)
            info["rows_count"] = len(t["rows"])
            info["cells_count"] = sum(len(r["cells"]) for r in t["rows"])
            infos.append(info)
    finally:
        pdf.close()
    if as_json:
        print(json.dumps({"file": str(path), "tables": infos}, ensure_ascii=False, indent=2))
        return 0
    if not infos:
        print(f"{path}: no tables found")
        return 0
    for t in infos:
        n = len(t["problems"])
        print(f"{t['id']}  page {t['page'] or '?'}  {t['rows_count']} rows, {t['cells_count']} cells  "
              f"{n} problem{'s' if n != 1 else ''}")
        for r, row in enumerate(t["rows"]):
            print(f"  row {r}" + (f" [{row['section']}]" if row["section"] else ""))
            for i, c in enumerate(row["cells"]):
                print(f"    {i}: {c['tag']} \"{_cut(c['text'])}\" scope={c['scope'] or '-'} "
                      f"span={c['rowspan']}x{c['colspan']} id={c['id'] or '-'} "
                      f"headers={','.join(c['headers']) if c['headers'] else '-'}")
        for p in t["problems"]:
            where = ""
            if p["row"] is not None:
                where = f" (row {p['row']}" + (f" cell {p['cell']})" if p["cell"] is not None else ")")
            print(f"  ! {p['code']}{where}: {p['detail']}")
    return 0


def _load(path, plan_path):
    """Open the PDF and check the plan; returns (pdf, tables, layouts) or None after printing the errors."""
    import tf_plan
    import tf_struct

    pdf = tf_struct.open_checked(path)
    try:
        tables = tf_struct.read_tables(pdf)
        layouts, errors = tf_plan.check_plan(tf_plan.load_plan(plan_path), tables)
    except Exception:
        pdf.close()
        raise
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        pdf.close()
        return None
    return pdf, tables, layouts


def _plan_diff(path, plan_path):
    import tf_plan

    loaded = _load(path, plan_path)
    if loaded is None:
        return 2
    pdf, tables, layouts = loaded
    try:
        by_id = {t["id"]: t for t in tables}
        for tid, layout in layouts.items():
            lines = tf_plan.diff(by_id[tid], layout)
            print(f"{tid}: " + ("no changes" if not lines else f"{len(lines)} change{'s' if len(lines) != 1 else ''}"))
            for line in lines:
                print("  " + line)
    finally:
        pdf.close()
    return 0


def main(argv=None):
    try:
        import pikepdf  # noqa: F401
    except ImportError:
        print(MISSING, file=sys.stderr)
        return 2
    import tf_struct

    ap = argparse.ArgumentParser(prog="tables.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inspect")
    p.add_argument("pdf")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("plan-diff")
    p.add_argument("pdf")
    p.add_argument("--plan", required=True)
    args = ap.parse_args(argv)
    try:
        if args.cmd == "inspect":
            return _inspect(args.pdf, args.json)
        if args.cmd == "plan-diff":
            return _plan_diff(args.pdf, args.plan)
    except tf_struct.Refusal as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
