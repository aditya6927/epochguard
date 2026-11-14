# Task 004E: live multi-claim evidence qualification

The original implementation phase started from clean `main` at `749b5ac` on
November 14, 2026 (Asia/Calcutta) and completed without live Tavily, PyPI or Gemini
calls. A subsequent maintainer-authorized live run on **November 14, 2026** met
the defined narrow acceptance checks, based on the report assessment below.
This qualifies the protected exact-template two-policy path with a controlled
provider, not a production service, commercial LLM or general factual verifier.

## Maintainer live qualification — November 14, 2026

The maintainer first executed the offline build/qualification:

```powershell
& .venv-003a/Scripts/python.exe tests/livequalification/qualify.py --build
```

Its result was `004E offline qualification passed; LIVE QUALIFICATION PENDING`.
That message describes the offline phase; it is not the current project status.
The maintainer then supplied explicit live opt-in and a temporary runtime Tavily
credential file and executed:

```powershell
& .venv-003a/Scripts/python.exe tests/livequalification/qualify.py --live
```

The runner printed `LIVE RUN COLLECTED: independent result review required`.
It did **not** print a final live PASS assertion. The maintainer reported that
all five client cases had `expectation_met=true`. This documentation-only review
independently inspected the existing local `artifacts/004e/live/preflight.json`,
`measurements.json` and `report.json` and confirmed they match the supplied
observations below. No qualification or source request was rerun, and no runtime
artifact or credential is added to the repository by this update.

| Preflight source | Retrieval mode | Observed version |
| --- | --- | --- |
| Python.org Windows through Tavily Extract | `tavily_live` | `3.15.2` |
| Fixed requests project, PyPI JSON API | `pypi_live` | `2.34.2` |

The reports record `fixture=false`. Case A used both observed versions; case B
claimed Python `3.15.1` against a fresh `3.15.2` observation, alongside the
supported requests `2.34.2` claim. These are observations from that run, not
permanent current-version assertions or future hardcoded test expectations.

| Protected ingress case | HTTP | Outcome / delivery | Elapsed ms |
| --- | --- | --- | --- |
| A-support | 200 | ALLOW; original candidate bytes match | 3963.358 |
| B-contradiction | 403 | REJECT; answer not released | 6542.582 |
| C-unsupported | 503 | UNAVAILABLE; answer not released | 25.517 |
| E-no-plugin | 503 | INGRESS_REFUSED; answer not released | 112.425 |
| F-provider-error | 400 | PROVIDER_ERROR; provider error preserved | 31.473 |

| Matching verifier record | Verdict and claim checks | Elapsed ms |
| --- | --- | --- |
| A | SUPPORTED; two individually SUPPORTED claims | 3900.605 |
| B | CONTRADICTED; one CONTRADICTED and one SUPPORTED claim | 6516.847 |
| C | INSUFFICIENT; no claims admitted | 0.154 |

| Source | Attempted | Completed | Recorded retrieval durations ms, in order |
| --- | --- | --- | --- |
| Tavily | 3 | 3 | 5792.614, 3589.463, 6114.624 |
| PyPI | 3 | 3 | 222.576, 305.546, 395.233 |

These counters are application-level retrieval invocations shared by preflight
and the two factual requests, not independent billing or origin-fetch evidence.
The values fit the fixed three-call budget per source. Pipeline and client
durations have different measurement boundaries; they are individual observations,
not performance guarantees. No unavailable provider/Go/ingress component timing
is inferred by subtracting them. Observation timestamps record local receipt of
evidence, not source publication time or an attested origin-fetch time.

**Report assessment:** the collected live data and five successful client
expectations satisfy the defined narrow acceptance checks. The requests exercised
real-source verification through the real gateway, independent Go validation and
the 004D receipt-gated protected ingress: supported two-claim delivery, terminal
contradiction refusal, unsupported-content refusal, missing-plugin refusal and
genuine provider-error handling. The receipt check occurs inside ingress; this
review does not claim separate cryptographic re-verification of raw receipts from
the JSON reports. F is a preserved failed provider operation, not a verification
success. E is a deployment-integrity control, not evidence-source qualification.

The original offline simulated source-failure, tampering and restart results
below retain their own scope. This live run does not qualify arbitrary prose,
additional policies, a real commercial LLM, production readiness/authentication,
the unauthenticated private verifier hop, generalized source freshness, streaming
or caching. This assessment is based on inspected reports and maintainer-supplied
execution evidence, not an independently repeated live execution.

## Requirement, design and trust

The protected route must use real evidence from both existing policies without
loosening complete-response coverage, comparisons, evidence modes, independent
Go validation or authenticated ingress release. This adds an explicitly selected
factory/profile and bounded qualification runner to the existing service, not
another production service or evidence policy.

```text
client-only runner -> protected ingress -> private real Bifrost/provider
 -> native EpochGuard -> existing 004B pipeline, fixture=False
 -> Tavily Extract(fixed Python.org URL), then fixed requests PyPI JSON
 -> deterministic per-claim comparisons -> whole-response aggregation
 -> independent Go validation -> 004D receipt -> ingress buffer/MAC checks
 -> original eligible answer or terminal safe refusal
```

The attacker can control requests, candidates, headers and evidence text. Source
failures, bad observations, unavailable/missing plugins and invalid receipts must
never release an unchecked answer. The host, pinned native artifacts, clock,
deployment configuration, management network, signing key, verifier and existing
source policies remain trusted. The Go-to-verifier hop is still unauthenticated
private HTTP; the receipt is not a substitute for separately authenticating it.
Neither HMAC nor live retrieval proves origin freshness or general factual truth.

Inspection included AGENTS, README, architecture, the integration spike,
003A/B/004B/C/D notes, old live tests/profile, Python sources/settings/contracts,
ingress/CLI, plugin, real provider and offline qualification drivers. The cached
actual upstream transport commit is `e869c3f9adc96ea53c38694a21bb04a8e1085487`,
core v1.14.1, Go 1.27.3 Linux/amd64. In particular transport
`handlers/middlewares.go:getBifrostContextFromFastHTTP` constructs a context with
`schemas.NoDeadline`; provider network timeout is not a whole-hook timeout.
`schemas/context.go` documents scoped context delegation and pooled root
lifetimes. No Bifrost hook, flag, core source or ABI change was invented.

The official [Tavily Extract reference](https://docs.tavily.com/documentation/api-reference/endpoint/extract)
was consulted: the existing bearer-authenticated POST, text/basic extraction,
fixed URL list, API timeout and results/failed-results handling remain compatible.
The [PyPI JSON reference](https://docs.pypi.org/api/json/) documents the project
metadata route. Existing stricter project identity, non-yanked boolean, canonical
numeric version, exact URL, duplicate-key and size checks are preserved. Neither
document guarantees that a future observation will satisfy these narrow parsers.
Current versions were not assumed or looked up for a candidate.

## Original implementation file inventory and ownership

New files:

| Paths | Responsibility |
| --- | --- |
| `services/verifier/verifier/multiclaim/deployment.py` | Trusted real-source factory, fixed profile, bounded per-process source budget, safe observations, one-shot preflight/report |
| `services/verifier/tests_live/{conftest,test_deployment,simulated,runner}.py` | Network-disabled configuration/resource/source-mode tests, explicitly simulated transport controls, private/operator and client runner |
| `services/verifier/Dockerfile.004e` | Separate live entry point based on the existing experimental image; offline tests during build |
| `compose.verify.004e.yaml`, `compose.verify.004e.offline.yaml` | Separate real-source opt-in and internal-only simulated deployments |
| `dev/live/{gateway,gateway-simulated,gateway-control}.json` | Trusted live mode, explicitly fixture test mode and unsafe private no-plugin control |
| `plugins/epochguard/live_test.go`, `internal/ingress/live_test.go` | Deadline/configuration, live-mode fixture rejection, negative readiness and unchanged receipt-age controls |
| `tests/livequalification/qualify.py` | Windows-compatible host orchestration, explicit paid gate, serial cases, measurement collection and cleanup |
| This report | Design, commands, actual evidence and limits |

Modified files:

| Paths | Change |
| --- | --- |
| `plugins/epochguard/http_decision.go` | Optional trusted timeout-profile discriminator; legacy source rejects it |
| `plugins/epochguard/multiclaim.go` | Explicit live profile validation, remaining decision deadline and no replayable POST body |
| `plugins/epochguard/main.go` | Monotonic request start on request-owned trace |
| `internal/ingress/ingress.go`, `cmd/protected-ingress/main.go` | Fixed opt-in live request/write deadlines and authenticated negative readiness |
| `services/verifier/verifier/multiclaim/app.py` | Parameterize the existing body/disconnect middleware path; its existing default behavior is unchanged; preflight reuses it |
| README, architecture and verifier README | Implemented boundary and live status pending at the end of the original implementation phase |

The qualified `/v1/verify` implementation, Python/PyPI policies, grammar,
contracts, aggregation, validators, dependencies, annotation data, old tests,
Dockerfiles and Compose profiles remain unchanged. `dev/Dockerfile` already
copies the new root package/tests; it needs no edit. Typed refusal/enforce and
the 004D signing/verification format and timestamp checks are unchanged.

## Trusted source construction and resource lifetimes

`live_app` requires `EPOCHGUARD_RUN_LIVE_004E=1`,
`EPOCHGUARD_004E_PROFILE=live` and `EPOCHGUARD_TAVILY_SECRET_FILE`. A bounded
ASCII runtime file supplies the key; missing/malformed/oversized keys fail
startup with fixed errors. An environment API key, test mode, fixture case or
source/endpoint/package/policy/timeout override is rejected. No input chooses a
URL, package, evidence mode, budget or policy. No fixture fallback exists.

The factory constructs one real `TavilyRetriever` and `PyPIRetriever`, wrapped
by process-wide budget counters and one shared `ObservedPipeline(fixture=False)`.
Admission is immediate, maximum one active factual/preflight operation; no waiter
queue. The underlying unchanged pipeline processes claims sequentially and
releases its active slot in `finally`. Each HTTP retrieval owns/closes its client
and response. Cancellation propagates; body/disconnect watchers cancel and join
their tasks. Counters retain at most three bounded rows per source, never Page
content/credentials. At most sixteen non-canary pipeline records are retained;
exhaustion refuses further work. Readiness canaries consume neither paid budget
nor telemetry slots. Independent process limits bound abandoned work even where
transport disconnect propagation is not established.

Private `/qualification/preflight` is one-shot even after failure; it runs the
actual fixed-source parsers and mode/age checks before returning canonical
versions and bounded evidence metadata. It accepts no source/candidate settings.
`/qualification/report` returns bounded request hashes, policy/version/reason
records, evidence references and source timings/counters. These endpoints have
no client-network route, budget reset or live endpoint override. The offline
test factory alone has a private reset/fault control and no external transport.

## Complete deadline hierarchy

| Boundary | Offline default | Fixed 004E live value |
| --- | --- | --- |
| Tavily API | 3s | 19s |
| Tavily total transport/retrieval | 4s | 20s |
| PyPI total retrieval | 4s | 4s |
| Per-claim pipeline retrieval ceiling | 4s | 20.5s; accommodates Tavily's own deadline handling |
| Shared pipeline work | 5s | 26s |
| Go verifier total HTTP call | Existing deployment setting | 30s |
| Bifrost fixture provider network request | 10s | 10s, no retries |
| EpochGuard remaining decision work | Existing behavior | Deadline 40s from HTTP pre-hook start |
| Protected ingress shared/upstream | 8s; old ceiling 10s | 44s |
| Ingress HTTP server write | 15s | 48s |
| Qualification external HTTP client | Existing runner setting | 52s |

Sequential 20s + 4s leaves two seconds for extraction/comparison within work 26s.
Go 30s adds body receipt, scheduling, serialization and validation room. Provider 10s
plus Go 30s fits the 40s execution allowance; the remaining deadline is computed
from the real monotonic HTTP start and can shorten the verifier call after a slow
provider/fallback. It cannot extend an earlier caller cancellation/deadline.

The pinned Bifrost transport has **no global HTTP execution deadline** to tune.
The 40s cap bounds EpochGuard's post-provider decision work, while the provider's
own 10s deadline bounds network work and ingress 44s bounds the client-facing
exchange, including two seconds for body receipt and two for transport/response overhead. It does not retrofit a global scheduler deadline or guarantee immediate
cancellation of Bifrost queue/transport work on client disconnect. No timer retains
or cancels a pooled Bifrost root context after its hook lifetime. This distinction
is material to the controlled qualification and broader deployment limits.

Only exact trusted profile names are accepted. The Go live profile requires
`004b.v1`, `evidence_mode=live` and exactly 30000ms. Ingress accepts exactly the
fixed live budget/canary combination; arbitrary/negative/excessive/inconsistent
values fail configuration. No header changes these limits. Offline defaults are
unchanged. There are no automatic source, verification or inference retries.

The signer timestamps the receipt **after** verification. The nonce, exact
status/body/candidate digests and policy remain bound to that request. Receipt
age remains at most 20s, issuance at least request-start minus 2s, clock lead at
most 2s. Tests accept fresh issuance after 35s of simulated work while still
rejecting 21s-old receipts. Longer live deadlines do not relax replay protection.

## Readiness and network/secret boundaries

004D offline readiness still requires its authenticated supported probe.
004E instead submits a fixed sentence outside the trusted grammar and requires
authenticated UNAVAILABLE/503, after checking gateway/plugin activity, placement,
order, policy mode and cache absence. Actual Python coverage rejects it before
retrieval. This proves participation and fail-closed enforcement, not source
health, verifier health or factual support. Every factual response independently
needs a valid receipt; readiness cannot authorize release.

The client network is internal and contains only ingress/client runner. Bifrost,
provider, management and verifier use a distinct internal private network. Only
ingress bridges client/private. Only the real-source verifier joins the egress
network; no service publishes a host port. The offline profile has no egress
network. Client tests deny private DNS targets and the actual gateway address
`10.77.24.10`. Do not run live/offline 004E profiles simultaneously: their isolated
private networks deliberately reserve the same subnet/address.

Only the verifier mounts the Tavily runtime secret; values never enter Compose
environment/configuration, image layers, runner or gateway. The independent
receipt secret is generated in a disposable volume and mounted read-only into
ingress/signers; runners/verifier have no signing-key mount. The key init job has
no network. Local-development setup credentials are not production authentication.

Actual evidence HTTP calls are fixed HTTPS, with environment proxies disabled,
redirects disabled and response bounds preserved. Docker egress attachment is
not a packet-level destination/HTTPS firewall: the verifier process/host remains
trusted. There is no public listener exposure, TLS/client identity system,
production secret manager or key rotation in this milestone.

## Operator commands: PowerShell

Docker Desktop must run Linux containers. The repository's pinned Python
environment is sufficient for the stdlib host driver. Initial builds require
network access for source/dependencies; test cases themselves require no live
credentials or external sources.

```powershell
# Builds native, existing experimental Python base, then separate 004E image.
# Executes all new real-gateway offline controls and removes its stacks/keys.
& .venv-003a/Scripts/python.exe tests/livequalification/qualify.py --build
```

For a **separate operator-authorized paid run**, enter a key without echoing or
putting it in history/Compose environment. Use a file under your private Windows
user temporary directory. Keep its ACL limited to your account and Docker's
required access. No agent-run paid execution has occurred.

```powershell
$env:EPOCHGUARD_TAVILY_SECRET_HOST_FILE = Join-Path $env:TEMP ('epochguard-004e-' + [guid]::NewGuid().ToString('N') + '.key')
$secureKey = Read-Host 'Tavily key for the bounded 004E run' -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $keyText = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    [IO.File]::WriteAllText($env:EPOCHGUARD_TAVILY_SECRET_HOST_FILE, $keyText, (New-Object Text.UTF8Encoding($false)))
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
    Remove-Variable keyText, secureKey, keyPointer -ErrorAction SilentlyContinue
}
$env:EPOCHGUARD_RUN_LIVE_004E = '1'
try {
    & .venv-003a/Scripts/python.exe tests/livequalification/qualify.py --live
    if ($LASTEXITCODE -ne 0) { Write-Host 'Inspect the collected failure; do not retry automatically.' }
} finally {
    # Driver already cleans up. This also handles interrupted manual execution.
    docker compose -f compose.verify.004e.yaml down --volumes --remove-orphans
    Remove-Item -LiteralPath $env:EPOCHGUARD_TAVILY_SECRET_HOST_FILE -ErrorAction SilentlyContinue
    Remove-Item Env:EPOCHGUARD_TAVILY_SECRET_HOST_FILE, Env:EPOCHGUARD_RUN_LIVE_004E -ErrorAction SilentlyContinue
}
```

If rebuilding is needed, use `--live --build` in that same explicit operator
context. Do not print resolved live Compose configuration or inspect/dump secret
files/container environments. Qualification runner services have a separate
Compose profile and do not run during ordinary service startup. Health checks
call only `/health`; readiness is not periodic paid polling.

The host driver prints the fixed sources and proposed budget before any action,
starts a disposable stack, checks source-free readiness, performs one private
preflight, then runs client-only cases through ingress. Cases A/B are the only
factual source requests: observed two-claim support and deterministic older
Python claim with supported PyPI neighbor. C adds unsupported prose, E uses
the private no-plugin control via its ingress, and F verifies a genuine provider
error. B asks for usable fallbacks; terminal refusal must prevent them. Provider
counters verify dispatch counts, with A/E's shared candidate reported as one
combined delta rather than invented per-case counts.

Maximum per dedicated process: three Tavily and three PyPI retrieval invocations,
including preflight, enforced independently for each source. Calls are sequential.
No retries, new URLs, source polling, Gemini or paid negative fault induction.
Failure stops/reports rather than looping until support. If observations change,
the original preflight is preserved, later versions and
`source_changed_since_preflight` are reported and unexpected outcomes are marked
inconclusive/failed. A repeat run requires another explicit operator invocation.

## Measurements and live status

`artifacts/004e/{offline,live}/measurements.json` contains case ID, start/finish,
HTTP status, elapsed and first-body-byte latency, release/exact candidate-byte
match, outcome, original claimed versions, source-change flag and matching private
verifier observations. Safe reports include source modes, validated versions,
policy reasons, evidence IDs/digests and observation times; no raw source bodies,
keys, receipts/nonces or arbitrary error text. Allowed HTTP entity bytes are
forwarded by ingress unchanged; the runner checks the exact assistant candidate
bytes and does not claim to independently recapture the original provider HTTP
entity at a second hop.

On a transport failure the runner preserves a sanitized case row with unknown
HTTP status/release/first-byte fields instead of inventing them or losing earlier
observations. The total 52s client deadline includes headers and every body chunk;
its cancellation closes the response/client, including a stalled partial body.

Per-source attempted/completed admitted underlying retrieval invocations and
durations are measured
inside the same budgeted process for preflight and inference. Completed means a
Page returned; later parser failure can still reject it. This is not Tavily
account billing, HTTP packet, redirect, origin-fetch or external-cache count.
Underlying clients have no retry/follow-redirect path. Pipeline elapsed time
includes retrieval/aggregation; client time includes all gateway/ingress work.
Separate provider latency, Go contract timing and ingress MAC/buffering timing
are unavailable. No unrelated timings are subtracted to invent them. Source
receipt times are not origin publication times.

At the end of the original implementation phase there were no live versions or
live results from that phase; the implementation agent made **zero** live calls.
The subsequent maintainer run and report assessment above supply the narrow live
qualification evidence. This documentation-only update also makes no live calls;
successful direct probes alone would not establish the protected end-to-end path.

## Original implementation: offline qualification evidence

Executed commands/results follow; all are offline.
Safe ignored logs are under `artifacts/004e/`; the existing 004D driver keeps its
own logs under `artifacts/004d/reproduction/`.

```powershell
& .venv-003a/Scripts/python.exe tests/livequalification/qualify.py --build
& .venv-003a/Scripts/python.exe tests/protectedingress/qualify.py

docker run --rm --network none epochguard-verifier:004e python -m pytest -p no:cacheprovider tests_multiclaim tests_gateway tests_live -q
docker run --rm --network none epochguard-verifier:003a python -m pytest -p no:cacheprovider -q

$env:PYTHONPATH = 'services/verifier;services/claim_analysis'
& .venv-003a/Scripts/python.exe -m pytest -c services/verifier/pytest.ini services/verifier/tests -q
& .venv-003a/Scripts/python.exe -m pytest -c services/verifier/pytest.ini services/verifier/tests_multiclaim services/verifier/tests_gateway services/verifier/tests_live -q
& .venv-003a/Scripts/python.exe -m pytest -c services/claim_analysis/pytest.ini services/claim_analysis/tests -q
```

The final experimental Docker image ran all 201 tests with networking disabled;
the earlier combined host run had 199 before adding two runner deadline/failure
tests. The final host new-test run passed 33. The legacy image's live marker is
explicitly deselected, not counted as a live pass.

The host driver executes these exact build commands (default builder name):

```powershell
docker buildx build --builder epochguard-002a --load -t epochguard-dev:002a -f dev/Dockerfile .
docker buildx build --builder epochguard-002a --load -t epochguard-verifier:004c -f services/verifier/Dockerfile.004c .
docker build -t epochguard-verifier:004e -f services/verifier/Dockerfile.004e .
```

Fresh Go checks additionally used copies of `dev/Dockerfile` with qualification
stages appended, following the 004D stage pattern. The plugin stage runs module
verification, then `go vet`, `go test -count=1 -mod=readonly -trimpath -v ./...`
and `go test -count=1 -race -p=2 -mod=readonly -trimpath ./...` in the pinned
plugin directory. The final ingress stage runs root formatting/vet and
`go test -count=1 -mod=readonly -trimpath -v ./internal/ingress ./cmd/protected-ingress`
plus the corresponding `-race` command. Test/vet RUN instructions use
`--network=none` and the existing module/build cache mounts. Exact invocations:

```powershell
docker buildx build --builder epochguard-002a --progress plain --target qualification-unit --no-cache-filter qualification-unit -f artifacts/004e/Dockerfile.unit .
docker buildx build --builder epochguard-002a --target qualification-ingress --progress plain -f artifacts/004e/Dockerfile.ingress .
```

Unchanged gateway regressions were run serially with these commands; each suite
was followed by `down --volumes --remove-orphans` using the same Compose flags:

```powershell
docker compose -f compose.verify.004c.yaml run --rm qualification
docker compose -f compose.verify.yaml run --rm verification-tests
docker compose --profile test run --rm smoke
docker compose -f compose.routes.yaml run --rm route-tests
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml run --rm verification-tests
```

| Check | Actual final result |
| --- | --- |
| Fresh plugin units | 33 top-level / 107 subtests passed; 0.235s |
| Fresh plugin race | Passed; 1.347s; no race report |
| Final fresh ingress + key CLI units | 11 top-level / 30 subtests passed; 0.533s / 0.003s |
| Final ingress + key CLI race | Passed; 1.585s / 1.017s; no race report |
| Go format/vet | Passed for plugin and ingress/CLI/relay/qualification components |
| Python legacy, Docker network none | 65 passed, 1 live deselected, 1 existing Starlette warning; 4.94s |
| Python 004B + endpoint + 004E, Docker network none | 201 passed (149 + 19 + 33); 3.31s |
| Claim analysis | 176 passed; 1.58s |
| Existing 004D client/operator | 4 top-level / 18 subtests and 4 top-level / 19 subtests passed |
| Existing 004D lifecycle | Startup, disable/in-flight, restart/recovery passed; final 30.20s window observed 496 supported, 136 safe refusals, recovered=true |
| Existing 004C gateway | 7 top-level / 42 subtests passed; unchanged concurrency test passed in 0.46s |
| Existing 003A gateway | 8 top-level / 31 subtests passed; live and separate long tests explicitly skipped in this short runner |
| Existing smoke | 10 top-level / 35 subtests passed |
| Existing routes | 4 top-level / 54 subtests passed |
| Separate existing long deadline | Passed 12.60s; HTTP 200; first body byte/total 12,584ms; provider/retrieval deltas 1/1 |
| Final 004E reproduction with builds | Passed; five client cases and 13 separately labeled simulated controls; cleanup passed |
| Opt-in/missing credential guards | Host rejects paid run without explicit flag/file before Docker/source calls; actual live-factory container rejects missing credentials with network none |
| Final scope/configuration audit | Nine existing files modified, 15 added; syntax/JSON/whitespace/fences, 61 local documentation links, `git diff --check`, both `config --quiet` profiles passed |

Race detection covers units, not live gateway processes. The original implementation
phase included no live test or isolated cache-lifecycle rerun. The fixture restart
counts are observations, not throughput benchmarks. Direct gateway/plugin/provider and all five legacy
test binaries were byte-identical before/after the final ingress-only deadline
adjustment; those suites' passing results apply to the unchanged binaries.

Final local native image:
`sha256:67ccd88959757eca25614aa67e8e2cf04d5dbdab39ef4551bf747439bab30bb0`.
Final 004E Python image:
`sha256:4c6cd9d04eded31efa053ff9df71dbfb7887f6210e5b29caadb052e147c5de2b`.
These identify tested local artifacts, not published releases.

### Measured final simulated demonstration

These versions/evidence are explicitly synthetic, not current source facts.
Standard source counters were 3 attempted / 3 completed per source: one preflight
and two factual requests. Readiness consumed zero. Cases C/E/F consumed no source
calls. Candidate bytes matched exactly for A; every refused case had no answer
leakage or internal receipt/debug headers. Provider deltas were A+E combined 2,
B/C/F 1 each; B did not release a fallback.

| Fixture case | HTTP | Total ms | First body byte ms |
| --- | --- | --- | --- |
| A: two supported claims | 200 | 92.967 | 90.688 |
| B: older Python + supported requests | 403 | 67.038 | 65.284 |
| C: unsupported extra content | 503 | 34.891 | 32.834 |
| E: missing plugin | 503 | 176.179 | 175.017 |
| F: genuine provider error | 400 | 44.357 | 41.763 |
| Long outer-deadline control | 200 | 21,039.561 | 21,036.861 |
| Fixture evidence sent to actual live-mode Go gateway | 503 | 161.232 | 160.041 |

The ten simulated Tavily/PyPI/credential/network faults all returned 503, with
total measured 24.545–43.912ms and no retry/answer leakage. They use injected
transport errors/responses rather than induced real outages. Evidence containing
an instruction to ALLOW an older candidate still produced 403 (29.494ms).
The long control deliberately gives its **test** transport 22s to sleep 21s,
isolating outer pipeline/ingress/receipt handling beyond the original limits.
Its fixture mode cannot satisfy live-mode evidence validation. Real Tavily keeps
its 20s transport limit; the long simulation is not a live Tavily observation.

### Preserved development failures

The initial 004C concurrent test failed with eight safe 503s while fresh Go work,
004D lifecycle and other gateway work were active. It remains recorded under
`artifacts/004e/regressions/004c-run.log`. The final serial run passed unchanged,
including the same eight-request assertion. Competing load is a plausible cause,
not a proven root cause; no deadline/assertion was weakened to obtain the pass.

Initial startup-sanitization tests used a sentinel identical to a word in the
fixed error message; nine assertions failed for that test-design mistake. A
distinct private sentinel corrected the check. Final tests verify that values
and file paths are not echoed. Later review tightened the ingress/client total
deadline hierarchy and added stalled-body cancellation/failure-record tests;
all affected checks and the complete 004D/004E ingress qualifications were rerun.

At the end of the original implementation phase, all task-owned stacks/networks
and generated signing-key volumes were removed; only the pre-existing BuildKit
builder remained running. That implementation agent created no real credential
file and performed no paid execution. The later maintainer-authorized live run
used its separately supplied temporary runtime credential file.

## Remaining limitations and review

This is a controlled, exact-template, two-source qualification with a synthetic
provider. The November 14 maintainer run met the narrow live acceptance checks;
broader verification remains unqualified. The existing numeric/label rules
may deliberately reject current/future source formatting; no policy was relaxed
to obtain support. Observation age is not origin freshness. General prose,
additional policies/providers, live model quality, production authentication,
authenticated verifier transport, safe streaming, protected caching and broader
routes/background work remain outside scope. A compromised trusted process,
host, key or verifier can defeat this trust boundary. External source changes
and transient failures can make a correctly failing live run inconclusive.

## Documentation-only consistency update

This follow-up started from clean `main` at
`662bc38639178ea4f39866740626b872d0820efb`. It changes only this report,
`README.md`, `AGENTS.md`, `docs/architecture.md` and
`services/verifier/README.md`. It records the supplied live results, scopes the
original no-live-call statements to their execution phase, distinguishes the
two-policy protected profile from legacy 003A, and corrects the obsolete claim
that isolated protected readiness is absent. Production readiness remains
unqualified.

The 002A/B/C, 003A/B/C, 004A/004A-H/004B/C/D reports and ADRs 0001–0003 were
reviewed without changing their execution-time results. Local validation passed
across all 24 tracked Markdown files: balanced fences, link/reference syntax,
152 local links including 10 anchor links, and the 17 tables in the five changed
documents. Inline repository/source references resolved; generated
runtime references were distinguished from tracked source paths. The sole
remaining pending-status phrase in these five documents is the
historical offline runner output above, explicitly labeled as such.

SHA-256 comparison with the starting tree confirms all other 210 tracked files
are unchanged, including implementation, tests, policies, contracts, Compose
profiles, older reports and ADRs. No new tracked files, credentials or private
runtime artifacts were added. The three existing live JSON reports matched the
documented versions, outcomes, timings, claim verdicts and application-level
counts. `git diff --check` passed; the final diff was reviewed for unrelated
formatting changes. Only offline documentation/report checks ran during this
update; no application tests, Tavily/PyPI/Gemini requests or paid qualifications
were executed.

Original implementation's recommended conventional commit:
`feat(verifier): add opt-in protected live multi-claim qualification`.

Recommended documentation commit, not created:
`docs: record 004E live qualification and align project status`.

Stop for maintainer review. This update changes documentation only; no
implementation, tests, policies, contracts, deployment configuration or runtime
behavior is changed, and no live requests, commits or pushes are performed.
