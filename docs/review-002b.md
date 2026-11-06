# Review of Task 002B (source inspection)

- **Reviewed commit:** `58c4b3b788cf59bb632feb1dc805edc4ff92a7de`
- **Review date:** 2026-11-06
- **Review source:** `https://github.com/aditya6927/epochguard`
- **Validation:** Static inspection of committed Go source, tests, Compose/Docker configuration, and documentation. Docker tests were **not rerun by the reviewer**. Execution evidence comes from `docs/task-002b.md`.

## Verdict

Accept Task 002B for its stated, narrow purpose: deterministic synchronous enforcement on the qualified buffered OpenAI chat route. No confirmed failure of the ALLOW / REJECT / UNAVAILABLE paths was found in source inspection. This is **not** approval for production deployment or broad protection claims.

## Review observations

1. `plugins/epochguard/decision.go`: the enforcement function returns a nil response and a typed terminal Bifrost error for REJECT and UNAVAILABLE, while passing genuine upstream errors unchanged. The `DecisionSource` interface is small and separable from enforcement. Caller cancellation is checked before and after evaluation.
2. `plugins/epochguard/guard.go`: unqualified inference paths and explicitly requested streaming/async modes are rejected before the provider dispatch path for the tested HTTP transport. The guard is not a complete schema validator, and it does not protect unrelated transports or direct SDK calls.
3. `plugins/epochguard/main.go`: immutable policy snapshots are loaded through an atomic pointer; request phase traces remain request-owned. Invalid config deliberately returns success from Init while leaving no ALLOW source installed. A plugin that fails to load entirely is a distinct, unresolved fail-open risk.
4. `tests/smoke/enforcement_test.go`: checks complete serialized refusal for sentinel markers, traces, provider call counts, fallback stopping, streaming controls, and the unprotected gateway negative control. This is meaningfully stronger than checking status codes alone.
5. `dev/Dockerfile` / `compose.yaml`: live gateway and native `.so` are built in one pinned Linux toolchain; plugin unit tests include race detection. The race detector does not instrument the running gateway process.

## Open findings and next actions

| Priority | Finding | Action |
| --- | --- | --- |
| High before public deployment | Missing/failed native plugin may leave Bifrost healthy and inference available. | Implement external readiness/traffic gating and prove a missing-plugin negative control prevents public ingress. Do not confuse this with invalid config in a loaded plugin. |
| High before external use | The development gateway uses hardcoded *test-only* ALLOW and disables inference auth. | Keep bound to loopback; add authenticated production profiles and disallow deterministic ALLOW in production. |
| Medium | Cache-hit ordering, unverified cache writes, and invalidation races are not qualified. | Task 002C should test the real built-in cache lifecycle, plugin placement, refusal on hits, and no-store behavior before designing a protected cache. |
| Medium | Guard coverage is deliberately route-specific. | Maintain a supported-route allowlist and integration tests as new paths or plugins are enabled. Add malformed-body and empty/ambiguous async-header cases if changing parsing or supported transports. |
| Medium before public release | No automated GitHub CI checks are present. | Add focused CI for formatting, unit/race tests, and at least one reproducible integration smoke suite when CI compute capacity allows. |
| Documentation | `docs/task-002b.md` accurately covers implementation and limitations. | Add ADR-0002 to record the typed-refusal decision; avoid duplicating the extensive test transcript. |

## Suggested next milestone

Task 002C should be an **integration study and test suite for Bifrost's cache behavior**, not immediate implementation of a large cache service. Use deterministic provider responses and actual cache requests to prove ordering, no-answer-leak enforcement on hits, no-store behavior on rejected misses, write/delete races, and missing-plugin detection. Preserve the existing enforcement tests throughout.
