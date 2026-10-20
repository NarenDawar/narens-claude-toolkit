# What this skill rests on

For maintainers. Not needed when writing. The full research report (about 100 lines, with links and every contradiction between sources) is in research-report.md next to this file. Research date: 2026-10-19. Grades: measured (quantified in a study), documented (stated in an official or primary source), anecdotal (user reports, blogs), unverified (secondhand or not confirmable).

| Design choice | Basis | Grade |
|---|---|---|
| Build around specificity, commitment and one reader, not a banned-word list | Skilled readers cite vocabulary (53%), sentence structure (36%), originality (24%), clarity (20%) when spotting AI text; the cues point to genericness | measured (Russell et al., ACL 2025) |
| Ask for a brief and voice samples before drafting | Few-shot samples of a real author beat zero-shot across 400+ authors; gains small past a few samples; genre-matched beats topic-matched | measured (arXiv 2509.14543) |
| Rank structure above vocabulary | Word ratios are measured but shift per model; structural patterns come from a community guide | measured (Kobak et al.) / documented (Wikipedia guide) |
| Positive fixes with before/after pairs | Anthropic's guides recommend saying what to do and using examples | documented |
| Substitution risk when banning phrases | Blog and forum reports; no Anthropic statement | anecdotal |
| Lint script for counts, not auto-fix | Regex cannot read intent; self-grading by the same model is a weak metric | inference |
| No detector or watermark promises | Detectors vary by year and vendor; 2023 tools flagged 61% of non-native essays; watermarks are statistical and survive light editing | measured / documented |
| Hygiene limited to real artifacts | oaicite, turnNsearchN, U+202F, utm parameters documented in forums; zero-width "watermark" claim has no primary source | anecdotal / unverified |

## Open gaps

No controlled evaluation of any humanizer skill exists in the sources, including this one. blader/humanizer (58k stars) and stop-slop have the largest followings; their blind-test claims could not be verified. No study covers 2026-era models on lightly edited text at scale. No measured frequency of Claude's own phrases was found. The Wikipedia guide was only partly read. Primary texts for EU AI Act Article 50, ICMJE and Nature policies, and the craft books were not read. Anthropic's August 2026 watermark announcement and OpenAI's October 2026 one are known mostly through secondary reports.

## Evaluation plan (not yet run at scale)

Blind pairwise preference from raters who use LLMs heavily, across 20 to 30 prompts and several genres, comparing plain Claude, this skill, blader/humanizer and stop-slop; lint counts before and after; fact-preservation diff in edit mode; a held-out voice-imitation test; re-runs on Haiku, Sonnet and Opus and at each new model release. Detector scores only as a secondary, caveated number.
