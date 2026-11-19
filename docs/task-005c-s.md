# Task 005C-S — bounded Gemini signature compatibility audit

## Result and requirement

Baseline: `0f5296ae9e7de2509d3781684a9e85e277b9439f`. **Compatibility adjustment withheld: the current converted representation is ambiguous.** This task does not meet `IMPLEMENTATION COMPLETE / LIVE QUALIFICATION PENDING`: the signature-bearing support case still fails closed before verification. The requested Stage 1 condition requires reporting this limitation rather than weakening eligibility.

The preserved latest real run, `artifacts/005c/live/20261118T205130Z-06b231a3`, records four HTTP 200 responses, exact intended visible text, STOP, one text part carrying `thoughtSignature`, and native `unsupported_provider_annotations` before verifier work. This establishes that run's compatibility blocker. It does not establish successful factual verification, and does not retroactively determine the older run's unrecorded structure.

The objective requires admitting that sole-signature case while refusing tools, reasoning, grounding, multimodal output, extra candidates/parts and ambiguous representations. A typed-only change cannot satisfy both sides under the inspected converter. No eligibility, attestation, response projection, model selection, token/thinking configuration, policy, module or receipt change was made. No paid model or real-source request was executed.

## Pinned contract inspection

Inspected the actual core `v1.14.1` export and compiled its converter in the existing pinned Linux/amd64 native build. Source Git blob hashes:

| Source | Blob SHA |
| --- | --- |
| `core/providers/gemini/chat.go` | `aa3b8e562b7ab64723c53960e1b8fbdda039f64e` |
| `core/providers/gemini/gemini.go` | `af11e1db8e50f9836752cab9e60e082b1325205c` |
| `core/schemas/chatcompletions.go` | `482f894c330754ed71c777057515261b11517928` |

The host/plugin remain pinned together to core `v1.14.1`, framework `v1.11.1`, transport revision `e869c3f9adc96ea53c38694a21bb04a8e1085487` and Go `1.27.3`. No upstream source or module manifest is patched. Historical [005C-R](task-005c-r.md) describes the prior refusal instrumentation; this audit adds conversion-collision tests.

For a single nonempty visible text part with a nonempty signature, the converter produces:

| Typed field | Observed representation |
| --- | --- |
| Chat object / choices / finish | `chat.completion`, one choice, `stop` |
| Assistant content | `ContentStr` points to the original visible text; `ContentBlocks` is nil |
| Assistant metadata | Non-nil `ChatAssistantMessage`; only `ReasoningDetails` is populated |
| Reasoning details | One entry: `Index=0`, `Type=reasoning.encrypted`, `Signature` points to the canonical standard-base64 signature |
| Other reasoning-detail fields | `ID`, `Summary`, `Text`, `Data` are nil |
| Other assistant fields | `Refusal`, `Audio`, `Reasoning` nil; images, annotations and tool calls empty |

The input signature is decoded to bytes by the native Gemini schema and re-encoded by conversion. Its bytes are opaque and untrusted; neither their presence, format nor value proves correctness, freshness or trusted origin.

The original strict `bufferedCandidate()` refuses the non-nil assistant union. `multiDecisionSource.Decide` uses that shared check before the Python POST. Successful attestation independently calls the strict helper, and post-conversion `attestedBody()` permits only role/content in an approved assistant message. Simply loosening one typed check would therefore be both insufficient for release and unsafe as an eligibility policy. Legacy profiles must retain their existing checks.

## Demonstrated ambiguity

`signature_contract_test.go` invokes the actual pinned `GenerateContentResponse.ToBifrostChatResponse`, then checks the **entire converted Bifrost response** with `reflect.DeepEqual`. All four altered inputs below produce the same response as the sole text-plus-signature input:

| Alteration | Why typed output cannot distinguish it |
| --- | --- |
| Add a neighboring `fileData` image part | This chat converter does not preserve the part |
| Add `fileData` to the text/signature part | The recognized file-data field is not represented in this converted output |
| Add a second native candidate with other text | Conversion selects `Candidates[0]` |
| Move the signature into a separate signature-only part | Conversion creates the same one encrypted entry with index zero |

The first three defeat the required multimodal/extra-candidate rejection if a signature-only typed allowlist is used. The fourth removes attachment/part provenance. Checking every assistant and reasoning-detail field, provider name, index, nil field, base64 form or visible-text digest cannot restore information that was discarded. Trusted request configuration asking for one answer also cannot prove that an untrusted provider returned only one candidate.

These are converter fixtures, not live responses, model-quality measurements or a mocked native loader. The gateway controls additionally submit supported finite text with an image-part neighbor and with a second native candidate. The retained signature refusal must continue to stop both before Python. The shared strict check was deliberately left intact.

The supported provider `send_back_raw_response` setting was identified during source inspection, but current generation does not retain that original envelope in its typed response by default. Enabling capture alone does not solve the problem: original-envelope validation, bounded in-memory ownership, exact text/structure correspondence, error handling and guaranteed exclusion of raw material from logs/client projection would all need a separately reviewed design. It must not be silently enabled or treated as evidence authority. A pre-conversion structural guarantee or a reviewed original-envelope validation path is needed before this compatibility change can meet its contract.

## Changes and qualification

Added Go representation/collision regressions and two synthetic native gateway controls. Existing response-shape batches remain offline-only and within their six-attempt limits; batch 3 now contains six cases, for 18 in total. No fixture is labeled real inference, and no relay field is stripped or response rewritten.

## Actual execution evidence

All four collision comparisons passed in Go unit execution and race execution against the actual pinned converter. Both added gateway controls passed through the real native loader, protected ingress and unchanged EpochGuard plugin: supported text/signature plus a neighboring image part, and supported text/signature plus a second native candidate, each returned `503 UNAVAILABLE` at `unsupported_provider_annotations`, with no verifier attempt. The sole-signature fixture also remains refused. These passes qualify the retained negative boundary, **not** the requested compatibility exception.

| Run under `artifacts/005c/offline/` | Scope | Result |
| --- | --- | --- |
| `20261119T074455Z-053c7293` | Ordinary 005C, eight cases | Existing support/contradiction/prose/paraphrase/provider error/timeout/missing-plugin controls passed |
| `20261119T074517Z-bc6a2b03` | Shape batch 1, six cases | Passed retained eligibility/verification expectations |
| `20261119T074536Z-7f9a0c70` | Shape batch 2, six cases | Passed; sole signature still UNAVAILABLE |
| `20261119T074558Z-85172d6a` | Shape batch 3, six cases | Passed, including both new signature-collision refusals |

Each run records baseline HEAD plus qualification input digest `1c7aff686c2c8af597d65234fa28e1fb8f581391a42b8ed07560a2c958e2add0`. Independent inspection matched those digests to current qualification source and all released content hashes to the observed original visible-text hashes. Those releases are existing plain-text controls. No signature-bearing candidate reached the verifier or achieved a supported ALLOW/contradicted REJECT, so the task's compatibility acceptance remains unmet. No synthetic result is described as a real-model result.

| Command actually executed | Result |
| --- | --- |
| `docker buildx build --builder epochguard-002a --load -t epochguard-dev:002a -f dev/Dockerfile .` | Passed pinned host/plugin module equivalence, format, vet, plugin and ingress unit/race checks, native compilation and dynamic executable checks |
| `docker build --load -t epochguard-model:005c -f dev/Dockerfile.model .` | Passed fixture/client image build |
| `.venv-003a/Scripts/python.exe tests/modelqualification/qualify.py` | Eight ordinary offline gateway cases passed; host process 21.328s |
| `.venv-003a/Scripts/python.exe tests/modelqualification/qualify.py --shape-batch 1` | Six native cases passed; 19.500s |
| `.venv-003a/Scripts/python.exe tests/modelqualification/qualify.py --shape-batch 2` | Six native cases passed; 22.078s |
| `.venv-003a/Scripts/python.exe tests/modelqualification/qualify.py --shape-batch 3` | Six native cases passed; 21.125s |
| `.venv-003a/Scripts/python.exe tests/boundedprose/qualify.py` | G security/lifecycle passed; 61.609s. Includes request substitution/retained nonce, receipt replay/mismatch/policy/age/downgrade/malformed checks, metadata projection, missing/disabled/restarted plugin, provider/fallback, concurrency/overload and timeout controls |
| `.venv-003a/Scripts/python.exe tests/boundedproselive/qualify.py` | G-L offline passed; 46.266s. Simulated evidence and source-mode controls |
| `docker buildx build --builder epochguard-002a --target go -f dev/Dockerfile.checks .` | Passed full pinned Go format/vet/unit/race checks and plugin compilation; unchanged internal/command checks reused their caches |
| `docker buildx build --builder epochguard-002a --target python -f dev/Dockerfile.checks .` | 652 passed, one live test deselected, one existing Starlette/httpx deprecation warning; 7 launcher and 2 documentation-checker tests passed. Test stages network-disabled |
| `.venv-003a/Scripts/python.exe -m pytest -c services/verifier/pytest.ini -p no:cacheprovider tests/modelqualification -q` with `PYTHONPATH=tests;services/verifier;services/claim_analysis` | 37 passed with socket-denying fixtures |
| `py -3.12 scripts/check_docs.py`; `git diff --check` | Passed links, anchors, paths and whitespace checks |

Gateway drivers ran sequentially with live/model/source opt-ins and credentials removed, `.env` bypassed and internal networks only. Fixtures use simulated evidence rather than origin fetches. Native and fixture images were rebuilt; unchanged verifier images were reused. Race detection covers unit execution, not the actual gateway process. Public build dependencies are distinct from model/evidence calls. This is not a cold installation or production performance claim.

Final SHA-256 inspection confirmed both historical real-run directories unchanged, six files each, with unchanged membership. Docker label-filtered inspection found zero task-owned containers, networks and volumes for 005C, G and G-L offline, including signing volumes. A known credential-prefix/private-key-pattern scan of all ten changed files found no matches. PowerShell parser inspection found zero syntax errors across 20 fenced command blocks in the operator/operations guides. These are bounded checks, not general secret-detection or security proofs.

## Changed-file inventory

| Area | Exact files |
| --- | --- |
| Pinned conversion proof | `plugins/epochguard/signature_contract_test.go` |
| Synthetic gateway controls | `tests/modelqualification/response_shapes.py` |
| Canonical capability and security information | `README.md`, `docs/architecture.md`, `docs/security.md`, `docs/compatibility.md`, `docs/operations.md`, `docs/evaluation.md`, `docs/real-model-qualification.md` |
| Contract audit and evidence | `docs/task-005c-s.md` |

Audit helpers/results remain ignored under `artifacts/005c-s/`; gateway collections retain unique offline directories. Historical task reports, both live runs, dataset/prompt/schema files, runtime enforcement, signing/ingress code, provider configuration, license and publication settings are unchanged.

## Remaining limitation

The exact latest live refusal is established, but safe signature compatibility is not implemented. Original structural information must be available and independently bound to the candidate before an exception can enforce the requested rejection of ambiguous/multimodal/extra-candidate responses. No new real-model ALLOW/REJECT, real-source run, hosted CI, browser qualification or 005D work was performed. Even a future safe structural path would still require the existing independent grammar/evidence checks, minimal envelope and a separately authorized live qualification. This audit does not establish general semantic completeness or production readiness.
