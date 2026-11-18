# Task 005C — native model path and claim-analysis evaluation

## Scope and design

Execution baseline: `5bf1a0b81b1abf9afb7e4519990342c496aadc7b`; source was initially clean. The [pre-implementation design assessment](real-model-qualification.md#design-assessment) records source contracts, ownership and the minimal supported path. The release authority remains the existing verifier/native plugin/protected ingress. No 005D work, new evidence policy, cache, authentication design, license or publication change is included.

Milestone: **IMPLEMENTATION COMPLETE / LIVE PENDING**. Offline qualification completed November 18–19, 2026 (Asia/Calcutta). Independent real-model qualification has not been met.

The new isolated profile sends actual native Gemini requests through a fixed-host resource relay, then the existing hooks, evidence verifier and v2 ingress checks. Offline execution uses simulated Gemini HTTP and simulated Python.org/PyPI evidence. Separate runtime opt-ins, credentials and matching offline preflight are required for paid generation. Model claim analysis reuses the existing adapter, prompt, schema, alignment and independent auditor. The new 18-case review packet is synthetic and draft-labeled; independent human review is pending.

Real gateway-model and real extraction runs are **PENDING OPERATOR RUN**. No model or live-source call has been authorized or made during implementation. A simulated native Gemini response is not real inference, and no historical diagnostic is substituted for fresh execution. Real model inference alone would not establish general factual correctness, complete PS06 compliance or freshness scores.

## Audit findings

The pinned transport module graph selects core `v1.14.1` and framework `v1.11.1`. Inspected sources are the transport at `e869c3f9adc96ea53c38694a21bb04a8e1085487`, core at tag `core/v1.14.1`, and framework at tag `framework/v1.11.1`. Native Gemini `ChatCompletion` dispatch, `generateContent` URL construction, key header, configurable base URL/network timeout, zero retry defaults, parameter conversion and `SecretVar` environment resolution were read before use. Model selection is explicit operator configuration; no live model ID or price is guessed.

| Upstream file | Inspected blob SHA |
| --- | --- |
| `transports/go.mod` | `ca87c34f7b1bfc548a7436a1fcf82896abb84328` |
| `core/providers/gemini/gemini.go` | `af11e1db8e50f9836752cab9e60e082b1325205c` |
| `core/providers/gemini/chat.go` | `aa3b8e562b7ab64723c53960e1b8fbdda039f64e` |
| `core/providers/gemini/utils.go` | `356305f513a0ef47d03c1388ddba3980ef7bab1a` |
| `core/providers/gemini/types.go` | `310f133c77a27ac7ed645e215e1176a755e0969a` |
| `core/schemas/provider.go` | `a87399709498c74966fa02ff019095ef1cfc9c21` |
| `core/schemas/secretvar.go` | `215f0e5092c7e36a2eaf08718afe5fde723367fb` |
| `framework/configstore/tables/key.go` | `ef801fecbd303a4708f11d3e474678a26bf92ede` |

Direct source links: [transport manifest](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/go.mod), [native Gemini](https://github.com/maximhq/bifrost/blob/core/v1.14.1/core/providers/gemini/gemini.go), [token conversion](https://github.com/maximhq/bifrost/blob/core/v1.14.1/core/providers/gemini/utils.go), [credential resolution](https://github.com/maximhq/bifrost/blob/core/v1.14.1/core/schemas/secretvar.go). The source audit establishes supported interfaces; actual gateway execution is a separate check.

Existing CI uses four offline jobs and no secrets/live/deployment path. [Baseline hosted run 43752637258](https://github.com/aditya6927/epochguard/actions/runs/43752637258) was inspected through GitHub check-run metadata: Go, Python, frontend and documentation all completed successfully at the expected baseline. This is subsequent evidence beyond the dated 005B report, not hosted execution of these changes. Native loader and lifecycle suites remain separately local.

Docker initially had no running engine. Docker Desktop was started and became available; the initial unavailable-engine probe is not a test pass. Host Python 3.12 with existing locked dependencies was available. Native build source checks and module-manifest comparisons ran; all execution claims below distinguish mocks, native gateway runs and live pending work.

## Implementation and security boundaries

The qualification-only ingress option admits bounded native Gemini output-token parameters while keeping the G v2 receipt and exact forwarded-body binding. Ordinary profiles keep their prior request language. The relay restricts exact model/path/prompts and native fields, rejects tools/cached content/system overrides, enforces one active request, per-request/run reservations, attempt ceilings, total deadlines and strict request/response limits. Failed/cancelled attempts retain their reservations. The live relay alone has egress; only the gateway mounts a dedicated credential file and loads it into its process environment using upstream's supported reference mechanism. Receipt keys remain separate. Gateway logs are suppressed, and reports contain sanitized categories and hashes rather than raw content/headers/receipts.

Native provider bytes pass unchanged. Observations, grammar parsing and usage measurements in the relay are diagnostic only. Existing independent Go/Python verification and authenticated ingress decide delivery. A noncompliant generation stays an observed noncompliance with its actual verdict; it is never replaced by the intended answer. Internal controlled canary/error/missing-plugin cases make no paid calls. Offline mode strips inherited credential/opt-in variables and has internal networks only. Emergency cleanup uses a separate manifest with no credential interpolation.

The analysis diagnostic loads only its explicit separately authorized key file, reuses `GeminiProvider`, `ModelExtractor`, `004a.prompt.v2`, `004a.identification.v1`, strict source alignment, `Analyzer`, auditor and scoring. It sends complete original responses, never preselected spans. All cases remain in the denominator; failures, abstentions, omissions, classification errors and missing model measurements are explicit. Existing 004A/004F data and historical results are unchanged. No evaluation result authorizes answers.

## Draft-label evaluation

The frozen [review packet](../tests/modelqualification/data/README.md) was authored from the required categories before any new model results. It includes exact original text, reference date, spans, classifications, policy proposals and uncertainty notes. All 18 cases are agent-authored drafts; no reviewer identity is invented. It is not blind evaluation. Repeated identical spans deliberately trigger the unchanged aligner/Analyzer's ambiguity refusal. Stable/historical/nonfactual units also enter classification denominators.

Offline execution used zero model attempts. The factual denominator is 20, dynamic/fresh-required denominator is 16 and all-unit classification denominator is 24. Each comparison includes all 18 responses, including one extraction failure on repeated text. Matching uses the existing frozen span IoU threshold 0.5; exact-span scores require 1.0. These draft-label measurements do not establish independently reviewed accuracy.

| Measurement | Deterministic 004A baseline | Independent 004F auditor | Gemini alone | Gemini + auditor |
| --- | --- | --- | --- | --- |
| Responses / extraction failures | 18 / 1 | 18 / 1 | Not executed | Not executed |
| Factual precision / recall | 17/17 / 17/20 | 6/6 / 6/20 | Missing | Missing |
| Exact factual spans | 14/17 precision, 14/20 recall | 6/6 precision, 6/20 recall | Missing | Missing |
| Dynamic claim recall | 14/16 | 6/16 | Missing | Missing |
| Fresh-required precision / recall | 14/15 / 14/16 | 6/6 / 6/16 | Missing | Missing |
| Classification triples correct | 19/24 | 6/24 | Missing | Missing |
| Unsupported policy mappings | Not supplied by extractor | 0 | Missing | Missing |
| Unaccounted risk units | Not supplied by extractor | 17 | Missing | Missing |
| False completeness | Not supplied by extractor | 0/18 | Missing | Missing |
| Correct abstentions on unsupported/ambiguous cases | Not supplied by extractor | 14/15; one failure separately counted | Missing | Missing |

Both engines failed case `eg005c-0014` with `EXTRACTION_FAILED`; both repeated claims count as misses. The baseline also omitted case 0007/c001 and misclassified 0007/c002 and 0008/c001 against the proposed labels. Its exact-span mismatches are separately reflected in 14/20 exact recall; overlap matching is not exact atomicity.

Auditor omissions across all 24 annotated units are: 0003/c001, 0004/c001, 0005/c001, 0006/c002, 0007/c001 and c002, 0008/c001, 0009/c001, 0010/c001, 0011/c001, 0012/c001, 0013/c002, 0014/c001 and c002, 0015/c001 and c002, 0016/c001 and 0017/c001 (all IDs use prefix `eg005c-`). Ten of those omissions are dynamic claims. This auditor is deliberately bounded; unsupported/nonfactual/ambiguous units and coverage refusals must not be presented as a general semantic extractor. Zero false completeness in this packet is not a proof of semantic completeness.

Final diagnostic: `artifacts/005c/analysis-005c-final.json`, 15ms total local evaluation time in that execution, no model latency/token/cost measurement. Per-case proposals, classifications, uncertainty and fixed failure diagnostics are retained without raw model replies. All omitted units remain in the denominator. The packet was not revised after these results.

| Reproducibility input | SHA-256 |
| --- | --- |
| Frozen review packet | `9a564900174eddd186a7b24313fc45fa2bd563cbcdd948b8d4a4e530209ae26e` |
| `004a.prompt.v2` | `fc3dd211240062ba0a1e7471cc622e64c6eea4139a2e43ec1cb1e1259fca9a53` |
| Runtime `004a.identification.v1` schema | `b4672a669e113fd216d29b9415bf00d3d5fb1e1bc9021dbbc0fb9ada767c5d3c` |

## Native gateway results

Final run: `artifacts/005c/offline/20261118T184058Z-a05b5543/`. It used the real pinned native loader and Gemini conversion with **simulated Gemini HTTP**, **simulated evidence**, `004g.v1/bounded-prose-v1` and receipt `004g.receipt.v2`. Source revision is the baseline above plus execution input digest `58b9ea8518587176b30ee0f122fd2ed8d689a1db671a013b2f5fc420af20ba54`. This digest identifies qualification source inputs, not a verification or origin-freshness proof.

| Scenario / observed simulated behavior | HTTP | Actual outcome | Answer released | Client elapsed ms |
| --- | --- | --- | --- | --- |
| Supported two-claim response, exact content preserved | 200 | ALLOW | Yes | 114.500 |
| Older Python version | 403 | REJECT | No | 27.164 |
| Supported prefix plus unsupported factual prose and forged policy/URL/hash text | 503 | UNAVAILABLE | No | 26.653 |
| Paraphrase outside accepted language | 503 | UNAVAILABLE | No | 31.819 |
| Native Gemini HTTP error control | 400 | PROVIDER_ERROR | No | 31.177 |
| Native Gemini mock timeout exception | 504 | PROVIDER_ERROR | No | 32.503 |
| Missing-plugin controlled-provider control | 503 | INGRESS_REFUSED | No | 184.618 |
| Controlled-provider HTTP error | 400 | PROVIDER_ERROR | No | 33.215 |

All eight expectations passed. The relay recorded six simulated attempts, four completed responses, two failed calls and zero cancellations; **zero real provider invocations**. The last two cases use the separate controlled provider and cannot consume a paid model call. Readiness consumed neither model nor source budget. The approved content hash matched the exact native provider text; client metadata and refusal projections were checked. Private-service connections from the qualification client were denied. All source observations retained fixture identity; no source fetch was live. Token/cost usage is null, not invented zero; simulated zero-rate reservations are not real billing measurements. Timings are local client observations, not provider or production performance claims.

Two failed offline experiments preceded success. Run `20261118T183216Z-32c8e507` passed readiness but made zero relay admissions; its client cases failed expected behavior. A second run, `20261118T183349Z-f8556d7b`, added fixed rejection categories and sanitized client summaries: all six native attempts were rejected at `root_fields` with safe provider-error HTTP 429. Reinspection of `GeminiGenerationRequest` demonstrated that the pinned native request includes a `model` body field. The relay's initial root allowlist had omitted it. Admission now requires that field to equal trusted configuration; request bytes still pass unchanged. No enforcement check was relaxed and no provider output was repaired. Both failed runs cleaned up; their artifacts are preserved. Later successful collections are retained separately rather than overwriting failures.

## Commands and observed checks

Commands below ran during this task. The initial full native build used Docker's selected `desktop-linux` builder; subsequent builds used the existing `epochguard-002a` cache. The plugin source was unchanged, so later stages reused cached plugin checks; the initial native build executed plugin unit/race checks. Race detection covers unit execution, not the actual gateway process. Existing verifier C/E/G/G-L images were reused from the unchanged pinned baseline; the native and new model images were rebuilt. This is not a cold installation claim.

| Command | Observed result |
| --- | --- |
| `docker buildx build --load -t epochguard-dev:002a -f dev/Dockerfile .` | Passed pinned upstream fetch/manifest equivalence, plugin format/vet/unit/race/build, ingress unit/race, command checks and dynamic ELF inspection |
| `docker buildx build --builder epochguard-002a --load -t epochguard-dev:002a -f dev/Dockerfile .` | Passed final ingress admission and explicit profile negative-control tests; matched native/plugin build |
| `docker build --load -t epochguard-model:005c -f dev/Dockerfile.model .` | Passed; separate relay/client image, no embedded credential |
| `docker buildx build --builder epochguard-002a --target go -f dev/Dockerfile.checks .` | Passed pinned format/vet, all internal/command unit and race tests, plugin compilation |
| `docker buildx build --builder epochguard-002a --target python -f dev/Dockerfile.checks .` | 632 passed, one live test deselected, one existing Starlette/httpx deprecation warning; 7 launcher and 2 documentation-checker tests passed; test stages network-disabled |
| `.venv-003a/Scripts/python.exe -m pytest -c services/verifier/pytest.ini -p no:cacheprovider tests/modelqualification -q` with `PYTHONPATH=tests;services/verifier;services/claim_analysis` | 17 passed, socket-denying fixtures; mock adapters are plumbing evidence only |
| `.venv-003a/Scripts/python.exe tests/modelqualification/qualify.py` | Final eight-case native gateway run passed, source-bound report written only after successful cleanup |
| `py -3.12 tests/boundedprose/qualify.py` | G passed; 56.563s host process, request substitution/receipt/metadata/fallback/fault/overload/lifecycle controls |
| `py -3.12 tests/boundedproselive/qualify.py` | G-L offline passed; 34.500s, simulated evidence and source identity boundary |
| `py -3.12 tests/protectedingress/qualify.py` | D passed; 71.609s, explicitly legacy v1 lifecycle checks |
| `py -3.12 tests/livequalification/qualify.py` | E offline passed; 51.625s, simulated source failures and legacy v1 |
| `.venv-003a/Scripts/python.exe tests/modelqualification/analysis.py --output artifacts/005c/analysis-005c-final.json` | 18 draft cases, zero model attempts, explicit missing Gemini cells |
| `py -3.12 scripts/check_docs.py` | Passed links/anchors/repository references and document secret-pattern checks |
| `py -3.12 -m unittest discover -s scripts -p 'test_*.py'` | 2 passed |
| `py -3.12 -m unittest discover -s tests/lab -p test_manage.py` | 7 passed |
| `docker run --rm --network none --mount "type=bind,source=$($PWD.Path),target=/src,readonly" --workdir /src rhysd/actionlint:1.7.12 -color .github/workflows/checks.yaml` | Passed |
| `docker compose --env-file dev/lab.compose.env -f compose.verify.005c.cleanup.yaml down --volumes --remove-orphans` | Passed; no remaining project resources to remove |

The combined mounted-source Python command also ran independently of the CI build, with 632 passed, one live test deselected and the same warning:

```powershell
docker run --rm --network none --mount "type=bind,source=$($PWD.Path),target=/src,readonly" --workdir /src -e PYTHONPATH=/src/tests:/src/services/verifier:/src/services/claim_analysis -e PYTHONDONTWRITEBYTECODE=1 epochguard-verifier:004gl python -B -m pytest -c /src/services/verifier/pytest.ini -p no:cacheprovider services/verifier/tests services/verifier/tests_multiclaim services/verifier/tests_gateway services/verifier/tests_live services/verifier/tests_prose services/verifier/tests_bounded_prose services/verifier/tests_live_g services/claim_analysis/tests tests/modelqualification -q
```

The four historical gateway drivers ran sequentially with `COMPOSE_DISABLE_ENV_FILE=1`, `COMPOSE_ENV_FILES` selecting `dev/lab.compose.env`, and inherited live/model/source credentials and opt-ins removed. No credential file was supplied and no live marker selected. Cleanup inspection counted zero containers, networks and volumes for 005C, G, G-L offline, D and E offline, including all task-owned signing volumes. Existing unrelated resources were retained. The complete 31-file change set had no known credential-prefix/private-key-pattern matches. Historical tracked 004A/004F datasets/results and 004G-L reports were not modified.

Not executed: real-model gateway calls, real Gemini extraction evaluation, combined model/live-source calls, independent human annotation review, hosted CI on these changes, a new frontend/browser run or a cold rebuild of the entire operator image chain. Existing frontend source is unchanged. These omissions do not become model-quality or production-readiness claims.

## Changed-file inventory

| Area | Exact files |
| --- | --- |
| Ingress | `internal/ingress/ingress.go`, `internal/ingress/model_test.go`, `cmd/protected-ingress/main.go` |
| Isolated deployment | `compose.verify.005c.yaml`, `compose.verify.005c.live.yaml`, `compose.verify.005c.cleanup.yaml`, `dev/Dockerfile.model`, `dev/model/start-gateway.sh`, `dev/model/settings.example.json` |
| Qualification and controls | `tests/modelqualification/__init__.py`, `tests/modelqualification/common.py`, `tests/modelqualification/relay.py`, `tests/modelqualification/runner.py`, `tests/modelqualification/qualify.py`, `tests/modelqualification/conftest.py`, `tests/modelqualification/test_controls.py` |
| Analysis and packet | `tests/modelqualification/analysis.py`, `tests/modelqualification/data/README.md`, `tests/modelqualification/data/manifest.v1.json`, `tests/modelqualification/data/review-packet.v1.json` |
| Offline CI | `dev/Dockerfile.checks`, `.github/workflows/checks.yaml` |
| Canonical documentation | `README.md`, `CONTRIBUTING.md`, `docs/architecture.md`, `docs/compatibility.md`, `docs/security.md`, `docs/operations.md`, `docs/evaluation.md` |
| New guides and evidence | `docs/real-model-qualification.md`, `docs/task-005c.md` |

Run outputs and temporary audit helpers remain in ignored `artifacts/005c/`; they are not published source. No raw live provider output, private prompt, secret or internal receipt is included in this report.

## Remaining qualification

Independent human review, actual authorized Gemini generation/extraction and inspection of their sanitized reports remain pending. A real-model plus real-source mode is neither executed nor enabled. Provider availability, current pricing, model compliance, remote cancellation/billing and production credential management remain operator/provider boundaries. General semantic completeness, production readiness, arbitrary transports, caching and per-claim freshness scoring are not claimed.
