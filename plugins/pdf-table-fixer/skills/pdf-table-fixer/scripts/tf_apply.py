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


def _stream_bytes(s):
    """The stream's decoded bytes, so re-encoding on save is not mistaken for a change."""
    try:
        return s.read_bytes()
    except pikepdf.PdfError:  # a filter qpdf cannot decode: fall back to the stored bytes
        return s.read_raw_bytes()


def _content_bytes(page):
    c = page.obj.get("/Contents")
    if c is None:
        return b""
    if isinstance(c, pikepdf.Array):
        return b"\n".join(_stream_bytes(s) for s in c)
    return _stream_bytes(c)


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


def check_layout(before_tables, layouts, after_tables):
    """Compare the tables re-read from the written file with what each plan resolved to."""
    problems = []
    before = {t["id"]: t for t in before_tables}
    after = {t["id"]: t for t in after_tables}
    for tid, layout in layouts.items():
        got = after.get(tid)
        if got is None:
            problems.append(f"{tid}: the table is missing from the written file")
            continue
        if len(got["rows"]) != len(layout["arranged"]):
            problems.append(f"{tid}: the written table has {len(got['rows'])} rows, the plan resolved to "
                            f"{len(layout['arranged'])}")
            continue
        for p, refs in enumerate(layout["arranged"]):
            cells = got["rows"][p]["cells"]
            if len(cells) != len(refs):
                problems.append(f"{tid}: row {p} has {len(cells)} cells, the plan resolved to {len(refs)}")
                continue
            for j, (r0, i0) in enumerate(refs):
                at, old, now = layout["attrs"][(r0, i0)], before[tid]["rows"][r0]["cells"][i0], cells[j]
                want = (at["tag"], at["scope"], at["rowspan"], at["colspan"], at["id"], at["headers"] or None,
                        old["text"])
                have = (now["tag"], now["scope"], now["rowspan"], now["colspan"], now["id"], now["headers"] or None,
                        now["text"])
                if want != have:
                    problems.append(f"{tid}: row {p} cell {j} is not what the plan resolved to "
                                    f"(wrote {have}, expected {want})")
        spans = [[(c["rowspan"], c["colspan"]) for c in r["cells"]] for r in got["rows"]]
        for code, _r, _i, msg in tf_struct.layout_grid(spans)[2]:
            problems.append(f"{tid}: written table has {code}: {msg}")
    return problems


def rebuild_idtree(pdf):
    """Flat /IDTree listing every element that has an /ID, so readers can resolve /Headers."""
    root = pdf.Root.StructTreeRoot
    found = []

    def walk(e, depth):
        if depth > tf_struct.MAX_DEPTH:
            raise tf_struct.Refusal("structure tree too deep or cyclic")
        if "/ID" in e:
            found.append((bytes(e["/ID"]), e))
        for k in tf_struct.kids(e):
            if isinstance(k, pikepdf.Dictionary) and "/S" in k:
                walk(k, depth + 1)

    walk(root, 0)
    found.sort(key=lambda item: item[0])
    names = []
    for _key, e in found:
        names += [e["/ID"], e]
    root.IDTree = pikepdf.Dictionary(Names=Array(names))


def apply_layout(table, layout):
    """Write only what differs from the file, so untouched attributes keep their original objects."""
    rows = table["rows"]
    ids_changed = False
    for (r, i), at in layout["attrs"].items():
        cur = rows[r]["cells"][i]
        e = cur["_obj"]
        want = {}
        if at["scope"] != cur["scope"]:
            want["/Scope"] = Name(f"/{at['scope']}") if at["scope"] else None
        if at["rowspan"] != cur["rowspan"]:
            want["/RowSpan"] = at["rowspan"] if at["rowspan"] > 1 else None
        if at["colspan"] != cur["colspan"]:
            want["/ColSpan"] = at["colspan"] if at["colspan"] > 1 else None
        if (at["headers"] or None) != (cur["headers"] or None):
            want["/Headers"] = Array([String(h) for h in at["headers"]]) if at["headers"] else None
        if want:
            a = tf_struct.own_table_attrs(e)
            for key, value in want.items():
                if value is None:
                    if key in a:
                        del a[key]
                else:
                    a[key] = value
        if at["id"] != cur["id"]:
            ids_changed = True
            if at["id"]:
                e["/ID"] = String(at["id"])
            elif "/ID" in e:
                del e["/ID"]
        if at["tag"] != cur["tag"]:
            e.S = Name(f"/{at['tag']}")
    table["_ids_changed"] = ids_changed
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
        layouts, errors = tf_plan.check_plan(tf_plan.load_plan(plan_path), tables, taken=tf_struct.all_ids(pdf))
        if errors:
            raise tf_struct.Refusal("\n".join(errors))
        before = snapshot(pdf)
        summary = []
        by_id = {t["id"]: t for t in tables}
        for tid, layout in layouts.items():
            changes = tf_plan.diff(by_id[tid], layout)
            apply_layout(by_id[tid], layout)
            summary.append(f"{tid}: {len(changes)} change{'s' if len(changes) != 1 else ''} applied")
        if any(by_id[tid].get("_ids_changed") for tid in layouts):
            rebuild_idtree(pdf)
        fd, tmp = tempfile.mkstemp(dir=str(out_path.parent), suffix=".tmp")
        os.close(fd)
        pdf.save(tmp)
    finally:
        pdf.close()
    try:
        with pikepdf.open(tmp) as written:
            problems = check_after(before, written)
            problems += check_layout(tables, layouts, tf_struct.read_tables(written))
        if problems:
            raise PostCheckFailed("; ".join(problems))
        os.replace(tmp, out_path)
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)
    return summary
