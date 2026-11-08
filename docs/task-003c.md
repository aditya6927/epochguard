# Task 003C — HTTP route surface and enforcement boundary audit

Executed November 8, 2026, using Docker Desktop's Linux/amd64 gateway and the real native plugin loader. This is an offline boundary qualification, not an expansion of the evidence policy. No Tavily or paid-provider calls were made. Application enforcement code, verification contract, policies and existing regression assertions are unchanged.

## Outcome and severity

**No provider-answer bypass was reproduced in the tested route matrix with EpochGuard active.** All eight registered passthrough prefixes were refused before dispatch. Configured Warp chat bypasses HTTP hooks but reaches the typed core guard, which rejects its unsupported Responses stream before a provider call. Usable controls without EpochGuard expose the synthetic provider answer through both passthrough and Warp.

The findings constrain what can be claimed:

| Finding | Evidence and impact |
| --- | --- |
| Deployment boundary limitation | API routes do not run the HTTP transport interceptor. Source also explicitly exempts some Warp background model/embedding work from plugins. A plugin-only all-route firewall claim would be unsafe. Background execution was not runtime-qualified here and is not a reproduced client answer leak. |
| Refusal status limitation | Configured Warp returns HTTP **200** containing an error or SSE error event after the typed core refusal. Provider delta is zero; no synthetic provider answer is returned. HTTP status alone cannot establish successful verification. |
| Path abstraction limitation | Router dispatch uses the original path; the plugin sees a normalized path without an authoritative raw-target field. Differences were reproduced, but tested mismatches did not dispatch a model or leak an answer. |
| Passing enforcement controls | Protected buffered chat rejects after exactly one provider call; registered passthrough and selected alternate entry points reject before dispatch; unchanged enforcement/service regressions pass. |

No production guard fix is justified by the tested answer paths. No Bifrost core change, ingress service, verification-policy expansion or ADR was introduced. Broader ingress/background enforcement requires architectural review; options and acceptance criteria are below.

## Pinned sources inspected

The sources were exported from the actual cached build/module graph into ignored `artifacts/003c/upstream/`, rather than inspecting current upstream HEAD.

| Component | Exact pin and relevant source |
| --- | --- |
| HTTP transport | `transports/v2.4.0`, commit [`e869c3f9adc96ea53c38694a21bb04a8e1085487`](https://github.com/maximhq/bifrost/tree/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http) |
| Core | `github.com/maximhq/bifrost/core v1.14.1`; `schemas/plugin.go`, `bifrost.go`, `utils.go`, `agent/manager.go` |
| Framework | `github.com/maximhq/bifrost/framework v1.11.1`; `warp/{client,service,config,indexer,topics,topicdiscovery,topicthemes}.go` |
| HTTP parser/router | `github.com/valyala/fasthttp v1.74.0`, `uri.go`; `github.com/fasthttp/router v1.5.4`, `router.go` |
| Native ABI | Existing `dev/Dockerfile` Go `1.27.3`, Linux/amd64, dynamic host and `.so`, identical pinned host/plugin dependency manifests |

Transport references below are relative to the pinned `transports/bifrost-http/` tree:

- `server/server.go:2858–2930`, `2965–3204`, `3502–3515`, `3587–3746`: inference/API registration, async prerequisites, middleware construction and optional A2A gRPC listener.
- `handlers/integrations.go:31–82`, `integrations/passthrough.go`, `integrations/router.go:3677–4011`: integration registrations, dedicated passthrough prefixes, normalized prefix validation and core passthrough dispatch.
- `handlers/middlewares.go:1123`: HTTP wrapper receives `string(ctx.Path())`.
- `handlers/warp.go:146`, `227–265`, `handlers/warpchat.go:100–211`: model executor wiring, API registration, prerequisites and JSON/SSE response wrapping.
- `handlers/inference.go:872` onwards, `asyncinference.go:53–98`, `wsresponses.go:77`, `wsrealtime.go:63`, `wslive.go:46`, `webrtclive.go:39`, `relaygateway.go:45`, `agentgateway.go:238–263`: additional route families and conditional registration.

The dependency versions are checked in [the plugin manifest](../plugins/epochguard/go.mod). Build checks compare it and `go.sum` with the pinned transport manifests. Exact registration functions, rather than HTTP compatibility names alone, determine the surface.

## Middleware and model execution

The source and observed traces agree:

```text
Inference route:
  tracing/recovery + common middleware + pre-auth interceptor + inference auth
  -> HTTP transport pre hooks -> route handler
  -> core PreRequest -> core PreLLM -> provider -> core PostLLM
  -> HTTP transport post hooks -> tracing completion

Management route, including /api/warp/chat:
  common middleware + setup lock/API authentication -> handler
  -> if it calls a core model method, the core plugin pipeline can run
  -> API-specific response wrapper (no HTTP transport hooks)
```

Core pre-hooks run in configured order, post-hooks unwind in reverse. The audit observer is `pre_builtin`, order `-1`, immediately before EpochGuard at order `0`; therefore it sees the HTTP request before EpochGuard stops it and sees the typed error after EpochGuard's post-hook. Built-ins are omitted from the compact traces. A complete HTTP short-circuit stops before core hooks. The production HTTP post-hook diagnostic is not used as enforcement evidence.

The test observer only copies phase/type/path/error-code strings into a mutex-protected, bounded event list and exposes it on internal port 9010. It neither changes decisions nor retains pooled requests, contexts or candidate text. Events show pipeline entry, not a verifier verdict. Typed EpochGuard errors, provider counters and no-leak checks establish refusal. The observer remains in the controls too: “no-plugin control” here means **no EpochGuard**, not no Bifrost built-ins or observer.

## Isolated deployment and controls

[compose.routes.yaml](../compose.routes.yaml) has an internal network and publishes no host ports. [The audit configurations](../dev/bifrost/routes/) contain fake provider keys only. All candidate bytes come from [the route fixture](../cmd/route-provider-fixture/main.go); there is no external verifier or credential. The eight-prefix tests never dispatch the hardcoded ChatGPT upstream. Network isolation prevents external egress.

| Gateway | EpochGuard | Logging/Warp prerequisites |
| --- | --- | --- |
| `reject` | Fixed trusted test-only REJECT | Logging off, Warp not configured |
| `control` | Absent | Same as `reject` |
| `nolog` | Fixed REJECT | Warp configuration/vector backend supplied, logging off |
| `warp-reject` | Fixed REJECT | Logging + SQLite logs store, Redis vector store, enabled Warp config |
| `warp-control` | Absent | Same Warp dependencies |

Redis is a Warp **vector backend**, not the semantic response cache. Runtime plugin-name/status probes confirm the observer, EpochGuard's active `pre_builtin`/order `0` where expected, and absence of `semantic_cache` in every gateway. Neither the normal deployment nor verification deployment is changed to enable Warp.

Warp configuration requires a vector store when saving enabled settings, nonempty embedding provider/model, positive embedding dimension, and `max_iterations >= 2`. The fixture uses one-dimensional embeddings and two iterations. The `warp` feature flag uses `{ "flags": { "warp": { "enabled": true } } }` under `feature_flags`. Logging-off gateways cannot chat even with these settings. Configuring logging, storage and Warp changes the executable surface without changing EpochGuard code.

The fixture's `/stats` counts actual non-health/model-list upstream requests by path. Synthetic text `ROUTE_PROVIDER_ANSWER` and completion ID `chatcmpl-route-audit` identify exposure. Tests scan both response headers and complete buffered/SSE bodies. Each case records deltas and observer events; cases run sequentially. Forged `X-EpochGuard-Decision: ALLOW` and `X-EpochGuard-Bypass: true` are sent throughout and do not select the trusted fixed decision.

## Runtime results: registered routes

`H` = observer HTTP pre, `R` = core PreRequest, `L` = core PreLLM, `P` = core PostLLM. Each delta below is per request; buffer and stream are separate tests where indicated.

| Exact target / request | With EpochGuard: status; provider delta; hooks | No-EpochGuard control |
| --- | --- | --- |
| `POST /openai/v1/chat/completions`, buffered | 403; **1**; `H R L P(epochguard_rejected)`; no answer bytes | 200; **1**; `H R L P`; answer exposed |
| Same path, `stream:true` | 400; **0**; `H` only | Existing streaming fixture control is retained in 002B regressions |
| `/openai_passthrough/v1/chat/completions`, buffer and stream | 400; **0**; `H` only | 200; **1** each; `H R L P`; answer exposed |
| `/anthropic_passthrough/v1/messages`, buffer and stream | 400; **0**; `H` only | 200; **1** each; same core passthrough behavior; answer exposed |
| `/genai_passthrough/v1/models/test:generateContent` | 400; **0**; `H` only | Not dispatched |
| `/azure_passthrough/openai/deployments/test/chat/completions` | 400; **0**; `H` only | Not dispatched |
| `/bedrock_passthrough/agent/test/alias/test/session/test/text` | 400; **0**; `H` only | Not dispatched |
| `/chatgpt_passthrough/backend-api/codex/responses` | 400; **0**; `H` only | Deliberately not dispatched: hardcoded external upstream |
| `/sagemaker_passthrough/endpoints/test/invocations` | 400; **0**; `H` only | Not dispatched |
| `/runware_passthrough/v1` | 400; **0**; `H` only | Not dispatched |
| `POST /v1/chat/completions`, `/v1/responses`, `/openai/v1/responses` | 400; **0** each; `H` only | Not dispatched |
| Supported chat with `X-Bf-Async: true` or `X-Bf-Async-Id: test` | 400; **0** each; `H` only | Existing suite retains unsupported-request controls |
| `GET /v1/responses`, `/v1/realtime`, `/v1/live/sessions` with Upgrade headers | 400; **0** each; `H` only; no 101 upgrade | Connection protocol beyond refusal unqualified |
| `POST /v1/live/sessions` | 400; **0**; `H` only | WebRTC provider session not attempted |
| `POST /relay/test/v1/chat/completions` | 400; **0**; `H` only | Relay endpoint execution not configured/qualified |
| `GET /health` without setup token | 200; **0**; no hooks | Health is outside inference enforcement |
| `GET /api/plugins/loaded` with / without setup token | 200 / 401; **0**; no hooks | Authenticated management retained; unauthenticated request refused by API auth |

Every tested EpochGuard HTTP refusal above contains `epochguard_unsupported_request`, rather than relying on a 400 alone. Buffered passthrough controls use core request type `passthrough`; streaming controls use `passthrough_stream`, with two observed post-hook callbacks (stream processing). Refusal occurs before that core path. Anthropic passthrough deliberately forwards synthetic OpenAI-shaped bytes without translation; this qualifies raw passthrough enforcement, not Anthropic model compatibility.

The final audit provider snapshot was exactly:

```json
{"/v1/chat/completions":5,"/v1/messages":2,"/v1/responses":2}
```

These nine calls are protected chat plus its control (2), OpenAI passthrough controls including the repeated-separator case (3), Anthropic passthrough controls (2), and the two usable Warp controls (2). Every other audit request had provider delta zero. No embedding request occurred during this observed run; that does not qualify background indexing.

## Runtime results: raw and normalized paths

[The runner](../tests/routesurface/routes_test.go) writes the exact origin-form request target directly to a TCP socket and logs `sent_target`. It does not use a URL builder, normalize dot segments or follow redirects. `Connection: Upgrade` is used for the upgrade probes. `fasthttp.URI.PathOriginal()` preserves the original path for router lookup; `ctx.Path()` percent-decodes/normalizes separators and dot segments. `schemas.HTTPRequest` has `Path`, query, headers, body and route parameters, but no dedicated original target or matched-route identity. Common middleware stores a matched-route template on the fasthttp request for metrics; that is not an original-target field in the plugin HTTP wrapper, and this audit does not qualify using it as a security authority.

Both guarded and no-EpochGuard gateways produced these results:

| Exact transmitted POST targets | Status | Hook/path evidence and classification |
| --- | --- | --- |
| `/openai%2fv1/chat/completions`, `/openai/v1/chat%2fcompletions` | 308 | No hooks; redirect to canonical chat path; router behavior |
| `/openai//v1/chat/completions`, `/openai/v1/chat/completions/`, `/OpenAI/v1/chat/completions` | 308 | No hooks; canonical redirect; router behavior |
| `/openai/v1/x/../chat/completions`, `/openai/v1/%2e%2e/v1/chat/completions` | 308 | No hooks; canonical redirect; router behavior |
| `/api/warp/%2e/chat`, `/api//warp/chat` | 308 | No hooks; redirect to `/api/warp/chat`; router behavior |
| `/v1/async/chat/completions`, `/openai/v1/passthrough` | 405 | No hooks; route unavailable in these logging-off deployments; **not** proof of EpochGuard enforcement |
| `/openai_passthrough/../openai/v1/chat/completions` | 404 | `H` receives `/openai/v1/chat/completions`; no core hooks; passthrough prefix no longer matches normalized path |
| `/openai_passthrough/%2e%2e/api/warp/chat` | 404 | `H` receives `/api/warp/chat`; API exemption does not dispatch Warp; passthrough prefix validation fails |

All rows above had provider delta **0**, no synthetic answer bytes and identical guarded/control outcomes. The router defaults `RedirectTrailingSlash` and `RedirectFixedPath` to true; redirect responses precede plugin execution and are not classified as EpochGuard refusals. Following a redirect would be another request, subject to the destination route's middleware; the runner intentionally does not follow it.

One additional mismatch reaches a usable handler:

```text
sent: /openai_passthrough//v1/chat/completions
HTTP wrapper: /openai_passthrough/v1/chat/completions
EpochGuard: 400, provider_delta=0, [H]
control:    200, provider_delta=1, [H R(passthrough) L(passthrough) P]
            ROUTE_PROVIDER_ANSWER exposed
```

Thus normalization disagreement is real and can change which guard branch is taken. In the tested dot-segment cases the handler's independent prefix check prevents model dispatch. This is a bounded regression matrix, not a proof for every byte encoding, proxy rewrite, HTTP method or future router version. The public HTTP request abstraction cannot independently enforce exact raw-target identity. A client-supplied “original path” header would not repair that trust boundary.

## Runtime results: Warp

`POST /api/warp/chat` is registered even when unusable. The OSS Warp flag is enabled in the audit. Its API chain never emits `H` on either buffered or streaming output:

| Gateway/request | Status and body | Provider delta | Observed core trace |
| --- | --- | --- | --- |
| `reject`, `control`, `nolog`; buffer and stream | 503, `reason: no_log_store` | **0** each | None: prerequisite refusal, not enforcement |
| `warp-reject`, buffered | 200, empty `answer`, `error.code: upstream_error`, fixed EpochGuard unsupported message | **0** | `R(responses_stream) L(responses_stream) P(epochguard_unsupported_request)` |
| `warp-reject`, streaming | 200 SSE, `start` then `error`, same fixed message; no provider delta/done answer | **0** | Same typed refusal trace |
| `warp-control`, buffered | 200, `answer: ROUTE_PROVIDER_ANSWER`, one iteration | **1** | `R(responses_stream) L(responses_stream) P` |
| `warp-control`, streaming | 200 SSE, `start`, `delta: ROUTE_PROVIDER_ANSWER`, `done` | **1** | Same successful core trace |

The configured no-EpochGuard controls establish that logging/configuration, not an unreachable fixture, was the only obstacle to execution. Even `stream:false` Warp uses the Responses **stream** executor internally. EpochGuard's typed pre-LLM guard prevents that request type, rather than executing its fixed REJECT source or an evidence verifier. Warp then wraps the error in its own protocol instead of propagating typed HTTP 400. SSE start metadata can be delivered; no provider answer is delivered. This is not qualified safe streaming or a successful verification verdict.

Narrowing the `/api` exemption in `guardHTTP()` would not affect this route because the HTTP hook never runs. The defense observed here is the independent core guard. Changing Warp to buffered chat calls, enabling additional background work, or replacing the transport requires requalification.

## Other registered families and explicit gaps

The registration inventory is source-backed; runtime confirmation is limited to the rows above. “Source-only refusal” means the route is wired through the inference interceptor whose guard denies its path/method, not that every operation was executed.

| Family / registration | Boundary classification |
| --- | --- |
| Native `/v1/models`, completions/chat, Responses create/retrieve/delete/cancel/input items/input tokens/compact, embeddings/rerank/decisions/OCR, audio/images/videos, files/batches/containers and their resources | Inference middleware. Selected chat/Responses paths runtime-refused by EpochGuard; other operations source-only refusal, not verified delivery. Handlers call corresponding core methods. |
| OpenAI, Anthropic, GenAI, LiteLLM, Cohere, Azure, LangChain, PydanticAI, Bedrock, Typesafe and Cursor compatibility integrations | Registered in `handlers/integrations.go`; inference middleware. Only exact buffered OpenAI chat is supported. Other aliases are source-only refusals unless tested above; no provider-family compatibility claim. |
| All eight dedicated passthrough prefixes | Runtime-refused by EpochGuard before core/provider dispatch; OpenAI/Anthropic usable buffer/stream controls included. `/openai/v1/passthrough` was never a substitute for these tests. |
| Async `/v1/async/...` submit/retrieve | Registration requires async executor (logs store + governance). Missing in `reject`/`control`: runtime 405 before hooks. Enabled registration uses inference middleware; enabled jobs/retrieval remain separately unqualified. Async headers on supported chat are runtime-refused. |
| Responses WebSocket, realtime WebSocket, live sessions/sideband/content, WebRTC calls/client secrets | Inference chain. Selected WS/live entry points runtime-refused before upgrade/dispatch; remaining aliases and session lifecycles source-only/unqualified. SSE passthrough and Warp evaluated separately above. |
| `/relay/{endpoint}/{path:*}` | Inference middleware, dedicated relay manager rather than the supported chat decision path. Representative runtime HTTP refusal; arbitrary configured relay execution unqualified. |
| `/agents/a2a/{name}/...` cards, JSON-RPC, REST and push callbacks | Inference chain plus an outer `requireAgentGatewayURL` gate; protocol-specific authentication. Without external URL, source says prerequisite 503 before transport hooks. Registered upstream-agent execution/push callbacks not exercised. Core agent/relay hooks are not automatically equivalent to EpochGuard's LLM verdict interface. |
| Optional A2A gRPC listener | Configured independently using base domain and port, outside the HTTP interceptor; not enabled or tested. Requires separate ingress/protocol qualification. |
| MCP tool execution and MCP server routes | Registered through inference middleware; source-only refusal for current allowlist. Tool/upstream content is not factual verification; independent tool lifecycles unqualified. |
| Management: providers/keys, agents/relays, config, plugins, logs, cache management, governance/routing, prompts/skills, sessions, OAuth, notifications/RSS, Warp/jobs; `/ws` log/event stream | API/common middleware, not HTTP transport enforcement. Configuration/authentication are trusted. Authenticated log/history/event content can contain historical provider data and must not be represented as a verified answer channel. Only health and plugin probes runtime-tested here. |
| Warp log backfill/indexing, topic clustering/discovery/naming/themes | **Outside the core enforcement boundary by source:** `warp/indexer.go:407` sets `BifrostContextKeySkipPluginPipeline`; `warp/client.go:334–335` calls `PrepareContextForInternalRequest` for `withBackgroundWork`. Topic jobs use that marker. Core `utils.go:534` sets the skip flag; core execution paths honor it. No background job was triggered/qualified here. |
| Internal live-model catalog refresh and batch/video accounting polling | Source also sets the skip flag in `server/server.go`'s `newListModelsCtx` and `server/batchaccounting.go`'s `internalJobContext`. These internal provider operations are outside the answer-verdict boundary, not evidence of an enforced or verified model response. |

Background bypass is an explicit upstream execution mechanism, not an untrusted client verification switch. It still prevents any guarantee that enabling all Bifrost capabilities forces every model call through EpochGuard. This report does not claim absence of leaks on untested management, stored-history, tool, agent or background surfaces.

## Tests executed and reproducibility

From repository root, with Docker Desktop running and no live override/credential:

```sh
docker compose build --builder epochguard-002a gateway
docker compose -f compose.routes.yaml up -d --force-recreate --wait provider reject control warp-control warp-reject nolog
docker compose -f compose.routes.yaml run --rm --no-deps route-tests
docker compose -f compose.routes.yaml down --volumes --remove-orphans

docker compose --profile test up -d --force-recreate --wait provider gateway gateway-control gateway-reject gateway-unavailable
docker compose --profile test run --rm --no-deps smoke
docker compose --profile test down --remove-orphans

docker compose -f compose.verify.yaml build verifier-supported
docker compose -f compose.verify.yaml run --rm --no-deps --entrypoint python verifier-supported -m pytest -q
docker compose -f compose.verify.yaml run --rm verification-tests
docker compose -f compose.verify.yaml down --remove-orphans

docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml up -d --wait gateway-supported
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml run --rm --no-deps verification-tests
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml down --remove-orphans
```

Native build formatting, root fixture checks and runner compilation passed. To force fresh plugin tests instead of reusing a successful build layer, an ignored `artifacts/003c/Dockerfile.unit` copied the current Dockerfile and appended:

```dockerfile
FROM build AS qualification-unit
WORKDIR /src/epochguard/plugins/epochguard
RUN --network=none --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build go test -count=1 -mod=readonly -trimpath -v ./... && go test -count=1 -race -p=2 -mod=readonly -trimpath ./...
```

Executed with `docker buildx build --builder epochguard-002a --progress plain --target qualification-unit -f artifacts/003c/Dockerfile.unit .`. Both commands passed: ordinary unit execution `0.157s`, race execution `1.209s`. This is unit race detection, not gateway-process race qualification.

| Check | Actual result |
| --- | --- |
| Final native build | Built `epochguard-dev:002a`, including actual `.so`, observer and route runner |
| Route audit | **4 top-level tests, 54 subtests passed**: 5 plugin configuration, 29 route matrix, 10 Warp, 10 management/async/alternate entry probes |
| Existing 002B smoke | **10 top-level tests, 35 subtests passed**; upstream errors, terminal fallback, no-answer leak and missing-plugin controls retained |
| Fresh Python offline policy tests | **41 passed, 1 live test deselected**, 2.99s; existing dependency deprecation and non-root pytest cache-write warnings |
| Existing offline gateway/service suite | **8 top-level tests, 31 subtests passed**; live and long-budget tests explicitly skipped in this short-profile deployment |
| Separate offline long-budget regression | **1 passed**, 12.57s; HTTP 200 after `first_byte_ms=12562`, total 12562ms, provider delta **1**, fixture retrieval delta **1**; ten-second provider network timeout did not cut off post-hook verification |
| Fresh plugin units and race detector | Passed with `-count=1`, no race report |
| Final checks | Go formatting clean; audit Compose configuration valid; 49 relative documentation links and balanced fences checked across four documents; changed/new text whitespace and audit JSON syntax passed; `git diff --check` exit 0 |
| Cleanup | Audit, smoke, offline verification and long-budget Compose stacks removed; only the pre-existing BuildKit builder remains running |

The new matrix initially failed its Warp no-EpochGuard control: `max_iterations: 1` prevented configuration, so Warp returned `not_configured` without calling the fixture. Correcting the test config to the documented minimum of 2 made the control usable; assertions were strengthened rather than skipped. An earlier malformed boolean feature-flag record failed startup and was corrected to the typed record. A final-stack startup also encountered a Docker Desktop API 500 while inspecting an already healthy provider; rerunning `up -d --wait ...` succeeded. These are preserved setup failures, not successful enforcement evidence. The final route suite exited 0.

Ignored local evidence remains under `artifacts/003c/`: `build-final.log`, `unit-race.log`, `routes-initial.log`, `routes-warp.log`, `routes-final.log`, `provider-final.json`, `gateway-final.log`, smoke/Python/verification logs, startup/cleanup transcripts and source exports. The tables and selected traces above preserve the reviewable outcomes in the repository. PowerShell redirection can include `NativeCommandError` formatting for Docker progress on stderr; final test `PASS`, exit status and assertions establish results.

Files changed: `AGENTS.md`, `README.md`, `docs/architecture.md`, `docs/task-003c.md`, `dev/Dockerfile`, `compose.routes.yaml`, `cmd/route-provider-fixture/main.go`, `tests/routeobserver/main.go`, `tests/routesurface/routes_test.go`, and five configs under `dev/bifrost/routes/`: `reject.json`, `control.json`, `warp-reject.json`, `warp-control.json`, `nolog.json`. The Dockerfile adds audit artifacts to the development image; the observer is loaded only by audit configs. No production plugin/service implementation or existing test was edited.

## Deployment implications and next review

Keep the current protected contract narrow: exact buffered OpenAI chat, active native plugin at `pre_builtin` order 0, cache disabled, trusted verifier/configuration and management, loopback-only development exposure. Health alone is not readiness. No claim is made that `/api/*` is filtered by EpochGuard, or that a 200 response from an arbitrary gateway endpoint is verified.

If broader exposure is required, review these alternatives before implementation:

1. **Restrict configuration and isolate management/background work.** Keep Warp jobs, independent transports and unqualified agents/tools unavailable to answer clients; authenticate and isolate management. This reduces exposure but depends on administrative controls and startup/readiness enforcement.
2. **Trusted transport ingress.** Allow only the qualified method and canonical raw target, reject ambiguous encodings, separate management listeners/credentials, and deny unqualified upgrades/transports. This requires its own component/configuration and was not introduced automatically. It cannot alone mediate internal background model calls.
3. **Pinned upstream contract changes.** Expose authoritative raw target/matched route to plugins and provide a non-skippable policy boundary for internal/provider calls; propagate typed refusals consistently through Warp. This requires upstream/core/transport design review and ABI requalification, not a local `/api` guard edit.

Acceptance for any expanded boundary must include configured positive controls for every exposed model route, background and stored-output paths; no successful answer or paid dispatch outside policy; terminal refusal/no leakage across JSON/SSE/upgrades; raw path agreement across actual proxies; management authorization and health preserved; missing-plugin readiness failure; and regression tests for configured async/agent/gRPC routes. Do not treat an unreachable route, logging disabled, or a prerequisite 503 as the security boundary.

Recommended commit, not created: `test(gateway): qualify HTTP route enforcement boundaries`. Stop after Task 003C for maintainer review; no Task 004A work.
