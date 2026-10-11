"""Validate a fix plan against a file's tables and resolve it to a concrete layout."""
import json

import tf_struct

TABLE_KEYS = {"expect", "header_rows", "header_cols", "spans", "row_order", "cell_order", "headers"}


def load_plan(path):
    try:
        with open(path, encoding="utf-8") as fh:
            plan = json.load(fh)
    except (OSError, ValueError) as exc:
        raise tf_struct.Refusal(f"{path}: cannot read plan ({exc})") from None
    if not isinstance(plan, dict):
        raise tf_struct.Refusal(f"{path}: a plan is a JSON object with a 'tables' key")
    return plan


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _perm(value, n):
    return isinstance(value, list) and all(_is_int(v) for v in value) and sorted(value) == list(range(n))


def _ref(text):
    try:
        r, i = str(text).split(".")
        return int(r), int(i)
    except ValueError:
        return None


def resolve(tid, table, tp, taken=None):
    taken = set(taken or ())
    errors = []
    rows = table["rows"]
    nrows = len(rows)
    ncells = sum(len(r["cells"]) for r in rows)

    def err(msg):
        errors.append(f"{tid}: {msg}")

    for key in tp:
        if key not in TABLE_KEYS:
            err(f"unknown key '{key}'")
    expect = tp.get("expect")
    if expect is None:
        err('expect is required: copy {"rows": rows_count, "cells": cells_count} for this table from `inspect --json`')
        return None, errors
    if not isinstance(expect, dict) or (expect.get("rows"), expect.get("cells")) != (nrows, ncells):
        err(f"expect {expect} does not match this file ({nrows} rows, {ncells} cells); is the plan for another file?")
        return None, errors

    span = {(r, i): (c["rowspan"], c["colspan"]) for r, row in enumerate(rows) for i, c in enumerate(row["cells"])}
    for s in tp.get("spans", []):
        r, i = s.get("row"), s.get("cell")
        if not (_is_int(r) and _is_int(i) and 0 <= r < nrows and 0 <= i < len(rows[r]["cells"])):
            err(f"spans entry has no such cell: row {r} cell {i}")
            continue
        rs, cs = s.get("rowspan", span[(r, i)][0]), s.get("colspan", span[(r, i)][1])
        if not (_is_int(rs) and _is_int(cs) and rs >= 1 and cs >= 1):
            err(f"spans entry row {r} cell {i}: rowspan and colspan must be whole numbers of 1 or more")
            continue
        span[(r, i)] = (rs, cs)

    row_order = tp.get("row_order", list(range(nrows)))
    if not _perm(row_order, nrows):
        err(f"row_order must list each row 0..{nrows - 1} exactly once")
        row_order = list(range(nrows))
    elif any(rows[row_order[p]]["_parent"].objgen != rows[p]["_parent"].objgen for p in range(nrows)):
        err("row_order moves a row out of its THead/TBody/TFoot section")
        row_order = list(range(nrows))
    cell_order = {}
    for key, order in (tp.get("cell_order") or {}).items():
        try:
            r = int(key)
        except ValueError:
            r = -1
        if not (0 <= r < nrows) or not _perm(order, len(rows[r]["cells"])):
            err(f"cell_order '{key}' must name a row and list each of its cells exactly once")
        elif rows[r]["extras"] and order != sorted(order):
            err(f"cell_order row {r}: the row has non-cell children, so its cells are not reordered")
        else:
            cell_order[r] = order
    for p in range(nrows):
        if row_order[p] != p and rows[row_order[p]]["extras"]:
            err(f"row_order moves row {row_order[p]}, which has non-cell children")
            break

    arranged = [[(r0, j) for j in cell_order.get(r0, range(len(rows[r0]["cells"])))] for r0 in row_order]
    place, width, problems = tf_struct.layout_grid([[span[ref] for ref in row] for row in arranged])
    for code, r, i, msg in problems:
        err(f"{code}: {msg}")
    grid = {ref: place[(p, j)] for p, row in enumerate(arranged) for j, ref in enumerate(row)}

    declares = "header_rows" in tp or "header_cols" in tp
    hr, hc = tp.get("header_rows", 0), tp.get("header_cols", 0)
    if declares:
        if not _is_int(hr) or hr < 0 or hr > nrows:
            err(f"header_rows must be 0..{nrows}")
            hr = 0
        if not _is_int(hc) or hc < 0 or hc > width:
            err(f"header_cols must be 0..{width}")
            hc = 0

    attrs = {}
    for r, row in enumerate(rows):
        for i, c in enumerate(row["cells"]):
            a = {"tag": c["tag"], "scope": c["scope"], "rowspan": span[(r, i)][0], "colspan": span[(r, i)][1],
                 "id": c["id"], "headers": c["headers"]}
            if declares:
                gr, gc = grid.get((r, i), (0, 0))
                if gr < hr or gc < hc:
                    a["tag"] = "TH"
                    a["scope"] = "Both" if (gr < hr and gc < hc) else ("Column" if gr < hr else "Row")
                else:
                    a["tag"], a["scope"] = "TD", None
            attrs[(r, i)] = a

    for dep, targets in (tp.get("headers") or {}).items():
        d = _ref(dep)
        if d not in attrs:
            err(f"headers entry '{dep}' is not a cell")
            continue
        if targets == []:
            attrs[d]["headers"] = None  # an empty list clears the cell's Headers
            continue
        ids = []
        for t in targets if isinstance(targets, list) else []:
            ref = _ref(t)
            if ref not in attrs:
                err(f"headers entry '{dep}' points at '{t}', which is not a cell")
            elif attrs[ref]["tag"] != "TH":
                err(f"headers entry '{dep}' points at '{t}', which is not a header cell after this plan")
            else:
                if not attrs[ref]["id"]:
                    base = new = f"{tid}-h{ref[0]}-{ref[1]}"
                    n = 1
                    while new in taken:
                        n += 1
                        new = f"{base}-{n}"
                    attrs[ref]["id"] = new
                    taken.add(new)
                ids.append(attrs[ref]["id"])
        if ids:
            attrs[d]["headers"] = ids
    by_id = {a["id"]: ref for ref, a in attrs.items() if a["id"]}
    for ref, a in attrs.items():
        for hid in a["headers"] or []:
            target = by_id.get(hid)
            if target is not None and attrs[target]["tag"] != "TH":
                err(f"cell {ref[0]}.{ref[1]} keeps Headers pointing at '{hid}' (cell {target[0]}.{target[1]}), "
                    f"which is no longer a header cell; clear it with \"headers\": {{\"{ref[0]}.{ref[1]}\": []}}")
    if errors:
        return None, errors
    return {"arranged": arranged, "attrs": attrs, "row_order": row_order, "cell_order": cell_order}, errors


def check_plan(plan, tables, taken=None):
    """taken: every /ID already used in the document, so minted ids never collide."""
    errors, layouts = [], {}
    taken = set(taken or ())
    for t in tables:
        for row in t["rows"]:
            taken.update(c["id"] for c in row["cells"] if c["id"])
    extra = set(plan) - {"tables"}
    if extra or not isinstance(plan.get("tables"), dict):
        errors.append("a plan is an object with only a 'tables' key holding one entry per table id")
        return layouts, errors
    by_id = {t["id"]: t for t in tables}
    for tid, tp in plan["tables"].items():
        if tid not in by_id:
            errors.append(f"{tid}: no such table in this file (it has {', '.join(by_id) or 'none'})")
        elif not isinstance(tp, dict):
            errors.append(f"{tid}: the entry must be an object")
        else:
            layout, errs = resolve(tid, by_id[tid], tp, taken)
            errors += errs
            if layout is not None:
                layouts[tid] = layout
                taken.update(a["id"] for a in layout["attrs"].values() if a["id"])
    return layouts, errors


def diff(table, layout):
    lines = []
    rows = table["rows"]
    if layout["row_order"] != list(range(len(rows))):
        lines.append("rows reordered: new order is old rows " + ", ".join(map(str, layout["row_order"])))
    for r, order in sorted(layout["cell_order"].items()):
        if order != list(range(len(rows[r]["cells"]))):
            lines.append(f"row {r}: cells reordered to old cells " + ", ".join(map(str, order)))
    for r, row in enumerate(rows):
        for i, c in enumerate(row["cells"]):
            a = layout["attrs"][(r, i)]
            ch = []
            if a["tag"] != c["tag"]:
                ch.append(f"{c['tag']}->{a['tag']}")
            if a["scope"] != c["scope"]:
                ch.append(f"scope {c['scope'] or 'none'}->{a['scope'] or 'none'}")
            if a["rowspan"] != c["rowspan"]:
                ch.append(f"rowspan {c['rowspan']}->{a['rowspan']}")
            if a["colspan"] != c["colspan"]:
                ch.append(f"colspan {c['colspan']}->{a['colspan']}")
            if a["id"] != c["id"]:
                ch.append(f"id {c['id'] or '-'}->{a['id']}")
            if a["headers"] != c["headers"]:
                ch.append(f"headers {c['headers'] or '-'}->{a['headers']}")
            if ch:
                text = c["text"] if len(c["text"]) <= 30 else c["text"][:29] + "…"
                lines.append(f"row {r} cell {i} \"{text}\": " + ", ".join(ch))
    return lines
