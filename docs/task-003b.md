# Task 003B — live gateway qualification

Date: 2026-11-08 (Asia/Calcutta). Scope: qualify the existing buffered Bifrost → EpochGuard Go plugin → FastAPI → Tavily route, without changing the claim policy, enforcement architecture, timeouts, or cache ownership.

**Result: completed narrow live gateway qualification**, based on the successful rerun supplied by the maintainer on **November 8, 2026**. Full `TestLiveGatewayQualification` passed in **18.16 seconds**, including all five subtests. Supported and older claims traversed the real Bifrost → Go → FastAPI → Tavily route, with the older answer refused without leakage or unintended fallback. The earlier blocked 401 qualification is preserved below. This qualifies the existing single policy with the local provider fixture, not general factual verification, production providers, production readiness, or a protected cache.

## Evidence supplied before this qualification

The maintainer reported the first credentialed FastAPI policy pass:

| Field | Reported result |
| --- | --- |
| Verdict / reason | SUPPORTED / MATCHED_PRIMARY_LABEL |
| Observed primary label | Python 3.15.2 |
| FastAPI request duration | 13.106 seconds |
| Trusted budgets | Tavily API 19s, whole retrieval 20s, FastAPI work 22s |

This is a maintainer-reported **FastAPI + Tavily** result, not an independently rerun result in this task or evidence that Bifrost/Go delivered or refused an answer. No request identifier, content digest, or observation timestamp was supplied with that report; none is invented here. The observed version is historical evidence, not a permanent test expectation.

## Deployment inspected before changes

The repository started clean. Inspection covered AGENTS, README, architecture, the integration spike, verification report, Compose configurations, provider fixture, typed contract, Go DecisionSource and existing gateway tests. The initial process environment had no Tavily key or live opt-in flag, `.env` was absent, and no live gateway was running. Compose's required-key interpolation refused to resolve the live stack. No key was fetched from another account or printed.

After the maintainer started the live stack, runtime preflight observed:

- Gateway healthy at **127.0.0.1:8081**; outbound-capable Compose network.
- Credential present in the verifier container; test mode and endpoint override both inactive.
- Actual verifier settings **19/20/22s**; gateway plugin file expects `tavily_live`, uses **25s**, `pre_builtin`, order **0**, and no semantic-cache configuration.
- The test's real management calls independently required EpochGuard loaded/active at that placement and `semantic_cache` absent. Health or configuration files alone were not accepted as execution proof.
- Gateway container image matched the built native test image. The gateway and plugin pins remain unchanged.

The preflight outputs only credential presence and public settings. It does not print environment values, resolved secret-bearing Compose configuration, provider credentials, or API response bodies. The Go runner receives only the public development management token and its explicit opt-in/client-budget settings; the Tavily key stays in the existing verifier container.

## Minimal changes and execution path

`tests/verification/live_test.go` adds a separate explicit live test and a small offline version-derivation check. Existing plugin-management assertions are shared through `requireActivePlugin`; existing exchange/refusal/no-answer assertions remain authoritative. `compose.verify.live.yaml` selects only the live gateway test, with `EPOCHGUARD_RUN_LIVE_TAVILY` defaulting to **0**. Production Go/Python verification code and claim coverage are unchanged.

The runner:

1. Requires opt-in and the 30-second client budget; checks the actual gateway's active plugin/order and absence of semantic cache before paid calls.
2. Exercises an unsupported answer containing an ALLOW instruction, a genuine provider error, and unsupported streaming.
3. Makes one direct `/v1/verify` observation using the supported minimum-version sentence (`3.0.0`). It validates request/hash binding, policy/schema, live mode, canonical authority, observation metadata and verdict consistency. The observed version determines the gateway candidates. The minimum-version probe is not an expected current fact.
4. Sends the observed version through the real gateway, requiring the original answer with HTTP 200. It derives an older numeric version and requires a safe terminal 403, no candidate/completion/private-sentinel bytes or answer/raw-response fields in serialized HTTP output, and exactly one provider call despite two usable fallbacks.
5. Stops at a failed live assertion without retries or relaxed expectations. If the source changes between observations and the expected outcome fails, that is a failed qualification, not a reason to freeze a version or relabel unavailable evidence.

Requests forge ALLOW, bypass, verified, excessive timeout, sub-millisecond retrieval timeout, no-store-false and raw-response headers. Expected policy outcomes, provider counts and hook traces must still hold. Actual deadlines are trusted configuration; client headers do not alter them. Existing unit/offline tests separately cover configured deadline propagation, parent cancellation, malformed contracts, unavailable evidence and terminal fallbacks.

A successful run makes up to **three extraction requests**: one direct bootstrap and two gateway candidates. These are independent observations, not automatic retries. Runtime diagnostics performed while investigating a failure are separate calls and must be counted separately from a passing run.

## Initial blocked qualification (preserved)

| Check | Observed result |
| --- | --- |
| Initial native runner invocation | PowerShell split an unquoted Go flag; runner stopped in flag parsing before any requests. Corrected by quoting the dotted Go flags |
| Real active plugin/order/cache inspection | Passed: EpochGuard active, pre_builtin/order 0; semantic_cache absent |
| Unsupported claim with forged controls and usable fallbacks | **503**, first byte/total **104/104 ms**, no answer leakage, provider delta **1**, full hook trace |
| Genuine upstream error | Original **400** / fixture upstream failure, **11 ms**, provider delta **1** |
| Unsupported streaming | **400**, **1 ms total**, provider delta **0**, no SSE delivery |
| Initial live version discovery | No usable evidence record; run stopped after **5.11s** total; supported/older gateway subtests did not run |
| Separate diagnostic fixed-URL extraction in verifier container | **HTTP 401**; no page body, key or raw API error was logged |
| Attempt after observed verifier recreation | Bootstrap returned **INSUFFICIENT / RETRIEVAL_FAILURE**, **4902 ms**; whole run **5.04s**. Unsupported 503 **112 ms**, original upstream 400 **12 ms**, stream 400 **1 ms** passed again; supported/older subtests did not run |
| Supported exact claim through gateway with live evidence | **Not run / blocked** by failed live discovery |
| Older exact claim through gateway with live evidence | **Not run / blocked** by failed live discovery |

The 401 was reported to the maintainer. After a verifier recreation was observed, one further qualification attempt still returned RETRIEVAL_FAILURE. The maintainer then selected **“Record blocked qualification”**; no further live calls were made during that agent-run qualification. This was a run after an external state change, not an automatic retrieval retry. A credential failure must not become an ALLOW. These failed observations remain part of the record; the later successful maintainer rerun is recorded separately below.

## Successful maintainer rerun — November 8, 2026

The following results were **supplied by the maintainer** and are recorded in this documentation-only update. They were not independently rerun by the documentation agent. The maintainer independently validated a working real Tavily credential with **HTTP 200**, then recreated the live Compose stack. The gateway, verifier, provider and evidence fixture all became healthy. Actual test inspection confirmed EpochGuard active at **pre_builtin, order 0**, with the semantic cache absent.

The full `TestLiveGatewayQualification` passed in **18.16 seconds**. All **five subtests passed**, with no observed bypass or fallback regression:

| Stage / subtest | Maintainer-supplied result | Reported latency | Provider delta |
| --- | --- | --- | --- |
| Live bootstrap, `3.0.0` probe | Discovered **3.15.2**; CONTRADICTED / OLDER_THAN_PRIMARY_LABEL | **5933 ms** | Direct verifier observation; no gateway provider call |
| Supported exact `3.15.2` claim | **HTTP 200** | **5964 ms** | **1** |
| Older exact `3.15.1` claim | **HTTP 403**, terminal refusal with no provider answer leakage | **6136 ms** | **1** |
| Unsupported answer | **HTTP 503** | **88 ms** | Not supplied in the rerun summary |
| Genuine provider error | Original **HTTP 400** preserved | **10 ms** | Not supplied in the rerun summary |
| Streaming request | Refused **HTTP 400** | **1 ms** | Not supplied in the rerun summary |

The plugin/cache checks and bootstrap run in the parent test; the five subtests are unsupported answer, genuine provider error, streaming refusal, supported claim and older claim. The reported passing test retains the existing forged-header, usable-fallback, provider-counter and no-answer assertions. No application code, policy, timeout setting or test assertion was changed for this documentation update.

The successful rerun followed supplying a working credential and recreating the stack. **The exact root cause of the original credential mismatch is not proven.** The earlier 401 and RETRIEVAL_FAILURE observations must not be rewritten as successes or assigned an unconfirmed configuration cause.

Version **3.15.2** is the label observed in this run, not a permanently correct live answer. The runner still discovers its candidate dynamically and derives the older version; no version was hardcoded into test expectations. The supplied summary contains outcomes and timings, not retrieval IDs, content hashes or observation timestamps; those fields are not invented here. These are individual request observations, not performance benchmarks or latency guarantees.

**Live retrieval counts remain unavailable.** Planned test calls, elapsed time and provider counters are not substitutes for independently measured Tavily retrieval counts. After the successful run, the maintainer reported stopping the Compose stack and clearing `TAVILY_API_KEY`. This supersedes the initial session's preserved-stack state; no credential value is recorded in the report.

## Counts and observability limits

The provider fixture exposes per-candidate counters; tests use before/after deltas and do not reset shared state. In the initial agent-run controls, unsupported 503 and genuine 400 each used one provider call; streaming used none. The successful maintainer rerun reports delta **1** for both supported and older candidates. The older refusal therefore did not advance to either of the two usable fallbacks requested by the test. Provider deltas for the other successful-rerun subtests were not included in the supplied summary; their assertions are covered by the reported full test pass.

The production verifier does **not** expose a live retrieval-attempt counter. A live bootstrap returns a retrieval ID and evidence metadata only on usable evidence; terminal gateway refusals intentionally return no provider/evidence record. A test runner's planned call count and response latency are not an independently measured Tavily account count. No new metrics endpoint, proxy or credentialed account-usage query was added just for this task.

For unsupported candidates, actual source inspection shows `plainCandidate` returning before HTTP request construction in `httpDecisionSource.Decide`. The real offline gateway suite independently observes **zero** retrieval-fixture increments for unsupported/additional claims, while valid supported/older controls increment once. The live 503/provider-count observation complements that evidence; it is not described as a directly measured zero Tavily count. Other traffic on the same verifier/account could also confound aggregate external counts.

## Reproduction

Build the native image from the repository root. In a trusted shell with `TAVILY_API_KEY` already set, start only the live gateway and its dependencies, then explicitly opt in the runner:

```sh
docker compose build gateway
docker compose -f compose.verify.yaml -f compose.verify.live.yaml up -d --wait gateway-supported
docker compose -f compose.verify.yaml -f compose.verify.live.yaml run --rm --no-deps -e EPOCHGUARD_RUN_LIVE_TAVILY=1 verification-tests
```

Use `--builder epochguard-002a` for the native build if the documented builder DNS workaround is needed. The live override selects `TestLiveGatewayQualification` only; it does not run synthetic-version offline expectations against Tavily. A skipped test without opt-in is not a live pass. Keep credentials out of command values/history and do not print resolved Compose configuration. README shows masked PowerShell entry and environment cleanup.

When the maintainer starts a credentialed stack from another terminal, an agent whose environment has no key can attach the keyless native runner directly to the existing network. The actual invocation here was:

```sh
docker run --rm --network epochguard-003a-live_default -e EPOCHGUARD_RUN_LIVE_TAVILY=1 -e EPOCHGUARD_GATEWAY_CLIENT_TIMEOUT_MS=30000 -e EPOCHGUARD_SETUP_TOKEN=epochguard-local-dev-only epochguard-dev:002a /app/verification.test '-test.v' '-test.run=^TestLiveGatewayQualification$' '-test.timeout=150s'
```

The setup token above is the repository's explicitly public local-development-only token, not a production secret. The test still uses the real gateway and native loader. Its supported/older assertions must execute and pass; a generic final PASS with a skipped live test is insufficient.

## Offline regressions from the original qualification

```sh
docker compose build --builder epochguard-002a gateway
docker run --rm --network none epochguard-verifier:003a python -m pytest -q -o cache_dir=/tmp/pytest-cache
docker compose -f compose.verify.yaml up -d --force-recreate --wait gateway-supported gateway-missing gateway-ambiguous gateway-timeout gateway-failure gateway-malformed
docker compose -f compose.verify.yaml run --rm --no-deps verification-tests
docker compose --profile test up -d --force-recreate --wait provider gateway gateway-control gateway-reject gateway-unavailable
docker compose --profile test run --rm --no-deps smoke
docker compose -f compose.verify.yaml down --remove-orphans
docker compose --profile test down --remove-orphans
```

Fresh plugin unit/race execution used the same pinned build stage and its existing dependency caches, with networking disabled for the test step. An ignored `artifacts/003b/Dockerfile.unit` appends `FROM build AS qualification-unit`, selects the plugin directory, and runs `go test -count=1 -mod=readonly -trimpath -v ./...` followed by `go test -count=1 -race -p=2 -mod=readonly -trimpath ./...` with the existing module/build cache mounts. The repository Dockerfile is unchanged. Exact invocation:

```sh
docker buildx build --builder epochguard-002a --file artifacts/003b/Dockerfile.unit --target qualification-unit --output type=cacheonly .
docker run --rm --network none epochguard-dev:002a /app/verification.test '-test.v' '-test.run=^TestLiveGatewayQualification$'
```

| Check | Actual result |
| --- | --- |
| Python offline tests, no network | **41 passed, 1 live deselected, 1 warning in 3.32s**; existing Starlette/HTTPX deprecation warning remains visible |
| Native image and new test binary | Build exit 0; formatting passed; unchanged gateway/plugin/unit/race layers reused from the prior successful build |
| Fresh plugin unit / race runs, `-count=1` and test-step network disabled | **18 top-level tests passed**, unit package **0.145s**, race package **1.224s**; exit 0, no reported races |
| Real offline evidence gateway suite | **8 top-level passed, 31 subtests passed**; live and long-profile tests explicitly skipped in this short offline environment |
| Final offline gateway rerun after safe diagnostic logging update | **8 top-level passed, 31 subtests passed**; same explicit live/long skips; exit 0 |
| Existing real gateway enforcement regression | **10 top-level passed, 35 subtests passed**; no test failures |
| New live opt-in guard with network disabled and no flag/key | **1 skipped**, exit 0; no network or live qualification |
| Offline fixture call controls | Unsupported/additional claims: provider delta 1, retrieval delta 0; genuine errors skip evaluation; supported/older/unavailable controls and usable fallback assertions passed |
| Final Compose validation, documentation and diff checks | Live/offline/legacy configurations valid; **45 local links** and balanced code fences checked across five documents; `git diff --check` exit 0 |
| Cleanup at the initial review | Offline stacks created by this task removed; maintainer-started live stack preserved then. The maintainer subsequently stopped it after the successful rerun |

Safe ignored evidence from the original agent-run qualification is retained under `artifacts/003b/`: native build logs, `go-unit-final.log`, offline suites, live preflight, initial flag-parsing transcript, `live-gateway-initial.log`, `live-gateway.log`, sanitized diagnostic status, and runtime traces. These original blocked-run logs are not replaced or presented as the successful rerun transcript. The successful rerun is recorded from the maintainer-supplied results above. No credential is part of source or logs.

## Documentation-only rerun update checks

For this November 8 documentation update, `git diff --check` exited 0. A local Python documentation check validated **45 relative links/anchors** and balanced code fences across README, AGENTS, architecture and the two verification reports; it also checked the supplied timings and preserved failure/limitation statements. A SHA-256 comparison of repository files before/after editing confirmed changes only to `README.md`, `AGENTS.md`, `docs/architecture.md` and this report. Application code, policy, configuration and test assertions are unchanged. No application tests, live requests or credential operations were executed for this update.

## Limits and review boundary

This qualification uses the controlled local provider and the existing single exact Python.org Windows release-label policy. It does not qualify production model providers, general factual verification, publication freshness, signed evidence, arbitrary plugins/transports, safe streaming delivery, production authentication, or a protected cache. Client disconnect propagation across every transport remains unqualified; supplied-context cancellation and bounded work are covered by existing unit tests. The built-in cache remains disabled.

Narrow live gateway qualification is complete on the maintainer-supplied evidence above; the initial blocked attempts remain visible. No verification architecture or ADR change is needed. This follow-up changes documentation only and does not rerun application/live tests or alter their assertions. Recommended documentation commit, not created: `docs: record successful narrow live gateway qualification`. Stop for maintainer review without committing.
