# ADR-0001: Qualify a native Bifrost plugin before building the verification engine

- **Status:** Accepted for the Task 002A integration; caching and production enforcement decisions remain provisional.
- **Date:** 2026-11-06
- **Decision owners:** EpochGuard project maintainers

## Context

EpochGuard must intercept real AI gateway traffic and eventually enforce response-freshness policy. Bifrost's open-source Go plugin interface is available but the official published binaries are normally statically linked. Native Go plugins require binary compatibility between host and plugin. Bifrost's built-in semantic cache can short-circuit model requests and its write lifecycle complicates post-response verification.

## Options considered

1. **Native Go plugin in a source-built dynamic Bifrost gateway:** direct access to documented request/response hooks and typed errors; requires a controlled Linux/Go build and explicit activation checks.
2. **Sidecar HTTP proxy around stock Bifrost:** stock image compatible, but the proxy—not a native Bifrost extension—would own interception; can introduce another gateway boundary and trust risk.
3. **Modify Bifrost core:** direct integration, but higher maintenance burden, less clear upstream acceptance, and unnecessary for the basic hook spike.

## Decision

For Task 002A, use option 1, pinned to Bifrost HTTP `transports/v2.4.0` (source commit `e869c3f9adc96ea53c38694a21bb04a8e1085487`) and Go 1.27.3 on Linux/amd64. Export only the upstream-compatible Go plugin symbols, configure `pre_builtin` placement and order `0`, and validate the actual loader and request lifecycle through the containerized gateway. Use a deterministic local provider fixture and independent negative control.

Do not enable the built-in semantic cache in this qualified development path. A future EpochGuard-owned verified cache is the leading design, **not** an implemented component or irrevocable decision. Investigate a stock-Bifrost adapter as a separate compatibility mode if the challenge's deployment criteria require it; do not call it a native plugin.

## Consequences

- **Positive:** real execution at the intended enforcement boundary, upstream interfaces retained, reproducible local qualification without paid provider credentials.
- **Costs:** dynamic gateway build and exact Go dependency alignment; Linux plugin binary cannot be hot-swapped safely; default static Bifrost images cannot load it as-is.
- **Risks:** plugin-load failure may leave the gateway serving traffic; plugin ordering and cache behavior require production-level readiness and refusal testing; supported route/mode coverage is limited.
- **Mitigations:** test active plugin/order plus request execution; explicitly gate traffic in future deployments; add typed-error refusal and cached-response tests before making protection claims.

## Evidence and re-evaluation

The reported Task 002A build, provider request, negative control, and concurrency smoke tests are recorded in `docs/task-002a.md`. Future decisions should be revised if upstream plugin interfaces change, stock deployment becomes mandatory, or a measured cache safety/performance test invalidates the proposed design.
