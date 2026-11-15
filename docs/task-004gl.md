# Protected bounded-prose live qualification harness

**Narrow live-source acceptance reviewed and met**, based on the November 15, 2026 operator-authorized run and subsequent inspection of its sanitized records. The original implementation/offline evidence remains below with its execution-time scope. This qualifies the fixed two-policy bounded-prose path with a controlled provider and v2 protected ingress, not general prose, a commercial model or production readiness.

## Reviewed live qualification — November 15, 2026

The operator supplied `artifacts/004gl/live/20261115T103325Z-964a2976`. Subsequent local inspection of `preflight.json`, `observations.json`, `measurements.json` and `cleanup.json` confirmed the reported summary. The run identifies revision `34ec0756dbf979955d2a351985eac97a39783be8`, schema `004gl.qualification.v1`, `simulated_transports=false`, `004g.receipt.v2` and `expectations_met=true`. The runner status is `LIVE_RUN_COLLECTED_REVIEW_REQUIRED`, not a final approval; its pending flag describes the state before this subsequent assessment.

| Case | HTTP / outcome | Elapsed ms | First body chunk ms | Provider calls |
| --- | --- | --- | --- | --- |
| A-support | 200 / ALLOW; exact content match | 1444.173 | 1442.914 | 1 |
| B-contradiction | 403 / REJECT | 5114.083 | 5110.886 | 1 |
| C-unsupported | 503 / UNAVAILABLE | 33.529 | 32.383 | 1 |
| D-no-plugin | 503 / INGRESS_REFUSED | 105.676 | 104.623 | 1 |
| E-provider-error | 400 / PROVIDER_ERROR | 28.665 | 27.636 | 1 |

All five records are `EXPECTED_OUTCOME`, without a preflight-to-evaluation version change. Both sources record three attempted/three completed application retrievals; `cleanup.completed=true`. The preflight observed Python `3.15.2` at `2026-11-15T10:33:47.509828Z` in `tavily_live` mode and requests `2.34.2` at `2026-11-15T10:33:47.902115Z` in `pypi_live` mode. These are dated observations, not permanent current-version facts.

Inspection recomputed the exact candidate and serialized-request digests for all five cases, validated evidence identity hashes/modes/timestamp bindings and matched each case's verifier records to the separate observations file. The protected ingress performed receipt verification during execution; this assessment does not independently reverify raw HMAC receipts, which are not exported. No source request, model call or paid qualification was repeated for this review.

**Assessment:** the supplied execution and inspected records meet the narrow live acceptance checks. Refusal/provider-error cases demonstrate their expected boundaries, not successful factual verification. Counts do not independently establish billing or origin fetches; first-byte timing means the first decoded body chunk, not packet or internal component timing. Origin freshness, general natural-language coverage, production client authentication/readiness and commercial LLMs remain unqualified.

## Original implementation scope

Implemented and exercised offline on November 15, 2026. No real source/model request or existing private credential access occurred during that implementation phase. Its historical pending statements below precede the operator run and assessment.

Implementation baseline: `ad2b9edca59ae585dc2cfab14e6d3d1761acf07b`. [Architecture](architecture.md) defines the unchanged enforcement/receipt boundary. [Operations](operations.md#bounded-prose-live-qualification) provides complete Windows PowerShell setup, separate opt-ins, invocation, report inspection and cleanup.

## Minimal composition and compatibility

The new qualification factory wraps the existing G `Pipeline`, delegating evidence to E's `ObservedPipeline`. It reuses the real fixed-source retrievers, `live_key()` credential/configuration admission, three-invocation source budgets, one-shot preflight, single active evidence slot and live deadlines. The wrapper retains only bounded original/canonical digests, claim IDs/policies/versions/verdicts and evidence metadata; telemetry never contributes to authorization.

The Go plugin, independent grammar/record/evidence validation, `004g.receipt.v2` signer, exact request binding, minimal HTTP projection and ingress release checks are unchanged. No grammar, policy, model authority, cache, fallback mechanism or authentication redesign was added. Existing D/E deployments, source code, tests and historical evidence remain unchanged.

| Profile | Source and deployment boundary |
| --- | --- |
| `compose.verify.004gl.yaml` | Real retrievers, `fixture=False`, both E/G live opt-ins, fixed live profile and verifier-only runtime Tavily secret. Go mode `004g.v1`, evidence `live`, 30s verifier timeout and existing 40s remaining-work profile. No automatic invocation |
| `compose.verify.004gl.offline.yaml` | Real source parsers over `httpx.MockTransport`, explicitly `fixture=True` and `simulated_transports=true`; internal networks without egress or credentials. Go evidence `fixture`, 30s verifier ceiling without the live-only remaining-work profile |
| Offline `gateway-live-mode` control | Unchanged live-configured Go validator receives supported fixture records and must return authenticated UNAVAILABLE/503 |

Both profiles retain G-live ingress's 44s exchange/48s write bounds, client 52s wall-clock deadline and Uvicorn concurrency 32. Evidence admission is independently one active operation, with 26s shared work, Tavily API/transport 19s/20s, PyPI 4s and per-claim ceiling 20.5s. These limits do not establish host resource isolation or a global Bifrost execution deadline.

Only the live verifier has egress capability and mounts the source credential. No host ports are published. The network-disabled key initializer independently creates the disposable 32-byte HMAC key; only ingress and configured signers mount it. Client roles cannot reach gateway DNS/private IP, management, provider or verifier. The test-only metadata control remains private. Source egress is not a destination firewall.

## Cases and accounting

Preflight validates actual observations before constructing candidates. Live candidates never hardcode historical source versions. A and B use finite G paraphrases and both policies. A includes admitted leading/trailing whitespace and CR/LF/tab separators to exercise exact content preservation. B derives an eligible older Python version and requests a usable provider fallback; terminal refusal must prevent that fallback. C adds an unsupported assertion. D uses a missing-plugin gateway behind its own v2 ingress. E causes a genuine controlled-provider failure and requires the fixed safe G error projection.

Each case has a unique candidate hash. Provider counter deltas must therefore be exactly one for each case, rather than a shared aggregate. One preflight plus A/B consume at most three attempted invocations per source; failures consume budget, with no retries or polling. Readiness is checked before preflight and must consume zero source invocations or telemetry records. Unsupported input and genuine provider errors must not become supported factual deliveries.

The private provider inserts a unique unverified sentinel into its ID before the standard cases. A must retain exact assistant content and the minimal envelope with no provider metadata. The unchanged G security suite separately exercises each other metadata channel, malformed/cross-policy/old/replayed receipts, request substitution, disabled-plugin concurrency and restart recovery.

## Reporting and cleanup contract

The stdlib host driver defaults to offline operation. `--live` refuses before Docker invocation unless both `EPOCHGUARD_RUN_LIVE_004E=1`, `EPOCHGUARD_RUN_LIVE_004G=1` and the runtime secret file path are supplied. It does not read that file. The live service independently validates the bounded secret, fixed profile and forbidden overrides using the existing E boundary.

Every invocation creates a fresh timestamp/random artifact directory. The driver does not save arbitrary Docker stdout/stderr, service logs, raw receipts, keys, candidate text or source bodies. It validates closed JSON shapes, evidence identities, source modes, canonical bindings, call counts and case expectations before exporting measurements. Private source identifiers and observation metadata remain bounded by the existing evidence schema. Unknown fields, malformed/duplicate/nonfinite JSON and mismatched bindings are refused with fixed diagnostics.

`004gl.qualification.v1` records:

- Baseline Git revision, a digest of the selected driver/runner/report/factory/live-config/Compose inputs, policy and configured receipt protocol.
- Per-case HTTP outcome/status, original-content match, serialized-request/candidate digests, client elapsed and first-body-chunk latency, claim IDs/policies, evidence modes/versions/hashes/times and separate provider invocation count.
- Source changes since preflight, attempted/completed application retrieval counts, and explicit inconclusive/failure categories.
- Controlled-provider and simulated-transport flags, measurement scope and `live_qualification_pending=true`.

Receipt validation is inferred from the protected ingress's release contract; raw receipts are not archived or independently reverified by the runner. Generic ingress refusal means validation was unavailable/refused, not a more specific cryptographic diagnosis. First-byte latency is the first decoded HTTP body chunk observed by the client, not packet timing. No component duration is inferred by subtraction. Source counts are application retrieval invocations, not billing or origin-fetch evidence. Local observation timestamps do not attest origin freshness.

After a failure, the driver attempts one source-free observation collection if the stack is available and observations were not already collected. Cleanup always runs; a failed/unavailable cleanup cannot produce success and is recorded for manual recovery. Host unit tests inject startup, malformed observation, timeout and cleanup failures and prove that private subprocess values are not persisted. The operator's outer PowerShell `finally` separately removes the temporary source secret; the driver removes its Compose environment and signing-key volume.

## Executed offline evidence

Final new-image build:

```powershell
docker build -t epochguard-verifier:004gl -f services/verifier/Dockerfile.004gl .
python tests/boundedproselive/qualify.py
```

The image's test stage uses `RUN --network=none`. Final result: **43 passed in 0.65s**. The final host run passed and recorded `cleanup.completed=true`; its separate fixture/live-mode boundary check also passed. The two earlier successful development runs used earlier harness revisions and are preserved separately, not counted as independent live evidence.

Final simulated case observations from `artifacts/004gl/offline/20261115T094038Z-3edc9815/measurements.json`:

| Case | HTTP | Elapsed ms | First body chunk ms | Provider calls | Observation |
| --- | --- | --- | --- | --- | --- |
| A-support | 200 | 34.973 | 33.783 | 1 | Exact approved content; minimal metadata |
| B-contradiction | 403 | 29.613 | 28.037 | 1 | Terminal despite configured fallback |
| C-unsupported | 503 | 27.046 | 25.974 | 1 | Authenticated unavailable; no answer |
| D-no-plugin | 503 | 110.876 | 109.496 | 1 | Ingress refused unchecked response |
| E-provider-error | 400 | 37.470 | 36.070 | 1 | Genuine failure with safe projected error |

Both sources recorded three attempted/three completed **simulated** retrievals for preflight/A/B. No source changed in this run. Readiness used zero retrievals. These are single-run fixture timings, not live performance measurements or service guarantees.

Combined current-source Python regression, with a read-only mount and no network:

```powershell
docker run --rm --network none --mount "type=bind,source=$($PWD.Path),target=/src,readonly" --workdir /src/services/verifier -e PYTHONPATH=/src/services/verifier:/src/services/claim_analysis -e PYTHONDONTWRITEBYTECODE=1 epochguard-verifier:004gl python -B -m pytest -c /src/services/verifier/pytest.ini -p no:cacheprovider /src/services/verifier/tests /src/services/verifier/tests_multiclaim /src/services/verifier/tests_gateway /src/services/verifier/tests_live /src/services/verifier/tests_prose /src/services/verifier/tests_bounded_prose /src/services/verifier/tests_live_g /src/services/claim_analysis/tests -q
```

Result: **615 passed, one live test deselected, one existing Starlette deprecation warning in 21.09s**. Tests cover live configuration/missing-secret admission with synthetic credentials, fixed retrievers/budgets, one-shot preflight, supported/older/ambiguous/failed evidence, wrong source mode, cancellation/recovery, report injection/binding/count errors, total client deadline, response bounds, metadata headers and cleanup on success/failure. No fake-provider score is a model-quality result.

Go checks used a temporary qualification Dockerfile derived from the tracked `dev/Dockerfile`: its Go test stages were network-disabled, then explicit `-count=1` format/vet/unit/race checks were appended for the plugin, ingress, protected-ingress command and cache proxy. The exact executed command was:

```powershell
docker buildx build --builder epochguard-002a --target qualification-offline --build-arg "QUALIFICATION_RUN=$([guid]::NewGuid().ToString('N'))" -f artifacts/004gl/Dockerfile.offline-units .
```

It passed. The final fresh plugin unit/race outputs were 0.216s/1.521s; ingress unit/race outputs were 0.550s/1.661s. Format and vet checks passed. The ignored generated Dockerfile/log retain the command definitions; the ordinary tracked native build remains the fresh-clone reproduction for its packaged Go checks. Race detection covers unit execution, not the real gateway process.

Existing real gateway qualifications executed against the unchanged native image:

```powershell
python tests/boundedprose/qualify.py
python tests/protectedingress/qualify.py
python tests/livequalification/qualify.py

docker compose -f compose.verify.004c.yaml up -d --wait --no-build gateway gateway-faults gateway-control
docker compose -f compose.verify.004c.yaml run --rm --no-deps qualification
docker compose -f compose.verify.004c.yaml down --volumes --remove-orphans

docker compose -f compose.verify.yaml run --rm verification-tests
docker compose -f compose.verify.yaml down --volumes --remove-orphans
```

All passed. E ran its default **offline** mode, including simulated source faults. D/G included actual restarts, disabled-plugin behavior, receipt faults and recovery; G also checked runtime logs in memory for candidate/metadata sentinels. Existing private Compose suites had no egress/live credentials. Cleanup removed all qualification stacks/networks/signing-key volumes, leaving unrelated resources untouched.

Both new Compose definitions passed `config --quiet`. The live definition was only parsed with both opt-in flags and a nonexistent synthetic secret path; no live container was started and no secret was opened.

Final tested native image: `sha256:7820344dee00851c7090bdf5f4658596aeeb78229b1e5b9f67af7e246faf0aa4`.
Final qualification image: `sha256:53a874e327d3c83a059422ca577285cf89aca5c9236b27c911db41ecab45085f`.
These identify local tested artifacts, not published releases.

During development, offline tests first caught container path discovery and a fixture/live source-mode mismatch in the new harness. The offline configuration was corrected to keep fixture identities and add a separate live-mode rejection control; no fixture was relabeled as real-source evidence and no enforcement rule was relaxed.

## Security assessment and remaining limits

No enforcement architecture, cryptography or grammar blocker was found. The harness is ready for a separately authorized operator run within the fixed scope; this is an implementation self-review, not independent production security approval. The existing real G attack regressions passed; finite tests do not prove arbitrary transport/provider compatibility or exhaustive parser agreement.

The private verifier hop, host, management, pinned binaries, clock, configured plugins and signing key remain trusted. Existing cache, streaming, authentication, global execution-deadline and origin-freshness limitations remain. Process restart resets the qualification budget; it must never be used for automatic paid retries. Source/API changes and unavailable evidence may safely make a future run inconclusive. A failed provider operation is not verification success.

**Original implementation-stage status: 004G LIVE QUALIFICATION PENDING.** At that time, real-source observations, API compatibility, live latency and reviewed live acceptance were unmeasured for G. The dated assessment above records the subsequent narrow qualification. The 004F/Gemini planner remains non-authorizing. Historical E live evidence does not qualify G's v2 path.
