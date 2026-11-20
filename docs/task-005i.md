# 005I — General evidence-assisted claim assessment

## Scope and status

The Experimental Evidence Explorer implements a separate single-claim assessment pipeline and local interface. Live mode performs bounded Tavily Search followed by a dedicated Gemini semantic assessment; default mode uses explicitly simulated HTTP transports. Every result is `experimental-evidence`, `authorization=false`, with no signature, receipt or gateway authorization. The protected system remains independently implemented and unchanged.

Implementation baseline: `dab1fc6db4dfa24094693d09beb030ff1d7a5bae`. Local execution occurred November 20, 2026 IST / November 19 UTC. The frozen packet uses an explicit November 20 UTC reference clock; the running service uses its actual UTC clock. Implementation and offline plumbing are tested. **Live semantic assessment qualification is pending**; no paid Gemini/Tavily request or live source API call was made. Public documentation and source pages were inspected to design the integration and author fixtures; that is not a live assessment execution.

## Pipeline and isolation

1. The loopback-only FastAPI application accepts an exact original claim, at most 512 characters / 2048 UTF-8 bytes, in a 4096-byte JSON request. Extra fields, duplicate keys, nonfinite constants, invalid text and unknown routes refuse. Valid claims retain original whitespace and bytes; malformed requests return a null claim with a fixed error category.
2. A conservative English scope check abstains on obvious multiple sentences, conjunctions, questions, unresolved pronouns and subjective markers. More subtle scope decisions remain model-assessed. Admission permits at most two active assessments and four active HTTP bodies; there is no unbounded provider queue.
3. Before search, an atomic per-process budget reserves one search plus the maximum serialized prompt planning estimate and configured output limit. Reservations remain consumed after failure, timeout, cancellation or no model call. Live settings allow at most three requests; the documented smoke uses one. No retry or fallback exists.
4. The fixed Tavily HTTPS `/search` client requests at most five basic/general results, with auto-parameters, generated answers, raw pages and images disabled. Every selected row must have a valid bounded HTTPS URL/title/snippet and valid optional metadata; an invalid row invalidates the whole set. No arbitrary URL is fetched. IDs S1–S5 are assigned locally.
5. The dedicated Gemini prompt treats claims and excerpts as untrusted data, asks for scope and exhaustive per-source stance/quotation records, and requests one strict structured JSON assessment. It does not modify the existing extraction prompt. The only reused analyzer helper converts a JSON schema to a provider hint; local strict validation remains authoritative. Generation uses one candidate, temperature zero and an explicit output ceiling. Tools, reasoning parts, extra parts, grounding/citation annotations and incomplete finishes cannot produce an assessment. An opaque same-part thought signature is ignored and never returned.
6. The validator binds the exact claim, all retrieved source IDs, unique citation IDs and exact snippet quote substrings. Decisive quotations need at least 20 characters after trimming whitespace. A conclusive result requires at least two cited publisher groups, matching decisive stances, no conflicting/unclear relevant stance, and no declared uncertainty about independence. Copies and near-copies abstain before model submission. Missing/invalid evidence, provider errors, malformed output, conflict and unresolved corroboration yield INSUFFICIENT_EVIDENCE.
7. The page displays SUPPORTED, CONTRADICTED or INSUFFICIENT_EVIDENCE, explanation, uncertainty, actual retrieved source links and simulated/live labeling. Retrieval and unverified publication metadata are distinct. Text nodes prevent HTML interpretation; editing the claim aborts/invalidates old results. No source text or provider diagnostic is inserted as markup.

The service has no plugin, receipt key, protected ingress target or verifier fallback. The original `/extract` source retriever, nine-form grammar, Python/PyPI policy, native plugin, Gemini gateway adaptation, receipt-v2 validation and release rules are unmodified. A comparison against the baseline found no changes under their production paths or historical task reports. An LF-normalized digest over 85 existing plugin/ingress/verifier/claim-analysis source files was recorded as `c2115cb47d9f78615edc578c72d7e7643e87d23ec260c313e24f0f7eddcbcfc1`. This local digest is a preservation aid, not an independent source-origin attestation.

The [Tavily Search API contract](https://docs.tavily.com/documentation/api-reference/endpoint/search) and [Gemini generateContent contract](https://ai.google.dev/api/generate-content) informed the fixed endpoints and payloads. Endpoint/payload tests inspect the actual outgoing HTTP requests with simulated transports. No user-selectable endpoint, redirect following, tool access or raw provider error reflection is added.

## Frozen evaluation and actual outcomes

The [packet provenance](../services/evidence_assessment/data/README.md) identifies authored search paraphrases and authored model replies, representative public URLs, the reference clock and non-human-reviewed labels. SHA-256: `77deb8d225124aca38d9fbd177056b798d8fad0124a112e702e3aae73c098e04`. Altered packet bytes refuse loading. The default simulated UI exposes only designated demonstration rows; unfamiliar claims have no simulated evidence. Core live pipeline code contains no target claim or fixed verdict.

The final packet evaluator ran inside the Explorer image with `--network none`. **19/19** expected assessments, reasons and invocation counts matched: 2 SUPPORTED, 2 CONTRADICTED, 15 INSUFFICIENT_EVIDENCE; every case preserved its valid original claim and `authorization=false`. Total invocations: **16 simulated searches / 11 simulated model submissions**. Each row has one-case denominator; counts below are actual search/model calls, including failed submissions.

| Case | Actual assessment | Actual reason | Search/model |
| --- | --- | --- | --- |
| Incorrect current officeholder, target Trump/Japan statement | CONTRADICTED | AI_EVIDENCE_ASSESSMENT | 1/1 |
| Correct current officeholder | SUPPORTED | AI_EVIDENCE_ASSESSMENT | 1/1 |
| Stable gold-symbol assertion | SUPPORTED | AI_EVIDENCE_ASSESSMENT | 1/1 |
| Incorrect Apollo historical assertion | CONTRADICTED | AI_EVIDENCE_ASSESSMENT | 1/1 |
| Ambiguous pronoun | INSUFFICIENT_EVIDENCE | SCOPE_ABSTENTION | 0/0 |
| Subjective preference | INSUFFICIENT_EVIDENCE | SCOPE_ABSTENTION | 0/0 |
| Multiple claims | INSUFFICIENT_EVIDENCE | SCOPE_ABSTENTION | 0/0 |
| Unanswerable statement | INSUFFICIENT_EVIDENCE | SCOPE_ABSTENTION | 1/1 |
| Missing evidence | INSUFFICIENT_EVIDENCE | INSUFFICIENT_SOURCES | 1/0 |
| Conflicting results | INSUFFICIENT_EVIDENCE | SOURCE_DISAGREEMENT | 1/1 |
| Search timeout | INSUFFICIENT_EVIDENCE | SEARCH_TIMEOUT | 1/0 |
| Model timeout | INSUFFICIENT_EVIDENCE | MODEL_TIMEOUT | 1/1 |
| Injected source instructions and hostile model fields | INSUFFICIENT_EVIDENCE | INVALID_MODEL_OUTPUT | 1/1 |
| Forged citation | INSUFFICIENT_EVIDENCE | INVALID_MODEL_OUTPUT | 1/1 |
| Forged quotation | INSUFFICIENT_EVIDENCE | INVALID_MODEL_OUTPUT | 1/1 |
| Partially invalid search set | INSUFFICIENT_EVIDENCE | INVALID_SEARCH_EVIDENCE | 1/0 |
| Same publisher on two pages | INSUFFICIENT_EVIDENCE | INSUFFICIENT_SOURCES | 1/0 |
| Copied excerpts | INSUFFICIENT_EVIDENCE | DUPLICATED_EVIDENCE | 1/0 |
| Model-detected subjective scope | INSUFFICIENT_EVIDENCE | SCOPE_ABSTENTION | 1/1 |

The actual container HTTP smoke passed **3/3** demonstrations, each with two bounded supplied sources: target CONTRADICTED (S1/S2 citations), unrelated gold statement SUPPORTED (S1/S2), and unanswerable statement INSUFFICIENT_EVIDENCE (no decisive citations). Headless Edge independently displayed all three expected outcomes, checked external HTTPS link attributes, cleared stale results after editing and passed a 390-pixel mobile overflow check. These are genuine running backend/browser observations with simulated providers, **not real Gemini accuracy or current source-freshness evidence**.

## Commands and regression evidence

Commands ran from the repository root in PowerShell. The existing `.venv-003a` used locked shared Python dependencies plus the one pinned PSL dependency; no existing lock was changed.

| Actual command / selection | Observed result |
| --- | --- |
| `.venv-003a/Scripts/python.exe -B -m pytest services/evidence_assessment/tests tests/evidence_assessment/test_explorer_manage.py -q --tb=short` with the two service directories on PYTHONPATH | 96 passed in 1.26 seconds: 90 service tests and 6 lifecycle tests |
| `docker build --progress=plain -t epochguard-explorer:005i -f services/evidence_assessment/Dockerfile .` | Successful final image; 90 service tests passed with `RUN --network=none` |
| `docker build --progress=plain --target python -t epochguard-checks:005i-python -f dev/Dockerfile.checks .` | 1,315 passed, 1 deselected by existing marker selection; 6 Explorer lifecycle, 7 Lab lifecycle and 2 documentation-tool unittests passed separately, all test stages network-disabled |
| `docker build --progress=plain --target go -t epochguard-checks:005i-go -f dev/Dockerfile.checks .` | Pinned native plugin and root-module format/vet/unit/race checks and plugin compilation passed; race execution covers unit tests, not the gateway process |
| `docker run --rm --network none --read-only` with checkout mounted read-only at `/src`, writable `artifacts/005i` at `/output`, working directory `/src`, image `epochguard-explorer:005i`, command `python -B tests/evidence_assessment/evaluate.py /output/offline-packet-final` | 19/19 packet outcomes, 16/11 simulated invocations |
| `.venv-003a/Scripts/python.exe -B services/evidence_assessment/manage.py test` | Actual offline container HTTP 3/3; project cleanup verified |
| `.venv-003a/Scripts/python.exe -B services/evidence_assessment/manage.py up`, then `node tests/evidence_assessment/browser.cjs artifacts/005i/browser-1`, then `manage.py down` | Actual headless Edge 3/3; stale-result/mobile checks passed; cleanup verified |
| `.venv-003a/Scripts/python.exe -B tests/evidence_assessment/protected_smoke.py` | Actual existing protected ingress/Bifrost/native-plugin/Python/v2 path 5/5: 200 support, 403 older contradiction, 503 unsupported prose, 503 missing-plugin ingress refusal, distinct 400 provider error; exact bytes only for support |
| `.venv-003a/Scripts/python.exe -B scripts/check_docs.py`, then `.venv-003a/Scripts/python.exe -B -m unittest discover -s scripts -p 'test_*.py'` | 56 Markdown files, 354 local links, 60 anchor links and 45 repository paths validated; 2 tool tests passed |
| `git diff --check` | Passed; Git reported only configured LF/CRLF conversion notices |

The Python selection includes the existing verifier, multi-claim, gateway, live-transport mocks, prose/bounded prose, source, reporting, claim-analysis, model/combined qualification and variable-evidence regressions. It produced one existing Starlette TestClient/httpx deprecation warning. No `httpx2` dependency was introduced to suppress that warning. No hosted CI run or new full historical matrix execution is claimed.

Initial failed experiments are preserved: the first lifecycle cleanup manifest did not associate the named network with a service, leaving an orphan network, and the first Python build passed 1,313 tests but failed repository-private-file rejection because its `/src` image lacked AGENTS.md. Cleanup now names both the service and its network; root discovery also recognizes the shared repository lock path. Existing-resource preflight refused taking ownership until explicit cleanup. Corrected and final runs passed without loosening credential exclusion or evidence validation.

## Artifacts and identities

Ignored local outputs are under `artifacts/005i/`: `offline-packet-final/report.json` (per-case hashes, reasons, source/citation counts and elapsed nanoseconds), `browser-1/report.json` and `mobile.png`, final `*-http-smoke.json`, `20261119T204937529024Z-protected/report.json`, `focused-tests-final.log`, `build-explorer-qualified.log`, `checks-python-final.log` and `checks-go.log`. Earlier failed/corrected logs remain alongside them. There are no credentials, raw model error bodies, private source bodies or receipts in these reports.

The final packet report records implementation SHA-256 `b79198188d75fdcff1e8cad049e4bda57893b9aa54f18d85ac519d1f1b24e0bb` over normalized service package/assets. Image IDs are local immutable observations, not remote provenance attestations:

| Image | Observed immutable ID |
| --- | --- |
| Final Explorer | `sha256:29f441850db4f5339d1093c5a1c2729e687aef3486a7bb1a63d66f76f224aa7f` |
| Final Python check image | `sha256:c546ad4964a45169ee6494e5986a970fab132899056e73bb446c94218aa205db` |
| Go check image | `sha256:ad55075bf4ab954add3b0265951f01b1f562de9dcf6c52157d5ca645a24ef7be` |
| Reused protected native runtime | `sha256:1e0b3683aa31e01f4186edd813d9c9330849fc990958c75cf48e863088420d89` |
| Reused protected G verifier | `sha256:4a442170bff0e85874b9005c1d377d9716cb8ff132bfdc741a5ea72b13b46fc0` |

Both owned projects, `epochguard-005i` and `epochguard-005i-protected`, reported zero remaining containers, networks and volumes after cleanup. The protected disposable signing volume was removed. No lifecycle lock remained; images and evidence reports were retained. Historical 005C/005E and other qualification runs were not rewritten.

## File inventory

| Area | Files |
| --- | --- |
| New backend | `services/evidence_assessment/evidence_assessment/`: `schema.py`, `config.py`, `sources.py`, `providers.py`, `pipeline.py`, `factory.py`, `app.py`, `__init__.py` |
| New local UI | Same package's `web/index.html`, `web/app.js`, `web/app.css`; no framework or npm dependency |
| Packaging/lifecycle | `services/evidence_assessment/Dockerfile`, `requirements-extra.lock`, `manage.py`, intentionally incomplete `settings.example.json`; root `compose.explorer.yaml`, `.live.yaml`, `.cleanup.yaml` |
| Frozen packet and tests | `services/evidence_assessment/data/offline-v1.json`; three service test modules; `tests/evidence_assessment/build_packet.py`, `evaluate.py`, `test_explorer_manage.py`, `browser.cjs`, `protected_smoke.py` |
| Documentation and check selection | Service/packet READMEs, this report, root README, architecture, security, compatibility, operations, evaluation and third-party docs; `dev/Dockerfile.checks` includes the new isolated dependency/tests |

## Limits and separately authorized smoke

This is an English single-statement MVP. Conservative lexical scope checks can unnecessarily refuse legitimate coordinated names or miss complex multiple propositions. Model-assessed relevance, scope, stance, quote meaning and independence can be wrong. Exact quotes/citation IDs validate provenance within the supplied packet, not semantic truth, source honesty or injection immunity. Search snippets can omit essential context; there is no direct full-page retrieval. Current officeholders need execution-time evidence, and search-supplied publication dates remain unverified (missing timezone metadata is normalized to UTC).

Publisher groups use pinned `publicsuffix2==2.20191221`, bundled 2019 suffix data, selected common-owner groups and government grouping. Unknown suffixes refuse. Different registrable domains can still share owners, syndication or underlying evidence; copy detection and the model independence flag do not prove independence. This heuristic must not be described as independent-source attestation. The [third-party audit](third-party.md) records the additional license/data notice boundary.

Provider spend reservations are conservative application estimates, not billing counts or strict provider-side caps; rate accuracy, hidden accounting and restart remain operator concerns. The entry bridge is not a network firewall. Body/JSON/admission limits are tested controls, not a complete CPU/memory isolation claim. No public endpoint, tenant identity or production deployment is qualified. On Linux the private mounted files need UID/mapping configuration for the non-root service; Windows ACLs require operator inspection.

The [startup/live-smoke guide](../services/evidence_assessment/README.md#separately-authorized-live-smoke) is ready for one separately authorized search plus at most one model submission, with current model/prices, private external files and `max_requests=1`. No provider call occurs at startup. The live-factory regression constructs real HTTP clients with both opt-ins and confirms startup is source-free; it does not contact providers. A future smoke must inspect actual evidence and accept abstention when corroboration is unavailable. Real Gemini semantic accuracy, live provider compatibility and live source quality remain unmeasured here; existing protected qualifications are neither extended nor replaced.
