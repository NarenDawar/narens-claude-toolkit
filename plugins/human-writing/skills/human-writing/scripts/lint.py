#!/usr/bin/env python3
"""Advisory lint for prose that may read as machine-written.

Python 3.8+, standard library only.

Usage:
    python lint.py draft.txt
    python lint.py draft.txt --sample my_writing.txt --original old_draft.txt
    python lint.py draft.txt --json
    python lint.py draft.txt --clean > cleaned.txt     (writes cleaned text to stdout)

The report is a prompt for judgment, not a pass/fail score. A regex cannot read
intent, so counts like "tricolons: 3" can be fine in a speech and a problem in an
email. When --sample is given, compare against the writer's own numbers instead
of any fixed target. Nothing here promises to change what an AI detector or a
watermark detector reports.
"""
import argparse
import json
import re
import statistics
import sys

LEXICON_DATE = "2026-10-19"
# Perishable list; see references/tells-lexical.md. Counts only, never auto-replaced.
LEXICON = [
    "delve", "delves", "delving", "tapestry", "testament", "underscore", "underscores",
    "showcasing", "showcase", "emphasizing", "highlighting", "fostering", "foster",
    "leverage", "leveraging", "multifaceted", "prioritize", "pivotal", "robust",
    "seamless", "seamlessly", "crucial", "landscape", "comprehensive", "intricate",
    "vibrant", "nestled", "boasts", "stands as", "serves as", "worth noting",
    "important to note", "dive into", "navigate the", "align with",
]

RESIDUE = [
    r"^\s*(certainly|absolutely|sure thing|of course|great question)[!,.]",
    r"\bi hope this (helps|finds you well)\b",
    r"\blet me know if\b",
    r"\bfeel free to\b",
    r"\bwould you like me to\b",
    r"\byou'?re absolutely right\b",
    r"\bas an ai\b",
    r"\bhere'?s a (revised|rewritten|polished) version\b",
]

NEG_PARALLEL = [
    r"\b(it'?s|it is|this is|that'?s|that is) not (just|only|merely|simply)\b",
    r"\bnot (just|only|merely|simply) [^.!?\n]{1,80}?,? (but|it'?s|it is)\b",
    r"\b(isn'?t|aren'?t|wasn'?t|weren'?t|doesn'?t|don'?t) (just|only|about) [^.!?\n]{1,80}?(?:[.;,]|\s[—–-]+)\s*(it'?s|it is|they'?re|they are)\b",
    r"\bit'?s not [^.!?\n]{1,60}?[,;—-]\s*(it'?s|but)\b",
]

ING_TAIL = re.compile(
    r",\s+(highlighting|underscoring|emphasizing|showcasing|reflecting|ensuring|"
    r"fostering|contributing to|demonstrating|illustrating|symbolizing|reinforcing|"
    r"marking|signaling|signalling|shaping|paving)\b",
    re.I,
)

CLOSERS = re.compile(
    r"^(ultimately|in the end|at the end of the day|in conclusion|in short|"
    r"in summary|all in all|the future (looks|is)|whether you)\b",
    re.I,
)

ARTIFACT_PATTERNS = {
    "oaicite markers": re.compile(r":{0,2}contentReference\[oaicite:\d+\](\{[^}]*\})?|\[oaicite:\d+\]\{[^}]*\}"),
    "turnNsearchN tokens": re.compile(r"\bturn\d+(search|view|news|file|image)\d+\b"),
    "deep-research markers": re.compile(r"【\d+†[^】]*】"),
    "utm_ tracking params": re.compile(r"[?&]utm_[a-z]+=[^&\s)\]]*"),
}
CHAR_CLASSES = {
    "narrow no-break space (U+202F)": " ",
    "non-breaking space (U+00A0)": " ",
    "zero-width space/joiner/BOM": "​‌‍⁠﻿",
    "tag characters (U+E0000-E007F)": None,
    "private-use characters": None,
}


def strip_code(text):
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", " ", text)


def words(text):
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", text)


def sentences(text):
    flat = re.sub(r"\s+", " ", re.sub(r"^\s*([-*#>]+|\d+[.)])\s+", "", text, flags=re.M))
    parts = re.split(r"(?<=[.!?])[\"')\]]*\s+(?=[\"'(\[]?[A-Z0-9])", flat)
    return [p.strip() for p in parts if len(words(p)) >= 1]


def paragraphs(text):
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def per_1000(count, nwords):
    return round(1000.0 * count / nwords, 1) if nwords else 0.0


def count_regex(patterns, text):
    return sum(len(re.findall(p, text, flags=re.I | re.M)) for p in patterns)


def count_chars(text):
    out = {}
    for label, chars in CHAR_CLASSES.items():
        if label.startswith("tag"):
            n = sum(1 for c in text if 0xE0000 <= ord(c) <= 0xE007F)
        elif label.startswith("private"):
            n = sum(1 for c in text if 0xE000 <= ord(c) <= 0xF8FF)
        else:
            n = sum(text.count(c) for c in chars)
        if n:
            out[label] = n
    return out


def analyze(raw):
    text = strip_code(raw)
    ws = words(text)
    n = len(ws)
    sents = sentences(text)
    lens = [len(words(s)) for s in sents] or [0]
    paras = paragraphs(text)
    plens = [len(words(p)) for p in paras] or [0]
    lower = text.lower()

    lex = {}
    for term in LEXICON:
        c = len(re.findall(r"\b" + re.escape(term) + r"\b", lower))
        if c:
            lex[term] = c

    triads = len(re.findall(r"\b[\w'-]+, [\w'-]+,? (?:and|or) [\w'-]+\b", text))
    bold_bullets = len(re.findall(r"^\s*[-*]\s+\*\*[^*\n]+\*\*", text, flags=re.M))
    closers = sum(1 for p in paras if any(CLOSERS.match(x) for x in sentences(p)[-3:]))
    em = text.count("—")
    en = text.count("–")
    spaced_hyphen = len(re.findall(r" - ", text))
    contractions = len(
        re.findall(
            r"\b(?:\w+(?:n['’]t|['’]re|['’]ve|['’]ll|['’]d|['’]m)"
            r"|(?:it|that|there|here|he|she|what|let|who|where)['’]s)\b",
            text,
            flags=re.I,
        )
    )
    mean = statistics.mean(lens) if lens else 0
    sd = statistics.pstdev(lens) if len(lens) > 1 else 0

    artifacts = {k: len(p.findall(raw)) for k, p in ARTIFACT_PATTERNS.items()}
    artifacts = {k: v for k, v in artifacts.items() if v}
    artifacts.update(count_chars(raw))

    return {
        "words": n,
        "sentences": len(sents),
        "sentence_length_mean": round(mean, 1),
        "sentence_length_sd": round(sd, 1),
        "sentence_length_cv": round(sd / mean, 2) if mean else 0,
        "short_sentences_pct": round(100.0 * sum(1 for l in lens if l <= 6) / max(len(lens), 1)),
        "long_sentences_pct": round(100.0 * sum(1 for l in lens if l >= 30) / max(len(lens), 1)),
        "paragraphs": len(paras),
        "paragraph_length_sd": round(statistics.pstdev(plens), 1) if len(plens) > 1 else 0,
        "per_1000": {
            "em dashes": per_1000(em, n),
            "en dashes": per_1000(en, n),
            "spaced hyphens used as dashes": per_1000(spaced_hyphen, n),
            "semicolons": per_1000(text.count(";"), n),
            "contractions": per_1000(contractions, n),
            "negative parallelism (not just X, but Y)": per_1000(count_regex(NEG_PARALLEL, text), n),
            "trailing -ing analysis clauses": per_1000(len(ING_TAIL.findall(text)), n),
            "word triads (a, b, and c)": per_1000(triads, n),
            "bold-label bullets": per_1000(bold_bullets, n),
            "quippy paragraph closers": per_1000(closers, n),
            "assistant residue": per_1000(count_regex(RESIDUE, text), n),
            "listed vocabulary tells": per_1000(sum(lex.values()), n),
        },
        "vocabulary_hits": lex,
        "artifacts": artifacts,
    }


NUM = re.compile(r"\b\d[\d,.]*\d%?|\b\d%?")
QUOTE = re.compile(r"[\"“]([^\"”\n]{4,200})[\"”]")
NAME = re.compile(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b", re.M)


def facts(text):
    t = strip_code(text)
    return {
        "numbers": set(NUM.findall(t)),
        "quotes": set(q.strip() for q in QUOTE.findall(t)),
        "names": set(m for m in NAME.findall(t) if len(m) > 2),
    }


def diff_facts(orig, new):
    a, b = facts(orig), facts(new)
    out = {}
    for k in a:
        dropped = sorted(a[k] - b[k])
        added = sorted(b[k] - a[k])
        if dropped or added:
            out[k] = {"possibly_dropped": dropped, "possibly_added": added}
    return out


def clean(text):
    for p in ARTIFACT_PATTERNS.values():
        text = p.sub("", text)
    out = []
    chars = list(text)
    for i, c in enumerate(chars):
        o = ord(c)
        if c in "  ":
            out.append(" ")
        elif c in "​⁠﻿":
            continue
        elif c in "‌‍":
            prev = chars[i - 1] if i else ""
            nxt = chars[i + 1] if i + 1 < len(chars) else ""
            if (prev and ord(prev) > 127) or (nxt and ord(nxt) > 127):
                out.append(c)  # emoji sequence or script-specific joiner; keep
        elif 0xE0000 <= o <= 0xE007F or 0xE000 <= o <= 0xF8FF:
            continue
        else:
            out.append(c)
    return "".join(out)


def fmt_report(name, r, sample=None):
    lines = []
    lines.append(f"== {name}: {r['words']} words, {r['sentences']} sentences, {r['paragraphs']} paragraphs ==")
    cols = "  {:<44}{:>8}" + ("{:>10}" if sample else "")
    head = ["Per 1,000 words", "draft"] + (["sample"] if sample else [])
    lines.append(cols.format(*head))
    for k, v in r["per_1000"].items():
        row = [k, v] + ([sample["per_1000"][k]] if sample else [])
        lines.append(cols.format(*row))
    lines.append("")
    lines.append("  Sentence length (words)" + ("      draft  sample" if sample else ""))
    for key, label in [
        ("sentence_length_mean", "mean"),
        ("sentence_length_sd", "spread (SD)"),
        ("sentence_length_cv", "spread / mean (low = uniform rhythm)"),
        ("short_sentences_pct", "% of sentences 6 words or fewer"),
        ("long_sentences_pct", "% of sentences 30 words or more"),
        ("paragraph_length_sd", "paragraph length SD"),
    ]:
        row = f"    {label:<40}{r[key]:>6}"
        if sample:
            row += f"{sample[key]:>8}"
        lines.append(row)
    if r["vocabulary_hits"]:
        lines.append("")
        lines.append(f"  Listed vocabulary (list dated {LEXICON_DATE}; a hit is a prompt to ask what the sentence should say):")
        lines.append("    " + ", ".join(f"{k} x{v}" for k, v in sorted(r["vocabulary_hits"].items())))
    if r["artifacts"]:
        lines.append("")
        lines.append("  Artifacts (run with --clean to remove):")
        for k, v in r["artifacts"].items():
            lines.append(f"    {k}: {v}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", help="text file to check (default: stdin)")
    ap.add_argument("--sample", help="a file of the writer's own text to compare against")
    ap.add_argument("--original", help="the text before editing; reports dropped or added numbers, quotes and names")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--clean", action="store_true", help="print the text with artifacts removed and exit")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")

    def read(path):
        with open(path, encoding="utf-8-sig") as f:
            return f.read()

    raw = read(args.file) if args.file else sys.stdin.read()

    if args.clean:
        sys.stdout.write(clean(raw))
        return

    result = analyze(raw)
    sample = analyze(read(args.sample)) if args.sample else None
    fact_diff = diff_facts(read(args.original), raw) if args.original else None

    if args.json:
        payload = {"draft": result}
        if sample:
            payload["sample"] = sample
        if fact_diff is not None:
            payload["fact_diff"] = fact_diff
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print(fmt_report(args.file or "stdin", result, sample))
    if fact_diff is not None:
        print("\n== Facts vs original (heuristic; check each by hand) ==")
        if not fact_diff:
            print("  No numbers, quotes or capitalised names differ.")
        for k, v in fact_diff.items():
            if v["possibly_dropped"]:
                print(f"  {k} possibly dropped: {', '.join(map(str, v['possibly_dropped']))}")
            if v["possibly_added"]:
                print(f"  {k} possibly added:   {', '.join(map(str, v['possibly_added']))}")
    print("\nAdvisory only. Counts do not prove anything about who wrote the text.")


if __name__ == "__main__":
    main()
