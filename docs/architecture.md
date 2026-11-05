# EpochGuard architecture

**Status:** working integration spike (Task 002A); future product architecture is *proposed*, not yet implemented. Updated: 2026-11-06.

## Problem and system boundary

EpochGuard is intended to verify time-sensitive claims in AI-generated responses, track supporting evidence, and prevent known-stale responses from being returned or reused. The first verified engineering boundary is more limited: a native Go plugin can execute in Bifrost's gateway lifecycle for one buffered inference route.

### As implemented in Task 002A

```text
Client (HTTP, non-streaming)
    |
    v
Bifrost HTTP gateway (v2.4.0, dynamic Linux build)
    |-- HTTPTransportPreHook     [EpochGuard: record]
    |-- PreRequestHook          [EpochGuard: record]
    |-- PreLLMHook              [EpochGuard: pass through]
    |       |
    |       v
    |   local OpenAI-compatible fixture provider
    |       |
    |       v
    |-- PostLLMHook             [EpochGuard: preserve result/error]
    |-- HTTPTransportPostHook   [EpochGuard: diagnostic headers]
    v
Client sees fixture response
```

`plugins/epochguard/main.go` keeps phase names in a request-owned `hookTrace`. A pointer created at the HTTP phase is visible in the child core context. A `sync.Mutex` protects the trace's slice. The plugin does not retain request or response wrappers beyond hook execution and does not yet reject unsafe model output.

The plugin loads using upstream exported Go symbols and matching shared module versions. `dev/Dockerfile` checks out the fixed Bifrost commit, builds a dynamically linked gateway and plugin on the same Linux/amd64 Go toolchain, then runs unit and smoke tests. The built-in Bifrost semantic cache is **not enabled** in the qualified 002A deployment.

### Supported and unsupported surface

| Qualified in 002A | Not qualified in 002A |
| --- | --- |
| `/openai/v1/chat/completions` | Other HTTP inference routes, direct SDK calls |
| Buffered `stream: false` requests | Streamed responses, realtime, passthrough, async jobs |
| Local deterministic OpenAI-compatible fixture | Production providers, private repositories, third-party user data |
| Plugin load status/order and complete hook trace | Enforced startup readiness, response refusal, live verification |
| Six concurrent smoke requests | Load testing, race detection at scale, production performance |

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

Future non-streaming enforcement must wait for the verification result before returning protected answer bytes, use Bifrost's typed error/short-circuit carrier to refuse, and test no-leak behavior. The verification service may suggest actions; the trusted gateway policy chooses and enforces them. Verification may be unavailable; that is an explicit policy outcome, **not** a successful verdict.

Future caching must bind a response to request scope, policy version, evidence IDs/versions, and expiry. A stale physical cache entry must not become returnable after a concurrent write or invalidation race. Do not reuse Bifrost's built-in cache for protected traffic without a separate compatibility test: its pre-hook may short-circuit and its post-hook may queue writes before a later verification hook rejects a candidate.

## Next acceptance boundary

Task 002B will exercise **ALLOW**, **REJECT**, and **UNAVAILABLE** decisions on *real* Bifrost provider responses. Acceptance requires zero rejected fixture sentinel bytes in the client-visible HTTP response, no undesired fallback, and negative controls. Do not add claim extraction or Tavily before that gate behaves as intended.

## Primary references

- `docs/bifrost-integration-spike.md` — source investigation and hook/cache contracts.
- `docs/task-002a.md` — executed build and smoke-test evidence.
- `docs/decisions/0001-native-bifrost-plugin.md` — rationale and alternatives.
