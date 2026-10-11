"""Read-only: the text and position of each marked-content id on a page."""
import re

import pikepdf

IDENT = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
_HEX = re.compile(rb"<([0-9A-Fa-f\s]*)>")


def mul(a, b):
    """Affine product, row-vector convention: apply a, then b."""
    return (
        a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
        a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
        a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5],
    )


def inherited(obj, key):
    while obj is not None:
        if key in obj:
            return obj[key]
        obj = obj.get("/Parent")
    return None


def _utf16(hexbytes):
    raw = bytes.fromhex(re.sub(rb"\s+", b"", hexbytes).decode())
    return raw.decode("utf-16-be", errors="replace")


def parse_tounicode(data):
    """Map character codes to text from the bfchar and bfrange blocks of a ToUnicode CMap."""
    table = {}
    for block in re.findall(rb"beginbfchar(.*?)endbfchar", data, re.S):
        h = _HEX.findall(block)
        for i in range(0, len(h) - 1, 2):
            table[int(re.sub(rb"\s+", b"", h[i]), 16)] = _utf16(h[i + 1])
    for block in re.findall(rb"beginbfrange(.*?)endbfrange", data, re.S):
        for lo, hi, rest in re.findall(
            rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(\[[^\]]*\]|<[0-9A-Fa-f\s]*>)", block
        ):
            lo, hi = int(lo, 16), int(hi, 16)
            dsts = _HEX.findall(rest)
            if rest.startswith(b"["):
                for i, d in enumerate(dsts[: hi - lo + 1]):
                    table[lo + i] = _utf16(d)
            elif dsts and hi - lo < 65536:
                base = _utf16(dsts[0])
                for i in range(hi - lo + 1):
                    table[lo + i] = (base[:-1] + chr(ord(base[-1]) + i)) if base else ""
    return table


def _decoder(font):
    wide = str(font.get("/Subtype")) == "/Type0"
    tu = font.get("/ToUnicode")
    if tu is not None:
        table = parse_tounicode(tu.read_bytes())
        width = 2 if wide else 1

        def dec(b):
            return "".join(
                table.get(int.from_bytes(b[i:i + width], "big"), "�")
                for i in range(0, len(b) - width + 1, width)
            )

        return dec
    if wide:
        return lambda b: "�" * (len(b) // 2)
    return lambda b: b.decode("cp1252", errors="replace")


def _mcid(operand, props):
    if isinstance(operand, pikepdf.Dictionary):
        v = operand.get("/MCID")
    elif isinstance(operand, pikepdf.Name) and props is not None:
        d = props.get(str(operand))
        v = d.get("/MCID") if d is not None else None
    else:
        v = None
    return int(v) if v is not None else None


def page_text(page):
    """{mcid: {"text": str, "pos": (x, y) or None}} for one pikepdf Page."""
    res = inherited(page.obj, "/Resources")
    fonts = res.get("/Font") if res is not None else None
    props = res.get("/Properties") if res is not None else None
    decoders, out, stack = {}, {}, []
    ctm, ctm_stack, tm, lm, leading, font = IDENT, [], IDENT, IDENT, 0.0, None

    def decoder_for(name):
        if name not in decoders:
            f = fonts.get(name) if fonts is not None else None
            decoders[name] = _decoder(f) if f is not None else (lambda b: b.decode("latin-1"))
        return decoders[name]

    def floats(operands):
        return tuple(float(x) for x in operands)

    for operands, op in pikepdf.parse_content_stream(page):
        o = str(op)
        if o == "q":
            ctm_stack.append(ctm)
        elif o == "Q":
            ctm = ctm_stack.pop() if ctm_stack else IDENT
        elif o == "cm":
            ctm = mul(floats(operands), ctm)
        elif o == "BT":
            tm = lm = IDENT
        elif o == "Tm":
            tm = lm = floats(operands)
        elif o in ("Td", "TD"):
            tx, ty = float(operands[0]), float(operands[1])
            if o == "TD":
                leading = -ty
            lm = mul((1.0, 0.0, 0.0, 1.0, tx, ty), lm)
            tm = lm
        elif o == "TL":
            leading = float(operands[0])
        elif o == "T*":
            lm = mul((1.0, 0.0, 0.0, 1.0, 0.0, -leading), lm)
            tm = lm
        elif o == "Tf":
            font = decoder_for(str(operands[0]))
        elif o == "BMC":
            stack.append(None)
        elif o == "BDC":
            stack.append(_mcid(operands[1], props))
        elif o == "EMC":
            if stack:
                stack.pop()
        elif o in ("Tj", "TJ", "'", '"'):
            if o in ("'", '"'):
                lm = mul((1.0, 0.0, 0.0, 1.0, 0.0, -leading), lm)
                tm = lm
            current = next((m for m in reversed(stack) if m is not None), None)
            if current is None or font is None:
                continue
            items = list(operands[0]) if o == "TJ" else [operands[-1]]
            text = ""
            for it in items:
                if isinstance(it, pikepdf.String):
                    text += font(bytes(it))
                elif float(it) < -200:
                    text += " "
            entry = out.setdefault(current, {"text": "", "pos": None})
            entry["text"] += text
            if entry["pos"] is None:
                full = mul(tm, ctm)
                entry["pos"] = (full[4], full[5])
    for entry in out.values():
        entry["text"] = entry["text"].strip()
    return out
