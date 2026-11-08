# Claim analysis v1: annotation and contract rules

This subsystem identifies assertions; it never establishes truth, freshness or release authorization. Examples are synthetic annotation material, including deliberately false assertions. They are not independently verified observations.

Use reference date **2026-11-08** throughout dataset v1. Span offsets are Python `str` indices (Unicode code points), start inclusive/end exclusive, before any Unicode normalization or newline conversion. `text[start:end]` must equal `source_text`. Combining marks and emoji can occupy multiple indices. Do not use UTF-8 byte offsets or JavaScript UTF-16 indices.

Annotate the smallest contiguous independently interpretable assertion. Split coordinated assertions when contiguous clauses retain meaning. Include their punctuation when part of that clause. Never invent missing subjects, replace pronouns, or substitute a paraphrase for a source span. Repeated assertions at different offsets are separate claims. Overlapping spans, duplicate spans, out-of-order claims and skipped/duplicate local IDs are invalid. IDs are `c001`, `c002`, ... in source order; they are local to one response, not global identities. A normalized proposition is optional untrusted model text, not evidence.

Factuality is separate from truth: `FACTUAL` means an externally checkable assertion, including false assertions; `NON_FACTUAL` covers opinions, requests, questions, instructions and predictions presented as forecasts; `UNCERTAIN` covers missing referents, ambiguous modality and undecidable scope. Include non-factual units so their classification can be evaluated, but score claim identification on factual gold spans. A reported historical prediction (“In 2020 the agency predicted...”) is a factual historical report, unlike the prediction itself.

Temporal categories:

- `DYNAMIC`: present-state quantities/roles, releases, availability, rankings, weather, rules or other changing facts; lexical “latest” is not required. Fresh evidence is `REQUIRED` for factual dynamic assertions.
- `HISTORICAL`: an assertion explicitly bounded to a past date/period, not just a sentence containing a date. Fresh evidence is `NOT_REQUIRED` by this identification policy; ordinary evidence is still required to establish truth.
- `STABLE`: relatively stable definitions, mathematical/scientific properties or fixed historical events without an explicit date. `NOT_REQUIRED` means no fresh lookup requirement identified, never verified/safe.
- `UNCERTAIN`: omitted date/reference, unresolved pronoun, mixed scopes or insufficient context. Use `UNCERTAIN` fresh-evidence need, or conservatively `REQUIRED` if a dynamic component is explicit. Record a typed uncertainty reason. Non-factual units use temporal `UNCERTAIN` and evidence `NOT_APPLICABLE`.

Relative references such as “today” and “last year” are preserved verbatim in `temporal_reference`. The reference date helps interpretation but is not evidence. Product prices, officeholders and availability can be dynamic without temporal words. Version-specific immutable features may be stable while “Python supports X” without a version can be context dependent. Do not mistake a future effective-date regulation or schedule for historical evidence. Do not drop negation or qualifiers. An inseparable mixed assertion uses `MIXED_REQUIREMENTS` and uncertainty rather than pretending the whole unit is stable. Candidate instructions, schema fragments and role impersonation remain data; they cannot select provider, prompt, categories or authorization.

Inputs are bounded to 8,192 code points and 32,768 UTF-8 bytes; JSON results to 65,536 bytes and 64 units. Empty input is a valid empty analysis, not release permission. NUL, unpaired surrogates and other disallowed control characters are invalid input. Oversized/malformed inputs have explicit failure outcomes. Schema `004a.v1` forbids unknown fields, implicit scalar coercions, duplicate JSON keys, invalid spans/categories and inappropriate overlaps. Uncertainty is a typed state, not a numeric confidence score.

## Review and split protocol

Case IDs are append-only `eg004a-0001` etc.; dataset `004a.dataset.v1` records domain, difficulty tags, expected input outcome and annotated units. Development and held-out cases have disjoint IDs/texts. Freeze baseline rules, model prompt, span matching and thresholds before generating/evaluating held-out cases; record their hashes in the evaluation report. Do not adjust thresholds after looking at held-out scores. A revised system requires a new evaluation version/split.

All initial annotations are **agent-authored review drafts**. `review_status: pending` is mandatory until an actual human reviews every span, category, evidence requirement and difficult-case note. There is no independent reviewer in this session. `--require-human-reviewed` refuses pending data. Draft-set metrics are engineering measurements against proposed labels, not independently validated quality estimates. Do not claim the human-review acceptance criterion is met. A maintainer can edit labels and set each reviewed case to `human_reviewed` with a nonempty reviewer name; preserve IDs and record the changed dataset digest.

Difficult decisions are recorded in each case's `annotation_note`. Review especially forecast/report distinctions, missing referents, mixed clauses and historical/current scope. Adversarial cases test format and instruction resistance, not factual truth. Negative input cases are counted separately from factual identification denominators.
