# Task 004A — Time-sensitive claim identification and evaluation

Follow-up: [Task 004A-H](task-004a-hardening.md) records contract-parser, sanitized-diagnostic, baseline lexical and schema-byte hardening. Schema file hashes below now refer to normalized LF bytes stored in Git; earlier CRLF hashes are preserved in that report. Historical evaluation results remain unchanged.

Implemented November 8–9, 2026 as a **stand-alone experiment**, outside the qualified gateway. The offline implementation and regressions are complete for review. **Full acceptance is pending independent human annotation review and real-model performance qualification.** No paid model or Tavily call was made, and no model-quality improvement is claimed. The evaluation reference date remains fixed to November 8 across the local date rollover.

## Scope and contract

The existing `003a.v1` API still checks one exact Python-release sentence. Its request/hash binding, primary-label comparison, fail-closed enforcement, cancellation, no-answer-leak and terminal-fallback semantics remain unchanged. The route boundaries documented in [Task 003C](task-003c.md) remain unchanged too. Nothing in the new package is imported by FastAPI, Go or a Compose production/development verification default.

The new [package](../services/claim_analysis/README.md) accepts ordinary response text plus an explicit reference date. It emits schema `004a.v1`, defined in [schema.py](../services/claim_analysis/claim_analysis/schema.py) and its [versioned JSON Schema](../services/claim_analysis/schema-004a.v1.json). The schema and [annotation rules](../services/claim_analysis/ANNOTATION.md) were written before the extraction pipeline.

Each unit contains a response-local sequential `claim_id`, verbatim `source_text`, `start`/`end`, optional untrusted `normalized_proposition`, `factuality`, `temporal`, `fresh_evidence`, typed uncertainty reasons, and an optional verbatim `temporal_reference`. The version is on the containing extraction. IDs are not durable identities across edits.

Offsets use **Python Unicode code-point indices**, start inclusive/end exclusive, on the original text. There is no Unicode normalization or model-output offset repair. `text[start:end] == source_text` must hold; spans must be in source order and nonoverlapping. Repeated text at distinct positions is allowed, repeated/overlapping spans and IDs are rejected. A model paraphrase cannot substitute for the original span. UTF-8 byte offsets and JavaScript UTF-16 offsets are invalid when they do not point to the exact substring.

| Dimension | Values and meaning |
| --- | --- |
| Factuality | `FACTUAL`: externally checkable assertion, not necessarily true; `NON_FACTUAL`: opinion/question/instruction/prediction; `UNCERTAIN`: insufficient context or ambiguous assertion |
| Temporal scope | `DYNAMIC`, explicitly past-bounded `HISTORICAL`, relatively `STABLE`, or `UNCERTAIN` |
| Fresh evidence | `REQUIRED`, `NOT_REQUIRED`, `UNCERTAIN`, `NOT_APPLICABLE`; factual dynamic assertions require fresh evidence |
| Uncertainty | Typed reasons such as `MISSING_CONTEXT`, `AMBIGUOUS_REFERENCE`, `MIXED_REQUIREMENTS`, `MODEL_ABSTENTION`, `UNTRUSTED_INSTRUCTION`, and baseline provenance |

NON_FACTUAL uses temporal UNCERTAIN/evidence NOT_APPLICABLE. Uncertain temporal classification cannot waive fresh evidence. Inseparable mixed factual scopes should remain uncertain, requiring evidence when a changing component is identified. Historical/stable classification **does not verify truth or authorize release**. There is no truth, ALLOW or release-verdict field. CLI output explicitly states `authorization: false`.

## Implementation and trust boundaries

```text
Text + explicit reference date
  -> strict input bounds
  -> sentence/lexicon baseline OR original-text model extraction
  -> strict JSON/category/source-span validation
  -> analysis / explicit analysis failure
  -> offline evaluation and review; no gateway connection
```

[baseline.py](../services/claim_analysis/claim_analysis/baseline.py) is intentionally a sentence benchmark. It recognizes explicit temporal words, dates and small domain lexicons, preserves spans and abstains on unresolved scope. It does not split coordinated clauses reliably or identify arbitrary implicit changing facts. A positive dynamic signal takes precedence over stable lexicon matches; detected historical/current mixtures require fresh evidence. An unrecognized component or an opinion/instruction mixed with a fact can still cause a dangerous omission. The measured baseline is unsuitable for response authorization.

[model.py](../services/claim_analysis/claim_analysis/model.py) defines a small asynchronous provider interface, strict extraction adapter, typed safe failure codes, prompt version and fixed-output fake. The real model receives **the complete original response**, not regex-selected claims, along with rules for atomic spans, implicit dynamic facts, historical scope, predictions, uncertainty and injection resistance. It must perform substantive extraction/classification. Format/span validation does not prove that its semantic classifications or coverage are correct. Numeric self-reported confidence is neither requested nor accepted.

[gemini.py](../services/claim_analysis/claim_analysis/gemini.py) implements an actual Gemini REST adapter using existing `httpx`, a fixed HTTPS API host and an operator-selected `gemini-...` model. Candidate text is JSON data in the user message; it cannot choose endpoint, tools, model, prompt or budgets. No tools, browsing, fallback extractor, automatic retry or JSON repair is enabled. The documented [GenerateContent API](https://ai.google.dev/api/generate-content) and [structured-output guidance](https://ai.google.dev/gemini-api/docs/structured-output) informed request construction. The JSON Schema is reduced to the API-supported subset for generation; complete strict validation remains local. Compatibility with a particular paid model is **not qualified without a real run**.

Trusted configuration requires `EPOCHGUARD_ALLOW_MODEL_CALLS=1`, `GEMINI_API_KEY`, explicit model and operator-supplied input/output rates. No credential or opt-in was present in this session. The CLI never logs a key, request headers or raw provider error bodies. Redirects and environment proxies are disabled. Provider failures, blocked/truncated generation, timeout, malformed JSON, duplicate keys, extra fields, invented source text, bad spans/categories and invalid usage become explicit analysis failures. Cancellation propagates rather than producing success. Empty input yields empty analysis without a call; a nonempty model response with no identified units is treated as a failure.

Bounds are 8,192 input code points, 32,768 UTF-8 bytes, 65,536 result/provider-envelope bytes and 64 units. NUL/disallowed controls/unpaired surrogates fail validation. A total model deadline defaults to 30 seconds and validates 0.1–60; output defaults to 4,096 tokens, bounded 128–8,192; request count is 1–100, default 1. Per-request and entire-run cost admission use finite operator rates, a pessimistic prompt-byte planning estimate and the output token limit. Failed/cancelled attempts retain their reservations. These are **planning guards, not a provider billing guarantee**; use provider-side spending controls. Usage/cost is null when unknown and successful reported totals include thought tokens. Failed outputs may incur costs not available in a successful-analysis usage record; reserved planning cost and attempted requests are reported separately.

## Dataset integrity and review status

[Dataset v1](../services/claim_analysis/data/v1/) contains **112 response examples, 184 factual annotations**, 60 development and 52 held-out cases. There are 105 development factual annotations and 79 held-out factual annotations. Held-out includes 47 nonempty valid responses, two valid empty/whitespace responses and three invalid-input examples. The full set covers software, finance, sports, weather/travel, policy, science/history, products and mixed answers. Tags cover coordinated claims, implicit time dependence, historical/relative/future dates, numbers, qualifiers/negation, pronouns, predictions, questions, injection, repetition, Unicode and invalid/oversized text. Reference date is fixed to **2026-11-08**.

These are **agent-authored synthetic draft annotations**, not independently verified facts or human-reviewed gold. No human reviewer was available during implementation. Every case records `review_status: pending`, a null reviewer and a labeling note. The loader rejects an assertion of human review without a named reviewer; `--require-human-reviewed` refuses the current dataset. It cannot prove that a reviewer actually did the work: the review process remains a maintainer responsibility. Human review of every label/span is still required to meet the task's dataset-integrity criterion.

[build_v1.py](../services/claim_analysis/data/build_v1.py) preserves the explicitly authored unit/label specifications and constructs their literal offsets; it is not an extraction algorithm. Do not run it over later human edits. IDs are stable/append-only, with disjoint split IDs and texts. The held-out examples were authored after baseline rules and model prompt were implemented; those rules/prompt were not tuned from held-out outcomes. Dataset/prompt/implementation hashes are embedded in each report. This separation controls engineering iteration but does not make an author-created draft an independently held-out human benchmark.

Difficult labels requiring particular review include: version-specific immutable features versus unspecified software capabilities; past-tense assertions without a date; a historical report of a forecast versus the forecast itself; claims about future schedules/regulations; and atomic clauses that depend on a shared subject. An unresolved historical reference must not be silently rewritten as a present fact. Adding fresh evidence is a future operation, not something these annotations establish.

## Evaluation methodology

[evaluation.py](../services/claim_analysis/claim_analysis/evaluation.py) uses frozen, deterministic **character-span IoU ≥ 0.5**, greedy highest overlap first, then gold/prediction index ties, one-to-one. There is no fractional credit. A large sentence can match at most one annotated assertion; a partial overlap below the threshold counts as both FP and FN. Exact-span metrics use IoU 1.0 and are reported separately. The method can still credit a broader-than-atomic span; it is not semantic entailment matching.

Claim precision/recall/F1 uses FACTUAL gold and FACTUAL predictions. Non-factual and uncertain statements remain in the analyses but do not become factual true positives. Fresh-evidence precision/recall separately matches units marked REQUIRED, including conservative uncertain-factual predictions. This prevents a classification abstention from erasing a positive fresh-evidence request.

Temporal accuracy is reported both among matched factual claims and end to end over all factual gold. Macro-F1 uses the four fixed temporal categories; absent classes contribute zero. Missing gold predictions count as false negatives, spurious predictions as false positives. Fixed categories make sparse subgroup macro-F1 values low even when a group contains only dynamic facts; consult counts/confusion matrices. All invalid input outcomes are checked separately from factual identification denominators. Failed analyses on valid responses contribute omissions rather than disappearing from evaluation.

The report exposes dynamic omissions, dynamic facts mislabeled stable/historical, matched dynamic facts left uncertain, full confusion counts, error examples, uncertainty rate and per-response failures. Mixed groups include `mixed`, `multi_claim`, `mixed_scope`; adversarial groups use the explicit tag and include empty/invalid controls. Latency is per-response local processing including validation, not startup or a production benchmark. Token/cost totals are reported only when provided; fake and baseline runs have no measured model usage.

## Measured results — draft labels only

Actual baseline outputs are committed as [development JSON](../services/claim_analysis/reports/baseline-dev.json), [held-out JSON](../services/claim_analysis/reports/baseline-heldout.json) and adjacent text summaries. No real-model comparison table is manufactured.

| Metric | Development | Held-out |
| --- | --- | --- |
| Factual gold / predicted / matches | 105 / 106 / 103 | 79 / 79 / 72 |
| Claim precision / recall / F1 | 0.972 / 0.981 / 0.976 | **0.911 / 0.911 / 0.911** |
| Exact-span F1 | See JSON report | **0.861** |
| Temporal matched accuracy | 0.825 | **0.417** |
| Temporal end-to-end accuracy | 0.810 | **0.380** |
| Temporal macro-F1 | 0.677 | **0.522** |
| Fresh-evidence precision / recall | 0.966 / 0.824 | **0.812 / 0.232** |
| REQUIRED gold / matched fresh requests | 68 / 56 | **56 / 13** |
| Dynamic omissions / mislabeled stable or historical | 1 / 0 | **6 / 0** |
| Matched dynamic facts left uncertain | 11 | **37** |
| Unit uncertainty rate | 0.179 | **0.533** |

| Held-out subgroup | Responses | Claim P / R / F1 | Fresh P / R | Dynamic omissions |
| --- | --- | --- | --- | --- |
| Mixed | 11 | 0.889 / 0.727 / 0.800 | 0.667 / **0.143** | 5 |
| Adversarial | 8 | 0.667 / 0.667 / 0.667 | 0.667 / 0.667 | 1 |

There are zero analysis/input-outcome failures in the baseline run, but that does **not** mean the classifications are correct. The held-out run misses **43 of 56 required fresh-evidence requests**. Of 55 dynamic gold assertions, only 12 receive the correct dynamic classification; 37 matched assertions remain uncertain and six are omitted/not identified as factual. The high claim F1 conceals poor temporal understanding if read alone.

Measured baseline median/max local latency was 0.0556/0.2200ms on development and 0.0338/0.3307ms on held-out in this Windows Python 3.12 environment. These tiny synthetic responses say nothing about gateway or model latency. No model tokens, model latency or paid cost were measured. No fake-adapter F1 is presented as model performance.

Failure examples retained in the JSON reports:

- `eg004a-0066`, “Cobalt has 700 employees.”: sentence identified, but changing employee count is UNCERTAIN instead of DYNAMIC; no positive fresh-evidence request.
- `eg004a-0068`, “The fund holds 15 assets” plus a stable percentage clause: one broad sentence cannot match both atomic annotations; the dynamic clause is omitted by the factual matching rule.
- `eg004a-0078`, ferry departure and pier closure in one sentence: both factual gold spans are missed under the fixed overlap threshold. This is a segmentation failure, not evidence that transport conditions are stable.
- `eg004a-0101`, injected JSON followed by “The tickets are sold out.”: naive sentence segmentation combines the JSON and factual sentence; the factual assertion is missed and a broad spurious unit can appear.
- Ambiguous context such as “The figure includes something else.” can be labeled FACTUAL/UNCERTAIN instead of uncertain factuality, contributing a factual false positive.
- Relative past assertions such as package withdrawal “last year” are not correctly historical merely because the baseline preserves a relative reference. No change to held-out matching or rules was made to improve these outcomes.

## Demonstrations and actual execution

Five [demo inputs](../services/claim_analysis/demos/) cover mixed stable/dynamic text, an ordinary old-version assertion, implicit changing coaching role, explicit 2018 history, and instructions plus ambiguous reference. Ten CLI commands (baseline and fake for each) executed successfully. `implicit` makes the baseline's missing semantic coverage visible: its output is uncertain while the **scripted** model-path fixture says dynamic. This is an expected-output illustration, not a measured LLM advantage. Mixed/version/history/adversarial examples illustrate spans and typed distinctions; none verifies the example's truth. See the [package instructions](../services/claim_analysis/README.md) for exact commands and opt-in credential handling.

Executed from repository root in PowerShell:

```powershell
$env:PYTHONPATH = 'services/claim_analysis'
& .venv-003a/Scripts/python.exe -m pytest -c services/claim_analysis/pytest.ini services/claim_analysis/tests -q
& .venv-003a/Scripts/python.exe -m claim_analysis evaluate --engine baseline --split dev --output services/claim_analysis/reports/baseline-dev.json
& .venv-003a/Scripts/python.exe -m claim_analysis evaluate --engine baseline --split heldout --output services/claim_analysis/reports/baseline-heldout.json
# Both following controls deliberately exit 2 without output authorizing release:
& .venv-003a/Scripts/python.exe -m claim_analysis evaluate --engine baseline --split heldout --require-human-reviewed --output artifacts/004a/review-gate.json
& .venv-003a/Scripts/python.exe -m claim_analysis analyze --engine gemini --text-file services/claim_analysis/demos/implicit.txt

$env:PYTHONPATH = 'services/verifier'
& .venv-003a/Scripts/python.exe -m pytest -c services/verifier/pytest.ini services/verifier/tests -q

docker compose --profile test up -d --force-recreate --wait provider gateway gateway-control gateway-reject gateway-unavailable
docker compose --profile test run --rm --no-deps smoke
docker compose --profile test down --remove-orphans
docker compose -f compose.verify.yaml run --rm verification-tests
docker compose -f compose.verify.yaml down --remove-orphans
docker compose -f compose.routes.yaml up -d --wait reject control warp-control warp-reject nolog
docker compose -f compose.routes.yaml run --rm --no-deps route-tests
docker compose -f compose.routes.yaml down --volumes --remove-orphans
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml up -d --wait gateway-supported
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml run --rm --no-deps verification-tests
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml down --remove-orphans
```

| Executed check | Actual result |
| --- | --- |
| New claim-analysis offline suite | **64 passed**, final rerun 0.60s; external sockets blocked except Windows asyncio loopback self-pipes; model HTTP uses MockTransport |
| Existing verifier policy suite | **41 passed, 1 live test deselected**, 3.17s; existing Starlette/httpx deprecation warning |
| Existing real gateway enforcement suite | **10 top-level, 35 subtests passed** |
| Existing offline real gateway/service verification | **8 top-level, 31 subtests passed**; live/long-profile skips explicit in short profile |
| Existing route audit | **4 top-level, 54 subtests passed** |
| Separate deterministic long-budget regression | **1 passed**, 12.70s; HTTP 200 after 12,683ms, provider delta 1, fixture retrieval delta 1 |
| Fresh pinned plugin unit/race execution | Passed with `-count=1`: unit 0.186s, race 1.220s; no race report |
| Review and model opt-in CLI negative controls | Expected exit 2; no paid call or successful classification |
| Ten demo CLI commands | All exited 0; fake outputs explicitly labeled, authorization false |
| Reproducibility and final checks | Repeated held-out run has identical non-latency metrics and dataset/source hashes; 66 relative links and code fences checked across six documents; changed/new text whitespace and JSON syntax passed; `git diff --check` exit 0 |
| Scope and cleanup | Exactly 37 files, all in the new package/four documentation files; qualified implementation/configuration files unchanged. All task-owned stacks removed; only the pre-existing BuildKit builder remains running |

Go tests used an ignored `artifacts/004a/Dockerfile.unit`: the existing `dev/Dockerfile` plus `FROM build AS qualification-unit`, plugin workdir, a public `go mod download && go mod verify` cache-restoration step, then a network-disabled RUN with cache mounts executing `go test -count=1 -mod=readonly -trimpath -v ./... && go test -count=1 -race -p=2 -mod=readonly -trimpath ./...`. Command: `docker buildx build --builder epochguard-002a --progress plain --target qualification-unit --no-cache-filter qualification-unit -f artifacts/004a/Dockerfile.unit .`. Existing gateway image `sha256:fbb0ae3ef47e6dc763c13d4ac543247db7fecac6a14e48194e9f7c289365ca49` was reused for unchanged native gateway suites.

Initial failures are retained, not hidden: blocking every socket connection interfered with Windows asyncio self-pipe creation (17 failures); permitting its loopback connection while keeping external sockets blocked corrected the test harness. An initial legacy gateway startup exited before the suite ran; recreating the stack made the unchanged suite pass. An initial fresh Go run with `--network=none` could not obtain missing public core/cache module zip files; restoring the dependency cache allowed subsequent network-disabled unit/race tests to run. No enforcement assertion was skipped or weakened to obtain passes. Logs remain ignored under `artifacts/004a/`; baseline reports and per-case predictions/errors are checked in under the new package.

## Limitations and next integration review

This implementation is not a complete stale-answer detector. The baseline is measurably weak on implicit/mixed temporal facts. Structured output, exact spans and a prompt do not prove model instruction resistance, coverage, classification accuracy or factual truth. Offline injection tests check separation and validation, not how a real model behaves under attack. Nonoverlapping contiguous spans also cannot naturally represent every shared-subject or discontinuous proposition. The draft set is small, synthetic and author-created; review, inter-annotator disagreement and a new independently curated holdout are needed before quality claims.

Real-model performance remains pending because no API credential/opt-in/quota was available. An implementation-level MockTransport pass is not a live API compatibility pass. No Tavily or model subscription is inferred to supply application quota. Once a maintainer reviews annotations and explicitly selects provider/model/rates/budgets, the CLI can produce a real held-out report including failures, usage and latency. Do not freeze a fake-adapter score as a model benchmark, tune against this holdout or relabel unknown evidence as a successful verdict.

Task 004B should first specify response-level coverage/aggregation and a new experimental service boundary, without silently expanding `003a.v1`. Every relevant factual assertion needs an explicitly supported evidence policy and source-bound parameters; a model paraphrase must not become a trusted policy input. Missing, uncertain, unsupported, contradicted or omitted claims must prevent whole-answer authorization. Stable/historical labels still need an ordinary evidence policy where truth matters. A verified Python version cannot authorize a neighboring unverified price, instruction or availability assertion. Review how claim omissions are detected before connecting this analyzer to enforcement. No Task 004B endpoint, cache, revalidation worker or aggregation implementation was added here.

Changed files (37 total), grouped by exact directory:

| Directory | Files |
| --- | --- |
| Root | `README.md`, `AGENTS.md` |
| `docs/` | `architecture.md`, `task-004a.md` |
| `services/claim_analysis/` | `ANNOTATION.md`, `README.md`, `pytest.ini`, `requirements.txt`, `schema-004a.v1.json` |
| `services/claim_analysis/claim_analysis/` | `__init__.py`, `__main__.py`, `baseline.py`, `cli.py`, `dataset.py`, `evaluation.py`, `gemini.py`, `model.py`, `schema.py` |
| `services/claim_analysis/data/` | `build_v1.py` |
| `services/claim_analysis/data/v1/` | `dev.jsonl`, `heldout.jsonl` |
| `services/claim_analysis/demos/` | `adversarial.txt`, `adversarial.fake.json`, `historical.txt`, `historical.fake.json`, `implicit.txt`, `implicit.fake.json`, `mixed.txt`, `mixed.fake.json`, `version.txt`, `version.fake.json` |
| `services/claim_analysis/reports/` | `baseline-dev.json`, `baseline-dev.txt`, `baseline-heldout.json`, `baseline-heldout.txt` |
| `services/claim_analysis/tests/` | `conftest.py`, `test_analysis.py` |

No existing Go/Python verifier implementation, Bifrost config, deployment file or enforcement assertion changed.

Recommended commit, not created: `feat(claims): add isolated temporal claim analysis and draft evaluation`. Stop for maintainer review with human-review/model-quality acceptance items explicitly pending.

## Gemini schema compatibility follow-up (2026-11-09)

The maintainer supplied the following `gemini-3.5-flash-lite` diagnostics: model listing, basic generation, generation settings without a schema, and minimal `responseJsonSchema` returned HTTP 200; the full EpochGuard generation schema returned HTTP 400 `INVALID_ARGUMENT`. These are maintainer observations, not live results from this session. They isolate the full generation schema as the suspect; they do not prove which individual constraint caused rejection.

Local reproduction confirmed these two bounds in the exact provider conversion:

```text
$.$defs.Claim.properties.uncertainty.maxItems = 6
$.properties.claims.maxItems = 64
```

Google's [structured-output documentation](https://ai.google.dev/gemini-api/docs/structured-output) lists `maxItems` as supported and warns that complex schemas may be rejected. The hypothesis is constrained-decoding complexity from the bounded/nested arrays, not a claim that `maxItems` is categorically unsupported. Schema size alone does not measure the decoder's state space. Credentialed comparison remains necessary.

The normal `provider_schema()` now omits **only those two maxItems entries** relative to the previous provider conversion. Required properties, enums, references, nullable branches, types and numeric bounds remain unchanged. `schema.py`, `model.py` and `schema-004a.v1.json` are untouched; all strict checks still run after generation, including the 64-claim/six-uncertainty caps, duplicate/overlapping spans, verbatim binding, typed categories and fail-closed analysis. Input/output/token bounds remain active even though generation no longer encodes array counts.

Canonical JSON here means sorted keys with compact separators, UTF-8:

| Artifact | Bytes / SHA-256 |
| --- | --- |
| Original provider schema | 1,483 bytes; `60c4fc533d2ed73aa922a140282f91fd0e854e34ebb2e230a688a825f17e8130` |
| Provider schema without maxItems | 1,456 bytes; `d556b807cadc5587af599f6b4afbcaee436874ecf5f85a0b58e3bece3343c5a7` |
| Unchanged strict JSON Schema, normalized LF file bytes | `4844a67557f27a96feca2a439d68cefd1a70724010f923bf3f135a45158d4986` |

The new `claim_analysis.schema_diagnostic` command exports both variants entirely offline and optionally compares them using the **same** `GeminiProvider` request, cost-reservation, timeout and output-parsing path. A small private generation-schema hook permits the diagnostic subclass to select a fixed local schema. A transport wrapper observes status only. The probe runs the unchanged `ModelExtractor`, so HTTP acceptance and valid strict extraction are separate report fields. It uses one fixed synthetic response, no evaluation labels, no model-listing requests and no candidate-supplied configuration.

Default live comparison is original versus `no_max_items`, at most two attempts, with the existing environment opt-in/key/model/rates plus explicit `--live`. Failed attempts consume existing reservations. Auth/rate/server errors, timeout or no observed HTTP status stop the experiment. There are no retries or automatic production fallback. Budget-denied attempts do not dispatch. Reports contain no raw provider output, error messages, request headers or credentials. HTTP 200 with invalid/truncated extraction is explicitly not a successful local analysis; it can still show that a schema was accepted by the API.

If array-bound removal is insufficient, explicitly selected diagnostic-only variants isolate one further factor relative to `no_max_items`: remove metadata titles, remove the remaining numeric bounds, replace two nullable string `anyOf` branches with equivalent type unions, or inline the nonrecursive Claim reference. No other production conversion is changed without live evidence and review. These experiments are available offline and credential-gated; remaining constraints have **not** been live-diagnosed in this session. If an alternative passes while `no_max_items` fails, the default remains unqualified and the command exits 1.

Executed commands and actual results:

```powershell
$env:PYTHONPATH = 'services/claim_analysis'
& .venv-003a/Scripts/python.exe -m pytest -c services/claim_analysis/pytest.ini services/claim_analysis/tests -q
& .venv-003a/Scripts/python.exe -m claim_analysis.schema_diagnostic --output artifacts/004a-gemini-schema/compare
& .venv-003a/Scripts/python.exe -m claim_analysis.schema_diagnostic --variants original no_max_items no_titles no_numeric_bounds nullable_type_union inline_refs --max-requests 6 --output artifacts/004a-gemini-schema/incremental
```

- Before edits: **64 existing tests passed**, 0.56s.
- After edits: **81 tests passed**, 0.59s: all original 64 and 17 added regressions. Tests cover exact original reproduction, minimal conversion diff, wire schema selection, strict count limits, 65-claim fail-closed behavior, isolated further variants, dry export, opt-in, shared budgets, no retries, safe status observation and HTTP-200/invalid-analysis distinction.
- Offline exports exited 0. Comparing pre-change export with the diagnostic's original schema gave exact equality. Removing exactly two entries gave exact equality with the normal adapter's changed schema. Every export reports `live_qualification_pending: true` and an empty live-results list.
- Final documentation/scope checks passed: 21 local links/anchors, balanced code fences, changed/new whitespace, exact five-file scope, unchanged strict-schema hash and `git diff --check` exit 0.
- No live diagnostic ran: neither a Gemini key nor the model-call environment opt-in was available. **API incompatibility is not claimed resolved.** MockTransport tests are not real Gemini results. Model quality, annotation review, evaluation metrics/labels, `003a.v1`, Bifrost and caching are unchanged. Historical baseline reports are preserved with their original implementation hashes, not rewritten as new measurements.

Exact credential-safe PowerShell qualification commands, including key/model/rates, the two-request cap and cleanup, are in the [package README](../services/claim_analysis/README.md#gemini-schema-compatibility-diagnostic). Success of the changed variant on the fixed input qualifies only that narrow API/local-parse route, not model extraction quality. Compare original and changed statuses to support or refute the maxItems hypothesis; if both now pass, the earlier cause remains unproven.

Follow-up files: `claim_analysis/gemini.py`, new `claim_analysis/schema_diagnostic.py` and `tests/test_schema_diagnostic.py` under `services/claim_analysis/`, package README and this report. No schema, policy, label, evaluation or deployment change was made. Recommended follow-up commit, not created: `fix(claims): simplify Gemini generation schema and add bounded diagnostics`. Stop for review pending credentialed qualification.

## Safe model validation diagnostics (2026-11-09)

Subsequent **maintainer-supplied live evidence** established original schema HTTP 400, reduced schema HTTP 200 with `INVALID_MODEL_ANALYSIS`, and a successful separate standalone extraction. Both paths use `ModelExtractor` but analyze different inputs in separate generations. The earlier generic failure does not reveal its exact rejected field. No new live request was made during this follow-up; the new metadata cannot recover details from a discarded previous output.

This change adds bounded diagnostic metadata without changing public failure codes, prompts, provider/model selection, generation schemas, validation acceptance, evaluation semantics or authorization. Existing uncommitted schema-conversion work was preserved. Neither the evaluation dataset nor the qualified gateway, `003a.v1`, caches or deployment defaults changed.

### Failure taxonomy

The legacy `AnalysisFailure` string/args remain the existing code, such as `INVALID_MODEL_ANALYSIS`, `MODEL_PROVIDER_FAILURE`, `MODEL_TIMEOUT` or `EMPTY_MODEL_ANALYSIS`. Its optional `diagnostic` attribute contains frozen metadata; the schema diagnostic serializes this as a new `failure_details` field. Existing HTTP acceptance, strict-validation results, counters and budgeting remain intact. Successful rows use null failure details. Normal analysis/evaluation CLI error output is unchanged.

| Diagnostic stage | Stable code examples / interpretation |
| --- | --- |
| `PROVIDER_TRANSPORT` | `TRANSPORT_FAILURE`, `TIMEOUT`, `UNEXPECTED_PROVIDER_FAILURE`; transport failure or unexpected provider adapter exception |
| `PROVIDER_HTTP` | `HTTP_FAILURE`; non-200 HTTP status, with no provider body included |
| `PROVIDER_ENVELOPE` | `ENVELOPE_INVALID`, `ENVELOPE_INCOMPLETE`, `ENVELOPE_CONTENT_INVALID`, `ENVELOPE_USAGE_INVALID`, JSON/size codes; outer API envelope or completion state failed |
| `MODEL_JSON` | `JSON_INVALID_OR_INCOMPLETE`, `JSON_DUPLICATE_KEY`, `JSON_NONFINITE_NUMBER`, `JSON_INVALID_ENCODING`, `OUTPUT_TOO_LARGE`; the model's structured text failed strict JSON handling |
| `MODEL_SCHEMA` | `SCHEMA_MISSING_FIELD`, `SCHEMA_EXTRA_FIELD`, `SCHEMA_LITERAL_INVALID`, `SCHEMA_TYPE_INVALID`, `SCHEMA_LIMIT`, `SCHEMA_CONSTRAINT`; Pydantic schema rejection |
| `MODEL_SCHEMA` cross-field rules | `CLAIM_DYNAMIC_REQUIRES_FRESH`, `CLAIM_NON_DYNAMIC_EVIDENCE`, `CLAIM_UNCERTAINTY_MISSING`, `CLAIM_NONFACTUAL_COMBINATION`, `CLAIM_UNCERTAIN_TEMPORAL_COMBINATION`, `CLAIM_EVIDENCE_NOT_APPLICABLE`, `CLAIM_REFERENCE_MISMATCH`, `CLAIM_SPAN_ORDER`, `CLAIM_DUPLICATE_UNCERTAINTY` |
| `SOURCE_BINDING` | `BINDING_ID_SEQUENCE`, `BINDING_OVERLAP`, `BINDING_RANGE`, `BINDING_TEXT_MISMATCH`; binding to the actual original response failed |
| `EMPTY_ANALYSIS` | `EMPTY_MODEL_ANALYSIS`; nonempty input generated no extracted units |
| `CONTROL` | `BUDGET_EXCEEDED`, `NOT_ENABLED`, `INVALID_CONFIGURATION`; trusted process configuration or existing budget guard |

Unknown Pydantic error types map to `SCHEMA_INVALID`; arbitrary type/message strings are never copied. Some cross-field failures correctly point to the claim itself instead of implying that one field alone is wrong. Transport versus outer-envelope versus inner-model JSON failures are distinguished by where validation failed, not by inspecting untrusted error messages.

Illustrative **offline fixture**, not a diagnosis of the earlier live generation:

```json
{
  "http_status": 200,
  "http_accepted": true,
  "strict_analysis_valid": false,
  "failure_code": "INVALID_MODEL_ANALYSIS",
  "failure_details": {
    "stage": "SOURCE_BINDING",
    "errors": [{"code": "BINDING_RANGE", "field_path": "$.claims[0].end"}],
    "error_count": 1,
    "truncated": false
  }
}
```

Here the request was accepted, but a span end exceeded the original response length. The report contains neither the offending offset nor the response text. A `MODEL_SCHEMA` / `CLAIM_DYNAMIC_REQUIRES_FRESH` result would instead identify a temporal/evidence cross-field violation. A `MODEL_JSON` result identifies JSON parsing rather than span binding. None means a verified answer.

### Implementation and non-disclosure boundary

`validation_diagnostics.py` defines allowlisted stages/codes, path sanitization, bounded serialization and typed JSON/binding failures. `schema.py` preserves every condition and bound while assigning typed constant errors at existing rejection sites. Pydantic cross-field validators use constant `PydanticCustomError` types, so no exception-message parsing is needed. Binding exceptions remain `ValueError` subclasses. The generated `schema-004a.v1.json` is byte-for-byte unchanged, and existing strict-validation tests remain passing.

`model.py` attaches metadata at JSON, Pydantic, binding and empty-analysis failures while keeping the legacy public code. Provider errors preserve their existing public codes and cancellation still propagates. `gemini.py` tags HTTP, transport and envelope failures, keeping model configuration, body/token/deadline limits, opt-in and attempt/cost reservations unchanged. `schema_diagnostic.py` adds only the sanitized metadata to its rows; no raw model output or provider error body is added to the report.

Pydantic errors are requested with `include_input=False`, `include_context=False`, `include_url=False`. Only mapped types and sanitized locations are retained, never `msg` or arbitrary error types. Unknown field names become `<unknown>`; numeric indices must be 0–63, otherwise `[*]`. Paths are bounded to six components and 192 characters. Metadata retains at most four issues; serialized error counts cap at 64 and `truncated` signals omitted detail. Unknown raw path tokens are sanitized before storage in diagnostic objects. Candidate/source strings, normalized propositions, API keys, headers, provider error bodies and arbitrary exception messages never become diagnostic fields.

This is reporting only: no output repair, retry, permissive JSON parser, fallback extractor or partial acceptance was introduced. Strict failures still produce no analysis result, and valid analysis results are unchanged. Diagnostics never feed back into classification, policy or release authorization.

### Executed tests and rerun command

Executed from repository root in PowerShell:

```powershell
$env:PYTHONPATH = 'services/claim_analysis'
& .venv-003a/Scripts/python.exe -m pytest -c services/claim_analysis/pytest.ini services/claim_analysis/tests -q
```

- Before changes: **81 existing tests passed**, 1.94s.
- After implementation, before new tests: **81 existing tests passed**, 0.74s.
- With new regressions: **116 tests passed**, 1.08s: all existing 81 plus 35 added cases. Tests cover spans/overlap/IDs, missing required and unsupported fields, invalid temporal/evidence combinations, malformed/duplicate/nonfinite JSON, encoding/size limits, empty analyses, bounded paths/counts, unknown error types, secret/candidate non-disclosure, provider transport/HTTP/envelope stages, legacy codes, valid responses and diagnostic report results.
- Offline non-disclosure tests inject a private sentinel into candidates, unknown keys, invalid values, provider bodies and arbitrary exception messages, and assert that it appears in neither serialized metadata nor diagnostic object representations. HTTP uses MockTransport; external sockets remain blocked by the existing test guard.
- Logs are retained under ignored `artifacts/004a-validation-diagnostics/`. No paid/model/Tavily call, gateway deployment or live qualification was performed during this change.
- Offline reduced-schema export and a MockTransport HTTP-200/binding-failure example exited 0; the latter produced `SOURCE_BINDING` / `BINDING_RANGE` at `$.claims[0].end` with no source text. Final checks verified unchanged dataset hashes, prompt, strict schema, generation schemas and earlier diagnostic tests; 22 local links/anchors, code fences, changed/new whitespace, exact combined nine-file scope (including earlier uncommitted work), and `git diff --check` passed.

After configuring the existing trusted Gemini key/model/rates and explicit model-call opt-in as shown in the [package README](../services/claim_analysis/README.md#gemini-schema-compatibility-diagnostic), repeat only the reduced variant:

```powershell
$env:PYTHONPATH = 'services/claim_analysis'
& .\.venv-003a\Scripts\python.exe -m claim_analysis.schema_diagnostic --live --variants no_max_items --max-requests 1 --output artifacts/004a-validation-diagnostics/live-reduced
```

This makes at most one model call and writes a fresh `report.json`. Read `failure_details.stage`, then each error's code and sanitized path. The invocation still requires the key, `EPOCHGUARD_ALLOW_MODEL_CALLS=1`, an explicitly selected model and configured rates; existing timeout/output/cost guards apply. It does not retry a failed generation or rerun a dataset. A new generation can differ from the old one, so a new success would not identify the previous failure retrospectively. The live failure's exact category remains unknown until observed safely in a fresh failing run.

Changed in this follow-up: `model.py`, `schema.py`, `gemini.py`, `schema_diagnostic.py`, new `validation_diagnostics.py` and `tests/test_validation_diagnostics.py` under `services/claim_analysis/`, package README and this report. Earlier schema-diagnostic changes and tests remain preserved. Recommended commit, not created: `feat(claims): add sanitized model validation diagnostics`. Stop for maintainer review without committing or pushing.

## Evaluation report diagnostics (2026-11-09)

The maintainer reported seven `INVALID_MODEL_ANALYSIS` records in a ten-case Gemini development evaluation while the baseline completed all ten without analysis failures. Those outcomes alone neither identify the rejected fields nor establish better baseline classification quality. This follow-up exposes the already-available sanitized metadata in evaluation records; no new live call was made.

The implementation change is confined to `claim_analysis/cli.py`: initialize `failure_details` to null for each case, copy `failure.diagnostic.to_dict()` when catching an `AnalysisFailure` with diagnostics, and include that value in the existing record. No exception messages, Pydantic errors, candidate text, model output, credentials or provider bodies are parsed or copied into this field. The same sanitizer already used by the schema diagnostic supplies stages, allowlisted codes/paths, at most four issues, a count capped at 64, and a truncation flag.

`reason`, `status`, `extraction`, usage, metrics, summaries and the `004a.evaluation.v1` report structure remain as before, with this additive per-record key. Failed model records retain `extraction: null`. Successful records and failures without metadata use `failure_details: null`. Existing validated-extraction spans and gold metric examples remain unchanged; no new raw-text logging is added. The field is informational and never changes scoring or authorizes delivery. All validation rules, prompts, schema constraints, Gemini settings, labels, gateway enforcement, `003a.v1` and caching remain unchanged. Historical reports retain their old data and implementation hashes.

For example, a failure can retain `reason: INVALID_MODEL_ANALYSIS` while its details say `MODEL_JSON` / `JSON_INVALID_OR_INCOMPLETE`, `MODEL_SCHEMA` / `SCHEMA_MISSING_FIELD` at `$.claims[0].temporal`, or `SOURCE_BINDING` / `BINDING_RANGE` at `$.claims[0].end`. These examples are offline regression cases, not diagnoses of the earlier live outputs.

Executed from repository root:

```powershell
$env:PYTHONPATH = 'services/claim_analysis'
& .venv-003a/Scripts/python.exe -m pytest -c services/claim_analysis/pytest.ini services/claim_analysis/tests -q
& .venv-003a/Scripts/python.exe -m claim_analysis evaluate --engine baseline --split dev --output artifacts/004a-evaluation-diagnostics/baseline-before.json
# After the CLI change:
& .venv-003a/Scripts/python.exe -m claim_analysis evaluate --engine baseline --split dev --output artifacts/004a-evaluation-diagnostics/baseline-after.json
& .venv-003a/Scripts/python.exe -m claim_analysis evaluate --engine baseline --split dev --dataset artifacts/004a-evaluation-diagnostics/dev-three.jsonl --output artifacts/004a-evaluation-diagnostics/baseline-three.json
```

- Before changes: **116 tests passed**, 1.28s.
- After changes: **124 tests passed**, final rerun 2.28s: all existing 116 and eight new regressions for JSON/schema/binding failures, successful analyses, absent metadata, invalid input, redaction and bounded counts. A three-case fake run also verifies that failure details never leak into a later successful record. Failure metrics still count factual omissions; successful extraction and scoring remain unchanged. Tests use fixed fake replies and block external sockets; there are no model calls.
- The entire development baseline's pre/post non-latency metrics are exactly equal, including all subgroup results. Every existing per-case field is also equal after excluding timing and the new null field. Source-hash checks confirm no other analysis implementation, prompt, schema, setting, dataset, demo, historical report or existing test changed.
- The documented PowerShell subset selection was executed offline: it selected exactly `eg004a-0001`, `eg004a-0007`, `eg004a-0019`, preserved their original labels/text, and all three baseline analyses completed with null failure details. This is a command/record check, not Gemini performance evidence.
- Final checks passed: exact four-file scope, unchanged protected implementation/data/report/test hashes, 23 local documentation links/anchors, balanced code fences, changed/new whitespace and `git diff --check` exit 0.

The [package README](../services/claim_analysis/README.md#evaluation-records-with-validation-diagnostics) contains exact PowerShell commands to select those three original JSONL lines, supply credentials securely, and explicitly run Gemini with `--max-requests 3`. Existing timeout/token/cost controls apply. The final command displays only IDs/status/reasons/sanitized details. Use a fresh output directory; a new generation may differ from the previously failed output, and this field cannot reconstruct a discarded old validation exception.

Changed files: `services/claim_analysis/claim_analysis/cli.py`, new `services/claim_analysis/tests/test_evaluation_diagnostics.py`, `services/claim_analysis/README.md`, and this report. Logs/subset artifacts remain ignored under `artifacts/004a-evaluation-diagnostics/`. Recommended commit, not created: `fix(claims): include sanitized validation details in evaluations`. Stop for review without committing or pushing.

## Deterministic source-span alignment (2026-11-09)

### Scope and contract separation

The maintainer's three-case diagnostic localized `eg004a-0001` and `eg004a-0007` to `SOURCE_BINDING / BINDING_TEXT_MISMATCH`, and `eg004a-0019` to `SOURCE_BINDING / BINDING_RANGE`. This does not establish that every failed output contained a correct quote with only bad offsets: raw failed outputs were not retained. The change removes offset calculation from the model's responsibilities while retaining all canonical acceptance conditions.

The model now emits a separate strict [identification contract](../services/claim_analysis/schema-004a.identification.v1.json), `004a.identification.v1`, with eight claim fields: ID, exact source text, optional untrusted normalized proposition, factuality, temporal category, fresh-evidence requirement, uncertainty and temporal reference. **Start/end are not allowed in this wire format.** Python computes them, constructs canonical `004a.v1`, then runs its original Pydantic consistency checks and final source binding. The canonical schema and its generated artifact are unchanged; old offset-bearing provider replies are rejected rather than repaired.

`alignment.py` clones the canonical non-offset field definitions and limits into the provider model, avoiding a second independently maintained set of semantic field constraints. Validators that require offsets are not inherited by this intermediate model; the complete canonical validators run when the aligned result is constructed. Required fields, supported categories, six-uncertainty and 64-claim limits, extra-field rejection, body bounds and strict JSON parsing remain active. No claim is discarded or reclassified to force success.

### Exact algorithm and failure behavior

For every supplied quote, in provider order:

1. Find an exact occurrence in the original Python string. If absent, reject the entire extraction with `ALIGNMENT_TEXT_NOT_FOUND`.
2. Search again from the first match's start plus one code point. Any second occurrence, including an overlapping occurrence, causes `ALIGNMENT_AMBIGUOUS`. There is no first/nth/next-occurrence selection and no contextual assignment of repeated quotes.
3. Compute `end = start + len(source_text)` in original Unicode code points. Reject reversed source order (`ALIGNMENT_OUT_OF_ORDER`) or overlap (`ALIGNMENT_OVERLAP`). Adjacent spans are allowed. Claims are never sorted.
4. Preserve every semantic field and quote, add only the calculated offsets, validate the entire canonical extraction, and run `Extraction.bind()` against the original input.

There is no whitespace/case/Unicode normalization, approximate matching, paraphrase substitution, guessed subject, offset correction or partial acceptance. `normalized_proposition` is never an alignment source. If any claim fails, no extraction result is returned. New sanitized failures use stage `ALIGNMENT` and an allowlisted `source_text` field path; existing diagnostics/count/path bounds remain unchanged. Canonical cross-field failures remain `MODEL_SCHEMA`, and the final ID/source guard remains `SOURCE_BINDING`. The public analysis failure string remains `INVALID_MODEL_ANALYSIS`.

Repeated identical text is conservatively refused even if a more complex global/contextual resolver might uniquely assign it. Conversely, a unique substring can still be a misleading fragment of a negated/qualified statement. The aligner preserves the quote exactly and never adds missing context; it cannot establish that the model selected a complete proposition, preserved semantic scope, extracted every assertion, classified correctly or verified truth. Full wording/negation/qualifiers remain requirements on semantic extraction, with exact-preservation and altered-quote rejection covered by tests.

### Provider generation and evaluation changes

Prompt version changes from `004a.prompt.v1` to `004a.prompt.v2`: the offset-generation instructions are replaced with exact-quote/no-offset instructions and the new wire version. The factuality/temporal/evidence classification rules are unchanged. This is not prompt tuning from held-out outcomes.

The generation schema now has `$defs.IdentifiedClaim`, no offset fields or numeric offset constraints, and version literal `004a.identification.v1`. As before, the provider converter omits only array `maxItems` hints while local count limits remain enforced. The schema diagnostic now labels this profile `004a.gemini-schema.v2` and records `identification_schema`; `original` and `no_max_items` refer to this new profile, not the historical offset-bearing schemas. Its obsolete `no_numeric_bounds` option was removed because it would send a duplicate request; titles/nullable representation/reference experiments remain explicit diagnostic-only choices. Historical schema reports/hashes are preserved.

| Artifact | SHA-256 |
| --- | --- |
| Unchanged canonical `schema-004a.v1.json` file | `4844a67557f27a96feca2a439d68cefd1a70724010f923bf3f135a45158d4986` |
| New `schema-004a.identification.v1.json` file | `4514b8bc30d2acf9e7ac1f928cb28180db499e52297e26b4cc11d85b454e526a` |
| Compact/sorted new provider `no_max_items` schema, 1,397 bytes | `d643b5fed04ed6590350556cbb59774bca32e0908ee62a5a45a536d6d712d758` |

No Gemini pricing, credentials, model selection, endpoint, timeout/token bounds, reservation algorithm or retry policy changed. The new schema/prompt still require actual live compatibility and quality qualification. The Go gateway, 003A verifier, `003a.v1`, caches and evaluation labels remain unchanged.

Evaluation retains the original frozen matching/scoring rules and original `all`, `mixed` and `adversarial` metrics. It adds `analysis_outcomes` (analyzed, extraction failures, invalid inputs) and `metrics.analyzed_only`, which applies the same scorer only to structurally valid analyses. This separates mechanical/provider failures from semantic-label comparisons on accepted outputs. The primary all-response metrics still count failures as misses; conditional scores must never conceal those failures. Report provenance includes `alignment.py` and the new prompt hash/version. Historical reports are not rewritten.

Offline fake/demo fixtures were explicitly migrated to the new identification wire format. A test-only fixture helper removes offsets from canonical **test expectations**; it is not imported by production and never converts actual model replies. Canonical-parser regressions for invalid offsets remain intact; model-format tests now assert the new strict contract. No tests were skipped to obtain a passing run.

### Tests and measured development results

Before implementation, **124 offline tests passed**, 1.47s. After fixture migration, the same 124 tests passed, 1.77s. With alignment and evaluation regressions, **151 tests passed**, final rerun 3.45s. Tests cover fixture reproductions of all three reported failures, legacy-format rejection, Unicode/combining/emoji/CRLF offsets, overlapping repeated occurrences, repeated identical assertions, ambiguity despite surrounding context, missing/paraphrased/normalized text, negation/qualifiers, multiple atomic claims and adjacent spans, overlap/order, adversarial instructions, no claim dropping, count limits, canonical semantic constraints and exact final binding. A separate test shows that a structurally valid but semantically wrong label remains an analyzed result scored as wrong, not an extraction failure.

Commands executed, in order (all tests before development comparison):

```powershell
$env:PYTHONPATH = 'services/claim_analysis'
& .venv-003a/Scripts/python.exe -m pytest -c services/claim_analysis/pytest.ini services/claim_analysis/tests -q
& .venv-003a/Scripts/python.exe -m claim_analysis evaluate --engine baseline --split dev --dataset artifacts/004a-alignment/dev-ten.jsonl --output artifacts/004a-alignment/baseline-ten.json
& .venv-003a/Scripts/python.exe -m claim_analysis evaluate --engine fake --split dev --dataset artifacts/004a-alignment/dev-ten.jsonl --fake-replies artifacts/004a-alignment/scripted-ten.jsonl --output artifacts/004a-alignment/scripted-roundtrip.json
& .venv-003a/Scripts/python.exe -m claim_analysis.schema_diagnostic --variants no_max_items --max-requests 1 --output artifacts/004a-alignment/provider-schema
```

The exact historical ten examples were located in `artifacts/004a/dev-smoke.jsonl` and verified against the current frozen annotations: `0001`, `0007`, `0013`, `0019`, `0021`, `0025`, `0031`, `0033`, `0037`, `0043` (each prefixed `eg004a-`). They are not the first ten rows. No held-out evaluation or tuning was performed. Existing held-out schema/review integrity tests remain unchanged.

| Same ten-case development set | Current baseline rerun | Historical Gemini, before alignment | Revised Gemini |
| --- | --- | --- | --- |
| Valid analyses / extraction failures | 10 / 0 | 3 / 7 | **Pending live opt-in** |
| Overall factual matches / gold | 21 / 21 | 6 / 21 | Pending |
| Overall claim F1 | 1.000 | 0.444 | Pending |
| Overall temporal macro-F1 | 0.650 | 0.361 | Pending |
| Overall fresh-evidence recall | 0.889 | 0.222 | Pending |
| Temporal matched accuracy among valid analyses | 0.810 (21 matched claims) | 1.000 (only six matched claims in three responses) | Pending |

Baseline non-latency metrics are exactly equal to the saved historical baseline report. Historical Gemini numbers come from the existing `gemini-dev-smoke.json`, not a new model run. The conditional historical accuracy was recomputed from its three saved accepted extractions using the same frozen scorer. Its small successful subset does not offset seven failures or qualify model quality.

Ten **scripted** identification replies constructed from development annotation expectations round-trip through the revised pipeline to exact canonical expectations. That exercises alignment/evaluation plumbing and is labeled `fake-adapter plumbing only`, not a model prediction or model-versus-baseline quality result. It does not prove that the real model will emit the same quotes or labels.

The session has no live model-call opt-in/key available. **No live Gemini or Tavily request was made. The revised baseline-versus-Gemini performance comparison remains pending.** Do not infer that seven failures will disappear: verbatim quote selection, ambiguity, schema compliance, truncation and semantic errors can still fail. The schema diagnostic export reports live qualification pending. Logs, fixed-subset copies and fixture-only outputs remain ignored under `artifacts/004a-alignment/`.

The exact PowerShell subset-construction commands were also executed offline and produced the verified same ten case IDs/labels. All five migrated fake demo commands passed. Final checks passed: 12 protected implementation/data/report/schema hashes, unchanged canonical schema, fake-fixture changes restricted to wire version/removing offsets, unchanged baseline non-latency metrics, 36 relative documentation links/anchors, code fences, changed/new whitespace and JSON syntax, 20-file scope, and `git diff --check` exit 0.

The [package README](../services/claim_analysis/README.md#qualify-alignment-on-the-original-ten-development-examples) provides complete PowerShell commands to reconstruct exactly these ten examples from unchanged repository JSONL, run the baseline, configure trusted Gemini credentials/rates, explicitly enable model calls and run with `--max-requests 10`. Existing per-request/whole-run cost and timeout/token guards apply; there are no automatic retries. Use a fresh output directory and record failures alongside conditional classification scores.

### Review boundary and files

Remaining limitations include globally repeated quotes, unique but incomplete/semantically misleading fragments, omitted assertions, incorrect classifications, hallucinated/paraphrased quotes, context-dependent pronouns, discontinuous claims and provider/schema/output failures. Exact alignment is source integrity, not semantic verification or coverage proof. The dataset remains an agent-authored human-review draft. No unrestricted verification, response aggregation, protected cache or Task 004B work was added.

Changed files: new `claim_analysis/alignment.py`, `schema-004a.identification.v1.json`, `tests/test_alignment.py`, `tests/wire_helpers.py`; existing `claim_analysis/model.py`, `validation_diagnostics.py`, `schema_diagnostic.py`, `cli.py`; four existing test modules (`test_analysis.py`, `test_schema_diagnostic.py`, `test_validation_diagnostics.py`, `test_evaluation_diagnostics.py`); five `demos/*.fake.json` fixtures; package README; `docs/architecture.md`; and this report. All package paths are under `services/claim_analysis/`. Canonical `schema.py`, `schema-004a.v1.json`, pricing/configuration code, datasets, original scoring implementation and historical reports are unchanged.

Recommended commit, not created: `feat(claims): align exact source quotes before canonical validation`. Stop for review with revised live-model qualification explicitly pending; no commit or push.
