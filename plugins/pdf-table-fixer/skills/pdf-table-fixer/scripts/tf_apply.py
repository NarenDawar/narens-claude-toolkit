"""Apply a resolved plan to a PDF and check the result before it is kept."""
import os
import tempfile
from pathlib import Path

import pikepdf
from pikepdf import Array, Name, String

import tf_plan
import tf_struct


class PostCheckFailed(Exception):
    """The written file failed a check; nothing was kept."""


def _content_bytes(page):
    c = page.obj.get("/Contents")
    if c is None:
        return b""
    if isinstance(c, pikepdf.Array):
        return b"\n".join(s.read_raw_bytes() for s in c)
    return c.read_raw_bytes()


def snapshot(pdf):
    return {"pages": len(pdf.pages), "refs": tf_struct.marked_refs(pdf),
            "content": [_content_bytes(p) for p in pdf.pages]}


def check_after(before, pdf):
    after = snapshot(pdf)
    problems = []
    if after["pages"] != before["pages"]:
        problems.append(f"page count changed from {before['pages']} to {after['pages']}")
    if after["content"] != before["content"]:
        problems.append("a page's content stream changed")
    lost = before["refs"] - after["refs"]
    if lost:
        problems.append(f"{len(lost)} marked-content reference(s) are no longer in the structure tree")
    new = after["refs"] - before["refs"]
    if new:
        problems.append(f"{len(new)} marked-content reference(s) appeared that were not there before")
    return problems


def _reorder(parent, old_items, new_items):
    k = parent.get("/K")
    slots = list(k) if isinstance(k, pikepdf.Array) else [k]
    ids = {o.objgen for o in old_items}
    if any(g == (0, 0) for g in ids):
        raise tf_struct.Refusal("a table element is a direct object and cannot be reordered safely")
    it = iter(new_items)
    parent.K = Array([next(it) if (isinstance(s, pikepdf.Dictionary) and s.objgen in ids) else s for s in slots])


def apply_layout(table, layout):
    rows = table["rows"]
    for (r, i), at in layout["attrs"].items():
        e = rows[r]["cells"][i]["_obj"]
        e.S = Name(f"/{at['tag']}")
        a = tf_struct.table_attrs(e)
        want = {
            "/Scope": Name(f"/{at['scope']}") if at["scope"] else None,
            "/RowSpan": at["rowspan"] if at["rowspan"] > 1 else None,
            "/ColSpan": at["colspan"] if at["colspan"] > 1 else None,
            "/Headers": Array([String(h) for h in at["headers"]]) if at["headers"] else None,
        }
        if a is None and any(v is not None for v in want.values()):
            a = tf_struct.table_attrs(e, create=True)
        if a is not None:
            for key, value in want.items():
                if value is None:
                    if key in a:
                        del a[key]
                else:
                    a[key] = value
        if at["id"]:
            e["/ID"] = String(at["id"])
    for r0, order in layout["cell_order"].items():
        cells = [c["_obj"] for c in rows[r0]["cells"]]
        if order != list(range(len(cells))):
            _reorder(rows[r0]["_obj"], cells, [cells[j] for j in order])
    ro = layout["row_order"]
    if ro != list(range(len(rows))):
        groups = {}
        for p, row in enumerate(rows):
            groups.setdefault(row["_parent"].objgen, (row["_parent"], []))[1].append(p)
        for parent, slots in groups.values():
            _reorder(parent, [rows[p]["_obj"] for p in slots], [rows[ro[p]]["_obj"] for p in slots])


def run_apply(in_path, plan_path, out_path):
    in_path, out_path = Path(in_path), Path(out_path)
    same = in_path.resolve() == out_path.resolve() or (
        out_path.exists() and in_path.exists() and os.path.samefile(in_path, out_path))
    if same:
        raise tf_struct.Refusal("refusing to overwrite the input file; give --out a different path")
    pdf = tf_struct.open_checked(in_path, for_write=True)
    tmp = None
    try:
        tables = tf_struct.read_tables(pdf)
        layouts, errors = tf_plan.check_plan(tf_plan.load_plan(plan_path), tables)
        if errors:
            raise tf_struct.Refusal("\n".join(errors))
        before = snapshot(pdf)
        summary = []
        by_id = {t["id"]: t for t in tables}
        for tid, layout in layouts.items():
            changes = tf_plan.diff(by_id[tid], layout)
            apply_layout(by_id[tid], layout)
            summary.append(f"{tid}: {len(changes)} change{'s' if len(changes) != 1 else ''} applied")
        fd, tmp = tempfile.mkstemp(dir=str(out_path.parent), suffix=".tmp")
        os.close(fd)
        pdf.save(tmp)
    finally:
        pdf.close()
    try:
        with pikepdf.open(tmp) as written:
            problems = check_after(before, written)
        if problems:
            raise PostCheckFailed("; ".join(problems))
        os.replace(tmp, out_path)
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)
    return summary
