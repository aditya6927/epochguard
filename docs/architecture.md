# EpochGuard architecture

**Status:** Task 002C qualifies the built-in direct-cache lifecycle in an isolated deployment, preserving Task 002B enforcement. Unsafe admission/order/race controls are reproduced; the default deployment keeps caching disabled. Live freshness verification and the protected cache remain *proposed*, not implemented. Updated: 2026-11-06.

## Problem and system boundary

EpochGuard is intended to verify time-sensitive claims in AI-generated responses, track supporting evidence, and prevent known-stale responses from being returned or reused. The qualified engineering boundary is more limited: a native Go plugin enforces deterministic test decisions in Bifrost's gateway lifecycle for one buffered inference route.

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

`decision.go` defines `DecisionSource.Decide(context.Context, *schemas.BifrostResponse) (Decision, error)` and the enforcement policy. A fixed, test-only source ignores client input and provider content. Immutable process configuration is published through an atomic pointer; absent configuration defaults to UNAVAILABLE. ALLOW/REJECT configuration requires `test_only: true`. This switch acknowledges a fixture, not a production verification policy. A future external service can implement the interface; the gateway will still own the refusal decision. Source errors never become client-visible refusal text.

On a successful candidate, the post-hook waits synchronously. REJECT, UNAVAILABLE, evaluation errors, unknown decisions, missing candidates, and cancelled evaluation never return the answer. Refusals use `BifrostError` with a fixed message and `AllowFallbacks: &false`, and return nil for the ordinary Go hook error. Genuine provider errors are preserved by pointer and skip evaluation, including their original fallback policy. Every successful fallback candidate is evaluated. No HTTP post-hook error or header is used to enforce this policy.

`guard.go` returns a complete HTTP 400 before dispatch for streaming, async headers, malformed/missing body snapshots, and registered inference routes other than the supported buffered chat route. Health and `/api` management are outside the inference boundary and must be trusted. Bifrost may reject unregistered URLs before invoking plugin middleware; the tested unregistered OpenAI passthrough URL returns 405. The typed pre-LLM guard also refuses non-chat and streaming request types. This does not qualify direct SDK traffic or alternate transports.

The plugin loads using upstream exported Go symbols and matching shared module versions. `dev/Dockerfile` checks out the fixed Bifrost commit, builds a dynamically linked gateway and plugin on the same Linux/amd64 Go toolchain, and runs unit tests including the race detector. Compose runs the real gateway smoke tests. The built-in cache is **not enabled** in the default deployment; it is enabled only in the isolated Task 002C qualification stack.

### Task 002C cache qualification

`compose.cache.yaml` adds a real Redis Stack vector backend and direct-only `semantic_cache` configuration (`dimension: 1`, no embedding provider). Seven gateway processes use fixed trusted decisions/placement. A transparent test-only TCP proxy can hold a real Redis HSET before forwarding it, making pending-write/invalidation races deterministic. No service in this stack publishes a host port.

Observed order, with unrelated built-ins omitted:

| Placement | Miss | Hit |
| --- | --- | --- |
| pre_builtin | E.Pre, C.Pre, provider, C.Post, E.Post | E.Pre, C.Pre, C.Post, E.Post |
| post_builtin | C.Pre, E.Pre, provider, E.Post, C.Post | C.Pre, C.Post; EpochGuard LLM hooks skipped |

The cache serializes and launches its own writer before early EpochGuard evaluates the candidate. Experiments observed physical storage while a REJECT decision was pending. Moving EpochGuard late prevents writing rejected misses but lets cached answers bypass its LLM hooks. These are isolated unsafe controls, not approved protected configurations.

The optional trusted `cache_no_store` flag sets the exported `semanticcache.CacheNoStoreKey` in EpochGuard's pre-hook, after transport parses headers. It suppresses all built-in writes, including allowed ones, while preserving reads. The tests prove a client false value cannot undo it and that cached candidates still receive safe early refusals. `test_decision_delay_ms` is a bounded, cancellation-aware test fixture; no external verification service exists. `X-EpochGuard-Cache-At-Post` snapshots cache telemetry for diagnostics only.

Both supported management deletion APIs removed settled entries, with scope and provider-counter controls. Both also allowed a held, older asynchronous writer to repopulate an absent entry after successful invalidation. Physical deletion and TTL do not establish logical revocation or factual freshness. [Task 002C](task-002c.md) records exact source, traces, counters, commands, and limitations; [ADR 0003](decisions/0003-protected-cache-ownership.md) proposes ownership of verified admission and generation-aware revocation for the future cache.

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

Task 002B establishes waiting, typed refusals, and no-leak behavior using deterministic fixtures. A future verification service may suggest actions; the trusted gateway policy chooses and enforces them. Verification may be unavailable; that is an explicit policy outcome, **not** a successful verdict.

Future caching must bind a response to trusted request scope, policy version, evidence IDs/versions, and expiry. A stale physical cache entry must not become returnable after a concurrent write or invalidation race. Task 002C reproduced both the built-in cache's enforcement-order hazards and late-write repopulation; unrestricted built-in writes remain unsuitable for the protected deployment. A future EpochGuard-owned cache needs explicit admission and read/release validity checks plus atomic generation/version comparison, not deletion alone.

## Current acceptance boundary

Task 002B exercises **ALLOW**, **REJECT**, and **UNAVAILABLE** decisions on *real* Bifrost provider responses. Its gate requires zero rejected fixture sentinel bytes in the client-visible HTTP response, no undesired fallback, and negative controls. Executed results, request-flow details, and limitations are recorded in [task-002b.md](task-002b.md). This milestone does not introduce claim extraction, Tavily, or a verified cache.

Task 002C extends that gate with isolated direct-cache lifecycle experiments and explicit unsafe controls. Its results qualify the documented experiments, not production cache safety or semantic similarity mode. The final protected cache remains outside this milestone.

## Primary references

- `docs/bifrost-integration-spike.md` — source investigation and hook/cache contracts.
- `docs/task-002a.md` — executed build and smoke-test evidence.
- `docs/task-002b.md` — synchronous enforcement design and executed qualification evidence.
- `docs/task-002c.md` — real direct-cache lifecycle and race evidence.
- `docs/decisions/0003-protected-cache-ownership.md` — proposed verified admission/revocation design.
- `docs/decisions/0001-native-bifrost-plugin.md` — rationale and alternatives.
