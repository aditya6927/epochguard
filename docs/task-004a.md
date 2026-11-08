# Task 004A — Time-sensitive claim identification and evaluation

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
