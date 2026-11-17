#!/usr/bin/env python3
"""List what a news article actually points at: where its links go, who it quotes or hides, and
which figures carry no source.

Usage:
  python source_audit.py ARTICLE.html [--url https://outlet/page]     # a saved page, or plain text

It reads the saved file only; it fetches nothing. Output is JSON. It finds what to check; it does
not judge whether the article is right.
"""
import argparse
import json
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urlparse

SKIP = {"script", "style", "nav", "footer", "aside", "header", "form", "noscript", "figcaption"}
SOCIAL = {"twitter.com", "x.com", "facebook.com", "instagram.com", "tiktok.com", "youtube.com", "youtu.be",
          "reddit.com", "t.me", "bsky.app", "threads.net", "linkedin.com"}
PRIMARY_HOSTS = {"doi.org", "arxiv.org", "nature.com", "science.org", "thelancet.com", "nejm.org", "bmj.com",
                 "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov", "who.int", "un.org", "europa.eu", "sec.gov",
                 "courtlistener.com", "supremecourt.gov", "justia.com", "congress.gov", "federalregister.gov",
                 "worldbank.org", "imf.org", "oecd.org", "plos.org", "sciencedirect.com", "springer.com",
                 "jamanetwork.com", "cell.com", "pnas.org", "biorxiv.org", "medrxiv.org"}
PRIMARY_TLD = re.compile(r"\.(gov|mil|int)$|\.gov\.[a-z]{2}$|\.gouv\.fr$|\.gc\.ca$|\.parliament\.[a-z.]+$")
ANONYMOUS = re.compile(
    r"\b(people|sources?|officials?|persons?|those|individuals?|employees?|insiders?) "
    r"(familiar|briefed|close|with knowledge|who (spoke|asked|requested|declined))\b"
    r"|on (the )?condition of anonymity|spoke anonymously|not to be (named|identified)|unnamed"
    r"|according to (a|an|two|three|several|multiple|one) (source|official|person|people|insider)",
    re.I,
)
ATTRIBUTION = re.compile(r"\b(said|says|told|according to|wrote|stated|argued|added|noted|reported|claimed|"
                         r"announced|confirmed|denied|found|showed|shows|estimated|data show)\b", re.I)
YEAR = re.compile(r"\b(19|20)\d\d\b")
FIGURE = re.compile(r"\d[\d,.]*\s?(%|percent|per cent|million|billion|trillion|thousand)\b|[$£€]\s?\d|\b\d{2,}\b", re.I)
QUOTE = re.compile(r"[“\"]([^”\"]{20,})[”\"]")
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z“\"‘'])")
MAX_FIGURES = 15


def registered(host):
    host = host.lower().removeprefix("www.")
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "gov", "ac", "net"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


class Page(HTMLParser):
    """Paragraphs with their links, from the article element when there is one."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.article = 0
        self.saw_article = False
        self.in_p = False
        self.text, self.links = [], []
        self.paragraphs, self.fallback = [], []
        self.canonical = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href")
        if tag == "meta" and attrs.get("property") == "og:url" and not self.canonical:
            self.canonical = attrs.get("content")
        if tag in SKIP:
            self.skip += 1
        if tag == "article":
            self.article += 1
            self.saw_article = True
        if tag == "p" and not self.skip:
            self.in_p, self.text, self.links = True, [], []
        if tag == "a" and self.in_p and attrs.get("href", "").startswith(("http://", "https://")):
            self.links.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag in SKIP and self.skip:
            self.skip -= 1
        if tag == "article" and self.article:
            self.article -= 1
        if tag == "p" and self.in_p:
            self.in_p = False
            text = re.sub(r"\s+", " ", "".join(self.text)).strip()
            if text:
                record = {"text": text, "links": self.links}
                self.fallback.append(record)
                if self.article:
                    self.paragraphs.append(record)

    def handle_data(self, data):
        if self.in_p and not self.skip:
            self.text.append(data)


def read_paragraphs(raw):
    """(paragraphs, canonical url). Plain text is split on blank lines."""
    if not re.search(r"<(p|article|html|body)[\s>]", raw, re.I):
        return [{"text": re.sub(r"\s+", " ", p).strip(), "links": re.findall(r"https?://[^\s)\]>]+", p)}
                for p in re.split(r"\n\s*\n", raw) if p.strip()], None
    page = Page()
    page.feed(raw)
    return (page.paragraphs or page.fallback), page.canonical


def classify(url, own):
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    base = registered(host)
    if own and base == own:
        return "same-outlet"
    if host in PRIMARY_HOSTS or base in PRIMARY_HOSTS or PRIMARY_TLD.search(host):
        return "primary"
    if base in SOCIAL:
        return "social"
    return "other"


def audit(paragraphs, own_url=None):
    own = registered(urlparse(own_url).hostname or "") if own_url else None
    sentences = [(s, p) for p in paragraphs for s in SENTENCE.split(p["text"])]
    links = {"primary": [], "same-outlet": [], "social": [], "other": []}
    seen = set()
    for paragraph in paragraphs:
        for url in paragraph["links"]:
            if url not in seen:
                seen.add(url)
                links[classify(url, own)].append(url)
    anonymous = [s for s, _ in sentences if ANONYMOUS.search(s)]
    named = sum(1 for s, _ in sentences if ATTRIBUTION.search(s) and not ANONYMOUS.search(s))
    figures = []
    for sentence, paragraph in sentences:
        stripped = YEAR.sub("", sentence)
        if FIGURE.search(stripped) and not ATTRIBUTION.search(sentence) and not paragraph["links"]:
            figures.append(sentence)
    return {
        "words": sum(len(p["text"].split()) for p in paragraphs),
        "paragraphs": len(paragraphs),
        "own_domain": own,
        "links": {"counts": {k: len(v) for k, v in links.items()}, **{k: v for k, v in links.items() if k != "other"}},
        "other_link_domains": sorted({registered(urlparse(u).hostname or "") for u in links["other"]}),
        "named_attributions": named,
        "anonymous_source_sentences": anonymous,
        "direct_quotes": sum(len(QUOTE.findall(p["text"])) for p in paragraphs),
        "figures_without_attribution_or_link": figures[:MAX_FIGURES],
        "figures_without_attribution_or_link_total": len(figures),
        "notes": [] if own else ["no outlet URL found: pass --url so same-outlet links are not counted as outside sources"],
    }


def main(argv=None):
    for stream in (sys.stdout,):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("article")
    parser.add_argument("--url", help="the article's own URL, if the saved page does not carry it")
    args = parser.parse_args(argv)
    try:
        with open(args.article, encoding="utf-8", errors="replace") as handle:
            raw = handle.read()
    except OSError as error:
        print(f"could not read {args.article}: {error}", file=sys.stderr)
        return 2
    paragraphs, canonical = read_paragraphs(raw)
    if not paragraphs:
        print("no article text found in the file", file=sys.stderr)
        return 2
    print(json.dumps(audit(paragraphs, args.url or canonical), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
