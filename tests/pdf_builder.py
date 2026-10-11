"""Build small tagged PDFs for table tests. Needs pikepdf; tests skip without it."""
try:
    import pikepdf
    from pikepdf import Array, Dictionary, Name, Pdf, String

    HAVE_PIKEPDF = True
except ImportError:  # pragma: no cover
    HAVE_PIKEPDF = False


def make_pdf(path, tables, *, tagged=True, encrypt=False, sections=False, rolemap=None):
    pdf = Pdf.new()
    font = pdf.make_indirect(
        Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica, Encoding=Name.WinAnsiEncoding)
    )
    page = pdf.add_blank_page(page_size=(612, 792))
    page.Resources = Dictionary(Font=Dictionary(F1=font))
    lines, built, mcid = [], [], 0
    for ti, rows in enumerate(tables):
        brows = []
        for ri, row in enumerate(rows):
            brow = []
            for ci, c in enumerate(row):
                c = dict(c) if isinstance(c, dict) else {"text": c}
                x = c.get("x", 72 + 120 * ci)
                y = c.get("y", 740 - 150 * ti - 20 * ri)
                lines.append(f"/P << /MCID {mcid} >> BDC BT /F1 12 Tf 1 0 0 1 {x} {y} Tm ({c['text']}) Tj ET EMC")
                brow.append((c, mcid))
                mcid += 1
            brows.append(brow)
        built.append(brows)
    page.Contents = pdf.make_stream("\n".join(lines).encode("latin-1"))
    if tagged:
        root = pdf.make_indirect(Dictionary(Type=Name.StructTreeRoot))
        doc = pdf.make_indirect(Dictionary(Type=Name.StructElem, S=Name.Document, P=root))
        table_objs = []
        for brows in built:
            table = pdf.make_indirect(Dictionary(Type=Name.StructElem, S=Name.Table, P=doc))
            trs = []
            for brow in brows:
                tr = pdf.make_indirect(Dictionary(Type=Name.StructElem, S=Name.TR, P=table))
                kids = []
                for c, m in brow:
                    cell = Dictionary(Type=Name.StructElem, S=Name(f"/{c.get('tag', 'TD')}"), P=tr, Pg=page.obj, K=m)
                    attrs = Dictionary(O=Name.Table)
                    has = False
                    if c.get("scope"):
                        attrs.Scope, has = Name(f"/{c['scope']}"), True
                    if c.get("rowspan"):
                        attrs.RowSpan, has = c["rowspan"], True
                    if c.get("colspan"):
                        attrs.ColSpan, has = c["colspan"], True
                    if c.get("headers"):
                        attrs.Headers, has = Array([String(h) for h in c["headers"]]), True
                    if has:
                        cell.A = attrs
                    if c.get("id"):
                        cell.ID = String(c["id"])
                    kids.append(pdf.make_indirect(cell))
                tr.K = Array(kids)
                trs.append(tr)
            if sections and len(trs) > 1:
                thead = pdf.make_indirect(Dictionary(Type=Name.StructElem, S=Name.THead, P=table, K=Array([trs[0]])))
                tbody = pdf.make_indirect(Dictionary(Type=Name.StructElem, S=Name.TBody, P=table, K=Array(trs[1:])))
                trs[0].P = thead
                for t in trs[1:]:
                    t.P = tbody
                table.K = Array([thead, tbody])
            else:
                table.K = Array(trs)
            table_objs.append(table)
        doc.K = Array(table_objs)
        root.K = doc
        if rolemap:
            root.RoleMap = Dictionary({f"/{k}": Name(f"/{v}") for k, v in rolemap.items()})
        pdf.Root.StructTreeRoot = root
        pdf.Root.MarkInfo = Dictionary(Marked=True)
    if encrypt:
        pdf.save(path, encryption=pikepdf.Encryption(owner="owner", user="user"))
    else:
        pdf.save(path)
