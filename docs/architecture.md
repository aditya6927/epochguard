# EpochGuard architecture

**Status:** narrow live Bifrost → Go → FastAPI → Tavily qualification is complete on the maintainer-supplied November 8 rerun: `TestLiveGatewayQualification` and all five subtests passed in 18.16s, including supported delivery and older terminal refusal without answer leakage. Initial blocked 401 attempts remain documented; their exact credential-mismatch cause is not proven. This covers the existing single policy with the local provider fixture. Default and verification deployments keep caching disabled; general verification, production readiness, and the protected cache remain unimplemented or unqualified. Updated: 2026-11-08.

## Problem and system boundary

EpochGuard is intended to verify time-sensitive claims in AI-generated responses, track supporting evidence, and prevent known-stale responses from being returned or reused. The qualified engineering boundary is more limited: a native Go plugin enforces decisions on one buffered inference route. Its HTTP source checks one exact Python Windows release-label claim through a narrow evidence policy. Offline fixtures and the maintainer-reported narrow live gateway rerun qualify that path, with the limits recorded in Task 003B.

### As implemented in Task 002B

```text
Client (HTTP, non-streaming)
    |
    v
Bifrost HTTP gateway (v2.4.0, dynamic Linux build)
    |-- HTTPTransportPreHook     [refuse streaming/async/unsupported routes]
    |-- PreRequestHook          [EpochGuard: record]
    |-- PreLLMHook              [typed buffered-chat guard]
    |       |
    |       v
    |   local OpenAI-compatible fixture provider
    |       |
    |       v
    |-- PostLLMHook             [preserve provider error OR wait for decision]
    |       |-- ALLOW          [same response pointer]
    |       |-- REJECT         [nil response, terminal typed 403]
    |       '-- UNAVAILABLE    [nil response, terminal typed 503]
    |-- HTTPTransportPostHook   [EpochGuard: diagnostic headers]
    v
Client sees allowed fixture response OR safe error
```

`plugins/epochguard/main.go` exports the native hooks and keeps phase names in a request-owned `hookTrace`. A pointer created at the HTTP phase is visible in the child core context. A `sync.Mutex` protects the trace's slice. Request/response wrappers are borrowed and never retained beyond hook execution.

`decision.go` defines `DecisionSource.Decide(context.Context, *schemas.BifrostResponse) (Decision, error)` and the enforcement policy. A fixed, test-only source ignores client input and provider content. Immutable process configuration is published through an atomic pointer; absent configuration defaults to UNAVAILABLE. Fixed ALLOW/REJECT configuration requires `test_only: true`. This switch acknowledges a fixture, not a production verification policy. Task 003A adds an HTTP implementation; the gateway still owns refusal. Source errors never become client-visible refusal text.

On a successful candidate, the post-hook waits synchronously. REJECT, UNAVAILABLE, evaluation errors, unknown decisions, missing candidates, and cancelled evaluation never return the answer. Refusals use `BifrostError` with a fixed message and `AllowFallbacks: &false`, and return nil for the ordinary Go hook error. Genuine provider errors are preserved by pointer and skip evaluation, including their original fallback policy. Every successful fallback candidate is evaluated. No HTTP post-hook error or header is used to enforce this policy.

`guard.go` returns a complete HTTP 400 before dispatch for streaming, async headers, malformed/missing body snapshots, and registered inference routes other than the supported buffered chat route. Health and management use a separate middleware chain without the HTTP transport interceptor; changing the guard's `/api` exemption would not close that boundary. The typed pre-LLM guard also refuses non-chat and streaming request types. This does not qualify direct SDK traffic or alternate transports.

[Task 003C](task-003c.md) qualifies the actual registered passthrough prefixes, selected alternate transports, raw path variants and configured Warp chat with an isolated synthetic provider. Passthrough buffer/stream controls reach core hooks and expose synthetic answers without EpochGuard; with it they stop at HTTP 400 before dispatch. The router matches `PathOriginal()` while the plugin receives normalized `ctx.Path()`. Tested redirects run before hooks; mismatched passthrough paths fail upstream prefix validation. No tested path released a provider answer with EpochGuard active.

Warp's interactive model call uses `ResponsesStreamRequest` even for buffered HTTP output. It skips HTTP hooks but reaches the core guard, which blocks it before the provider; Warp wraps the typed refusal in HTTP 200 JSON/SSE with an empty answer/error event. Logging/configuration prerequisite 503s are not enforcement. Warp indexing/topic jobs can explicitly skip the plugin pipeline, and management/log/history responses, separate A2A gRPC bindings and background execution are outside the qualified answer boundary. Keep these capabilities and configuration trusted; a raw-path ingress allowlist and isolation of management/background execution require separate design review before any broader deployment claim. No core change or ingress was implemented in this audit.

The plugin loads using upstream exported Go symbols and matching shared module versions. `dev/Dockerfile` checks out the fixed Bifrost commit, builds a dynamically linked gateway and plugin on the same Linux/amd64 Go toolchain, and runs unit tests including the race detector. Compose runs the real gateway smoke tests. The built-in cache is **not enabled** in the default deployment; it is enabled only in the isolated Task 002C qualification stack.

### Task 002C cache qualification

`compose.cache.yaml` adds a real Redis Stack vector backend and direct-only `semantic_cache` configuration (`dimension: 1`, no embedding provider). Seven gateway processes use fixed trusted decisions/placement. A transparent test-only TCP proxy can hold a real Redis HSET before forwarding it, making pending-write/invalidation races deterministic. No service in this stack publishes a host port.

Observed order, with unrelated built-ins omitted:

| Placement | Miss | Hit |
| --- | --- | --- |
| pre_builtin | E.Pre, C.Pre, provider, C.Post, E.Post | E.Pre, C.Pre, C.Post, E.Post |
| post_builtin | C.Pre, E.Pre, provider, E.Post, C.Post | C.Pre, C.Post; EpochGuard LLM hooks skipped |

The cache serializes and launches its own writer before early EpochGuard evaluates the candidate. Experiments observed physical storage while a REJECT decision was pending. Moving EpochGuard late prevents writing rejected misses but lets cached answers bypass its LLM hooks. These are isolated unsafe controls, not approved protected configurations.

The optional trusted `cache_no_store` flag sets the exported `semanticcache.CacheNoStoreKey` in EpochGuard's pre-hook, after transport parses headers. It suppresses all built-in writes, including allowed ones, while preserving reads. The tests prove a client false value cannot undo it and that cached candidates still receive safe early refusals. `test_decision_delay_ms` remains a bounded, cancellation-aware test fixture for 002C. Task 003A's HTTP source always sets server no-store as defense in depth and keeps caching disabled. `X-EpochGuard-Cache-At-Post` snapshots cache telemetry for diagnostics only.

Both supported management deletion APIs removed settled entries, with scope and provider-counter controls. Both also allowed a held, older asynchronous writer to repopulate an absent entry after successful invalidation. Physical deletion and TTL do not establish logical revocation or factual freshness. [Task 002C](task-002c.md) records exact source, traces, counters, commands, and limitations; [ADR 0003](decisions/0003-protected-cache-ownership.md) proposes ownership of verified admission and generation-aware revocation for the future cache.

### Task 003A narrow evidence path

```text
Buffered provider candidate inside Bifrost
  -> Go exact whole-answer parser / request nonce / SHA-256
  -> bounded, context-aware HTTP call to trusted FastAPI /v1/verify
  -> fixed-URL Tavily Extract (candidate is not sent to Tavily)
  -> unique Python.org Windows latest-stable label comparison
  -> typed verdict + evidence reference + observation times + reason
  -> Go validates binding, mode, timestamps and verdict consistency
  -> original response OR nil response + terminal typed refusal
```

The only accepted sentence is `The latest stable Python 3 release for Windows listed on Python.org is X.Y.Z.` Equal numeric versions map to SUPPORTED/ALLOW, older candidates to CONTRADICTED/REJECT, and newer candidates to INSUFFICIENT/UNAVAILABLE because the source extraction may lag. Unsupported/additional claims, ambiguous/missing evidence, timeout, malformed records, and network/verifier failures are unavailable. No LLM interprets retrieved instructions. Only one complete plain assistant choice is covered.

`services/verifier/verifier/contract.py` and `plugins/epochguard/http_decision.go` define schema `003a.v1`, policy `python-windows-latest-v1`, request/hash binding, typed claim/verdict/reasons, canonical evidence URL, content hash, retrieval ID/mode, and retrieval/observation/check times. Observation time is receipt of extracted text, not proof of origin publication time or Tavily's fetch age. The verifier and its network/configuration remain trusted; records are not signed attestations. `fixture` evidence requires explicit test configuration and is rejected in live mode.

FastAPI bounds bodies, retrieval and work deadlines; Go independently bounds response size and total HTTP duration and respects the supplied cancellation context. The 2026-11-07 follow-up makes service budgets validated process configuration: offline defaults remain 4/4.5/6 seconds, while the opt-in live profile uses 20/22/25 seconds and a 30-second integration client. Pinned source inspection and a real 12.567-second offline gateway test confirm that the fixture provider's ten-second network timeout does not bound post-hook work on this path. Existing synchronous typed refusals, genuine upstream error preservation, and no-fallback behavior remain unchanged. No answer is released while the decision is pending. Actual transport disconnect propagation and production providers remain unqualified.

`compose.verify.yaml` runs real gateway/plugin/service instances on an internal network, using only an HTTP Tavily fixture. `compose.verify.live.yaml` explicitly enables egress and loopback gateway access with an environment key for manual live follow-up. Default `compose.yaml` remains the fixed test-only 002B example. [Task 003A](task-003a.md) records the contract, trust assumptions, experiments, actual counters, latencies, and live-test instructions. There is no new cache or persistent evidence database.

The live override explicitly selects `TestLiveGatewayQualification` and requires a runner opt-in flag. The runner shares the existing HTTP assertions, receives no API credential, obtains a dynamic version from one direct verifier observation, and then exercises supported/older candidates through Bifrost with usable fallbacks and forged controls. No enforcement or verification architecture changes are introduced. [Task 003B](task-003b.md) distinguishes the earlier blocked attempts, separately reported FastAPI pass, successful maintainer-run gateway qualification, and unavailable live retrieval counts.

### Supported and unsupported surface

| Qualified in 002B | Not qualified in 002B |
| --- | --- |
| `/openai/v1/chat/completions` | Other HTTP inference routes, direct SDK calls |
| Buffered requests; streaming/async pre-dispatch refusal | Safe streamed response delivery, realtime, passthrough, async jobs |
| Local deterministic OpenAI-compatible fixture | Production providers, private repositories, third-party user data |
| Plugin load/order, typed refusal, no answer leak, terminal fallback | Enforced startup readiness, live verification, arbitrary plugin combinations |
| Concurrent smoke requests and plugin unit race detection | Race detection of gateway internals, load testing, production performance |

The configured development fixture is intentionally unauthenticated on inference and bound to host loopback. It must not be deployed as a production service.

## Proposed product components — not yet delivered

```text
Client -> Bifrost + EpochGuard enforcement -> verified response / safe refusal
                          |
                          v
                  Verification service
                  | claim extraction
                  | time-sensitivity classification
                  | Tavily evidence retrieval
                  | evidence comparison
                  | decision record
                          |
                          v
                  Evidence DB + verified cache
                          |
                          v
                  Periodic revalidation / invalidation
```

Task 002B establishes waiting, typed refusals, and no-leak behavior using deterministic fixtures. Task 003A implements the first narrow service policy above; the diagram's broader extraction, classification, durable evidence, and revalidation components remain proposed. The trusted gateway policy chooses and enforces actions. Verification may be unavailable; that is an explicit policy outcome, **not** a successful verdict.

Future caching must bind a response to trusted request scope, policy version, evidence IDs/versions, and expiry. A stale physical cache entry must not become returnable after a concurrent write or invalidation race. Task 002C reproduced both the built-in cache's enforcement-order hazards and late-write repopulation; unrestricted built-in writes remain unsuitable for the protected deployment. A future EpochGuard-owned cache needs explicit admission and read/release validity checks plus atomic generation/version comparison, not deletion alone.

## Current acceptance boundary

Task 002B exercises **ALLOW**, **REJECT**, and **UNAVAILABLE** decisions on *real* Bifrost provider responses. Its gate requires zero rejected fixture sentinel bytes in the client-visible HTTP response, no undesired fallback, and negative controls. Executed results, request-flow details, and limitations are recorded in [task-002b.md](task-002b.md); 003A reruns that gate unchanged.

Task 002C extends that gate with isolated direct-cache lifecycle experiments and explicit unsafe controls. Its results qualify the documented experiments, not production cache safety or semantic similarity mode. The final protected cache remains outside this milestone.

Task 003A and its timeout follow-up cover 41 offline service tests and real gateway acceptance with 31 subtests, plus a separate deterministic long-duration path. Task 003B reran that gate and added an offline version-derivation check and opt-in live gateway test. The maintainer subsequently reported a full live gateway pass with five passing subtests, distinct from the earlier FastAPI-only pass. Supported and older requests each used one provider call; live retrieval counts remain unavailable. This qualifies one policy with the controlled provider and explicitly recorded paths, not arbitrary response verification or production provider support.

## Primary references

- `docs/bifrost-integration-spike.md` — source investigation and hook/cache contracts.
- `docs/task-002a.md` — executed build and smoke-test evidence.
- `docs/task-002b.md` — synchronous enforcement design and executed qualification evidence.
- `docs/task-002c.md` — real direct-cache lifecycle and race evidence.
- `docs/task-003a.md` — narrow evidence policy, typed service contract, executed offline integration and live-test boundary.
- `docs/task-003b.md` — successful maintainer-run live gateway qualification, separately reported FastAPI evidence, preserved blocked attempts, and reproducible opt-in runner.
- `docs/decisions/0003-protected-cache-ownership.md` — proposed verified admission/revocation design.
- `docs/decisions/0001-native-bifrost-plugin.md` — rationale and alternatives.
