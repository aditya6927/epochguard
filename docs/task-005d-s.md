# TASK 005D-S — Singleton-policy contradiction correction

## Result and tested revision

**005D-S SECURITY REMEDIATION COMPLETE / 005E OFFLINE REQUALIFIED**

The tested source is baseline `a1c1528c598d4ca261eb4ce8ab717d367d7b9d9f` plus the changes listed below, executed November 19, 2026. Baseline HEAD matched and the checkout was clean before reproduction. Corrected evidence is offline: simulated native Gemini HTTP, fixture source transports, the actual pinned Bifrost loader/converter, independent Go validation and protected ingress. No Gemini, Tavily or origin PyPI requests were made. Combined live qualification remains pending separate authorization and execution.

## Demonstrated vulnerability

The original exact-template grammar deduplicated full sentences. The bounded grammar deduplicated canonical policy/version sentences. Consequently, different versions of one policy remained distinct admitted claims. Sequential source observations could support both independently, even though the whole candidate asserted mutually inconsistent singleton values.

Before changing runtime code, `artifacts/005ds/capture_before.py` exercised the actual Python pipelines with two synthetic Python assertions, versions `3.15.1` and `3.15.2`. A sequential fixture retriever returned the respective primary labels, with fixed valid observation times. Both modes actually produced:

| Before-state observation | Exact templates | Bounded prose |
| --- | --- | --- |
| Admitted claims | 2 | 2 |
| Individual verdicts | SUPPORTED, SUPPORTED | SUPPORTED, SUPPORTED |
| Python aggregate | SUPPORTED | SUPPORTED |
| Python/PyPI retrieval calls | 2 / 0 | 2 / 0 |
| Independent Go validation | ALLOW | ALLOW |

The Python command was `.venv-003a/Scripts/python.exe artifacts/005ds/capture_before.py`. It saved the genuine synthetic records now retained in [the regression fixture](../tests/conformance/005ds-before.json). A temporary before-state assertion in `TestSingletonCapturedBefore` passed through `validateMulti` and `validateProse` during `docker buildx build --builder epochguard-002a --load -t epochguard-dev:005ds-before -f dev/Dockerfile .`. The actual Go log contains both baseline ALLOW observations; this was unit execution of the real independent validator, not a pre-fix protected gateway run. Logs are retained in `artifacts/005ds/before-python.log` and `before-native-build.log`; the capture helper is retained locally with them. The permanent test now requires independent refusal of exactly those captured records.

## Corrected contract and defense in depth

One candidate may contain **at most one assertion per fixed singleton policy**:

- `python-windows-latest-v1`.
- `pypi-requests-reported-v1`.

Python exact-template coverage and bounded-prose parsing each track policy identity independently. The two separately authored Go scanners do the same. A repeated policy returns the existing `REPEATED_CLAIM` reason whether versions differ, sentences repeat exactly or recognized paraphrases express the same version. All nine forms, exact policy identifiers, separators and version rules are unchanged.

Refusal is atomic: UNCERTAIN coverage, no required IDs/admitted mappings or evidence results, no retrieval and no approved text. Bounded verification is absent; exact-template extraction is NOT_RUN and the verdict is INSUFFICIENT. Protected delivery returns **503 UNAVAILABLE**, not a source-authenticated 403 contradiction. Scanners may encounter a repeat before the transport limit; no partial prefix is admitted.

With two policies, complete admitted coverage currently contains one or two distinct policy claims. The eight-claim transport/schema limits and existing byte/depth bounds remain unchanged. These limits serve different purposes; the wire can represent a refused or forged larger record without making it eligible.

Python `aggregate()` independently refuses duplicate required policies even when passed caller-supplied COMPLETE coverage and individually valid supported result objects. Existing result schemas already reparse candidates and compare complete coverage, extraction and original/canonical mappings; the regression proves that the captured COMPLETE/SUPPORTED records fail schema revalidation. No schema version or new reason code is needed.

Go `validateMulti()` reparses the exact candidate before trusting a declared result. Go `validateProse()` independently reconstructs original mappings and canonical text, then invokes `validateMulti()`. The captured forged records now return Unavailable with a contract error in each validator. Valid atomic refusal records return Unavailable normally. Existing evidence identity/mode/time/comparison rules, claim order/hash/span bindings, request-body and receipt-v2 binding, minimal client envelopes and error distinction remain enforced. No upstream Bifrost contract or response adapter changed.

This change does not make a signature, diagnostic score, grammar parse or HMAC into factual evidence. Recognized claims still require independent policy evidence.

## Reporting and conformance changes

005D reparses the original candidate. Repeated singleton policies now produce UNCERTAIN coverage, no admitted claim entries, no numeric scores or fabricated partial mappings, and `authorization=false`. The captured pre-fix forged result also yields no score entries. Null remains the representation for an unknown score on an admitted diagnostic entry; a refused candidate has an empty entry list.

The frozen 23-case reporting corpus retains its case names and source text. Its `eight-claims` case formerly expected REJECT with scores `[100, 0, 0, 0, 0, 0, 0, 0]`. Its corrected expectation is UNAVAILABLE, UNCERTAIN / REPEATED_CLAIM, no verification and no score entries. Only that case's record/report/expectation changed. Historical report exports were preserved.

Exact-template grammar parity vector 15 changes from CLAIM_LIMIT to REPEATED_CLAIM. Bounded parity vectors 11 and 12 change from BOUNDED_GRAMMAR and CLAIM_LIMIT respectively to REPEATED_CLAIM. The bounded corpus adds all 123 ordered pairs of same-policy forms with different, reversed and identical versions, for 158 vectors total. Python and independently authored Go scanners consume these vectors.

## Corrected 005E gateway evidence

The complete new suite is `artifacts/005e/offline/20261119T124323Z-b9a0bc6d/report.json`. It records all seven batches, 24 protected client cases plus expected failed sampling, `offline_passed=true` and completed cleanup. Its selected-source SHA-256 is `476d7dcc405e0e7d3398c49495f34613dfade2341a325e90998f311e22e54cd7`; running Python source SHA-256 is `853fa666b253a018e908e72f0b7613b144ca206abb219f5c87156e533477edff`. These identify the tested source graph, rather than treating the unchanged baseline commit alone as the corrected implementation.

| Rebuilt image pinned by the suite | Immutable ID |
| --- | --- |
| `epochguard-dev:002a` | `sha256:2242e765036451f4fcc3a2fb251550f4b319ad5c2461939acd7870feb571d5c0` |
| `epochguard-combined:005e` | `sha256:e8e917f48532fd1690838edf265c0cd3b25552fed8a3a620db9a48fb57eb6935` |

| Batch | Cases and result |
| --- | --- |
| Standard | 8 passed; two-policy supported 200 ALLOW, older contradiction 403, unsupported language/paraphrase 503, provider/ingress controls distinct |
| Faults | 3 passed; unavailable, malformed and exhausted source evidence refused |
| Identity | 4 passed; source mode/identity failures plus Python and PyPI repeated-policy controls, all 503 UNAVAILABLE |
| Clock | 2 passed; old/future observations refused |
| Envelopes | 6 passed; lossy original-envelope collisions refused before conversion |
| Drift | 1 passed; changed source safely returns 403; intentionally inconclusive as a stable-label qualification |
| Sampling failure | Expected preflight failure, zero model submissions, cleanup completed |

Both added conflict controls completed the real native-to-Python verification path and independent Go refusal: stages include `verifier_request_completed` and `evidence_policy_validation_refused`. Each has UNCERTAIN coverage, no claims/canonical digest, REPEATED_CLAIM, no approved-content digest and no released text. Source reservations stay **6 → 6** across each control: two preflight calls and four earlier identity-control retrievals had already occurred, and the conflicts themselves make zero calls. Diagnostic entries are empty and authorization remains false.

The ordinary supported two-policy control has COMPLETE/SUPPORTED verification, two valid evidence records and protected 200. Approved original-content SHA-256 is `fb6f13725b5d5f7e80e5058893307f7198ad91dfa76e10e1290f109850abc3bc`; the runner verifies exact equality with the eligible original visible text. Canonical comparison text retains its separate digest. Non-authorizing telemetry records before/after source reservations and grammar reason; the report checks these controls but never participates in release authorization.

## Commands and validation results

Native and verifier images were rebuilt from corrected runtime source. Commands used repository-root contexts:

```powershell
docker buildx build --builder epochguard-002a --load -t epochguard-dev:002a -f dev/Dockerfile .
docker buildx build --builder epochguard-002a --target go -f dev/Dockerfile.checks .
docker buildx build --builder desktop-linux --load -t epochguard-verifier:004c -f services/verifier/Dockerfile.004c .
docker buildx build --builder desktop-linux --load -t epochguard-verifier:004e -f services/verifier/Dockerfile.004e .
docker buildx build --builder desktop-linux --load -t epochguard-verifier:004g -f services/verifier/Dockerfile.004g .
docker buildx build --builder desktop-linux --load -t epochguard-verifier:004gl -f services/verifier/Dockerfile.004gl .
docker buildx build --builder desktop-linux --load -t epochguard-model:005c -f dev/Dockerfile.model .
docker buildx build --builder desktop-linux --load -t epochguard-combined:005e -f dev/Dockerfile.combined .
```

Both native Go check stages passed: gofmt cleanliness, vet, unit tests, race checks and plugin compilation with pinned Go 1.27.3 Linux/amd64 and the shared host/plugin graph. The broader checks target also vets/tests/race-tests all local ingress and command packages. Race instrumentation covers unit execution; actual gateway processes use the normal rebuilt plugin.

Full Python execution used the current checkout mounted read-only in a network-disabled container:

```powershell
docker run --rm --network none --mount "type=bind,source=$($PWD.Path),target=/src,readonly" --workdir /src/services/verifier -e PYTHONPATH=/src/tests:/src/services/verifier:/src/services/claim_analysis -e PYTHONDONTWRITEBYTECODE=1 epochguard-verifier:004gl python -B -m pytest -c /src/services/verifier/pytest.ini -p no:cacheprovider /src/services/verifier/tests /src/services/verifier/tests_multiclaim /src/services/verifier/tests_gateway /src/services/verifier/tests_live /src/services/verifier/tests_prose /src/services/verifier/tests_bounded_prose /src/services/verifier/tests_live_g /src/services/verifier/tests_claim_report /src/services/claim_analysis/tests /src/tests/modelqualification /src/tests/combinedqualification -q --tb=short
```

Result: **1,126 passed, 1 deliberately deselected live test**, one existing FastAPI/httpx deprecation warning. New singleton regressions cover both modes, both policies, sequence/reversal/identical versions, missing/malformed source controls with zero calls, every same-policy pairing of nine forms, actual captured forged results, valid singles/two-policy support, older contradiction, unavailable evidence, order/hash/span/source binding and unchanged transport bounds. Existing request-substitution, replay, policy-binding, metadata, timeout, cancellation and concurrency regressions also passed.

| Actual command | Result / retained evidence |
| --- | --- |
| `.venv-003a/Scripts/python.exe tests/combinedqualification/qualify.py` | Seven batches passed; new suite above |
| `.venv-003a/Scripts/python.exe tests/boundedprose/qualify.py` | G security/lifecycle passed, including plugin disable, restart window, recovery and runtime log isolation; rolling logs in `artifacts/004g/qualification/` |
| `.venv-003a/Scripts/python.exe tests/boundedproselive/qualify.py` | G-L offline passed; `20261119T124757Z-80c66345` |
| `.venv-003a/Scripts/python.exe tests/modelqualification/qualify.py --strict-adapter` | Passed; `20261119T124454Z-9b33bc9f` |
| Same command with `--adapter-batch 1` through `6`, each executed separately | All six collision batches passed; `20261119T124518Z-bd0d2e9d`, `124541Z-6a2b86e9`, `124603Z-fe75b04b`, `124624Z-42c63997`, `124644Z-5b509862`, `124703Z-d049724d` |
| `.venv-003a/Scripts/python.exe tests/modelqualification/qualify.py` | Native unadapted suite passed; `20261119T124814Z-2f5a15e8` |
| Same command with `--shape-batch 1` through `3`, each executed separately | All three response-shape batches passed; `20261119T124835Z-9f938483`, `124855Z-bec5b141`, `124915Z-4ff7fa52` |
| `.venv-003a/Scripts/python.exe tests/claimreporting/evaluate.py artifacts/005ds/reporting-evaluation` | 23 corrected reporting cases passed; JSON/HTML and evaluation retained |
| `py -3.12 scripts/check_docs.py` | Documentation/link validation passed |
| `py -3.12 -m unittest discover -s scripts -p 'test_*.py'` | Documentation-tool regression tests passed |
| `git diff --check` and modified/new-file whitespace scan | Passed |

The first focused Python run exposed a strict datetime test-decoding error; changing that test to JSON-mode validation fixed it. Initial image checks exposed the new test's conformance path under `/app` and an old CLAIM_LIMIT parity expectation. The fixture locator now supports both repository and image layouts, and the obsolete expectations were explicitly corrected. Final complete checks above passed; early logs are retained in `artifacts/005ds/`.

## Preservation and cleanup

Before reproduction, SHA-256 hashes were captured for 234 existing files across historical task reports, all real-model/live-source run files and previously saved 005E offline runs. A final audit found all unchanged, including the November 15/19 live evidence and `docs/task-005e.md`. New runs use separate directories. G's documented reusable offline log directory contains this rerun.

The new suite records cleanup per batch, including sampling failure. A separate Docker-label audit found zero task-owned containers, networks or volumes for 005E, 005C, G and G-L offline. The 005E ownership file is absent. Signing volumes were removed by each profile's cleanup. Local summaries are `artifacts/005ds/evidence-audit.json`, `history-before.json` and `docker-cleanup.json`. They contain no credentials, raw receipts or real source/model text.

## Changed-file inventory

| Files | Purpose |
| --- | --- |
| `services/verifier/verifier/multiclaim/coverage.py`, `bounded_prose/grammar.py` | Independent Python singleton-policy grammar checks |
| `services/verifier/verifier/multiclaim/pipeline.py` | Aggregation defense against duplicate required policies |
| `plugins/epochguard/multiclaim.go`, `prose.go` | Independent Go policy uniqueness and atomic grammar refusal |
| `plugins/epochguard/singleton_security_test.go` | Captured forged-record and independent grammar regressions |
| `services/verifier/tests_multiclaim/test_singleton.py`, `test_pipeline.py` | Required security/positive matrix, zero retrieval, reporting and transport distinction |
| `tests/conformance/005ds-before.json` | Genuine synthetic pre-fix SUPPORTED records retained as negative controls |
| `tests/conformance/004b-grammar.json`, `004g-grammar.json` | Corrected and expanded independent grammar parity vectors |
| `tests/claimreporting/fixtures.py`, `tests/conformance/005d-reporting.json` | Explicit correction of the frozen eight-assertion reporting case |
| `tests/combinedqualification/common.py`, `sources.py`, `report.py`, `test_qualification.py` | Two actual gateway conflict scenarios, zero-retrieval measurements and mandatory atomic-refusal checks |
| `docs/architecture.md`, `security.md`, `evaluation.md`, `compatibility.md`, `operations.md`, `verification-lab.md`; `services/verifier/README.md`; this report | Current invariants, tighter cardinality, evidence and reproducible operation |

## Residual limits

The independent sources are observed separately; this does not create an atomic cross-source snapshot or attest origin publication freshness. Candidates that need two assertions about one policy, even repetitions of the same value, are deliberately outside the admitted language. General semantic consistency, arbitrary prose, tools, multimodal/streamed responses, other policies and protected caching remain outside qualification.

The source graph/image hashes and process observations identify tested artifacts and correlations; they do not authenticate remote source correctness or establish general semantic coverage. Trusted components, private HTTP hops and the structural adapter retain their existing security assumptions. The correction makes no production-readiness or real-model-plus-real-source qualification claim, and historical live results have not been rescored or rerun.
