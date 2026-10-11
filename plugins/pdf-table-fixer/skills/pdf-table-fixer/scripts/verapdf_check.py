"""Check a PDF with veraPDF (PDF/UA-1) and compare before and after.

Usage: python verapdf_check.py FILE.pdf [--against BEFORE.pdf]
Exit codes: 0 ok; 1 a rule fails after that did not fail before; 2 not validated
(veraPDF or Java missing, or its report could not be read).
PAC may disagree with veraPDF on some rules; this reports veraPDF only.
"""
import argparse
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

FLAVOUR = "ua1"
TABLE_WORDS = re.compile(r"\b(table|TH|TD|TR|headers?|scope|rowspan|colspan)\b", re.I)


def find_tools():
    return shutil.which("verapdf"), shutil.which("java")


def is_table_rule(clause, description):
    return clause == "7.5" or bool(TABLE_WORDS.search(description or ""))


def parse_report(xml_text):
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f"not XML ({exc})") from None
    local = lambda el: el.tag.rsplit("}", 1)[-1]
    compliant, rules, found = None, {}, False
    for el in root.iter():
        name = local(el)
        if name == "validationReport":
            found = True
            if el.get("isCompliant") in ("true", "false"):
                compliant = el.get("isCompliant") == "true"
        elif name == "rule" and el.get("status") == "failed":
            desc = next((c.text or "" for c in el if local(c) == "description"), "")
            clause, test = el.get("clause", "?"), el.get("testNumber", "?")
            rules[(clause, test)] = {"count": int(el.get("failedChecks") or 1), "description": desc.strip(),
                                     "table": is_table_rule(clause, desc)}
    if not found:
        raise ValueError("no validationReport in the output")
    return {"compliant": compliant, "rules": rules}


def compare(before, after):
    b, a = before["rules"], after["rules"]
    return {
        "new": sorted(set(a) - set(b)),
        "fixed": sorted(set(b) - set(a)),
        "table_before": sum(r["count"] for r in b.values() if r["table"]),
        "table_after": sum(r["count"] for r in a.values() if r["table"]),
    }


def _default_runner(exe):
    def run(path):
        done = subprocess.run([exe, "--flavour", FLAVOUR, "--format", "xml", str(path)],
                              capture_output=True, timeout=300)
        return done.stdout.decode("utf-8", errors="replace")

    return run


def _summary(label, rep):
    rules = rep["rules"]
    table = [k for k, r in rules.items() if r["table"]]
    print(f"{label}: {len(rules)} failed rules, {len(table)} about tables")
    for k in table:
        print(f"  {k[0]}-{k[1]} x{rules[k]['count']}: {rules[k]['description']}")


def main(argv=None, runner=None):
    ap = argparse.ArgumentParser(prog="verapdf_check.py")
    ap.add_argument("pdf")
    ap.add_argument("--against")
    args = ap.parse_args(argv)
    if runner is None:
        exe, java = find_tools()
        if not exe or not java:
            missing = " and ".join(n for n, p in (("veraPDF", exe), ("Java", java)) if not p)
            print(f"not validated: {missing} not found on PATH. Install veraPDF (needs Java) to validate.")
            return 2
        runner = _default_runner(exe)
    print("veraPDF PDF/UA-1:")
    try:
        after = parse_report(runner(args.pdf))
        before = parse_report(runner(args.against)) if args.against else None
    except (ValueError, OSError, subprocess.SubprocessError):
        print("not validated: could not read veraPDF's report")
        return 2
    if before is not None:
        _summary(f"before ({args.against})", before)
    _summary(f"{'after' if before is not None else 'result'} ({args.pdf})", after)
    if before is None:
        return 0
    c = compare(before, after)
    print(f"table-related failures: {c['table_before']} -> {c['table_after']}")
    for k in c["fixed"]:
        print(f"  fixed: {k[0]}-{k[1]}")
    for k in c["new"]:
        print(f"  regression: {k[0]}-{k[1]} fails now and did not before: {after['rules'][k]['description']}")
    return 1 if c["new"] else 0


if __name__ == "__main__":
    sys.exit(main())
