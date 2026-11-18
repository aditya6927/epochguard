# Task 005C-R — real Gemini refusal diagnostics

## Evidence and scope

Baseline: `4a45673d16946b466e77e975a95954efdd1d4d14`. The preserved run `artifacts/005c/live/20261118T193532Z-771f9f45` records four actual Gemini HTTPS submission attempts, all HTTP 200, and four authenticated protected `503 UNAVAILABLE` responses. No answer was released. Its verifier pipeline records and application source counters are zero. Missing-plugin and controlled-provider-error controls remained distinct, and cleanup succeeded. This establishes connectivity and safe non-release, not successful factual verification.

The original live artifacts are immutable diagnostic inputs. No additional model/source requests, model/token/thinking changes, eligibility relaxation, receipt change, license change or freshness scoring is part of this task. The prior 005C implementation report remains historical evidence.

## Source inspection and refusal gates

The exact pinned core `v1.14.1` sources were inspected from the local source export, with Git blob hashes checked against the earlier upstream inspection: `gemini.go` = `af11e1db8e50f9836752cab9e60e082b1325205c`, `chat.go` = `aa3b8e562b7ab64723c53960e1b8fbdda039f64e`, `types.go` = `310f133c77a27ac7ed645e215e1176a755e0969a`. The host/plugin manifest equivalence checks remain in the native build; the Go toolchain and module graph are unchanged.

| Gate | Behavior before the Python pipeline |
| --- | --- |
| Relay | Bounds HTTP body; passes admitted provider bytes unchanged. Its observation never authorizes delivery |
| Native Gemini provider | Checks HTTP result and decodes `GenerateContentResponse`; malformed JSON can become a Bifrost operation error |
| Native response conversion | Chooses the first candidate, maps finish reason, represents one visible text block as a string and multiple blocks as structured content. Thought text/signatures and grounding information can create assistant reasoning/annotations |
| `enforce()` | Preserves provider/Bifrost errors; requires a chat response, active source and usable context before calling the decision source |
| `bufferedCandidate()` | Requires one complete non-streaming plain assistant string, finish `stop`, no tool/reasoning/annotation union and no unsupported response features |
| Multi/prose eligibility | Applies text/control/size bounds, rejects mixed response unions and additional provider filter/diagnostic/extra fields |
| Request preparation | Creates a request ID, marshals a bounded verifier body and constructs a context-bound POST; live remaining-work limits apply only to their existing configured source profile |
| Verifier HTTP hop | Transport, timeout, admission and schema errors can prevent a Python pipeline record. Zero recorded pipeline requests alone does not prove zero attempted HTTP exchanges |
| Independent validation | After a response, Go strictly validates policy, source, request/candidate bindings, grammar coverage and evidence before the existing signed response/ingress release checks |

The legacy relay required exactly one `STOP` candidate and every part to contain only `text`/`thought` with a string text field before computing a hash. A signature or another extra field could suppress all three text observations even with visible text present. Usage was observed separately only after that branch completed. Consequently null hashes are not evidence of absent model text or of an exhausted output budget.

The source converter places nonempty `thoughtSignature` data into `ReasoningDetails`, then allocates `ChatAssistantMessage`. The existing eligibility restriction refuses that union, even if its visible text matches the finite language. This is a concrete candidate-boundary mechanism to reproduce offline, not an established description of the original live responses. Raw provider bodies were intentionally not retained, so finish reason, part structure and the exact historical Go refusal point cannot be recovered from those records.

## Diagnostic design

The qualification relay now records bounded structural observations: envelope parsing, capped candidate count, fixed finish categories, content/parts presence and types, visible-text presence/emptiness, thinking-only output, grammar applicability and reported output usage without a single stopped visible text part. Arbitrary finish strings and unknown field names are categorized; values are never exported. At most four candidate summaries and 64 part summaries per candidate are retained. One original visible text part can be hashed/parsed without stripping metadata; multiple parts are not concatenated or repaired. These observations are not native eligibility or factual approval.

Native instrumentation reuses the request-owned hook trace. Trusted `qualification_diagnostics: true` is accepted only for explicit fixture-evidence bounded prose with v2 attestation. The 005C generator enables it; other configurations default off. It records fixed stage enums and the existing actual-request digest into `/tmp/epochguard-005cr.jsonl`, mode 0600, in the gateway's existing private tmpfs. Output is capped at 64 KiB and 16 stages per exchange, serialized across reconfiguration and emitted once in HTTP post processing. No pooled gateway object is retained. Sink errors are swallowed without changing the decision or receipt.

The host operator role collects this fixed file using private Docker exec and joins its request digests to the sanitized client report. No new client header, protected response field, HTTP endpoint, port or general log is introduced. Gateway stdout/stderr remain suppressed. No prompt, model/thinking text, signature, credential, provider error string, source body or receipt is written to this file. Diagnostic records remain non-authorizing; collection failure cannot qualify a run.

Stages distinguish provider/Bifrost errors, missing chat, rejected buffered shape, unsupported finish, provider annotations, eligible candidate, verifier attempt/completion, transport/body failure and policy/contract refusal or approval. `verifier_request_completed` means an HTTP response was received, not that its body/evidence passed validation. The following body/contract stage preserves that distinction. An operation error marked by Bifrost is an error-origin classification; it is not an invented proof of one precise internal converter exception.

## Offline fixtures and validation

The separate `--shape-batch` mode is offline-only. Six or fewer synthetic Gemini envelopes pass through the actual native provider/loader per disposable stack. It cannot run with `--live`, and the relay refuses shape prompts before live transport. Batches preserve the existing six-attempt offline ceiling and the four-attempt live ceiling; no budget increase or paid reset path is introduced. Evidence remains simulated. Fixtures cover STOP, MAX_TOKENS, empty candidates/content/parts/text, thinking-only, visible text with a thought signature, unknown structural metadata, grounding annotations, malformed JSON, unsupported prose, contradiction, thinking plus text, multiple text parts and unknown finish reasons.

## Actual gateway results

All 16 response-shape cases passed through the actual pinned native gateway, plugin and protected ingress. Evidence was simulated; no new real model or origin-source request occurred. Three disposable runs under `artifacts/005c/offline/` retained the full sanitized observations:

| Run | Cases | Result |
| --- | --- | --- |
| `20261118T200739Z-219752d9` | Batch 1, six cases | Passed |
| `20261118T200804Z-dfe136f5` | Batch 2, six cases | Passed |
| `20261118T200824Z-a358bb90` | Batch 3, four cases | Passed |

Each has source revision `4a45673d16946b466e77e975a95954efdd1d4d14` plus qualification input digest `4897aebb1a57ab421cfce5858e46568586dedfa0ea44256a9cb1ee2b586c9be0`. This digest now also includes native plugin source/manifests, preventing reuse of the prior implementation's preflight. It identifies inputs, not factual correctness. Collection and cleanup succeeded.

| Synthetic response | Protected outcome | Localized native stage | Verifier POST attempted |
| --- | --- | --- | --- |
| STOP, one plain supported part | ALLOW / 200 | `evidence_policy_validated` | Yes |
| MAX_TOKENS with visible text | UNAVAILABLE / 503 | `unsupported_finish_reason` | No |
| Empty candidates | UNAVAILABLE / 503 | `buffered_candidate_shape` | No |
| STOP without content | UNAVAILABLE / 503 | `evidence_policy_validation_refused` | Yes |
| STOP without parts | UNAVAILABLE / 503 | `evidence_policy_validation_refused` | Yes |
| Thinking-only part | UNAVAILABLE / 503 | `unsupported_provider_annotations` | No |
| Supported text plus thought signature | UNAVAILABLE / 503 | `unsupported_provider_annotations` | No |
| Supported text plus an unknown structural field | ALLOW / 200 | `evidence_policy_validated` | Yes |
| Supported text plus grounding annotations | UNAVAILABLE / 503 | `unsupported_provider_annotations` | No |
| Malformed provider JSON | INGRESS_REFUSED / 503 | `provider_bifrost_failure` | No |
| STOP, unsupported factual prose | UNAVAILABLE / 503 | `evidence_policy_validation_refused` | Yes |
| STOP, older version | REJECT / 403 | `evidence_policy_validation_refused` | Yes |
| Visible text plus thinking | UNAVAILABLE / 503 | `unsupported_provider_annotations` | No |
| Two visible text parts | UNAVAILABLE / 503 | `buffered_candidate_shape` | No |
| Unknown finish value | UNAVAILABLE / 503 | `unsupported_finish_reason` | No |
| Empty visible text | UNAVAILABLE / 503 | `evidence_policy_validation_refused` | Yes |

Missing content/parts under STOP becomes an empty native assistant string in this converter; that still fails schema/coverage at the verifier HTTP boundary. It cannot authorize an empty answer. The unknown structural field is ignored by pinned native conversion, while approved visible content is verified unchanged and the field is absent from client output. This single observed drop behavior does not qualify arbitrary provider annotations. Recognized signatures/reasoning/grounding remain refused. Malformed native JSON becomes a Bifrost error rather than a factual contradiction; existing ingress does not authenticate it as an approved policy outcome and refuses delivery. No eligibility predicate or metadata restriction was removed to obtain these results.

The ordinary eight-case 005C offline run also passed in `20261118T200716Z-9973d82b`, with stage observations joined to exact request digests. An independent saved-report check found all released content digests equal the relay's observed original text digests across all four runs. Simulated bytes were also compared exactly in the relay tests. These are synthetic transport/eligibility results, not recorded/replayed Gemini generations.

## Root-cause assessment and minimum correction

**Established:** the historical run reached the provider and safely refused all four candidates without recorded evidence-policy work. Its relay observability was incomplete: a null digest could hide visible text with structural metadata. That observability defect is corrected, and each relevant native refusal boundary can now be distinguished offline and in an independently authorized later qualification collection.

**Reproduced mechanism:** a supported single visible text part with a nonempty thought signature is recognized by the new observer, converted to native assistant reasoning metadata, and refused by unchanged Go eligibility with no verifier attempt. This reproduces the old null-hash condition and the pre-verifier non-release pattern. Thinking, incomplete finish, structured content and other annotation cases are separately localized.

**Not established:** the original Gemini finish reasons, actual parts/signatures, whether a generation limit was reached, and the exact old Go refusal event. The saved usage does not supply those facts. A general Bifrost conversion failure is not demonstrated by null telemetry, and the malformed-JSON control produces a different protected outcome. Likewise there is no recorded source-policy contradiction or evidence-freshness finding to attribute the refusals to. Verifier transport/admission/schema behavior before pipeline recording remains a historical uncertainty because no attempt trace was saved.

The smallest justified correction is the implemented bounded observability and private stage collection. There is no evidence justifying a generation-setting or eligibility change. The successful-release qualification remains unmet; confirming the actual historical structural hypothesis would require inspecting a new provider response during a separately authorized future run. This task made no such call and does not recommend silently stripping reasoning/signatures, raising token limits, selecting another model or changing thinking settings. Model claims and diagnostic hashes/stages never authorize release.

## Commands and actual checks

| Command | Observed result |
| --- | --- |
| `docker buildx build --builder epochguard-002a --load -t epochguard-dev:002a -f dev/Dockerfile .` | Final build passed pinned module equivalence, native dynamic gateway/plugin build, format, vet, unit and race checks; actual gateway execution separately tested below |
| `docker build --load -t epochguard-model:005c -f dev/Dockerfile.model .` | Passed diagnostic client/relay image build |
| `.venv-003a/Scripts/python.exe tests/modelqualification/qualify.py` | Eight standard offline cases passed with private stage collection; 23.500s host process |
| `.venv-003a/Scripts/python.exe tests/modelqualification/qualify.py --shape-batch 1` | Six native cases passed; 24.093s |
| `.venv-003a/Scripts/python.exe tests/modelqualification/qualify.py --shape-batch 2` | Six native cases passed; 20.922s |
| `.venv-003a/Scripts/python.exe tests/modelqualification/qualify.py --shape-batch 3` | Four native cases passed; 20.125s |
| `.venv-003a/Scripts/python.exe tests/boundedprose/qualify.py` | G passed; 83.516s. Request substitution/retained nonce, receipt replay/downgrade/mismatch/age/malformed, missing/disabled plugin, metadata, fallback, overload and lifecycle controls |
| `.venv-003a/Scripts/python.exe tests/boundedproselive/qualify.py` | G-L offline passed; 43.781s, simulated evidence/source-mode controls |
| `docker buildx build --builder epochguard-002a --target go -f dev/Dockerfile.checks .` | Passed format/vet, plugin unit/race/compilation and internal/command unit/race checks |
| `docker buildx build --builder epochguard-002a --target python -f dev/Dockerfile.checks .` | 650 passed, one live test deselected, one existing Starlette/httpx deprecation warning; 7 launcher and 2 documentation-checker unit tests passed, test stages network-disabled |
| `.venv-003a/Scripts/python.exe -m pytest -c services/verifier/pytest.ini -p no:cacheprovider tests/modelqualification -q` with `PYTHONPATH=tests;services/verifier;services/claim_analysis` | 35 passed with socket-denying fixtures |
| `py -3.12 scripts/check_docs.py` and `git diff --check` | Passed documentation links, anchors, references and whitespace checks |

The full mounted-source Python regression command ran independently of the image-build stage and also passed 650 tests, one live deselection and the existing warning:

```powershell
docker run --rm --network none --mount "type=bind,source=$($PWD.Path),target=/src,readonly" --workdir /src -e PYTHONPATH=/src/tests:/src/services/verifier:/src/services/claim_analysis -e PYTHONDONTWRITEBYTECODE=1 epochguard-verifier:004gl python -B -m pytest -c services/verifier/pytest.ini -p no:cacheprovider services/verifier/tests services/verifier/tests_multiclaim services/verifier/tests_gateway services/verifier/tests_live services/verifier/tests_prose services/verifier/tests_bounded_prose services/verifier/tests_live_g services/claim_analysis/tests tests/modelqualification -q
```

All gateway drivers ran sequentially with inherited live/model/source credentials and opt-ins removed, `.env` bypassed, and only internal offline networks. Go race detection covers unit execution, not the actual gateway process. No model API, Tavily or PyPI origin was contacted by these qualifications; public build dependencies are a separate network boundary. Existing verifier images were reused from unchanged source. Native and diagnostic images were rebuilt, without upstream or module changes. This is not a cold installation or production performance claim.

Two meaningful failed build experiments are preserved in ignored artifacts. The initial build found modules missing from an evicted Buildx cache and correctly failed its network-disabled test stage. A temporary dependency-only build from the unchanged pinned manifest refilled that cache; network-disabled tests remained enforced. The first native converter test then exposed an incorrect fixture expectation for empty candidates (`buffered_candidate_shape`, not the initially expected finish boundary). A diagnostic-only test rerun isolated vector 2, and its expected stage was corrected to the actual pinned behavior. Final builds and gateway batches passed; no enforcement predicate was weakened.

Final SHA-256 comparison confirmed all six original live-run files unchanged, with no added file in that directory. Independent source/content checks matched the four new run reports to the final qualification digest and every released text hash to the observed original part. Docker label-filtered inspection found zero containers, networks and volumes for 005C, G and G-L offline, including signing volumes. A known credential-prefix/private-key-pattern scan of all 21 changed files found no matches. PowerShell parser inspection found zero syntax errors in 21 fenced command blocks across the operator, operations and diagnostic guides. These are bounded checks, not a general secret-detection or security proof.

No hosted CI, new paid run, new real-source run, claim-analysis evaluation or frontend/browser qualification was performed. Those remain separate from this diagnostic milestone.

## Complete changed-file inventory

| Area | Exact files |
| --- | --- |
| Native instrumentation | `plugins/epochguard/qualification.go`, `plugins/epochguard/qualification_test.go`, `plugins/epochguard/main.go`, `plugins/epochguard/attestation.go`, `plugins/epochguard/decision.go`, `plugins/epochguard/http_decision.go`, `plugins/epochguard/multiclaim.go` |
| Relay observations and synthetic controls | `tests/modelqualification/response_observations.py`, `tests/modelqualification/response_shapes.py`, `tests/modelqualification/test_response_shapes.py`, `tests/modelqualification/relay.py`, `tests/modelqualification/runner.py`, `tests/modelqualification/qualify.py` |
| Canonical documentation | `README.md`, `docs/architecture.md`, `docs/security.md`, `docs/evaluation.md`, `docs/compatibility.md`, `docs/operations.md`, `docs/real-model-qualification.md` |
| Investigation report | `docs/task-005c-r.md` |

The 21-file implementation preserves historical 005C/004G-L reports, datasets, prompt/schema versions, module manifests, ingress code, receipt protocol and generation settings. Run artifacts/audit helpers remain ignored under `artifacts/005c-r/` and the existing unique offline run directories.
