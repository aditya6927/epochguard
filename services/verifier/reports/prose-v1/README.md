# 004F offline draft-label measurements

All four JSON reports use the separate frozen 66-case collection (33 per split).
No Gemini, Tavily or PyPI request was made to generate these four offline reports. Every annotation remains a draft;
**MODEL QUALITY QUALIFICATION PENDING**. These are research diagnostics, not
production reliability or evidence that general prose completeness is proven.

| Extractor + audit | Split | Claim P/R/F1 | Exact-span P/R | Fresh P/R | Dynamic omitted / nonfresh | False complete | Unaccounted risk units | Extraction failures |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Existing 004A baseline | dev | .735 / .893 / .806 | .706 / .857 | .704 / .760 | 3 / 3 | 0 / 33 | 23 | 2 |
| Existing 004A baseline | heldout | .686 / .923 / .787 | .629 / .846 | .741 / .870 | 2 / 1 | 0 / 33 | 21 | 0 |
| Independent closed-form auditor | dev | 1.000 / .429 / .600 | 1.000 / .429 | 1.000 / .480 | 13 / 0 | 0 / 33 | 29 | 1 |
| Independent closed-form auditor | heldout | 1.000 / .500 / .667 | 1.000 / .500 | 1.000 / .565 | 10 / 0 | 0 / 33 | 26 | 0 |

Baseline + audit produces PLAN_READY on 7 dev/6 held-out responses; the independent
auditor on 8/8. Both abstain or fail on all 25 negative/ambiguous cases in each
split. Correct nonfailure abstentions are baseline 23/25 dev, 25/25 heldout;
auditor 24/25 dev, 25/25 heldout. Failures remain in denominators. All reports
record zero unsupported/wrong policy-version mappings on these draft cases.

The baseline fails `eg004f-0035` (repeated identical text) and `eg004f-0041`
(repeated code-fence quote); the auditor fails `eg004f-0035`. This conservatively
preserves global-unique alignment. Empty `false_complete_cases` arrays mean no
such error was observed on this collection; they are not completeness proofs.
Focused deliberately unsafe scoring controls demonstrate nonzero false-complete
and wrong-mapping detection instead of allowing an always-zero metric.

`extractor_only` metrics describe proposals and have no complete-coverage
decision (`false_complete_count=null`). `combined_extractor_and_auditor` reports
the selected engine with the independent audit. `independent_auditor` provides a
separate closed-form comparison. Real-model and combined model/audit scores are
not available in these four offline reports; scripted fake output is adapter testing only.

Default offline reports omit latency, tokens and cost rather than inventing
measurements. `--measure` enables actual local analysis timing. A separately
authorized Gemini diagnostic records attempted calls/reservations, measured
latency and the subset with reported usage, including usage retained before a
later alignment/schema failure. Unknown usage is not refunded or fabricated.

Each report includes selected IDs, source/dataset/manifest and implementation
hashes, original 004A prompt/schema provenance, all planning records and failure
metadata. Re-run the documented CLI with the same unmodified sources/data to
reproduce default reports byte-for-byte. See [Task 004F](../../../../docs/task-004f.md).

A later ten-call Gemini diagnostic is operator-reported against draft labels, separate from these deterministic reports. It is not an independently qualified benchmark; no additional diagnostic metrics or general quality guarantee is asserted here. See the [draft review protocol](../../data/prose-v1/README.md).
