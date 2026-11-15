# 004F draft annotation collection

This is a separate **agent-authored draft**, not human-reviewed gold. No reviewer
identity or agreement statistic is asserted. The 66 cases and their alternating
33-case dev/33-case held-out IDs are frozen in `manifest.json`. They contain
illustrative synthetic versions, not current source facts. The original 004A
112-case dataset and reports are not used or changed.

Each JSONL row has version `004f.dataset.v1`, original text, a SHA-256 of its
exact UTF-8 encoding, reference date, immutable split ID, tags, exact assertion
annotations and review status. File hashes normalize Git checkout CRLF to LF;
escaped CR/LF inside candidate strings remain part of the candidate hash.
`manifest.json` lists the files' hashes and the ten initial diagnostic case IDs.

Draft annotations were authored explicitly alongside synthetic examples; their
offsets locate the supplied verbatim quotes. No extractor prediction supplied
the reference labels. A label is not proof of semantic correctness. Code tests
may read either split to validate file structure/limits, but rules were developed
on focused adversarial tests and dev examples before the first held-out scoring.
Do not tune against held-out predictions and then call that independent quality.

For each case, an independent reviewer should:

1. Verify the source hash and read the complete response before viewing any
   prediction. Preserve Unicode code-point boundaries and all qualifiers.
2. Enumerate independent externally checkable assertions, including assertions
   inside opinions, parentheses, compounds and quoted material. Annotate uncertain
   referents explicitly; do not invent subjects or silently drop difficult units.
3. Check factuality, temporal scope and fresh-evidence need against the fixed
   reference date. STABLE/HISTORICAL/NOT_REQUIRED are classifications, not truth
   verdicts or exemptions from coverage.
4. Assign a policy ID only for an independently defensible Python Windows
   latest-label or fixed requests PyPI reported-version proposition. Negation,
   predictions, different packages/sources and safety/popularity claims cannot
   inherit an affirmative release/version policy.
5. Check `expected_bounded_accounting` against the documented closed grammar and
   context restrictions. This is a bounded planning target, not general semantic
   completeness. Unsupported/ambiguous/no-assertion cases cannot be PLAN_READY.
6. Record disagreements and corrections in an external review ledger with case
   ID, source hash, genuine reviewer, date and rationale. A second independent
   reviewer should resolve disputed atomic boundaries or classifications.

Keep these draft files unchanged. Create a separate reviewed copy, preserve IDs
and source hashes, document label changes, set `human_reviewed` and the actual
reviewer's name only after review, and update that copy's manifest file hashes.
Then evaluate with `--dataset-dir <reviewed-copy> --require-human-reviewed`.
The loader verifies declarations and hashes; it cannot authenticate a reviewer
or replace independent review. Changing a split/source requires a new collection,
not rewriting this frozen benchmark. Human-reviewed quality and real-model
performance qualification remain pending.

The evaluator reports all cases, including extraction/alignment failures. Claim
and exact-span P/R/F1 use one-to-one matching; one broad span cannot match several
assertions. False-complete cases are listed individually, with failure categories.
Extraction failures count as safe refusals where appropriate, but receive no
credit as correct semantic abstentions. Missing denominator information is null,
not zero. The historical 004A fresh recall 0.232 is not comparable to these scores.

See the [non-authorizing planner contract](../../README.md#experimental-natural-language-planning) and [published offline measurement scope](../../reports/prose-v1/README.md). These planning annotations do not define the gateway authorization grammar.
