# ADR-0002: Enforce buffered response decisions through typed Bifrost errors

- **Status:** Accepted for the qualified Task 002B development surface
- **Date:** 2026-11-06
- **Decision scope:** Pinned Bifrost HTTP v2.4.0, native EpochGuard Go plugin, non-streaming `POST /openai/v1/chat/completions`

## Context

Task 002A established real plugin loading and hook execution, but it did not prevent a successful provider answer from reaching the client. The gateway's ordinary Go hook-error return is not a reliable refusal mechanism. Bifrost also supports provider fallbacks, making it necessary to distinguish genuine upstream failures from EpochGuard policy refusals.

## Decision

1. Use a synchronous `DecisionSource.Decide(context.Context, *schemas.BifrostResponse) (Decision, error)` interface. Its test fixture supports ALLOW, REJECT, and UNAVAILABLE; no claim-level factual verification is implemented yet.
2. For successful buffered candidate responses, block release until the decision completes. ALLOW returns the unchanged provider response. REJECT returns a safe typed 403; UNAVAILABLE and decision errors return a safe typed 503. The refusal return tuple is `(nil, *schemas.BifrostError, nil)` with `AllowFallbacks` explicitly false.
3. Preserve genuine upstream `*schemas.BifrostError` by pointer and retain its fallback policy. A successful fallback candidate is subject to the same EpochGuard decision.
4. For the qualified HTTP route, reject streaming and asynchronous requests in the HTTP pre-hook before provider dispatch. The typed pre-LLM hook also rejects unsupported request kinds.
5. Keep deterministic ALLOW/REJECT decisions restricted to explicitly marked test configuration. Unknown/missing configuration must never yield a successful candidate response. A plugin-load failure remains outside this guarantee.

## Alternatives rejected

- **Return an ordinary Go error from `PostLLMHook`:** not a reliable enforcement signal in the pinned upstream pipeline.
- **Validate at the HTTP post-hook only:** it is later in the request lifecycle and not a safe universal stream or cache enforcement boundary.
- **Allow a fallback after policy rejection:** may return an unverified response following a terminal security decision.
- **Expose decision control through client-supplied headers:** lets untrusted callers bypass evaluation.

## Qualified evidence

The implementation and executed test results are recorded in [`../task-002b.md`](../task-002b.md). The repository's committed tests cover all three decision outcomes, answer-marker leakage, usable fallbacks, upstream error identity, pre-dispatch unsupported request refusal, concurrent hook requests, and no-plugin negative controls. Reported tests ran using the real pinned gateway with a deterministic local provider fixture. Source review of commit `58c4b3b788cf59bb632feb1dc805edc4ff92a7de` agrees with the described design; the review author did **not** rerun Docker tests.

## Consequences and open risks

- The current ALLOW mode is **test-only**; it must not be interpreted as verified freshness.
- No deployment-level readiness gate exists. Bifrost may serve inference if the plugin does not load at all; a runtime policy that defaults to UNAVAILABLE cannot prevent that case.
- Authentication is deliberately disabled in the loopback-only development fixture. Management, plugin configuration, and sibling plugins are trusted.
- Streaming, alternate routes, cache hits, arbitrary providers, and direct SDK calls are not qualified.
- A future verifier must impose deadlines, respect cancellation, handle partial evidence and ambiguous results, and avoid retaining pooled Bifrost objects.
- Future cache integration must avoid writing unverified provider results and must revalidate cached results before release.

## Revisit when

- Adding real Tavily/model verification or verifier retries/timeouts.
- Enabling the built-in Bifrost cache or an EpochGuard-owned protected cache.
- Exposing the service beyond local development, changing supported routes, or preparing an upstream/stock-installation demo.
