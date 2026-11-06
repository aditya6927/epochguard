# Task 002B: synchronous response enforcement

Validated on 2026-11-06 (Asia/Calcutta). Task boundary: extend the native Task 002A plugin to permit or refuse buffered provider responses using deterministic, test-only decisions. No claim extraction, freshness evidence checking, external verification service, Tavily, caching, dashboard, or Task 002C work is included.

## Result and policy

The real Bifrost gateway loads EpochGuard and enforces all three decisions synchronously through `PostLLMHook`. The original 002A loader, complete hook trace, provider-error, concurrency, and missing-plugin negative-control tests still pass.

| Input/outcome | Client result | Provider/fallback behavior |
| --- | --- | --- |
| Successful candidate + ALLOW | HTTP 200, same provider response | No fallback |
| Successful candidate + REJECT | HTTP 403, `epochguard_rejected` | Answer discarded; no further fallback |
| Successful candidate + UNAVAILABLE | HTTP 503, `epochguard_verification_unavailable` | Answer discarded; no further fallback |
| Evaluator error, unknown decision, absent source/candidate, cancellation | Same safe 503 policy | Fail closed; no further fallback |
| Genuine upstream error | Original typed provider error | Original provider fallback policy preserved |
| Unsupported streaming/async/registered inference route | HTTP 400, `epochguard_unsupported_request` | Refused before provider dispatch |
| Tested unregistered `/openai/v1/passthrough` URL | Bifrost router HTTP 405 | No provider call; plugin middleware does not run |

These are enforcement decisions, **not evidence of freshness or factual verification**. The fixed source checks no evidence. Diagnostic `X-EpochGuard-*` headers still report execution only.

## Upstream contracts inspected before implementation

The gateway stays at `transports/v2.4.0`, commit `e869c3f9adc96ea53c38694a21bb04a8e1085487`. Its actual released core dependency is `core v1.14.1`, commit `2975d142abcffc5783a60201394631b5576c748f`. No Bifrost core source or module pins were changed. Source downloads are retained locally in ignored `artifacts/002b/upstream/`.

| Pinned source | Relevant behavior |
| --- | --- |
| [core schemas/plugin.go](https://github.com/maximhq/bifrost/blob/2975d142abcffc5783a60201394631b5576c748f/core/schemas/plugin.go) | Exact native hook signatures; ordinary LLM hook errors are warnings; typed response/error modification is supported |
| [core schemas/plugin_native.go](https://github.com/maximhq/bifrost/blob/2975d142abcffc5783a60201394631b5576c748f/core/schemas/plugin_native.go) | `LLMPluginShortCircuit.Error` carries typed pre-LLM refusal |
| [framework native loader](https://github.com/maximhq/bifrost/blob/9e4f5db754307cebb248301bb88341c94b3d497e/framework/plugins/soloader.go) | Pinned framework v1.11.1 rejects loading when `Init` returns an error; final review confirmed why invalid policy configuration must keep `Init` successful |
| [core schemas/bifrost.go](https://github.com/maximhq/bifrost/blob/2975d142abcffc5783a60201394631b5576c748f/core/schemas/bifrost.go#L2253) | `BifrostError.StatusCode`, `ErrorField` pointer fields, `AllowFallbacks`; nil allows fallback by default |
| [core bifrost.go](https://github.com/maximhq/bifrost/blob/2975d142abcffc5783a60201394631b5576c748f/core/bifrost.go) | `shouldTryFallbacks` (5812), `shouldContinueWithFallbacks` (5986), buffered post-hooks (6621+), hook runners (9749+) |
| [transport middlewares.go](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/handlers/middlewares.go#L794) | A non-nil HTTP pre-hook response is applied and returns before the inference handler |
| [integration router.go](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/integrations/router.go) | Buffered chat error check precedes answer conversion (1143+); async headers select separate paths (777+, 976+) |
| [integration utils.go](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/integrations/utils.go#L293) | Real OpenAI integration fallbacks use a list of `provider/model` strings |
| [integration openai.go](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/integrations/openai.go#L3631) | This router has no passthrough catch-all (`NewGenericRouter` receives nil) |

An ordinary Go error in the third `PostLLMHook` result is accumulated and logged by the plugin pipeline. It is not the refusal carrier. EpochGuard instead returns `(nil, populatedBifrostError, nil)`: there is no successful response pointer to serialize, and the typed error has a non-empty constant message, status, type, and code. `AllowFallbacks` points explicitly to false. Both the primary-error and subsequent-fallback checks honor that field. Leaving it nil would allow the gateway to try another model.

## Minimal design and configuration boundary

`plugins/epochguard/decision.go` defines:

```go
type DecisionSource interface {
    Decide(context.Context, *schemas.BifrostResponse) (Decision, error)
}
```

`fixedDecision` implements it without inspecting context, headers, prompts, or provider content. Each gateway process has one immutable policy published via `atomic.Pointer[policy]`. Concurrent requests read that policy; no request is stored globally. Hooks load a policy once for the evaluation. Live policy updates are not a qualified deployment workflow; recreate processes after changing configuration.

Configuration comes from the native plugin's trusted `Init(config any)` argument:

```json
{"test_only": true, "decision": "REJECT"}
```

`ALLOW` and `REJECT` require the explicit test-only flag. Empty or absent configuration defaults to UNAVAILABLE. Unknown fields, malformed configuration, or unknown decisions clear any prior policy pointer and log a safe configuration error. `Init` deliberately returns nil so Bifrost keeps the plugin loaded; hooks executing without a policy refuse successful candidates with 503. Unit tests exercise this through the exported hooks. **A gateway that omits or otherwise fails to load the plugin can still serve unprotected responses**; handling invalid decision configuration is not an external readiness gate.

The Compose test network runs separate ALLOW, REJECT, UNAVAILABLE, and no-plugin processes with separate disposable SQLite directories. `config.json`, `config.reject.json`, and `config.unavailable.json` select the policies. The key pool admits both fixture test and fallback model names. Only the ALLOW gateway publishes a host port, still `127.0.0.1:8080`. The existing project/image/builder names containing `002a` are retained for build-cache and workflow continuity; they do not imply unchanged plugin behavior.

Untrusted inference clients have no supported way to change decisions. Tests send forged `X-EpochGuard-Decision`, `X-EpochGuard-Bypass`, `X-EpochGuard-Verified`, diagnostic headers, a prompt requesting ALLOW, and a raw-response request header; REJECT and UNAVAILABLE still refuse. Configuration files, management access, the plugin binary, and other loaded plugins are trusted deployment inputs. An administrator able to change plugins/configuration can remove enforcement. The public local-development setup token is not a production authorization boundary.

## Go code paths, ownership, and errors

1. `HTTPTransportPreHook` records the existing trace, then calls `guardHTTP`. The guard permits health and `/api` management, and accepts only buffered `POST /openai/v1/chat/completions` for inference. It checks the body snapshot and rejects `stream: true`, invalid JSON, absent/null bodies, and nonempty `x-bf-async` / `x-bf-async-id` headers. A missing large-payload snapshot also fails closed. It returns a complete constant HTTP 400 response rather than relying on an HTTP hook error.
2. `PreRequestHook` keeps the 002A trace behavior. It makes no enforcement decision through its ordinary error result.
3. `PreLLMHook` preserves the request pointer for supported typed chat requests. Any other request type, missing chat arm, or nil request gets `LLMPluginShortCircuit.Error` with `AllowFallbacks: false`. This is defense for the typed pipeline; real HTTP streaming tests exercise the earlier HTTP gate.
4. Bifrost calls the local provider. The plugin does not alter the prompt, provider credentials, request ID, or routing identity.
5. `PostLLMHook` records its phase and calls `enforce`. A genuine upstream error is returned by the same pointer without invoking the source. If an error and response both arrive, the error wins and the response is dropped. Provider fallback permissions remain unchanged.
6. For a non-nil chat candidate, `enforce` calls `Decide` inline. It does not spawn a verifier goroutine or release the answer while waiting. Cancellation before or during evaluation, a returned error, and unknown outcomes become UNAVAILABLE. ALLOW preserves response pointer identity. REJECT/UNAVAILABLE return no response and construct a new safe typed error with no provider answer, raw response, or copied response metadata.
7. Core applies routing metadata to the typed error and stops fallback when prohibited. The OpenAI buffered handler sends that error before successful response conversion. `HTTPTransportPostHook` adds the diagnostic headers; its error result is never used as proof of blocking.

The request-owned trace pointer and its mutex retain their 002A ownership model across parent/child contexts. The response and Bifrost wrappers belong to upstream and are borrowed only until the synchronous call returns. The fixed policy is immutable and shared safely. Error status/code/message allocations belong to the new refusal; no provider text or source error text is copied. Logging includes phases and Bifrost request IDs, not prompts or answers.

A future external source can replace the fixed implementation while preserving this enforcement branch. It must respect context cancellation, bound its network work, avoid retaining pooled Bifrost objects, and return UNAVAILABLE/errors for verification failures. An external timeout/retry/evidence policy has not been implemented or qualified here.

## Request-flow walkthrough

```text
buffered HTTP chat request
  -> HTTP guard accepts supported synchronous mode
  -> pre-request trace -> typed pre-LLM guard
  -> real provider response stays buffered
  -> PostLLMHook waits for DecisionSource
       ALLOW       -> original response -> HTTP diagnostics -> client 200
       REJECT      -> nil response + safe terminal BifrostError -> client 403
       UNAVAILABLE -> nil response + safe terminal BifrostError -> client 503

streaming HTTP chat request
  -> HTTP guard returns safe 400
  -> no core/provider call, no SSE writer, no answer bytes

primary provider error with explicit fallbacks
  -> same upstream error -> Bifrost's normal fallback handling
  -> fallback candidate -> EpochGuard decision again
  -> terminal refusal stops the remaining chain
```

Preserving upstream fallback behavior is intentional. A real provider failure is not itself an EpochGuard refusal. If a later provider succeeds, its candidate still must pass the policy. A policy refusal never requests a retry against another model.

## Executed checks and evidence

Docker Desktop Linux/amd64 ran the real dynamic gateway and external `.so` on the pinned Go 1.27.3 toolchain. No host Go installation, paid provider key, or mocked plugin loader was used. From the repository root:

```sh
docker compose build --builder epochguard-002a gateway
docker compose --profile test up -d --force-recreate --wait provider gateway gateway-control gateway-reject gateway-unavailable
docker compose --profile test run --rm --no-deps smoke
docker compose --profile test config --quiet
docker compose --profile test down --remove-orphans
```

| Executed check | Actual final result |
| --- | --- |
| Plugin formatting check and `go test -mod=readonly -trimpath -v ./...` in image build | All 11 top-level unit tests passed, including decision/error/default/cancellation and synchronous-release cases |
| `go test -race -p=2 -mod=readonly -trimpath ./...` in image build | `ok ... 1.059s`; exit 0, no reported races; includes 16 concurrent hook requests |
| Native plugin build; fixture/smoke formatting and compilation; ELF check | Passed; image build exit 0 |
| Original pinned gateway compilation, source pin, dependency download/verification and module-alignment steps | Unchanged 002A build-cache layers reused; no module files or upstream source changed |
| Gateway recreation and health sequencing | Provider and four gateway processes healthy; exit 0 |
| Complete real gateway smoke suite | All 10 top-level tests passed, including 35 subtests; final `PASS`, exit 0 |
| `docker compose --profile test config --quiet` | Exit 0 |
| `git diff --check` and disposable stack cleanup | Exit 0; test containers and network removed after evidence capture |

Integration assertions:

| Test | Observed proof |
| --- | --- |
| `TestResponseDecisions` | All three processes active at pre-builtin/order 0; ALLOW returned the sentinel answer; REJECT 403 and UNAVAILABLE 503 returned safe codes, no answer markers, and exactly one real provider call despite usable fallbacks |
| `TestProviderErrorPreservedForEveryDecision` | Real provider 400/message survived all three policies; one call; full hook trace |
| `TestRefusalStopsFallbackChain` | Genuine primary 400 allowed the first fallback; that successful fallback was refused; exactly two calls, no next fallback, no answer markers |
| `TestUnsupportedRequestsBeforeProvider` | Streaming, native chat, responses, async create/retrieve returned plugin 400; tested unregistered passthrough returned router 405; all had zero calls and no answer markers under all three policies |
| `TestEnforcementNegativeControls` | No-plugin buffered answer was detected by the no-leak assertion; no-plugin streaming returned real sentinel SSE bytes; no-plugin explicit fallback succeeded in exactly two calls |
| Original five 002A tests | Loading/order, real provider round trip, genuine error, six concurrent requests, and healthy missing-plugin detection all passed |

`noAnswerBytes` checks the complete client-visible response body plus serialized status/headers/trailers for the unique prompt sentinel, fixture answer prefix, and fixture completion ID. Refusal checks also exclude `choices`, raw-response fields, and SSE content type. This checks answer markers rather than merely checking `error.message`. The no-plugin answer/SSE controls prove the assertion detects real output and the fixture can emit it.

The first integration run failed only the added unregistered passthrough assertions: expected plugin 400, received router 405 `Method Not Allowed`. Inspection confirmed the pinned OpenAI router installs no passthrough catch-all. The test now explicitly requires that observed 405, no bytes, and zero provider calls; it is retained, not skipped. After adding race/synchronous/concurrent coverage and the raw-response header probe, the image was rebuilt, all processes recreated, and the entire suite passed. Final review changed invalid configuration handling to keep the plugin loaded in UNAVAILABLE mode; unit/race checks and the complete real gateway suite were rerun against that final implementation. No tests were disabled.

Ignored local artifacts in `artifacts/002b/` retain the initial and final build/smoke logs, startup logs, gateway logs, downloaded upstream source, and copied `build-info/`. `build-final.log` records the fresh unit/race runs; `smoke.log` records the final complete pass. Artifact version metadata continues to report Go 1.27.3, core v1.14.1, the pinned gateway VCS commit, plugin build mode, and the dynamic ELF interpreter.

## Limitations and security assumptions

- ALLOW is a deliberate test fixture, not production verification or a freshness assertion. The default published development gateway uses it to preserve the 002A example.
- The qualified provider is the controlled local OpenAI-compatible fixture. Real paid providers, other modalities, tools with side effects, arbitrary additional plugins, direct SDK traffic, and alternate transports are unqualified.
- Streaming is refused, not safely buffered/verified. Async execution is refused. Route guards do not establish blanket protection across all Bifrost features; `/api` management and health are deliberately outside the inference boundary.
- Bifrost can stay healthy and serve traffic if the plugin is absent or fails to load. Smoke detects that state; no external ready-to-serve gate is implemented. Configuration/management must be controlled by a trusted maintainer.
- No built-in semantic cache is enabled, and there is no EpochGuard cache. Cache reads, asynchronous writes, invalidation races, and hook ordering with cache plugins need a separate milestone.
- The race detector ran against plugin unit tests, not an instrumented gateway process. Smoke checks behavioral isolation, not gateway-wide race freedom, performance, or load limits.
- Decision-source errors and cancellation are unit-tested; actual verifier outages, network timeouts, retries, and evidence policy cannot be integration-tested because no external verifier exists yet.
- Inference auth remains disabled in the disposable development stack. Keep the host binding on loopback and do not expose the fixture/control network or public development setup token as production security.

Stop after Task 002B for maintainer review. Recommended commit (not created automatically): `feat(gateway): enforce buffered response decisions`.
