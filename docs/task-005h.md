# 005H — Variable-evidence qualification

## Result and scope

**90 protected gateway cases passed across 21 isolated profiles**, using four distinct synthetic evidence pairs and all nine accepted forms for each pair. Decisions followed supplied evidence values, including two same-text ALLOW → REJECT counterfactuals. This is offline qualification of the existing fixed policies, not real-world factual accuracy or origin-freshness evidence.

Baseline `e052517df12e5d26f7c533ae6a51a01bdab7727c` matched public `main` through an unauthenticated `git ls-remote` check before implementation. The run began November 19, 2026 UTC, on Windows x64 / Docker Desktop Linux/amd64. Production verification, grammar, native authorization, receipts, ingress and model adaptation were unchanged.

## Evidence matrix and measured outcomes

Each pair has 16 ordinary gateway cases plus two source-fault cases: nine matching single-claim forms, matching two-policy support, independently evidenced older Python and requests contradictions, unsupported neighboring prose, two singleton-policy repetitions, missing plugin, unavailable Python evidence and malformed requests evidence.

| Profile pair | Python evidence | requests evidence | Cases | ALLOW | REJECT | UNAVAILABLE | INGRESS_REFUSED | Python / PyPI calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Lower | `3.0.1` | `0.0.1` | 18 | 10 | 2 | 5 | 1 | 9 / 8 |
| Python-only change | `3.0.2` | `0.0.1` | 18 | 10 | 2 | 5 | 1 | 9 / 8 |
| PyPI-only change | `3.0.2` | `0.0.2` | 18 | 10 | 2 | 5 | 1 | 9 / 8 |
| Upper bounds | `3.99.999` | `999.999.999` | 18 | 10 | 2 | 5 | 1 | 9 / 8 |
| Additional invalid/unexpected evidence | — | — | 12 | 0 | 0 | 12 | 0 | 5 / 7 |
| Receipt-v2 controls using the lower pair | `3.0.1` | `0.0.1` | 6 | 1 | 0 | 0 | 5 | 6 / 6 |
| **Total** | | | **90** | **41** | **8** | **32** | **9** | **47 / 45** |

The four familiar-label replacements never use Python `3.15.2` or requests `2.34.2`. Pair transitions first vary only Python and then only requests. More directly, the exact same two-claim answer produced:

| Unchanged candidate | Evidence change | Observed decision |
| --- | --- | --- |
| Python `3.0.1`, requests `0.0.1` | Python `3.0.1` → `3.0.2`; requests remains `0.0.1` | ALLOW → REJECT |
| Python `3.0.2`, requests `0.0.1` | requests `0.0.1` → `0.0.2`; Python remains `3.0.2` | ALLOW → REJECT |

The suite asserts equal original candidate hashes across each transition. Every ALLOW released the exact original visible text in the existing minimal envelope; all 49 refusals had no released content or approved-content digest. Repeated-policy/neighbor refusals made zero evidence calls and admitted no partial mappings. Missing-plugin controls reached protected ingress and returned distinct INGRESS_REFUSED responses without verifier records.

Source counts are simulated HTTP invocations, including failed attempts, not origin requests or billing counts. Startup/readiness consumed zero evidence calls. Each profile's observed counters exactly equalled the sum of its per-request records.

## Invalid evidence expectations

Expectations were established from existing `primary_label()`, `PyPIRetriever.retrieve()`, `validate_page()`, `pypi_version()` and `verify_claim()`, then exercised through the actual gateway:

| Negative input | Existing policy reason | Protected result |
| --- | --- | --- |
| Python label `3.01.2` or `4.0.1` | INSUFFICIENT_EVIDENCE: no qualifying primary label | UNAVAILABLE / 503 |
| Two recognized primary Python labels | AMBIGUOUS_EVIDENCE | UNAVAILABLE / 503 |
| requests version `00.0.1`, `0.0.1rc1` or numeric JSON `1` | INSUFFICIENT_EVIDENCE | UNAVAILABLE / 503 |
| Wrong package name or `yanked=true` | INSUFFICIENT_EVIDENCE | UNAVAILABLE / 503 |
| Wrong Python Page URL or live-labelled PyPI Page in fixture mode | RETRIEVAL_FAILURE | UNAVAILABLE / 503 |
| Valid claimed Python/requests version ahead of valid source observation | CLAIM_AHEAD_OF_SOURCE | UNAVAILABLE / 503 |

Each pair additionally tests unavailable Python HTTP and malformed JSON with the required `application/json` media type. They produce RETRIEVAL_FAILURE and INSUFFICIENT_EVIDENCE respectively. An initial unit test accidentally supplied malformed JSON as `text/plain`; inspection showed that the existing retriever correctly refuses that earlier as RETRIEVAL_FAILURE. Only the fixture media type was corrected to reach the intended JSON-parser boundary. No policy rule was changed.

## Isolation and actual release path

The extension reuses `compose.verify.004g.yaml`, the existing native controlled provider, `ObservedProse`, normal evidence pipeline/retrievers and G's client/operator network split. A small Compose overlay selects the new test fixture. It adds no public port, browser route or production mode.

Every profile starts a fresh verifier process with a frozen, allowlisted configuration mounted read-only. Source values do not depend on candidate text, and no HTTP endpoint can change them. Each evidence pair's fault profile is a separate process with both fixed faults; no global evidence value is mutated between requests. Concurrent-instance unit tests verify isolation. CLI requests are sequential; client containers verify that gateway, verifier, provider and receipt-relay private ports are inaccessible. Only the private operator can read observations or select existing post-receipt relay faults.

Positive records were checked for expected observed versions, fixed URLs, fixture mode, evidence-ID/content-hash linkage, observation-time identity, original candidate binding and exact policy reasons. The actual Go plugin independently validated the normal Python contract before signing; ingress enforced `004g.receipt.v2`. The receipt block observed underlying SUPPORTED verification in all six cases, but MAC, response-body, policy-field, forwarded-request-field and replay faults each caused INGRESS_REFUSED / 503. Only the valid control released content. Raw receipts and signing keys were not exported; integrity observations are runtime ingress checks, not independent revalidation of saved receipts.

## Reproduction and validation

From the repository root, using Docker Linux containers, Compose/Buildx and Python 3.12:

```powershell
py -3.12 tests/boundedprose/qualify_variable.py --build --builder epochguard-002a
```

Select an available builder or omit `--builder` to use Docker's selection. `--build` builds isolated native → verifier 004C → 004E → 004G dependencies; the variable fixture image always rebuilds. No host virtual environment, credentials or new dependencies are needed for this driver. Initial builds can fetch public dependencies; runtime source HTTP is simulated and protected networks are internal. Without `--build`, the matching isolated dependencies must already exist. The inherited G private subnet requires coordination with another active G stack; the driver never removes another project.

| Executed check | Result |
| --- | --- |
| New fixture/pipeline regressions: `pytest tests/boundedprose/test_variable_evidence.py -q --tb=short` with existing test `PYTHONPATH` | **99 passed**; all profile/case policy reasons, nine forms, fixed configuration, concurrent isolation and parser negatives |
| New fixture Docker build | Same 99 tests passed with test-stage networking disabled |
| Full verifier/analysis/reporting/qualification Python selection, including bounded-prose and gate-comparison tests | **1,268 passed**, one intentionally deselected live test, one existing FastAPI/httpx deprecation warning; network-disabled, read-only checkout mount |
| Fresh native plugin and ingress/protected-ingress/relay/provider Go checks | Format, vet, unit and race passed with `-count=1`, networking disabled; commands without tests are reported as such |
| Actual gateway matrix | **21 profiles / 90 cases passed**, including all five receipt faults |
| Documentation/link checks, two documentation-tool tests, tracked/new-file whitespace | Passed |

The exact Go command was `docker buildx build --builder epochguard-002a --target checks-005h -f artifacts/005h/native-checks.Dockerfile .`; the test-only stage extends the unchanged native build. Commands/results are retained in `stages.json`, `validation-commands.json`, `go-checks.log`, `python-full.log` and the focused logs under `artifacts/005h/`. The new tests were added to the existing Python Docker check selection. Unit race instrumentation does not cover the running gateway process.

## Artifacts, cleanup and limitations

Measured run: `artifacts/005h/20261119T181628Z-82b6994c/`. Its root `report.json` records all denominators, outcomes, counters, same-text transitions, source revision and immutable image identities. Each profile retains its fixed configuration, client hashes/statuses, sanitized verifier/evidence observations, report and cleanup record. Selected-source SHA-256: `f18c6796edd1804c163064750f06dcaa58101483f7808c335a43e8fd36cb59ac`; running Python digest: `6f62e91a6d9fcd1835128d05c8d92524a50e3347565c078c761970f133c5e920`, checked against the checkout before requests.

| Runtime image | Immutable identity |
| --- | --- |
| `epochguard-005h-dev:002a` | `sha256:2242e765036451f4fcc3a2fb251550f4b319ad5c2461939acd7870feb571d5c0` |
| `epochguard-005h-verifier:005h` | `sha256:d9f5256c31ebd2cf02031d45e7f868e849f676c849ebf00f42798db35cb06992` |

An independent audit recomputed all profile assertions, verified **508 historical files unchanged** and found zero 005H containers, networks or volumes, with no ownership lock left. Disposable signing volumes were removed after every profile. Isolated images/build caches remain; nothing was pruned. Existing 005E reports, live qualifications and 005F evidence were preserved.

Changed files: seven variable-fixture/matrix/client/driver/test/build-overlay files under `tests/boundedprose/`, `dev/Dockerfile.checks`, this report and the evaluation-index paragraph. No production or existing fixture implementation was edited. Qualification remains finite: controlled provider, synthetic HTTP, fixed policies/nine forms, Windows/Docker Desktop Linux/amd64 and cache reuse. It does not establish real-source correctness, publication freshness, arbitrary semantic coverage, production readiness or combined live qualification. Digests identify artifacts and bindings; they are not factual authority.
