# Task 004A-H — correctness and reproducibility hardening

Date: November 10, 2026 (Asia/Calcutta). Starting commit: `29dbfd9b7881bae0911d6c30dc7080a2dded0b43` on `main`, with a clean working tree. Scope is four reproducible defects before Task 004B. No live Tavily or Gemini call, commit or push is part of this work.

## Requirement and minimal design

Accept only canonical JSON field names in the fixed verification record; diagnose failures with bounded metadata; correct instruction/opinion lexical matching in the experimental baseline; and make the two versioned schema file hashes independent of checkout line endings.

The existing `003a.v1` contract, evidence comparison, hook placement, typed terminal refusals, candidate/request binding, genuine provider errors and disabled caching remain authoritative. The analyzer remains separate from `/v1/verify`. No schema values, annotations, source alignment, Gemini settings or Task 004B implementation are changed.

Inspection included AGENTS, README, architecture, the integration spike, Tasks 003A/B/C/004A, the requested Go/Python implementations, attributes and their existing tests. The preserved pinned upstream core sources under ignored `artifacts/002b/upstream/` were re-read: `PluginPipeline.RunPostLLMHooks` records ordinary Go errors, whereas returned response/typed `BifrostError` control delivery; `AllowFallbacks=false` suppresses fallback. `dev/Dockerfile` still checks transport commit `e869c3f9adc96ea53c38694a21bb04a8e1085487`, core `v1.14.1` and matching host/plugin module graphs. No plugin API is added or changed.

## Reproductions and fixes

### Canonical verification fields

The old recursive precheck rejected exact duplicates, then `encoding/json` decoded a struct with case-insensitive matching. The focused real HTTP-source test reproduced seven accepted `ALLOW` records: a lone `Verdict` alias, canonical/alias duplicates in both orders, nested `Version`, nested `Observed_Version`, nested `URL` overriding an earlier value, and Unicode long-s in `schema_version`. Escaped canonical duplicates, exact nested duplicates and unknown fields already failed correctly (three negative controls).

[http_decision.go](../plugins/epochguard/http_decision.go) now checks exact canonical field names by object level (`response`, `claim`, `evidence`) before typed decoding. It retains exact duplicate detection and `DisallowUnknownFields`. Field names are compared after JSON escape decoding; aliases are rejected even when supplied alone. The fixed contract uses a small switch, with a depth bound of four and the existing 32 KiB body bound, rather than reflective field discovery or case-folded merging. Scalar decoding and the existing semantic/binding validator still run afterward. Ordinary valid records retain their original decisions.

[json_contract_test.go](../plugins/epochguard/json_contract_test.go) sends mutated records through the actual HTTP → typed decode → validation → enforcement path. Invalid records must produce no candidate, terminal HTTP 503 and no fallback. It never resolves ambiguous fields after decoding.

### Sanitized failure diagnostics

Previously `enforce()` discarded `Decide()` errors, and retrieval HTTP failures lost their status category. Errors still cause UNAVAILABLE; diagnostics now explain the class without copying error strings.

Go's [diagnostics.go](../plugins/epochguard/diagnostics.go) uses an internal metadata-only error, fixed `event=verification_failure`, an allowlist of categories, and optional integer `http_status` in 100–599. It never wraps or formats transport errors. Enforcement logs source errors, context cancellation/deadline, and other unavailable outcomes. HTTP body-read timeouts retain an already-received status. The existing validated verdict/reason log is preserved behind the same best-effort sink wrapper.

| Go category | Meaning |
| --- | --- |
| `request_failure` | Request construction/transport/body-read failure |
| `verification_timeout` / `verification_cancelled` | Total/client/parent deadline or cancellation |
| `verifier_http_failure` | Verifier non-200 response, including its numeric status |
| `invalid_contract` | Wrong media, excessive body, bad JSON/names, invalid binding/evidence record or evidence-mode mismatch |
| `unsupported_candidate` | Candidate outside the exact supported form; no verifier call |
| `verification_unavailable` | Other unavailable outcome, unknown decision, absent source/candidate or unknown diagnostic category |

Python's [diagnostics.py](../services/verifier/verifier/diagnostics.py) emits a small JSON log message through standard logging, with the same fields also present as structured log-record attributes. This keeps categories visible under the existing default log formatter. Events are only `verification_failure` or `retrieval_failure`. Categories distinguish Tavily 401 (`tavily_http_unauthorized`), 429 (`tavily_http_rate_limited`), 5xx (`tavily_http_server_error`), other HTTP failure, timeout, request failure, missing credentials, invalid/ambiguous evidence, stale observations, unsupported/ahead claims and other verification-unavailable outcomes. Non-200 Tavily records include status without reading the response body. A per-call `_HTTPObservation` retains only the received numeric status: body-read/socket/whole-retrieval timeouts, transport read failures and invalid JSON/envelopes after headers retain status 200; failures before headers have no status. This metadata is never shared on the reusable retriever. FastAPI work-deadline expiry is logged separately as `verification_timeout`.

For example, a Tavily 401 produces `{"category":"tavily_http_unauthorized","event":"retrieval_failure","http_status":401}` (spacing may differ). The public response remains `INSUFFICIENT / RETRIEVAL_FAILURE`; a FastAPI work timeout remains `INSUFFICIENT / VERIFIER_ERROR`. Internal diagnostics are never added to responses, refusal text or headers. No keys, authorization headers, candidate/model text, evidence, upstream bodies, request payloads, URL-bearing transport errors or arbitrary exception messages enter these new records.

Each failure emits one diagnostic at its owning layer; a valid INSUFFICIENT service response can also produce Go's existing safe verdict log and generic unavailable diagnostic. Logs are process-local best-effort metadata, with no new request/evidence persistence or correlation system. Request/response objects are still borrowed synchronously, and no new goroutines or retained pooled objects are introduced. Typed metadata lives only for the current call. Existing Go hook/configuration logs also use the panic-safe sink wrapper so a failing writer cannot prevent enforcement. Python handler exceptions are swallowed only around logging; cancellation and policy behavior retain their original handling.

Regression tests in [Go](../plugins/epochguard/diagnostics_test.go) and [Python](../services/verifier/tests/test_diagnostics.py) check categories, numeric statuses, synthetic private sentinels, log injection, unknown metadata, bounded emitted messages, and failing/panicking log sinks. Logging failures do not change ALLOW/REJECT/UNAVAILABLE. Go still preserves the original response pointer on ALLOW and original provider error pointer/fallback policy on upstream failure.

### Baseline lexical matching

The original `^(please|...|use|return|print|...)` had no word boundary. `Users`, `Used` and `Returns` were therefore NON_FACTUAL instructions. An unqualified `best` anywhere also erased factual assertions.

The fix in [baseline.py](../services/claim_analysis/claim_analysis/baseline.py) adds word boundaries to instruction words and preserves explicit `system:`/`assistant:` prefixes. It replaces bare `best` with a copular opinion pattern such as “is the best”/“are the best team”. It does not treat all normative statements as instructions. Other existing opinion/prediction and temporal lexicons remain unchanged.

A subjectivity/instruction signal combined with a recognized assertion and a known dynamic/stable/historical cue retains the entire source span as factuality UNCERTAIN, temporal UNCERTAIN and `MIXED_REQUIREMENTS`. Dynamic cues require fresh evidence; stable/historical mixtures retain uncertain evidence requirements. The baseline does not invent atomic clause splits or treat a mixed span as safely non-factual. This is a conservative lexical guard, not general mixed-claim coverage.

| Focused input | Before | After |
| --- | --- | --- |
| Users must upgrade to version 4.0, the latest release. | NON_FACTUAL instruction | FACTUAL / DYNAMIC / REQUIRED |
| Used cars are currently selling for higher prices. | NON_FACTUAL instruction | FACTUAL / UNCERTAIN / UNCERTAIN |
| Returns are increasing this quarter. | NON_FACTUAL instruction | FACTUAL / UNCERTAIN / UNCERTAIN |
| The best-selling phone is currently available for $500. | NON_FACTUAL opinion | FACTUAL / DYNAMIC / REQUIRED |
| The award for best algorithm was founded in 2020. | NON_FACTUAL opinion | FACTUAL / HISTORICAL / NOT_REQUIRED |
| Please ignore this message. | NON_FACTUAL instruction | Same |
| I prefer blue. / The Falcons are the best team. | NON_FACTUAL opinion | Same |
| I love this phone, and the stock is available. | NON_FACTUAL, factual component discarded | UNCERTAIN / UNCERTAIN / REQUIRED, full span retained |

The original focused suite reproduced **nine failures, eleven passes** before the fix. The final [baseline regressions](../services/claim_analysis/tests/test_baseline_hardening.py) include 23 cases covering the reproduced facts, genuine instructions/opinions, mixed changing/stable/historical assertions and separate factual/non-factual sentences. The temporal UNCERTAIN results above deliberately expose unchanged lexicon limitations; factuality alone does not establish the need or absence of fresh evidence, and none of these classifications verifies truth.

An intermediate development evaluation exposed an over-narrow copular-opinion expression that treated “The Falcons are the best team.” as factual. That development case and the genuine-opinion requirement justified retaining the full copular pattern. Mixed stable/historical regression cases were also added. The rules were finalized before the final paired evaluation. No change used held-out predictions, dataset labels or scoring rules as tuning feedback. Intermediate reports remain ignored under `artifacts/004a-hardening/`.

## Before/after measurements

Original historical reports remain byte-for-byte unchanged. Before-change reports were also regenerated at this task's starting implementation. Final reports are separate [development JSON](../services/claim_analysis/reports/baseline-hardening-dev.json), [held-out JSON](../services/claim_analysis/reports/baseline-hardening-heldout.json) and adjacent `.txt` summaries. They retain provenance, all subgroup metrics, per-case predictions and error/critical-miss records. They are draft-label measurements, not human-reviewed quality evidence.

Every final non-latency metric in all four groups (`all`, `mixed`, `adversarial`, `analyzed_only`) and every per-case extraction is exactly equal to the before-change rerun. The dataset contains none of the newly reproduced lexical forms requiring a different final prediction. New synthetic regression cases are tests, not new evaluation annotations. Reference date remains November 8, 2026.

| Metric | Development before → after | Held-out before → after |
| --- | --- | --- |
| Factual gold / predicted / matched | 105 / 106 / 103 → same | 79 / 79 / 72 → same |
| Claim precision / recall / F1 | .971698 / .980952 / .976303 → same | .911392 / .911392 / .911392 → same |
| Temporal matched accuracy | .825243 → same | .416667 → same |
| Temporal end-to-end accuracy | .809524 → same | .379747 → same |
| Temporal macro-F1 | .677355 → same | .522306 → same |
| Temporal class F1: dynamic / historical / stable / uncertain | .887097 / .827586 / .894737 / .100000 → same | .338028 / .842105 / .909091 / .000000 → same |
| Fresh-evidence precision / recall | .965517 / .823529 → same | .812500 / .232143 → same |
| Critical dynamic omissions / nonfresh labels | 1 / 0 → same | 6 / 0 → same |
| Matched dynamic facts left uncertain | 11 → same | 37 → same |
| Uncertainty rate (units) | .178862 (22/123) → same | .533333 (48/90) → same |
| Analysis/input-outcome failures | 0 → same | 0 → same |

Outcomes remain 60 analyzed development cases; held-out has 49 analyzed cases and three correctly refused invalid inputs. No model performance or quality improvement is inferred from unchanged scores. Held-out fresh-evidence recall remains inadequate, missing 43/56 required requests.

## Cross-platform schema integrity

`.gitattributes` previously had `* text=auto` and no JSON exception. Both schema working copies had CRLF while Git blobs had LF: 135 and 123 CRLF sequences respectively. Parsing either representation gave identical JSON. Only these two paths now have `text eol=lf`; their working-copy bytes were normalized without changing any schema value. Git already stored the desired LF content, so there is no semantic or Git-blob schema diff to stage.

| File | Previously documented Windows CRLF SHA-256 | Normalized LF / Git SHA-256 |
| --- | --- | --- |
| `schema-004a.v1.json` | `22537498b33b07939feae96b2000ed664ec666f49f9b310d5b091523a31dbd8e` | `4844a67557f27a96feca2a439d68cefd1a70724010f923bf3f135a45158d4986` |
| `schema-004a.identification.v1.json` | `1708eba595bb506f94e81101d58458e4a881425a245d16f34a56a6887fe7676d` | `4514b8bc30d2acf9e7ac1f928cb28180db499e52297e26b4cc11d85b454e526a` |

The three raw-file hash entries in [Task 004A](task-004a.md) now use LF hashes and link here; its historical results/development history remain intact. Compact sorted provider `no_max_items` JSON remains **1,397 bytes**, SHA-256 `d643b5fed04ed6590350556cbb59774bca32e0908ee62a5a45a536d6d712d758`. The compact/sorted strict canonical schema also remains 1,591 bytes, `dfcfb08fee54fb61143b2a5149f92a6a00ca67fbdeb6120f8e8c8d48251402f6`; the identification schema remains 1,511 bytes, `1427375059f4263184ad4e63ee8683473aba84aa3ed529734ffe1acc2e6aef36`. Schema meaning, canonical representation, generation conversion and compatibility do not change.

The new [integrity command](../services/claim_analysis/claim_analysis/schema_integrity.py) checks raw bytes, LF/final newline and pinned SHA-256, optionally comparing the exact bytes to a local Git revision. It reads Git blobs as binary (no PowerShell text pipeline). [Tests](../services/claim_analysis/tests/test_schema_integrity.py) reject simulated CRLF and other byte changes while existing tests still compare generated schema values. A legitimate schema change requires deliberate hash review.

```powershell
$env:PYTHONPATH = 'services/claim_analysis'
& .venv-003a/Scripts/python.exe -m claim_analysis.schema_integrity --git-ref HEAD
```

Both files passed exact comparison with `git show HEAD:<path>`. `git -c core.autocrlf=true cat-file --filters HEAD:<path>` and `core.autocrlf=false` both yielded those same bytes under the new attributes. A network-disabled Linux container running the same module also produced both identical hashes. No unrelated file normalization is included.

## Executed validation

All commands run from the repository root. Logs and before/intermediate reports are ignored under `artifacts/004a-hardening/`. Tests use deterministic fixtures and synthetic private sentinels; no paid call is authorized or made.

```powershell
$env:PYTHONPATH = 'services/verifier'
& .venv-003a/Scripts/python.exe -m pytest -c services/verifier/pytest.ini services/verifier/tests -q
$env:PYTHONPATH = 'services/claim_analysis'
& .venv-003a/Scripts/python.exe -m pytest -c services/claim_analysis/pytest.ini services/claim_analysis/tests -q
& .venv-003a/Scripts/python.exe -m claim_analysis evaluate --engine baseline --split dev --output artifacts/004a-hardening/baseline-before-dev.json
& .venv-003a/Scripts/python.exe -m claim_analysis evaluate --engine baseline --split heldout --output artifacts/004a-hardening/baseline-before-heldout.json
# Before paths above were executed before edits. Final measurements:
& .venv-003a/Scripts/python.exe -m claim_analysis evaluate --engine baseline --split dev --output services/claim_analysis/reports/baseline-hardening-dev.json
& .venv-003a/Scripts/python.exe -m claim_analysis evaluate --engine baseline --split heldout --output services/claim_analysis/reports/baseline-hardening-heldout.json
```

| Check | Actual result |
| --- | --- |
| Original verifier tests | 41 passed, one live test deselected; 3.16s |
| Original claim-analysis tests | 151 passed; 2.51s |
| Changed verifier and new diagnostics | Final: 65 passed, one live test deselected; Windows 5.51s, Linux image build 4.89s. Initial 62-case version also passed on Windows (4.02s) and Linux image build (3.95s); three final streamed-body cases retain status after headers |
| Changed claim-analysis and regressions | 176 passed; 2.98s |
| Go alias reproduction, unchanged parser | Expected exit 1: seven failing aliases, three passing negative controls |
| Windows/Linux schema hashes and Git filters | Exact matches for both files |

The existing Starlette/httpx deprecation warning remains; no dependency is changed to address it. The live test is intentionally excluded by the repository's default offline marker, not silently skipped.

The host has no `go` executable. Initial sandboxed Docker calls could not read its configuration and found no engine pipe; the escalated check confirmed Docker Desktop was stopped. `docker desktop start` restored the established Linux build environment. No host Go substitution or mock plugin loader was used. The initial focused Docker reproduction intentionally exited 1 on the seven parser regressions; its failure log is preserved.

The ignored `Dockerfile.unit` consists of the unchanged `dev/Dockerfile` followed by a `qualification-unit` stage. That stage selects the plugin workdir, runs `go mod download && go mod verify` with the established module cache, then a network-disabled cache-mounted RUN executing `test -z "$(gofmt -l .)" && go vet -mod=readonly ./... && go test -count=1 -mod=readonly -trimpath -v ./... && go test -count=1 -race -p=2 -mod=readonly -trimpath ./...`. Go is the repository-pinned **1.27.3 Linux/amd64** toolchain. The native image build separately runs its existing formatting/unit/race checks and builds the actual `.so`.

```powershell
# Focused reproduction before the parser fix (expected exit 1):
docker buildx build --builder epochguard-002a --progress plain -f artifacts/004a-hardening/Dockerfile.reproduce .
# Final fresh checks; Dockerfile.unit is described above:
docker buildx build --builder epochguard-002a --progress plain --target qualification-unit --no-cache-filter qualification-unit -f artifacts/004a-hardening/Dockerfile.unit .
docker buildx build --builder epochguard-002a --progress plain --load -t epochguard-dev:002a -f dev/Dockerfile .
docker compose -f compose.verify.yaml build verifier-supported

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

docker run --rm --network none --mount 'type=bind,source=C:\Users\Aditya Bhardwaj\OneDrive\Desktop\epochguard,target=/project,readonly' --workdir /project -e PYTHONPATH=services/claim_analysis --entrypoint python epochguard-verifier:003a -m claim_analysis.schema_integrity
git diff --check
```

| Native/runtime check | Actual result |
| --- | --- |
| Final fresh plugin unit tests | 22 top-level / 64 subtests passed; 0.205s |
| Final fresh race detector | Passed, 1.326s; no race report; covers plugin units, not gateway internals |
| `gofmt` and `go vet` | Passed in the final network-disabled qualification stage |
| Gateway image build | Passed, including native plugin compilation and existing unit/race checks |
| Gateway smoke | 10 top-level / 35 subtests passed, including provider failures, terminal fallback/no-answer controls and concurrency |
| Offline gateway/service verification | Final image: 8 top-level / 31 subtests passed; initial image also passed the same suite |
| Route audit | 4 top-level / 54 subtests passed, with the existing no-plugin/provider controls |
| Deterministic long profile | Final image: passed in 12.60s; HTTP 200 at first byte 12,592ms / total 12,593ms, provider/retrieval deltas 1/1. Initial image also passed in 12.61s |

The short verification runner explicitly skips live opt-in and the separate long profile; the long test is executed separately. After final review added three streamed-body diagnostic regressions, the verifier was rebuilt and both affected gateway-verification profiles were rerun against that final image. Smoke and route tests use the unchanged final Go image. There were no failed enforcement assertions to retry or weaken.

Final local image IDs: gateway `sha256:024b058a59089411119e0bb9b7acda69c1fb22ed5ddbd3883a65573658f4af6e`; verifier `sha256:1f905b9d056b4e523cc47c493b8d3d047884d7550eb854990acd865025d879c7`. These identify the locally tested builds, not published releases.

The final local review script checked 57 protected files against the starting Git contents, all 34 relative documentation links/anchors in the two edited reports, balanced code fences, whitespace/JSON syntax in all 22 changed/new content/attribute paths, and evaluation provenance hashes. Both normalized schema working copies match their existing Git blobs. `git diff --check` exited 0. All task-owned smoke, verification, long-profile and route stacks were removed; only the pre-existing BuildKit builder remains running.

## Remaining limitations and review boundary

These fixes do not change the successful November 8 narrow live qualification into a broader guarantee or constitute a new live rerun. General factual/freshness verification, origin freshness attestation, protected caching, atomic revocation, safe streaming and production readiness remain unimplemented/unqualified. The plugin is not an all-route firewall; API/background/Warp limitations from Task 003C remain.

Explicitly deferred: missing-plugin startup/ingress enforcement; production removal of test-only decision sources; gateway-to-verifier authentication; a shared Tavily client/single-flight retrieval; response-level claim aggregation; and verified caching. None is resolved here. Logs remain best-effort; a sink that blocks indefinitely can still delay its caller. There is no external logging service, OpenTelemetry rollout, audit-store guarantee or live retrieval counter.

The baseline still has limited temporal lexicons, sentence-level segmentation, incomplete mixed-assertion coverage, ambiguous pronouns and subjective/quoted/negated phrasing it cannot reliably classify. Its new mixed guard can conservatively request evidence for a genuine opinion containing a factual cue. Schema integrity and exact source alignment do not establish semantic coverage or truth. Human annotation review and real Gemini compatibility/quality qualification remain pending.

Changed files: `.gitattributes`; `plugins/epochguard/{decision.go,http_decision.go,main.go,diagnostics.go,diagnostics_test.go,json_contract_test.go}`; `services/verifier/verifier/{app.py,retrieval.py,policy.py,diagnostics.py}` and `tests/test_diagnostics.py`; `services/claim_analysis/claim_analysis/{baseline.py,schema_integrity.py}`, `tests/{test_baseline_hardening.py,test_schema_integrity.py}`, and four new `reports/baseline-hardening-{dev,heldout}.{json,txt}` files; this report and the minimal Task 004A hash/link correction. Both schema working copies are LF with unchanged Git blob contents. No README milestone log is added.

Recommended commit, not created: `fix: harden verifier contracts diagnostics and claim reproducibility`. Stop for maintainer review; do not begin Task 004B.
