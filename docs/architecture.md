# EpochGuard architecture

**Status:** Task 002B adds deterministic response enforcement to the qualified Task 002A integration. Live freshness verification and the remaining product architecture are *proposed*, not yet implemented. Updated: 2026-11-06.

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

The plugin loads using upstream exported Go symbols and matching shared module versions. `dev/Dockerfile` checks out the fixed Bifrost commit, builds a dynamically linked gateway and plugin on the same Linux/amd64 Go toolchain, and runs unit tests including the race detector. Compose runs the real gateway smoke tests. The built-in Bifrost semantic cache is **not enabled** in the qualified deployment.

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

Future caching must bind a response to request scope, policy version, evidence IDs/versions, and expiry. A stale physical cache entry must not become returnable after a concurrent write or invalidation race. Do not reuse Bifrost's built-in cache for protected traffic without a separate compatibility test: its pre-hook may short-circuit and its post-hook may queue writes before a later verification hook rejects a candidate.

## Current acceptance boundary

Task 002B exercises **ALLOW**, **REJECT**, and **UNAVAILABLE** decisions on *real* Bifrost provider responses. Its gate requires zero rejected fixture sentinel bytes in the client-visible HTTP response, no undesired fallback, and negative controls. Executed results, request-flow details, and limitations are recorded in [task-002b.md](task-002b.md). This milestone does not introduce claim extraction, Tavily, or a verified cache.

## Primary references

- `docs/bifrost-integration-spike.md` — source investigation and hook/cache contracts.
- `docs/task-002a.md` — executed build and smoke-test evidence.
- `docs/task-002b.md` — synchronous enforcement design and executed qualification evidence.
- `docs/decisions/0001-native-bifrost-plugin.md` — rationale and alternatives.
