# Text hygiene: artifacts, characters and watermarks

Contents: what gets cleaned, what does not, and what to say about watermarks.

Hygiene is about correctness. Pasted model output sometimes carries leftovers that look broken or messy to a reader. Cleaning them is harmless for any author. It is not a way to hide anything.

## Artifacts that are real and documented

All of the following come from user reports and forum threads, not from the providers' own documentation, except where noted.

- Citation markers that leak into text: `::contentReference[oaicite:0]{index=0}`, `[oaicite:9]{index=9}`, `turn0search0` style tokens, Deep Research markers like `【45†L75-L83】`.
- Private-use characters (U+E000 to U+F8FF), including U+E200 to U+E202 that wrapped some `turn0search0` tokens.
- Narrow no-break space U+202F, reported in OpenAI reasoning-model output from April 2025 and again in GPT-5 output. Replace it with a normal space. Do not delete it.
- Non-breaking space U+00A0 where an ordinary space was meant.
- Tracking parameters on links such as `utm_source=chatgpt.com`, added from June 2025. A search report in October 2026 said they may have been dropped, which OpenAI had not confirmed.
- Unicode tag characters (U+E0000 to U+E007F). These are a known prompt-injection vector, not a watermark. Remove them.
- Zero-width characters (U+200B, U+2060, U+FEFF). Remove them. Keep U+200D inside emoji sequences and U+200C where it is part of correct spelling in languages such as Persian and some Indic scripts. The lint script keeps a joiner when a non-ASCII character is next to it.

## What is a myth

The claim that a chatbot inserts zero-width spaces as a deliberate watermark has no primary support. Anthropic's published description of its own watermark says nothing is added to the text and there are no hidden characters.

## Watermarks

Statistical text watermarks bias word choice in a pattern a detector can test for. Anthropic says (Aug 2026, updated Sep 2026) that future Claude models carry one, applied globally. Google's SynthID-Text has been used in the Gemini app since 2024, and OpenAI announced an on-by-default EU rollout in October 2026. Whether the Gemini API marks text is unresolved. Most of these facts came from secondary reports, so verify before quoting them.

What follows for this skill:

- Character cleanup does nothing to a statistical watermark, so never say it does.
- Light editing probably leaves a mark intact, and a full rewrite weakens it. No one has guaranteed either, and this skill does not promise a result.
- A detected mark does not prove who wrote the text. It cannot tell "wrote" from "heavily edited", and research shows marks can be spoofed.
- Law is moving. The EU AI Act's Article 50 labelling duties apply from 2 August 2026 to some AI-generated text published on matters of public interest. This skill does not give legal advice; point the user to the rules for their situation.
