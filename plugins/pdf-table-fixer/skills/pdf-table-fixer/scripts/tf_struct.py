"""Read a PDF's table structure (read only) and lay its cells on a grid."""
import pikepdf

import tf_content

CELL_ROLES = ("TD", "TH")
SECTIONS = ("THead", "TBody", "TFoot")
MAX_DEPTH = 200


class Refusal(Exception):
    """A file or plan this skill will not touch."""


def open_checked(path, for_write=False):
    try:
        pdf = pikepdf.open(path)
    except pikepdf.PasswordError:
        raise Refusal(f"{path}: encrypted; not supported") from None
    except (pikepdf.PdfError, OSError) as exc:
        raise Refusal(f"{path}: cannot open ({exc})") from None
    try:
        if pdf.is_encrypted:
            raise Refusal(f"{path}: encrypted; not supported")
        if "/StructTreeRoot" not in pdf.Root:
            raise Refusal(f"{path}: untagged (no structure tree); out of scope")
        if for_write:
            form = pdf.Root.get("/AcroForm")
            if form is not None and int(form.get("/SigFlags", 0)) > 0:
                raise Refusal(f"{path}: signed; changing it would break the signature")
    except Refusal:
        pdf.close()  # an open handle keeps the file locked on Windows
        raise
    return pdf


def _role_map(root):
    rm = root.get("/RoleMap")
    return {str(k)[1:]: str(v)[1:] for k, v in rm.items()} if rm is not None else {}


def _role(e, rolemap):
    s = e.get("/S")
    if s is None:
        return None
    name = str(s)[1:]
    for _ in range(10):
        if name not in rolemap:
            break
        name = rolemap[name]
    return name


def kids(e):
    k = e.get("/K")
    if k is None:
        return []
    return list(k) if isinstance(k, pikepdf.Array) else [k]


def _is_elem(x):
    return isinstance(x, pikepdf.Dictionary) and "/S" in x


def refs_under(e, pg, depth=0):
    """Yield (page objgen, mcid) for every marked-content reference at or below struct element e."""
    if depth > MAX_DEPTH:
        raise Refusal("structure tree too deep or cyclic")
    p = e.get("/Pg")
    pg = p.objgen if p is not None else pg
    for k in kids(e):
        if isinstance(k, int):
            yield (pg, k)
        elif isinstance(k, pikepdf.Dictionary):
            if k.get("/Type") == "/MCR":
                kp = k.get("/Pg")
                yield (kp.objgen if kp is not None else pg, int(k["/MCID"]))
            elif "/S" in k:
                yield from refs_under(k, pg, depth + 1)


def marked_refs(pdf):
    index = {p.obj.objgen: i for i, p in enumerate(pdf.pages)}
    return {(index.get(g, -1), m) for g, m in refs_under(pdf.Root.StructTreeRoot, None)}


def table_attrs(e, create=False):
    a = e.get("/A")
    if isinstance(a, pikepdf.Dictionary) and a.get("/O") == "/Table":
        return a
    if isinstance(a, pikepdf.Array):
        for item in a:
            if isinstance(item, pikepdf.Dictionary) and item.get("/O") == "/Table":
                return item
    if not create:
        return None
    new = pikepdf.Dictionary(O=pikepdf.Name.Table)
    if a is None:
        e.A = new
    elif isinstance(a, pikepdf.Array):
        a.append(new)
    else:
        e.A = pikepdf.Array([a, new])
    return table_attrs(e)


def read_tables(pdf):
    root = pdf.Root.StructTreeRoot
    rolemap = _role_map(root)
    page_no = {p.obj.objgen: i + 1 for i, p in enumerate(pdf.pages)}
    pages = {p.obj.objgen: p for p in pdf.pages}
    cache = {}

    def texts(gen):
        if gen not in cache:
            cache[gen] = tf_content.page_text(pages[gen]) if gen in pages else {}
        return cache[gen]

    def read_cell(e, role, pg):
        a = table_attrs(e)
        get = (lambda k, d=None: a.get(k, d)) if a is not None else (lambda k, d=None: d)
        refs = list(refs_under(e, pg))
        infos = [(g, texts(g).get(m)) for g, m in refs]
        infos = [(g, i) for g, i in infos if i is not None]
        text = " ".join(i["text"] for _, i in infos if i["text"])
        pos = next((i["pos"] for _, i in infos if i["pos"] is not None), None)
        first = refs[0][0] if refs else None
        headers = get("/Headers")
        scope = get("/Scope")
        return {
            "tag": role, "text": text, "pos": pos, "page": page_no.get(first),
            "rowspan": int(get("/RowSpan", 1)), "colspan": int(get("/ColSpan", 1)),
            "scope": str(scope)[1:] if scope is not None else None,
            "id": str(e["/ID"]) if "/ID" in e else None,
            "headers": [str(h) for h in headers] if headers is not None else None,
            "_obj": e,
        }

    def read_table(t, pg, tid):
        rows = []

        def add_row(tr, section, parent):
            p = tr.get("/Pg")
            rpg = p.objgen if p is not None else pg
            cells, extras = [], []
            for k in kids(tr):
                role = _role(k, rolemap) if _is_elem(k) else None
                if role in CELL_ROLES:
                    cells.append(read_cell(k, role, rpg))
                else:
                    extras.append(role or "content")
            rows.append({"section": section, "cells": cells, "extras": extras, "_obj": tr, "_parent": parent})

        for k in kids(t):
            if not _is_elem(k):
                continue
            role = _role(k, rolemap)
            if role == "TR":
                add_row(k, None, t)
            elif role in SECTIONS:
                for r in kids(k):
                    if _is_elem(r) and _role(r, rolemap) == "TR":
                        add_row(r, role, k)
        page = next((c["page"] for r in rows for c in r["cells"] if c["page"]), None)
        return {"id": tid, "page": page, "rows": rows, "_obj": t}

    tables = []

    def walk(e, pg, depth):
        if depth > MAX_DEPTH:
            raise Refusal("structure tree too deep or cyclic")
        p = e.get("/Pg")
        pg = p.objgen if p is not None else pg
        if _role(e, rolemap) == "Table":
            tables.append(read_table(e, pg, f"t{len(tables) + 1}"))
        for k in kids(e):
            if _is_elem(k):
                walk(k, pg, depth + 1)

    walk(root, None, 0)
    return tables


def layout_grid(spans):
    occ, place, problems = {}, {}, []
    n = len(spans)
    for r, row in enumerate(spans):
        col = 0
        for i, (rs, cs) in enumerate(row):
            if rs < 1 or cs < 1:
                problems.append(("bad_span", r, i, f"row {r} cell {i}: spans must be 1 or more"))
                rs, cs = max(rs, 1), max(cs, 1)
            while (r, col) in occ:
                col += 1
            place[(r, i)] = (r, col)
            if r + rs > n:
                problems.append(("span_overrun", r, i, f"row {r} cell {i}: rowspan {rs} runs past the last row"))
            for dr in range(rs):
                for dc in range(cs):
                    key = (r + dr, col + dc)
                    if key in occ:
                        problems.append(
                            ("span_overlap", r, i, f"row {r} cell {i}: overlaps row {occ[key][0]} cell {occ[key][1]}"))
                    else:
                        occ[key] = (r, i)
            col += cs
    widths = {}
    for gr, gc in occ:
        if gr < n:
            widths[gr] = max(widths.get(gr, 0), gc + 1)
    width = max(widths.values(), default=0)
    odd = [r for r in range(n) if widths.get(r, 0) != width]
    if odd:
        problems.append(("ragged_rows", None, None,
                         "rows " + ", ".join(map(str, odd)) + f" differ from the widest row ({width} columns)"))
    return place, width, problems


def public(table):
    def clean(v):
        if isinstance(v, dict):
            return {k: clean(x) for k, x in v.items() if not k.startswith("_")}
        if isinstance(v, (list, tuple)):
            return [clean(x) for x in v]
        return v

    return clean(table)
