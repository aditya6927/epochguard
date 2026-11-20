# 005J — Diagnose Gemini output validation

## Observation and limits

Baseline: `6a79ffcc1fa0290412382e34f63ae4f930b1c6bf`. Implementation checks ran November 20, 2026, Asia/Calcutta.

The maintainer reported five valid Tavily results followed by `INVALID_MODEL_OUTPUT` in the first live Explorer assessment. The inspected 005I code used that reason for incomplete finishes, malformed model envelopes, invalid structured JSON/schema and four subsequent binding checks. It therefore cannot identify the historical cause. Under that code, the broad error occurs after the model HTTP request and outer JSON parsing succeeded; this does not establish a complete or valid structured answer. No finish/usage record from that live response was available for review. No raw response, original claim, excerpt or private credential/settings file was collected to reconstruct it, and no live request was repeated.

## Diagnostic contract

All eight categories return the same compatible Result fields, INSUFFICIENT_EVIDENCE and `authorization=false`. Only the existing free-form `reason_code` value becomes more specific. Successful assessments, strict schemas, complete source coverage, exact original-claim/quotation binding, corroboration, budgets, deadlines and provider-error handling retain their previous behavior.

| Reason | Meaning |
| --- | --- |
| `MODEL_FINISH_INCOMPLETE` | Present non-STOP finish, including MAX_TOKENS and safety termination |
| `MODEL_ENVELOPE_INVALID` | Invalid outer JSON/size/encoding, absent or ambiguous candidate, unsupported parts/role/annotations or invalid required usage fields |
| `MODEL_JSON_INVALID` | Invalid structured-answer JSON, duplicate keys, nonfinite constants or inner size/encoding failure |
| `MODEL_SCHEMA_INVALID` | Parsed answer violates the strict local model schema |
| `MODEL_CLAIM_MISMATCH` | Original claim was changed, including whitespace |
| `MODEL_SOURCE_COVERAGE` | Assessed source IDs do not exactly cover the retrieved set once each |
| `MODEL_CITATION_BINDING` | Repeated or unretrieved citation IDs |
| `MODEL_QUOTATION_BINDING` | Quotation is not an exact snippet substring or a decisive quotation is too short |

A schema-invalid source ID can fail at MODEL_SCHEMA_INVALID before coverage is tested; a well-typed but missing/unretrieved source fails at MODEL_SOURCE_COVERAGE. Categories identify the first failed check, not every defect. Provider HTTP errors and timeouts keep their existing distinct reasons. No retries, JSON repair, quote normalization, field dropping or partial assessment are introduced.

`ModelDiagnostics` captures immutable per-response metadata and travels alongside the parsed record to the pipeline. It is not a shared "last response" variable. Each validation failure emits one warning through `epochguard.experimental.model_validation`, with schema `005j.model-validation.v1`:

- Fixed event/category and allowlisted finish reason; unknown/missing values become UNKNOWN/MISSING.
- At most five fixed token-count fields, accepting only integers from 0 through 2³¹−1; missing/invalid values are omitted, never inferred as zero.
- Configured output cap, validated source count, and at most eight schema paths with bounded depth/indices. Arbitrary extra-field names become `[unknown]`.

No claims, snippets, URLs, model JSON, signatures, keys, provider error text, Pydantic messages/inputs/contexts or tracebacks are passed to this logger. Unknown finish strings and field names cannot smuggle content into diagnostics. Logging-sink failure cannot change the refusal. Structural metadata is untrusted provider telemetry, not factual evidence, independent origin proof or billing attestation. No new browser field, route or diagnostic export endpoint exists. See the [operator log procedure](../services/evidence_assessment/README.md#model-validation-diagnostics).

The native plugin, protected ingress, deterministic evidence policies, grammar, receipts, Gemini gateway adapter and shared claim analyzer are untouched. The Explorer's Result/model schema, prompt, settings defaults, live guards and cost-admission code are also unchanged. These diagnostics do not enlarge protected authorization or factual scope.

## Output-token investigation

`tests/evidence_assessment/output_budget.py` measures serialized JSON sizes without a tokenizer, provider credentials or API calls. Every constructed record passes the unchanged local model schema and existing 16,384-byte inner JSON bound. The maximal-fields example measures schema capacity only; it is not a factual or semantically verified response.

| Offline record | Compact characters/UTF-8 bytes | Pretty JSON characters | Rough compact tokens at 4 characters/token |
| --- | --- | --- | --- |
| Four existing conclusive two-source fixtures | 589–659 | 714–784 | 148–165 |
| Compact five-source assessment | 907 | 1,149 | 227 |
| Five sources at maximum string/list field lengths | 5,765 | 6,027 | 1,442 |

Character counts are exact measurements; the last column is only Google's [rough English token heuristic](https://ai.google.dev/gemini-api/docs/tokens), not actual Gemini tokenization. JSON punctuation, escaping, text content, formatting and reasoning can change the requirement. No `countTokens` call or new tokenizer dependency was used. The small fixtures show no structural requirement for more than 1536 tokens, but cannot establish that this cap accommodates real five-source generation. At the rough heuristic, even the maximal-fields visible output alone leaves little margin.

The [generateContent reference](https://ai.google.dev/api/generate-content) distinguishes candidate/thought usage counts and defines MAX_TOKENS as reaching the requested limit. Google's [Gemini thinking guidance](https://firebase.google.com/docs/ai-logic/thinking) also explains that thinking can leave less output capacity for the final answer. No actual thinking allocation for the reported request was measured. Current documentation about other APIs/models must not be treated as a measurement of this particular generateContent run.

Recommendation: **retain the existing 1536 default until diagnostic evidence is available**. If a future separately authorized assessment records MAX_TOKENS, consider 3072 as a bounded experimental setting within the existing 4096 ceiling, after checking the model and request/run cost admission. This doubles the output reservation; the extra planned output cost is `1536 × configured output USD-per-million / 1,000,000`. It is not a proven sufficient cap. If finish is STOP with schema or binding failure, increasing tokens is not supported by that evidence; inspect the safe field/category instead. No private setting, default, prompt or thinking configuration was automatically changed, and no follow-up request is authorized by this recommendation.

## Tests and artifacts

| Executed command or check | Result |
| --- | --- |
| `.venv-003a/Scripts/python.exe -B -m pytest services/evidence_assessment/tests tests/evidence_assessment/test_explorer_manage.py -q --tb=short`, with both service import paths | **133 passed**, including 37 new diagnostic regressions |
| `docker build --progress=plain -t epochguard-explorer:005j -f services/evidence_assessment/Dockerfile .` | **127 service tests passed** in its network-disabled test stage |
| `docker build --progress=plain --target python -t epochguard-checks:005j-python -f dev/Dockerfile.checks .` | **1,352 passed**, 1 deselected, existing Starlette/httpx deprecation warning; separate 6 Explorer lifecycle, 7 Lab lifecycle and 2 documentation-tool tests passed |
| Frozen evaluator inside `docker run --rm --network none --read-only`, checkout read-only at `/src`, 005J artifacts writable at `/output`, working directory `/src`; command `python -B tests/evidence_assessment/evaluate.py /output/offline-packet` | **19/19** expectations; unchanged **16 search / 11 model simulated invocations** |
| Same network-disabled container setup, command `python -B tests/evidence_assessment/output_budget.py /output/output-size-offline` | Six schema-valid structural measurements, **zero provider requests** |
| Network-disabled Explorer image: construct `uvicorn.Config` with the actual `log_level='critical'`, then check the custom logger's `isEnabledFor(logging.WARNING)` | Passed; Uvicorn's configured level does not suppress this separate diagnostic logger |
| `.venv-003a/Scripts/python.exe -B scripts/check_docs.py`, documentation-tool unittest discovery, `git diff --check` | 57 Markdown files, 362 local links, 63 anchor links and 46 repository paths validated; 2 tool tests passed; whitespace check passed |

New tests exercise every category, MAX_TOKENS and safety finishes, malformed/duplicate/nonfinite JSON, scalar JSON, schema errors, altered claims, missing/extra/repeated source coverage, repeated/unretrieved citations, mismatched/short quotes, malformed/ambiguous envelopes, log redaction, bounds, sink failure, concurrent isolation, unchanged success and HTTP response fields. Five-source controls accept a complete simulated record and refuse missing fifth-source coverage, bad citations, mismatched quotations and incomplete finish. Mocked usage counters are explicitly synthetic, not observations of the live failure.

The full Python selection retains existing verifier/grammar/receipt/reporting, claim-analysis, source-transport mock and model/combined/variable-evidence regressions. Go tests and a new actual protected-gateway qualification were not rerun: those components and their contracts were not changed. No hosted CI, live model accuracy, live source health or paid-service qualification is claimed.

The frozen 005I packet and its SHA-256 remain unchanged. Current tests/evaluator explicitly refine only its three former broad errors by case ID: injected fields → schema, forged citation → citation binding, forged quotation → quotation binding. All assessments, invocation counts and other expectations remain exact. New reports mark `reason_taxonomy=005j.v1`; old reports and artifacts retain their original labels.

New ignored artifacts are under `artifacts/005j/`: focused test logs, `build-explorer-final.log`, `checks-python-final.log`, `packet-run.log`, `offline-packet/report.json`, `output-size-offline/report.json` and size-run logs. The packet implementation digest is `ecec0d6b7b7bf9110456a7f794582bb383798b9f32a8c29d29db5169463dabd7`. Its diagnostic warning lines contain structural metadata only. Final local immutable image IDs:

- Explorer: `sha256:977290cc4ca2c416dfda9a31b04e07c78ed5f9c4431b67bff6e66dd650999a3b`.
- Python checks: `sha256:e12b07ede7a1b19d375cf9aea37a0f0eab6aebb6105bda8010e1c7b88b79c39d`.

Temporary Docker runners used `--rm`; no containers remained for these isolated images. No new service project, published port, network, signing volume or credential mount was created. The operator's existing Explorer was not started, stopped or restarted. Public API documentation browsing was separate from development execution; no Gemini/Tavily API submission occurred.

## Changed files

- Backend: `services/evidence_assessment/evidence_assessment/providers.py`, `pipeline.py`, new `diagnostics.py`.
- Regression expectations/tests: `services/evidence_assessment/tests/test_experimental_assessment.py`, `test_assessment_boundaries.py`, new `test_model_diagnostics.py`.
- Offline evidence tools: `tests/evidence_assessment/evaluate.py`, new `output_budget.py`.
- Documentation: service README, packet README, architecture, security, operations and this report.

The historical cause remains unclassified. The implemented diagnostics make a future authorized failure distinguishable while preserving abstention. No response metadata or synthetic passing test establishes general factual accuracy, prompt-injection immunity or source independence.
