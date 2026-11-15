# Verification Lab and reviewed live qualification record

Implemented and tested November 15, 2026, from baseline `34ec0756dbf979955d2a351985eac97a39783be8`. The local Lab performs actual protected gateway enforcement with simulated evidence and a controlled provider. No real Tavily/PyPI/Gemini request or commercial model call was performed for this task. Startup, interaction and recording instructions are in the [Lab guide](verification-lab.md).

## Reviewed live record

The existing operator-authorized G-L run `artifacts/004gl/live/20261115T103325Z-964a2976` matches the supplied summary. Review checked all five outcomes, exact candidate and serialized-request hashes, original/canonical claim bindings, claim IDs, evidence identity hashes/modes/timestamps, per-source invocation counts, the known harness input digest and cleanup. No raw receipt was available or independently cryptographically reverified, and no source call was repeated.

The [dated G-L assessment](task-004gl.md#reviewed-live-qualification--november-15-2026) now records narrow real-source acceptance reviewed and met. Preserved runtime output remains `LIVE_RUN_COLLECTED_REVIEW_REQUIRED`; historical implementation pending statements retain their chronology. Current README, architecture, operations and verifier status point to the reviewed assessment. This does not qualify arbitrary language, a commercial model, origin freshness, production readiness or production client authentication.

## Implementation boundary

| Component | Responsibility |
| --- | --- |
| `web/lab/` | React/TypeScript/Vite editor, scenarios, actual-outcome inspector, conceptual architecture, source-mode explanation, responsive styling and browser/component tests |
| `internal/lab/`, `cmd/verification-lab/` | Go standard-library presentation backend; fixed ingress targets, exact submitted candidate, local origin checks, strict safe result projection, bounded admission/HTTP work |
| `compose.lab.yaml`, `dev/Dockerfile.lab`, `dev/lab.compose.env` | Isolated offline deployment, scratch/nonroot read-only Lab runtime and credential-free build/launch configuration |
| `tests/lab/` | Stdlib lifecycle/build helper, actual gateway smoke tests, metadata/overload/infrastructure fault and cleanup checks |

The Lab uses the original G simulated evidence service, not G-L qualification instrumentation, so repeated use has no artificial three-call lifetime budget. Every accepted candidate still requires the same policy/evidence checks, independent Go validation and request-bound `004g.receipt.v2` ingress release. The plugin, ingress, provider fixture, source parsers, grammar, receipt cryptography, fallback rules, source policies and G-L deployment files are unchanged. No planner authorizes a response. The Lab leaves prompt-triggered provider shape controls disabled; metadata injection remains a private host-test control.

The UI cannot select URLs, policies, model credentials, management routes or raw fixture faults. Only a fixed scenario may choose the normal/no-plugin protected ingress or genuine provider-error role. Custom input is forwarded unchanged and is never repaired into a valid template. Preset expected statuses are instructional labels, not backend decisions. The result separates input from approved content, and 403/503 responses cannot expose a released-content field. Infrastructure refusal is not assigned a specific cause from HTTP status alone.

Only the Lab publishes `127.0.0.1:8787`. Its dedicated host-entry bridge is required for Docker Desktop port publication; only the Lab joins it. Internal client/private networks isolate gateway, management, provider and verifier. The backend is not on the private network, has no signing key, and only contacts its two fixed ingresses. Source credentials are neither read nor mounted, `.env` is bypassed, and Vite is configured not to load it. The host-entry bridge is not a general egress firewall. See [the guide's security boundary](verification-lab.md#execution-and-security-boundary) for precise HTTP, memory and trust limits.

## Executed checks

| Check | Actual result |
| --- | --- |
| Frontend `npm run build --prefix web/lab` | TypeScript no-emit check and Vite production build passed |
| Frontend `npm test --prefix web/lab` | Eight component tests passed; mocked APIs cover presentation, not factual qualification |
| Final Lab Docker build | Passed; frontend build/component tests and Go unit/vet/build run in network-disabled test stages |
| Backend unit tests | Seven top-level tests / 36 subtests passed, including exact input preservation, fixed targets, headers, malformed/duplicate/oversized JSON, origins/routes, metadata rejection, redirects, timeout/recovery and immediate overload refusal |
| Backend race / vet / formatting | Passed with pinned Go build stage; fresh race run reports `internal/lab` 1.152s; unit execution only |
| `python tests/lab/manage.py test --build --builder epochguard-002a` | Complete native/verifier/Lab build chain and actual-stack qualification passed, then removed its stack/key volume |
| Final `python tests/lab/manage.py test` | 21 standard/custom inference checks, metadata/error controls, 16-request overload, missing services and recovery passed; teardown completed |
| Visible Edge browser tests | Two passed on the final desktop/mobile UI; actual API responses and custom input, safe refusal states, keyboard submit, JSON inspector and 390px no-overflow layout verified |
| Existing G-L offline qualification | Passed, including fixture evidence refused by the live-configured Go validator; no live option or credential |
| Existing G security/lifecycle qualification | Passed after adding the observer-start handshake described below; all original security assertions retained |

The component tests run under jsdom and stub fetch; they are not substitutes for the real API/browser suites. The backend unit/race execution and packaged frontend tests were network-disabled. Real gateway tests used internal fixture networks; browser page requests were restricted to the loopback app. Only public build dependencies were downloaded. The initial jsdom version required a newer Node patch; it was replaced with pinned compatible jsdom 29.0.0. The package installation audit reported zero vulnerabilities at execution time, not a continuing security guarantee.

Final standard client sample from `artifacts/005a/lab-qualification-final-network.log` (Python high-resolution elapsed time, not an internal-stage measurement or performance guarantee):

| Preset | HTTP | Actual outcome | CLI client elapsed ms |
| --- | --- | --- | --- |
| Supported | 200 | ALLOW, exact content | 100.792 |
| Older Python | 403 | REJECT | 10.161 |
| Extra assertion | 503 | UNAVAILABLE at policy boundary | 22.691 |
| Missing plugin | 503 | INGRESS_REFUSED | 93.830 |
| Provider failure | 400 | PROVIDER_ERROR | 12.535 |

All five were repeated three times. Four additional custom cases covered explicit CR/LF/tab preservation, extra prose, a single requests claim and non-ASCII refusal. Two further negative controls reversed the preset expectations: supported text selected under "older" returned ALLOW, while contradicted text selected under "supported" returned REJECT. This verifies that scenario labels do not fabricate verdicts.

The overload burst admitted four requests and safely refused twelve at the Lab boundary, followed by successful delivery. A stopped verifier produced policy UNAVAILABLE/503; a stopped gateway produced ingress refusal/503. Both recovered to 200 after restoration. Those causes were known to the test operator; the UI only reports the returned boundary, not an inferred internal diagnosis. Metadata and provider-error sentinels were absent from client-visible results. All private services were inspected for absence of published ports and host-entry network membership.

## Commands and artifacts

Commands actually executed included:

```powershell
npm run build --prefix web/lab
npm test --prefix web/lab
python tests/lab/smoke.py
python tests/lab/manage.py test --build --builder epochguard-002a
python tests/lab/manage.py test

docker compose --env-file dev/lab.compose.env -f compose.lab.yaml build lab
```

Visible browser checks used `EPOCHGUARD_LAB_HEADED=1` and `npm run test:browser --prefix web/lab`. The [complete Windows procedure](verification-lab.md#tests-and-demonstration-recording) includes cleanup of that flag. Fixture-only desktop/mobile screenshots were captured under ignored `artifacts/005a/` and visually inspected. No secret-bearing IDE window or unrestricted desktop was captured. The architecture visualization is labeled conceptual; only browser end-to-end latency is measured in the UI.

The backend unit command used a read-only current-source mount:

```powershell
docker run --rm --network none --user 0 --mount "type=bind,source=$($PWD.Path),target=/src,readonly" --workdir /src -e CGO_ENABLED=0 -e GOWORK=off -e GOTOOLCHAIN=local epochguard-dev:002a go test -count=1 -timeout=60s -v ./internal/lab ./cmd/verification-lab
```

The separate race/vet/format check used the tracked native Dockerfile plus an ignored appended build target containing `RUN --network=none ... go test -count=1 -timeout=60s -race -v ./internal/lab ./cmd/verification-lab`:

```powershell
docker buildx build --builder epochguard-002a --target lab-offline-tests --build-arg "QUALIFICATION_RUN=$([guid]::NewGuid().ToString('N'))" -f artifacts/005a/Dockerfile.race .
```

Existing G/G-L regression commands were executed without `--live`, with `COMPOSE_DISABLE_ENV_FILE=1` and `COMPOSE_ENV_FILES` pointing to the deliberately empty `dev/lab.compose.env`. No pre-existing credential was read. The G-L runner's preserved collection-time pending message does not retract the separately reviewed live assessment.

All Lab containers, networks and the disposable signing-key volume were removed after testing. G/G-L qualification stacks also cleaned up; unrelated resources and saved live records were preserved. Sanitized observations/logs live in ignored `artifacts/005a/`, with the unchanged drivers' offline outputs in their existing artifact locations.

## Development failures and correction

The first host connection failed because Docker Desktop did not publish the port for an internal-only network. A separate Lab-only host-entry bridge resolved that; evidence services remained internal and unpublished. An initial browser test used an ambiguous accessible label matching both a region and textbox; the corrected test selects the textbox role. An initial backend unit test stalled because its absolute-form test URL did not match the intentional exact origin-form route; corrected test requests and a bounded test wait resolved it without widening server routing.

The first existing G restart-window check observed 59 HTTP 200 responses and no 503, so it did not establish restart-time refusal coverage. The old fixed four-second delay did not prove that the observer had started; precise overlap is unavailable from that log. A test-only successful pre-restart probe/start marker and bounded host wait now establish observer readiness before stopping the gateway. The original requirement for both supported 200 and safe 503 remains unchanged. The rerun observed **58 HTTP 200 and three safe 503**, with final recovery and the complete security suite passing. The initial failed log is preserved under `artifacts/005a/g-initial-restart-window.log`.

Final tested Lab image: `sha256:44e7202ffa6a2c1c4e724a693c5e68ee261020bbd568549e1316ed4677ce7185`. This identifies a local build, not a published release.

## Remaining limits

No trust-boundary blocker or confirmed enforcement regression was found within the exercised scope. P0/P1 functional and presentation goals are implemented and tested. The Lab is a local demonstration, not a production deployment: origin checks are not client authentication, the verifier hop/host/configuration remain trusted, and bounded admission is not general resource isolation. There is no general claim verification, commercial LLM, safe streaming, protected cache, origin freshness attestation, account system or persistent history. Browser checks used Edge and one desktop/mobile viewport pair; no exhaustive cross-browser or formal accessibility audit is claimed.
