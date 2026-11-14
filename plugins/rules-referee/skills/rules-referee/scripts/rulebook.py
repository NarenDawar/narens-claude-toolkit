#!/usr/bin/env python3
"""Read a rulebook PDF page by page, find rules text, and check quotes against it.

Usage:
  python rulebook.py info   BOOK.pdf
  python rulebook.py find   BOOK.pdf TERM [TERM ...]
  python rulebook.py page   BOOK.pdf N [N ...]          # the full text of those pages
  python rulebook.py verify BOOK.pdf < quotes.json     # [{"page": 3, "quote": "..."}, ...]

Pages are numbered as the PDF viewer numbers them (the first page is 1), which can differ
from the number printed on the page. Needs pypdf (pip install pypdf) or the pdftotext
program from poppler. Read-only.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

MIN_QUOTE_CHARS = 20  # a shorter quote proves nothing
NO_TEXT_BELOW = 40  # a page with fewer characters than this has no usable text layer
SNIPPET = 160


class NoReader(Exception):
    pass


def compact(text):
    """Lower-case letters and digits only. PDF extraction often drops spaces, so comparing
    in this form keeps a true quote from failing on spacing, hyphenation or punctuation."""
    return re.sub(r"[\W_]+", "", text.casefold())


def load_pages(path):
    """The text of each page, first page first."""
    try:
        from pypdf import PdfReader
    except ImportError:
        PdfReader = None
    if PdfReader is not None:
        return [page.extract_text() or "" for page in PdfReader(path).pages]
    if shutil.which("pdftotext"):
        out = subprocess.run(
            ["pdftotext", "-enc", "UTF-8", path, "-"], capture_output=True, timeout=120, check=True
        ).stdout.decode("utf-8", errors="replace")
        pages = out.split("\f")
        return pages[:-1] if pages and not pages[-1].strip() else pages
    raise NoReader("need pypdf (pip install pypdf) or the pdftotext program (poppler)")


def info(pages):
    return {
        "pages": len(pages),
        "characters_per_page": [len(page.strip()) for page in pages],
        "pages_without_text": [i for i, page in enumerate(pages, 1) if len(page.strip()) < NO_TEXT_BELOW],
    }


def find(pages, terms):
    """Pages ranked by how many of the terms they contain, each with a snippet per term."""
    wanted = [(term, compact(term)) for term in terms if compact(term)]
    hits = []
    for number, page in enumerate(pages, 1):
        flat = re.sub(r"\s+", " ", page)
        lower, squashed = flat.casefold(), compact(page)
        found = {}
        for term, key in wanted:
            at = lower.find(term.casefold())
            if at >= 0:
                found[term] = flat[max(0, at - SNIPPET): at + len(term) + SNIPPET].strip()
            elif key in squashed:
                found[term] = None  # present, but the page text has lost its spaces: read the page
        if found:
            hits.append({"page": number, "matched": len(found), "terms": found})
    return sorted(hits, key=lambda hit: (-hit["matched"], hit["page"]))


def verify(pages, quotes):
    """Per quote: ok, wrong-page, no-page (found, but no valid page was cited), not-found or
    too-short. One contiguous quote each."""
    squashed = [compact(page) for page in pages]
    results = []
    for entry in quotes:
        quote, page = entry.get("quote", ""), entry.get("page")
        key = compact(quote)
        result = {"page": page, "quote": quote}
        if len(key) < MIN_QUOTE_CHARS:
            result["status"] = "too-short"
        elif isinstance(page, int) and 1 <= page <= len(pages) and key in squashed[page - 1]:
            result["status"] = "ok"
        else:
            elsewhere = [i for i, text in enumerate(squashed, 1) if key in text]
            if not elsewhere:
                result["status"] = "not-found"
            else:
                has_page = isinstance(page, int) and 1 <= page <= len(pages)
                result["status"] = "wrong-page" if has_page else "no-page"
                result["found_on"] = elsewhere
        results.append(result)
    return results


def main(argv=None):
    for stream in (sys.stdout, sys.stdin):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["info", "find", "page", "verify"])
    parser.add_argument("book")
    parser.add_argument("terms", nargs="*")
    args = parser.parse_args(argv)
    path = os.path.abspath(args.book)
    if not os.path.isfile(path):
        print(f"no such file: {args.book}", file=sys.stderr)
        return 2
    if args.command in ("find", "page") and not args.terms:
        parser.error(f"{args.command} needs at least one {'term' if args.command == 'find' else 'page number'}")
    try:
        pages = load_pages(path)
    except NoReader as error:
        print(error, file=sys.stderr)
        return 2
    except Exception as error:  # an unreadable or damaged PDF
        print(f"could not read the PDF: {error}", file=sys.stderr)
        return 2
    if args.command == "info":
        print(json.dumps(info(pages)))
    elif args.command == "find":
        print(json.dumps(find(pages, args.terms), indent=1))
    elif args.command == "page":
        wanted = [int(n) if n.isdigit() else 0 for n in args.terms]
        if not wanted or not all(1 <= n <= len(pages) for n in wanted):
            parser.error(f"page needs page numbers from 1 to {len(pages)}")
        for n in wanted:
            print(f"=== page {n} ===")
            print(pages[n - 1].strip())
            print()
    else:
        try:
            quotes = json.load(sys.stdin)
            assert isinstance(quotes, list) and all(isinstance(q, dict) for q in quotes)
        except (ValueError, AssertionError):
            print('stdin must be a JSON list like [{"page": 3, "quote": "..."}]', file=sys.stderr)
            return 2
        results = verify(pages, quotes)
        print(json.dumps(results, indent=1))
        return 0 if all(r["status"] == "ok" for r in results) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
