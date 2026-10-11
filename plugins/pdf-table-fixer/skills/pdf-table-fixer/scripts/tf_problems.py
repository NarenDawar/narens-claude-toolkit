"""Problems in a table that can be shown from the file alone."""
import tf_struct

TOLERANCE = 2.0


def find_problems(table):
    probs = []

    def add(code, row, cell, detail):
        probs.append({"code": code, "row": row, "cell": cell, "detail": detail})

    rows = table["rows"]
    if not rows:
        add("empty_table", None, None, "the table has no rows")
        return probs
    spans = [[(c["rowspan"], c["colspan"]) for c in r["cells"]] for r in rows]
    for code, r, i, msg in tf_struct.layout_grid(spans)[2]:
        add(code, r, i, msg)
    cells = [c for r in rows for c in r["cells"]]
    for r, row in enumerate(rows):
        if row["extras"]:
            add("unexpected_child", r, None, "row holds non-cell children: " + ", ".join(row["extras"]))
        for i, c in enumerate(row["cells"]):
            if "�" in c["text"]:
                add("text_unreadable", r, i, "the cell's text could not be decoded from its font")
    linked = any(c["headers"] for c in cells)
    if len(rows) > 1 and not any(c["tag"] == "TH" for c in cells):
        add("no_header", None, None, "the table has no TH cells")
    for r, row in enumerate(rows):
        for i, c in enumerate(row["cells"]):
            if c["tag"] == "TH" and not c["scope"] and not c["id"] and not linked:
                add("th_no_scope", r, i, "TH has no Scope and no ID")
    prev = None
    for r, row in enumerate(rows):
        first = next(((c["page"], c["pos"][1]) for c in row["cells"] if c["pos"] and c["page"]), None)
        if first and prev and first[0] == prev[0] and first[1] > prev[1] + TOLERANCE:
            add("rows_out_of_order", r, None, "this row is drawn above the row before it")
        if first:
            prev = first
        last_x, last_page = None, None
        for i, c in enumerate(row["cells"]):
            if not (c["pos"] and c["page"]):
                continue
            if last_x is not None and c["page"] == last_page and c["pos"][0] < last_x - TOLERANCE:
                add("cells_out_of_order", r, i, "this cell is drawn left of the cell before it")
            last_x, last_page = c["pos"][0], c["page"]
    return probs
