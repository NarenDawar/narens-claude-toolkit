#!/usr/bin/env python3
"""Check that cited references exist and match, and that quoted text is in a source.

Usage:
  python refcheck.py check REFS.json                 # look each reference up in Crossref and OpenAlex
  python refcheck.py abstract DOI                    # the abstract OpenAlex holds for a DOI
  python refcheck.py quote SOURCE.txt < quotes.json  # [{"id": "smith2020", "quote": "..."}]

REFS.json is a list: [{"id": "smith2020", "title": "...", "authors": ["Smith", "Lee"],
"year": 2020, "doi": "10.1/x"}]. Only title is required. Authors may be "Family" or "Family, G.".
Statuses: verified, metadata-mismatch, doi-mismatch (the DOI is a different work), doi-not-found,
not-found, error. "not-found" means no match in these databases, not that the work is fake:
books, theses and non-English works are weakly covered. Reads the network; writes nothing.
Set OPENALEX_API_KEY to use your own OpenAlex quota.
"""
import argparse
import difflib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

AGENT = {"User-Agent": "citation-verifier/0.1 (open-source Claude Code skill)"}
TITLE_OK = 0.9  # similarity at which two titles are the same work
TITLE_DIFFERENT = 0.6  # below this a DOI belongs to some other work
MIN_QUOTE_CHARS = 20
CANDIDATES = 5


class LookupError_(Exception):
    pass


def get_json(url, tries=2):
    """JSON from a URL; None for a 404; LookupError_ for anything else that goes wrong."""
    last = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=25) as reply:
                return json.load(reply)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            last = f"HTTP {error.code}"
            if error.code not in (429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            last = str(error)
        time.sleep(1 + attempt)
    raise LookupError_(f"{url.split('?')[0]}: {last}")


def norm(text):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (text or "").casefold())).strip()


def title_similarity(cited, found):
    """0 to 1. A cited title with no subtitle also matches the found title's part before its colon:
    'Prospect theory' is the same work as 'Prospect theory: an analysis of decision under risk'.
    Two different subtitles after the same head are different works."""
    cited, found = cited or "", found or ""
    if not norm(cited) or not norm(found):
        return 0.0
    score = difflib.SequenceMatcher(None, norm(cited), norm(found)).ratio()
    head = found.split(":")[0]
    if ":" not in cited and ":" in found and len(norm(head)) >= 10:
        score = max(score, difflib.SequenceMatcher(None, norm(cited), norm(head)).ratio())
    return round(score, 3)


def surname(name):
    """The last word of the family name, so 'van Assen, M.', 'Assen' and 'Marcel van Assen' agree."""
    name = name.strip()
    family = name.split(",")[0] if "," in name else name
    words = norm(family).split()
    return words[-1] if words else ""


def crossref_item(item):
    years = []
    for key in ("issued", "published-print", "published-online"):
        parts = (item.get(key) or {}).get("date-parts") or [[None]]
        if parts[0] and parts[0][0] and parts[0][0] not in years:
            years.append(parts[0][0])
    year = years[0] if years else None
    return {
        "years": years,
        "source": "crossref",
        "title": " ".join((item.get("title") or [""])[:1]),
        "authors": [surname(a.get("family") or a.get("name") or "") for a in item.get("author", [])],
        "year": year,
        "doi": (item.get("DOI") or "").lower(),
        "venue": " ".join((item.get("container-title") or [""])[:1]),
        "url": item.get("URL"),
    }


def openalex_item(item):
    doi = (item.get("doi") or "").lower().removeprefix("https://doi.org/")
    return {
        "source": "openalex",
        "title": item.get("title") or item.get("display_name") or "",
        "authors": [surname(a["author"]["display_name"]) for a in item.get("authorships", []) if a.get("author")],
        "year": item.get("publication_year"),
        "years": [item["publication_year"]] if item.get("publication_year") else [],
        "doi": doi,
        "venue": (((item.get("primary_location") or {}).get("source")) or {}).get("display_name") or "",
        "url": item.get("id"),
        "oa_url": (item.get("open_access") or {}).get("oa_url"),
    }


def by_doi(doi):
    reply = get_json("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/"))
    if reply and reply.get("message"):
        return crossref_item(reply["message"])
    reply = openalex_get("/works/doi:" + urllib.parse.quote(doi, safe="/"))
    return openalex_item(reply) if reply else None


def openalex_get(path, query=None):
    params = dict(query or {})
    if os.environ.get("OPENALEX_API_KEY"):
        params["api_key"] = os.environ["OPENALEX_API_KEY"]
    return get_json("https://api.openalex.org" + path + ("?" + urllib.parse.urlencode(params) if params else ""))


def search(ref):
    """Candidate works for a title: Crossref first, OpenAlex as well (it holds preprints and
    proceedings that have no Crossref DOI)."""
    found = []
    query = ref["title"] + " " + " ".join(surname(a) for a in ref.get("authors", [])[:1])
    reply = get_json("https://api.crossref.org/works?" + urllib.parse.urlencode(
        {"query.bibliographic": query, "rows": CANDIDATES}))
    if reply:
        found += [crossref_item(i) for i in reply.get("message", {}).get("items", [])]
    try:
        reply = openalex_get("/works", {"search": ref["title"], "per-page": CANDIDATES})
    except LookupError_ as error:
        if not found:
            raise
        ref.setdefault("_notes", []).append(f"OpenAlex unavailable ({error}); checked in Crossref only")
        return found
    if reply:
        found += [openalex_item(i) for i in reply.get("results", [])]
    return found


def compare(ref, work):
    """(issues, notes): what differs between the reference as cited and the work found.
    A wrong author or year is an issue; a different venue is only a note, since venue names
    are abbreviated and renamed too often to be sure."""
    issues, notes = [], []
    want = [surname(a) for a in ref.get("authors", []) if a.strip()]
    have = [surname(a) for a in work["authors"]]
    if want and have and want[0] != have[0]:
        issues.append(f"first author: cited {want[0]!r}, found {have[0]!r}")
    elif want and have:
        missing = [w for w in want if w not in have]
        if missing and len(have) >= len(want):
            issues.append(f"cited authors not on the work: {', '.join(missing)}")
    year = ref.get("year")
    if isinstance(year, str) and year.isdigit():
        year = int(year)
    held = work.get("years") or ([work["year"]] if work.get("year") else [])
    if isinstance(year, int) and held and all(abs(year - y) > 1 for y in held):
        issues.append(f"year: cited {year}, found {', '.join(str(y) for y in held)}")
    cited_venue, found_venue = norm(ref.get("venue")), norm(work.get("venue"))
    if cited_venue and found_venue and cited_venue not in found_venue and found_venue not in cited_venue             and not set(cited_venue.split()) & set(found_venue.split()):
        notes.append(f"venue: cited {ref['venue']!r}, found {work['venue']!r}")
    return issues, notes


def shown(work):
    return {k: work[k] for k in ("title", "authors", "year", "doi", "venue", "url", "oa_url", "source") if work.get(k)} \
        | ({"authors": work["authors"][:4]} if work.get("authors") else {})


def finish(out, ref, work, similarity):
    issues, notes = compare(ref, work)
    if similarity < TITLE_OK:
        issues.append(f"title differs (similarity {similarity})")
    out.update(status="verified" if not issues else "metadata-mismatch", title_similarity=similarity,
               issues=issues, matched=shown(work))
    if notes + ref.get("_notes", []):
        out["notes"] = notes + ref.get("_notes", [])
    return out


def check_one(ref, lookup_doi=by_doi, lookup_search=search):
    out = {"id": ref.get("id"), "cited_title": ref.get("title")}
    doi = (ref.get("doi") or "").strip().lower().removeprefix("https://doi.org/").removeprefix("doi:")
    title = ref.get("title") or ""
    if not title and not doi:
        return {**out, "status": "error", "issues": ["no title or DOI to check"]}
    try:
        if doi:
            work = lookup_doi(doi)
            if work is not None:
                similarity = title_similarity(title, work["title"]) if title else 1.0
                if similarity < TITLE_DIFFERENT:
                    return {**out, "status": "doi-mismatch", "title_similarity": similarity,
                            "issues": [f"DOI {doi} is a different work from the one cited"], "doi_belongs_to": shown(work)}
                return finish(out, ref, work, similarity)
            out.update(status="doi-not-found", issues=[f"no record of DOI {doi}"])
        candidates = lookup_search(ref) if title else []
    except LookupError_ as error:
        return {**out, "status": "error", "issues": [str(error)]}
    scored = sorted(((title_similarity(title, c["title"]), c) for c in candidates), key=lambda pair: -pair[0])
    same = [(s, c) for s, c in scored if s >= TITLE_OK]
    if same:  # several records can share a title (reprints, translations): take the one that fits best
        similarity, work = min(same, key=lambda pair: (len(compare(ref, pair[1])[0]), -pair[0]))
        return finish(out, ref, work, similarity)
    result = {**out, "status": out.get("status", "not-found"),
              "issues": out.get("issues") or ["no work with this title in Crossref or OpenAlex"]}
    if scored:
        result["closest"] = {"title_similarity": scored[0][0], **shown(scored[0][1])}
    if ref.get("_notes"):
        result["notes"] = ref["_notes"]
    return result


def check(refs, **lookups):
    return [check_one(r, **lookups) for r in refs]


def abstract_of(doi):
    reply = openalex_get("/works/doi:" + urllib.parse.quote(doi, safe="/"))
    if not reply or not reply.get("abstract_inverted_index"):
        return None
    slots = {}
    for word, places in reply["abstract_inverted_index"].items():
        for place in places:
            slots[place] = word
    return " ".join(slots[i] for i in sorted(slots))


def compact(text):
    return re.sub(r"[\W_]+", "", (text or "").casefold())


def quote_check(source, quotes):
    """ok when the quote is in the source text, ignoring spacing, case and punctuation."""
    flat, results = compact(source), []
    for entry in quotes:
        key = compact(entry.get("quote", ""))
        if len(key) < MIN_QUOTE_CHARS:
            status = "too-short"
        else:
            status = "ok" if key in flat else "not-found"
        results.append({"id": entry.get("id"), "quote": entry.get("quote"), "status": status})
    return results


def main(argv=None):
    for stream in (sys.stdout, sys.stdin):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["check", "abstract", "quote"])
    parser.add_argument("target")
    args = parser.parse_args(argv)
    try:
        if args.command == "abstract":
            text = abstract_of(args.target.strip().lower().removeprefix("https://doi.org/"))
            if text is None:
                print("OpenAlex holds no abstract for that DOI", file=sys.stderr)
                return 1
            print(text)
            return 0
        if args.command == "check":
            with open(args.target, encoding="utf-8") as handle:
                refs = json.load(handle)
            assert isinstance(refs, list) and all(isinstance(r, dict) for r in refs)
            results = check(refs)
            print(json.dumps({"summary": {s: sum(r["status"] == s for r in results) for s in sorted({r["status"] for r in results})},
                              "results": results}, indent=1, ensure_ascii=False))
            return 0
        with open(args.target, encoding="utf-8", errors="replace") as handle:
            source = handle.read()
        quotes = json.load(sys.stdin)
        assert isinstance(quotes, list) and all(isinstance(q, dict) for q in quotes)
        results = quote_check(source, quotes)
        print(json.dumps(results, indent=1, ensure_ascii=False))
        return 0 if all(r["status"] == "ok" for r in results) else 1
    except (OSError, ValueError, AssertionError) as error:
        print(f"bad input: {error}", file=sys.stderr)
        return 2
    except LookupError_ as error:
        print(f"lookup failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
