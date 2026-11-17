import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import helpers

sys.path.insert(
    0,
    str(helpers.REPO_ROOT / "plugins" / "news-source-reader" / "skills" / "news-source-reader" / "scripts"),
)
import source_audit as sa  # noqa: E402

PAGE = """<html><head><link rel="canonical" href="https://www.example-news.co.uk/world/story"></head><body>
<nav><p>Subscribe now for 50% off for 12 months</p></nav>
<article>
<p>Grants rose 21-fold in 2025, the agency's database shows. See the <a href="https://reporter.nih.gov/x">record</a>.</p>
<p>The budget fell by 40 percent last year.</p>
<p>"We were told to stop the study immediately," said Dr Ana Ruiz. Officials who spoke on condition of anonymity confirmed it.</p>
<p>Earlier <a href="https://www.example-news.co.uk/older">coverage</a> and a <a href="https://twitter.com/a/1">post</a>
 and <a href="https://www.cdc.gov/x">CDC page</a> and <a href="https://blog.example.org/p">a blog</a>.</p>
<p>The firm was founded in 1998 and has offices in 2010.</p>
</article>
<aside><p>Related: 99% of readers agree</p></aside>
<footer><p>Copyright 2026 and 100 rights</p></footer>
</body></html>"""


def audit(text=PAGE, url=None):
    paragraphs, canonical = sa.read_paragraphs(text)
    return sa.audit(paragraphs, url or canonical)


class RegisteredTests(unittest.TestCase):
    def test_registered_domain(self):
        self.assertEqual(sa.registered("www.theguardian.com"), "theguardian.com")
        self.assertEqual(sa.registered("news.bbc.co.uk"), "bbc.co.uk")
        self.assertEqual(sa.registered("localhost"), "localhost")


class ClassifyTests(unittest.TestCase):
    def test_categories(self):
        for url, want in [
            ("https://www.cdc.gov/x", "primary"),
            ("https://www.legislation.gov.uk/x", "primary"),
            ("https://doi.org/10.1/2", "primary"),
            ("https://www.nature.com/articles/1", "primary"),
            ("https://twitter.com/a", "social"),
            ("https://news.example-news.co.uk/y", "same-outlet"),
            ("https://random-blog.example.org/p", "other"),
        ]:
            with self.subTest(url=url):
                self.assertEqual(sa.classify(url, "example-news.co.uk"), want)

    def test_without_an_own_domain_nothing_is_same_outlet(self):
        self.assertEqual(sa.classify("https://example-news.co.uk/y", None), "other")


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.out = audit()

    def test_only_the_article_body_is_read(self):
        self.assertEqual(self.out["paragraphs"], 5)  # nav, aside and footer paragraphs are left out
        self.assertEqual(self.out["own_domain"], "example-news.co.uk")

    def test_links_are_sorted_by_kind(self):
        self.assertEqual(self.out["links"]["counts"], {"primary": 2, "same-outlet": 1, "social": 1, "other": 1})
        self.assertIn("https://reporter.nih.gov/x", self.out["links"]["primary"])
        self.assertEqual(self.out["other_link_domains"], ["example.org"])

    def test_anonymous_sources_are_listed_and_named_ones_counted(self):
        self.assertEqual(len(self.out["anonymous_source_sentences"]), 1)
        self.assertIn("anonymity", self.out["anonymous_source_sentences"][0])
        self.assertGreaterEqual(self.out["named_attributions"], 2)  # "database shows" and "said Dr Ana Ruiz"

    def test_unattributed_figures_are_found_but_years_and_linked_figures_are_not(self):
        figures = self.out["figures_without_attribution_or_link"]
        self.assertEqual(figures, ["The budget fell by 40 percent last year."])

    def test_direct_quotes_are_counted(self):
        self.assertEqual(self.out["direct_quotes"], 1)

    def test_missing_outlet_url_is_noted(self):
        text = "<article><p>One short paragraph.</p></article>"
        self.assertTrue(audit(text)["notes"])
        self.assertEqual(audit(text, "https://a.com/x")["notes"], [])


class PlainTextTests(unittest.TestCase):
    def test_plain_text_is_split_on_blank_lines_and_urls_found(self):
        text = "Costs rose 30 percent.\n\nSee https://www.sec.gov/filing for the filing.\n"
        out = audit(text, "https://a.com/x")
        self.assertEqual(out["paragraphs"], 2)
        self.assertEqual(out["links"]["counts"]["primary"], 1)
        self.assertEqual(out["figures_without_attribution_or_link"], ["Costs rose 30 percent."])

    def test_a_page_without_article_tags_falls_back_to_all_paragraphs(self):
        out = audit("<html><body><p>Some text here with 25 percent.</p></body></html>", "https://a.com")
        self.assertEqual(out["paragraphs"], 1)


class CliTests(unittest.TestCase):
    def cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = sa.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_prints_json_for_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.html"
            path.write_text(PAGE, encoding="utf-8")
            code, out, _ = self.cli([str(path)])
        self.assertEqual((code, json.loads(out)["paragraphs"]), (0, 5))

    def test_missing_and_empty_files_are_usage_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "e.html"
            empty.write_text("<html></html>", encoding="utf-8")
            self.assertEqual(self.cli([str(Path(tmp) / "none.html")])[0], 2)
            self.assertEqual(self.cli([str(empty)])[0], 2)


if __name__ == "__main__":
    unittest.main()
