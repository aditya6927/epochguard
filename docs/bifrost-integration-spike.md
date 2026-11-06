# Bifrost integration spike

Investigation date: 2026-11-06 (Asia/Calcutta). Scope: official `maximhq/bifrost` source and repository documentation; no EpochGuard integration code implemented.

Runtime follow-up: [Task 002A](task-002a.md) subsequently built and loaded a minimal native plugin on this pin and exercised real provider requests. It also records configuration requirements and corrections discovered at runtime. The investigation and smoke-test design below remain broader than the integration qualified in Task 002A.

Enforcement follow-up: [Task 002B](task-002b.md) re-inspected the exact core v1.14.1 source and pinned transport, then qualified synchronous typed post-hook refusals, explicit fallback suppression, provider-error preservation, and pre-dispatch streaming rejection against the real gateway. At that milestone, cache and safe streaming delivery investigations below remained unimplemented.

Cache follow-up: [Task 002C](task-002c.md) subsequently qualified direct misses/hits on real Redis Stack, early/late placement, refusal of cached candidates, unsafe pre-refusal writes, server no-store, supported physical deletion, and deterministic pending-write repopulation. Those experiments are isolated; the default deployment keeps caching disabled. Embedding similarity mode, a protected cache, and safe streaming delivery remain unimplemented.

## Decision

**Proceed with a native Go plugin on a dynamically linked OSS Bifrost build, initially restricted to buffered, non-streaming chat completions. No core source changes are required. Do not describe this as a drop-in plugin for the default Linux distribution:** both the release executable build and the official Dockerfile use static linking, which prevents native plugin loading. The documented `DYNAMIC=1` build is the supported starting point. [Build guide][dynamic-doc], [Makefile][make], [release builder][release-build], [Dockerfile][docker].

Register EpochGuard **before the built-in plugins**, with the earliest configured order. This ensures it participates when the built-in cache short-circuits. Invalidate an unverified result by returning a populated `*schemas.BifrostError`, a nil response, and a nil ordinary Go error from `PostLLMHook`. Set `AllowFallbacks` explicitly to false for a terminal verification refusal. Ordinary LLM hook errors are logged and do not reliably reject requests. [Plugin contract][core-plugin], [pipeline implementation][core-flow].

**Cache reads, response release, cache writes, and physical deletion are separate concerns.** One plugin placement cannot both observe every built-in cache hit and verify a provider response before the built-in cache writes it. For an initial implementation, disable the built-in cache on the protected deployment and let EpochGuard own its verified cache. An optional interoperability mode can verify existing built-in entries on every read and suppress new built-in writes before lookup; it must not claim atomic invalidation or automatic regeneration of rejected hits. Details below.

## Evidence status and pins

“Verified” below means traced in the pinned source, not executed successfully in this workspace. “Proposed” means an EpochGuard design choice. Runtime compatibility remains subject to the Linux smoke test.

| Component | Pin | Evidence |
| --- | --- | --- |
| HTTP gateway release | `transports/v2.4.0` (release name: Bifrost HTTP v2.4.0; published 2026-10-29) | [Official release][release] |
| Gateway source commit | `e869c3f9adc96ea53c38694a21bb04a8e1085487` | [Annotated tag object][tag-object]; tag object SHA is `9c6ac22ceb9794b7dafdceced5f25d93a43f18e4` |
| Go toolchain | **Go 1.27.3**, exactly, for gateway and plugin | `transports/go.mod`, `transports/Dockerfile`, root `Makefile`, and example plugin Makefile |
| Core module | `github.com/maximhq/bifrost/core v1.14.1` | Gateway `transports/go.mod`; module tag resolves to `2975d142abcffc5783a60201394631b5576c748f` |
| Framework module | `github.com/maximhq/bifrost/framework v1.11.1` | Gateway `transports/go.mod`; module tag resolves to `9e4f5db754307cebb248301bb88341c94b3d497e` |
| Built-in cache module | `github.com/maximhq/bifrost/plugins/semanticcache v1.7.4` | Gateway `transports/go.mod`; module tag resolves to `8410bc47c3ee99464ebd5f46b7bab1bc429b278a` |
| First qualification target | `linux/amd64`, CGO enabled, Alpine/musl, dynamic gateway | Proposed target matching upstream's container build family |
| Builder image | `golang:1.27.3-alpine3.24@sha256:f2c872bcee949b7be9c490efd02b48a8a2fbf947cdf533f1c58525ec9d8170fd` | Exact upstream builder reference in root Makefile and Dockerfile |

These are compatibility pins for this spike, not a promise to support every Bifrost release. Bifrost is a multi-module repository: the gateway version is not the core version. Do not use `@latest`, a moving branch, or a floating runtime image as the compatibility identity. [Gateway module manifest][transport-mod].

The default production build uses `GOWORK=off`, so it consumes the tagged dependency modules rather than automatically using sibling directories. I compared Git tree entries at the dependency tags against the gateway tag: core and semanticcache differ only in their changelogs; framework additionally differs in `framework/warp/prompt.go`, `framework/warp/topics.go`, and its test. The loader and streaming files cited here match the framework module tag. **Use the released dependency graph when building the plugin**, not an unqualified local workspace replacement.

No Go executable was found on this Windows host. A Docker server query found no running engine; no Linux build, plugin load, provider request, cache test, or stream test was run. This is a source investigation and executable test design, not a runtime qualification result.

## Public plugin surface

The canonical interfaces are in `core/schemas/plugin.go`, with native short-circuit carriers in `core/schemas/plugin_native.go`. External `.so` plugins export **package-level functions**; they do not export an invented constructor, register through a blank import, or supply an SDK middleware object. The loader resolves and type-checks the exported symbols. [Contract][core-plugin], [native carriers][native-plugin], [loader][loader].

Relevant exact signatures (declarations only, not an implementation):

```go
// Required exported symbols for a native plugin:
GetName() string
Cleanup() error

// Optional initialization:
Init(config any) error

// LLM hooks, optional exported symbols:
PreRequestHook(ctx *schemas.BifrostContext, req *schemas.BifrostRequest) error
PreLLMHook(ctx *schemas.BifrostContext, req *schemas.BifrostRequest) (*schemas.BifrostRequest, *schemas.LLMPluginShortCircuit, error)
PostLLMHook(ctx *schemas.BifrostContext, resp *schemas.BifrostResponse, bifrostErr *schemas.BifrostError) (*schemas.BifrostResponse, *schemas.BifrostError, error)

// HTTP transport hooks, optional exported symbols:
HTTPTransportPreAuthHook(ctx *schemas.BifrostContext, req *schemas.HTTPRequest) (*schemas.HTTPResponse, error)
HTTPTransportPreHook(ctx *schemas.BifrostContext, req *schemas.HTTPRequest) (*schemas.HTTPResponse, error)
HTTPTransportPostHook(ctx *schemas.BifrostContext, req *schemas.HTTPRequest, resp *schemas.HTTPResponse) error
HTTPTransportResponseHeadersHook(ctx *schemas.BifrostContext, req *schemas.HTTPRequest, resp *schemas.HTTPResponseMetadata) error
HTTPTransportStreamChunkHook(ctx *schemas.BifrostContext, req *schemas.HTTPRequest, chunk *schemas.BifrostStreamChunk) (*schemas.BifrostStreamChunk, error)
```

`BasePlugin` requires `GetName` and `Cleanup`; `LLMPlugin` embeds it and declares all three LLM methods. `HTTPTransportPlugin` embeds it and declares all five HTTP methods. The dynamic wrapper provides no-op defaults for missing exports. `Init` is optional in the actual loader, despite some documentation skeletons describing it as required. Export a stable unique name such as `epochguard`. [Wrapper][wrapper], [loader][loader].

| Phase | Verified execution and useful capability | Enforcement implication |
| --- | --- | --- |
| HTTP pre-auth | Before transport authentication; can mutate serializable HTTP request or short-circuit | EpochGuard should normally use the authenticated pre-hook instead |
| HTTP pre | Once per HTTP request, after authentication; receives method, path, headers, query, body, path parameters | Can return a complete HTTP refusal before calling core; method/path mutation is rejected after routing |
| `PreRequestHook` | Once per top-level core request; mutations persist into attempts/fallbacks | Its error return cannot abort a request |
| `PreLLMHook` | Per attempt, registration order | Can skip the provider through `LLMPluginShortCircuit.Response`, `.Stream`, or `.Error` |
| `PostLLMHook` | Reverse order; on short-circuit, only plugins whose pre-hook executed | Can replace a result with a typed Bifrost error; receives errors as well as successes |
| HTTP post | Reverse order; buffered body can be rewritten before transport returns | An ordinary error does **not** itself construct a refusal body/status; explicitly overwrite `HTTPResponse` |
| HTTP response headers | Last safe header-mutation point; status is informational | Errors are warned and remaining header hooks skipped; this is not a verification gate |
| HTTP stream chunk | Before successful payload conversion/write, reverse order | `(nil, nil)` drops a chunk; `(nil, error)` terminates; a non-nil chunk plus error can continue |

Evidence: `core/schemas/plugin.go:236–428`; `core/bifrost.go:9749–9952`; `transports/bifrost-http/handlers/middlewares.go:727–1057`; `transports/bifrost-http/lib/config.go:8074–8112`; `transports/bifrost-http/integrations/router.go:3145–3183`. HTTP hooks apply to routes wrapped in the HTTP interceptor, not direct Go SDK calls. They must not be assumed to govern every management route or every realtime protocol. [Middleware][middleware], [HTTP interceptor][config], [router][router].

Hooks run in the gateway process and may execute concurrently across requests. Do not retain pooled request/response/context wrappers after a hook returns. `BifrostContext.SetValue` delegates scoped writes to the underlying context and blocks reserved keys during LLM hooks. Use plugin-owned keys; a client header is not evidence of a verified result. [Context implementation][context].

## Linux build, registration, and execution

### Build requirements

1. Build the gateway and plugin with the exact Go 1.27.3 toolchain and matching target architecture, libc, common dependency sources, relevant flags, build tags, and CGO environment. Use one controlled Linux build environment. `-trimpath` must agree; do not mix release-style gateway builds with the example's untrimmed native development build.
2. Use a Go `package main` and `go build -buildmode=plugin` to produce an ELF `.so`; `main()` is not the entrypoint. Shared package initialization occurs on first `plugin.Open`, then Bifrost calls optional `Init` and obtains the exported functions. This is native code in the host process, without an RPC boundary or separate plugin executable.
3. Build a **dynamic gateway**. The upstream root command is `make build DYNAMIC=1 VERSION=2.4.0 GOOS=linux GOARCH=amd64`; it also builds the UI and writes `tmp/bifrost-http`. Its Linux dynamic branch uses `CGO_ENABLED=1`, `GOWORK=off` by default, `-a -trimpath`, and no `sqlite_static` tag or static linker flag.
4. A corresponding plugin build shape is `CGO_ENABLED=1 GOWORK=off GOOS=linux GOARCH=amd64 go build -trimpath -buildmode=plugin -o build/epochguard.so .`, inside the same pinned builder with GCC/musl development packages. This is a proposed future command, not something executed in this spike. Lock the plugin's shared dependency graph to the gateway's resolved graph before building.
5. Inspect both artifacts with `go version -m`; inspect the gateway with `file`/`ldd` to confirm dynamic linkage. Native Windows builds are not a deployment target; use a Linux builder/container or Linux VM. Qualify arm64 separately.

Sources: root `Makefile:350–451`, `examples/plugins/hello-world/Makefile`, `transports/go.mod`, and [Go's own plugin package documentation][go-plugin]. Go requires identical sources for common packages; matching a version string alone is insufficient. Avoid importing unnecessary framework packages into EpochGuard to reduce the shared dependency surface.

### Registration

Provision a readable absolute path **inside the gateway's filesystem** using the top-level `plugins` configuration. This illustrative fragment assumes the future artifact exists; it does not implement or install the plugin:

```json
{
  "plugins": [
    {
      "name": "epochguard",
      "enabled": true,
      "path": "/app/data/plugins/epochguard.so",
      "placement": "pre_builtin",
      "order": 0,
      "config": {}
    }
  ]
}
```

Put `config.json` in an application directory and start the dynamic executable with `-app-dir /app/data` (plus desired `-host` and `-port`). The actual main flags are in `transports/bifrost-http/main.go`; do not copy the stale `-config` invocation from the build guide. Ensure the runtime UID can traverse the directories and read the plugin file. A container bind mount or copied artifact is sufficient; there is no verified automatic directory-discovery mechanism. [Main][main], [configuration docs][config-doc].

Verified registration chain:

1. `transports/bifrost-http/lib/config.go:6115+` loads persisted plugin config and merges/reconciles file entries, including ordering metadata.
2. `transports/bifrost-http/server/server.go:3451` constructs `SharedObjectPluginLoader` for OSS.
3. `transports/bifrost-http/server/plugins.go` loads built-ins, then enabled custom entries with a path via `InstantiatePlugin` / `loadCustomPlugin`.
4. `framework/plugins/soloader.go` calls `plugin.Open`, optional `Init(config any)`, required `GetName`/`Cleanup`, and optional hook symbol lookups. Wrong symbol types fail loading. HTTP(S) paths are also supported through a download helper, but the proposed deployment uses a local artifact.
5. The server calls `Config.ReloadPlugin`, records placement/order and status, then `SortAndRebuildPlugins`. `lib/config.go:8616+` sorts `pre_builtin → builtin → post_builtin`, ascending order, stably. Default custom placement is **post_builtin**. Derived interface lists drive the core and transport hook runners.

Do not assume the array order overrides placement. Ensure EpochGuard is the first applicable `pre_builtin` plugin; an earlier plugin's short-circuit or a later post-hook that rewrites a response can change the guarantee. Inspect the actual loaded order and test it. The OSS cache is built-in order 7 in this release (`server/plugins.go`); use the source rather than outdated example order tables. [Server registration][server-plugin], [runtime configuration][config], [sequencing docs][sequence-doc].

Management alternatives exist: `POST /api/plugins`, `PUT /api/plugins/{name}`, `DELETE /api/plugins/{name}`, `GET /api/plugins`, and `GET /api/plugins/loaded`. Setting a custom path through the API requires genuine authenticated admin access even if dashboard authentication is disabled. File provisioning is sufficient for the spike. [Management handler][plugin-api].

**Load failure is fail-open at the server level.** `loadCustomPlugins` logs an error, records an error status, and continues. A disabled/missing/mismatched EpochGuard plugin can leave inference available. The deployment must withhold traffic until the loaded status/order and an actual refusal probe pass; `/health` alone is inadequate. That readiness control is a proposed deployment requirement, not a built-in Bifrost guarantee.

Go plugins cannot be closed/unloaded, and reopening the same path returns the existing plugin. Bifrost's logical remove/reload and `Cleanup` do not undo that runtime rule. Use process restart for plugin code replacement; do not promise that overwriting a `.so` hot-swaps code. Global plugin state must be synchronized and `Init`/`Cleanup` lifecycle tested. [Go plugin semantics][go-plugin], [dynamic wrapper][wrapper].

## Caching lifecycle and hook bypass

The OSS response cache is the `semantic_cache` plugin under `plugins/semanticcache/`. It supports direct hashing and embedding similarity. It is distinct from provider-side prompt caching, which reuses input computation but still calls the provider. Neither TTL nor semantic similarity constitutes evidence of factual freshness. [Cache docs][cache-doc].

Verified flow:

1. HTTP headers map to exported cache context keys in `transports/bifrost-http/lib/ctx.go:565–618`. A cache key (`x-bf-cache-key` / `semanticcache.CacheKey`) or configured default key, a request ID, and a supported request type are required for lookup.
2. `plugins/semanticcache/main.go:379+` builds request metadata, tries direct lookup first, then semantic lookup when configured. Lookup/backend/embedding failures generally warn and continue to the provider; the cache is not a freshness verifier. A vector store is required even for direct-only caching. Direct-only configuration uses `dimension: 1` and omits embedding provider/model.
3. `search.go` derives the direct cache identity from request/parameter hashes, scope, and configured provider/model partitioning. Semantic lookup filters metadata and applies the configured threshold. Expired entries are treated as misses and deleted asynchronously; a missing expiry is treated as no expiry, and an unparseable expiry as a miss.
4. On a hit, `search.go:326–407` returns `LLMPluginShortCircuit{Response: ...}` or `{Stream: ...}`. This skips the provider and all remaining LLM pre-hooks.
5. `core/bifrost.go:6494–6513` runs post-hooks for the executed prefix on a buffered cache hit. The stream replay path at `6843+` similarly runs those post-hooks for replayed chunks. Therefore cache hits do not bypass **all** post-hooks; they bypass the post-hooks of plugins whose pre-hooks never ran.
6. On a provider success, cache `PostLLMHook` stamps metadata, serializes the result synchronously, then queues an asynchronous store write. Errors, no-store mode, and large-payload/large-response modes skip writes; cache hits are not rewritten. Streaming responses accumulate owned serialized chunks and flush on the final chunk. Cache store errors do not revoke a delivered response. [Cache implementation][cache-main], [lookup/replay][cache-search], [core dispatch][core-flow].

Ordering consequence, where `E` is EpochGuard and `C` is the built-in cache:

| Placement | Cache hit | Provider miss |
| --- | --- | --- |
| Default `post_builtin`: pre `C → E` | `C` short-circuits; **E's LLM hooks are skipped** | Post `E → C`: E can reject before C stores |
| Required `pre_builtin`: pre `E → C` | Post `C → E`: **E sees the hit before return** | Post `C → E`: C may already queue unverified bytes before E rejects |

HTTP transport post-hooks are outside this LLM short-circuit and still run for the wrapped buffered HTTP response. They provide another release boundary, but cannot retroactively prevent the cache post-hook from having stored a result.

Verified cache controls and limits:

- `CacheNoStoreKey` is the exported `schemas.BifrostContextKey("semantic_cache-no_store")`; HTTP spelling is `x-bf-cache-no-store`. It disables writes **while retaining reads**. Setting it in EpochGuard's pre-hook, before C runs, can prevent the ordering-related write. A false/no-store-absent client value must not override server policy. `ctx.SetValue` permits this non-reserved key. [Cache controls][cache-main], [context][context], [HTTP conversion][http-context].
- There is no verified “reject this candidate and continue C's search or call the provider” callback, nor an injected cache handle in `Init(config any)`. A refusal in E's post-hook returns a refusal; it is not a transparent cache miss. Do not invent such an API.
- Cache identity/diagnostic metadata is `BifrostResponseExtraFields.CacheDebug`, with `CacheHit`, `CacheID`, and related fields. HTTP headers include `x-bifrost-cache-hit`, `x-bifrost-cache-id`, and `x-bifrost-cache-hit-type`. A cache ID on a miss identifies the intended write; asynchronous failure can leave no stored entry. Stream hit metadata is stamped on the final replay chunk, so its absence on an early chunk does not establish a miss. [Metadata/replay][cache-search], [response headers][response-headers].
- Internal embedding calls deliberately skip the plugin pipeline (`search.go:132–155` calls `PrepareContextForInternalEmbeddingRequest`; the core runners honor `BifrostContextKeySkipPluginPipeline`). These are implementation calls, not a promise that every internal request is checked. EpochGuard should not use an unrestricted skip-pipeline mechanism for client responses.
- Upstream invalidation methods are `ClearCacheForCacheID` and `ClearCacheForKey`. HTTP routes are **`DELETE /api/cache/clear/{cacheId}`** and **`DELETE /api/cache/clear-by-key/{cacheKey}`**. The resolver fetches the current cache plugin per request. Use authenticated management access and URL-encode partition keys. [Cache handler][cache-api].
- Deletion is not atomic with queued writes or concurrent in-flight reads. A pending writer can repopulate a deleted entry; a reader can already hold it. Also, `ClearCacheForKey` logs per-result deletion errors after a successful `DeleteAll` call and can still return nil. A successful management response is not evidence of complete revocation. Enforce evidence/version validity at read time and test writer/delete races. [Deletion and async writes][cache-main].

## Preventing an unverified response from reaching the client

### Buffered responses: verified enforcement seam

For a successful protected result, `PostLLMHook` must synchronously wait for the verification decision. On refusal or verification infrastructure failure, return the logical tuple **`(nil, populatedBifrostError, nil)`**. Populate a non-empty safe message and status; set `AllowFallbacks` to false for a terminal denial. On a pre-request refusal use `LLMPluginShortCircuit.Error` instead of an ordinary Go error. Handle upstream errors without accidentally recovering them. [Error carrier][error-carrier], [pipeline][core-flow].

Why this blocks: the pipeline carries the typed Bifrost error; the non-streaming request path returns nil/error when post-hooks invalidate a success. The OpenAI integration checks that error before converting and serializing a successful chat response (`integrations/router.go:1143+`). Core checks `AllowFallbacks` in `shouldTryFallbacks` and `shouldContinueWithFallbacks`. Ordinary `error` values in the third LLM return slot are accumulated/logged; they are not the client refusal mechanism.

Proposed refusal status: 503 for temporarily unavailable verification, with a separate deliberate policy status for stale/unsupported evidence. Those statuses and EpochGuard's error code are product choices, not upstream-defined EpochGuard APIs. Never put the rejected answer into an error message.

For a buffered HTTP final check, `HTTPTransportPostHook` can **replace** `resp.StatusCode`, headers, and body with a safe refusal before returning. Returning an error while leaving the original response unchanged is unsafe: `runTransportPostHooks` applies that response and its caller ignores the ordinary error. The headers hook also cannot enforce refusal. Keep EpochGuard last in the response-transform order and qualify any other response-rewriting plugins. [Middleware implementation][middleware].

This guarantee is scoped to paths that supply a complete typed/buffered response. Large-response/body-stream modes can leave HTTP post-hook bodies nil; passthrough, async jobs, MCP, A2A, realtime/WebSocket, tools with external side effects, and non-text modalities require separate coverage. Do not advertise blanket gateway protection from a chat-completion hook alone. The first supported deployment should expose only qualified inference routes and reject unsupported request modes before execution.

### Streaming: available hooks, additional work required

`PostLLMHook` runs per stream chunk; validating only the terminal assembled response can leak earlier text. The HTTP stream interceptor can drop chunks or terminate before writing a particular successful chunk, but it cannot recall bytes already written or change an already committed HTTP status. An end-of-stream HTTP post-hook is too late. [Stream router][router], [HTTP contract][core-plugin].

There is a real pause/resume API: `BifrostContext.PauseStream`, `ResumeStream`, `ClearPausedStreamBuffer`, `EndStream`, and `GetAccumulatedResponse` in `core/schemas/context.go:798+`. Its implementation relies on a real tracer/accumulator; with the no-op tracer, pause is inert. **`EndStream(error)` flushes buffered chunks first**, so it is not a safe discard operation by itself. `framework/streaming/gate.go` implements the buffering and overflow behavior. Furthermore, cache stream replay has its own path and must be separately qualified. [Context API][context], [gate implementation][stream-gate].

Proposed initial policy: reject `stream: true`, realtime, async, passthrough, and unsupported routes through the authenticated HTTP pre-hook, and reject corresponding typed request types in the LLM pre-hook. Future streaming support requires a bounded hold-and-verify design, proof that pause is active on every supported provider/cache path, discard-before-end on refusal, cancellation/overflow tests, and client-byte assertions. The existing APIs make this worth investigating; this spike does not establish streaming support.

## Can an unchanged standard installation be supported?

| Installation | Result of investigation |
| --- | --- |
| Default published Linux executable / npx-downloaded executable | Native extension is unsuitable as delivered: release build uses static linking |
| Official default Linux Docker image build | Same limitation: `transports/Dockerfile` passes `-extldflags '-static'` and `sqlite_static` |
| OSS source built with documented `DYNAMIC=1` | Native plugin loading and enforcement are supported seams; no core source edit/fork required, pending runtime qualification |
| Existing compatible dynamic OSS gateway | Configuration plus a matching `.so` may suffice; inspect actual toolchain/linkage and run qualification |
| Direct Go SDK embedding | Public LLM plugin interfaces exist, but caller integration/build is required and HTTP hooks do not apply |
| Unchanged static gateway with an external verifier/proxy | A possible separate architecture, not an upstream native plugin mechanism; would need its own routing, buffering and cache-invalidation integration |

Do not claim WASM or webhooks solve the static installation constraint. The OSS server here selects the shared-object loader. The pinned WASM guide marks that mechanism deprecated; webhook plugins are described as planned, not as an available verified interface. [Getting started][getting-started], [WASM status][wasm-doc], [server wiring][server].

Documentation conflicts found: Go-plugin guide examples still mention older core versions and Go 1.26.1 despite the 1.27.3 prerequisites; sequencing prose has outdated built-in positions; config docs label ordering DB-only, whereas the source also carries file ordering directly when there are no stored plugins; the dynamic-build guide shows a `-config` flag absent from the actual main. The proposed baseline uses a fresh DB-backed app directory and explicitly verifies loaded order. Source contracts/build files take precedence over stale snippets. [Go guide][go-doc], [config docs][config-doc], [main][main], [runtime config][config].

## Proposed EpochGuard implementation approach

1. **Qualify the seam first.** Build the pinned dynamic OSS gateway and a minimal external probe plugin in Linux. Prove export loading, ordering, provider/cache response rejection, and deployment readiness before implementing evidence processing.
2. **Start with one supported surface:** buffered non-streaming chat completions. Use HTTP pre-hook checks to restrict routes/modes and LLM pre-hooks to defend typed paths. Use `PostLLMHook` as the authoritative decision point before release. Do not rely on `PreRequestHook` errors, response headers, or logging as enforcement.
3. **Keep evidence and cache identity explicit.** Proposed EpochGuard records bind trusted tenant scope, request/response digest, evidence identities/versions, verification policy version, and verification expiry. On any cache hit, reevaluate the evidence validity for the current request; upstream TTL and similarity alone cannot authorize reuse. Evidence formats, retrieval rules, and failure policy remain product decisions.
4. **Prefer an EpochGuard-owned verified cache for the first product.** Disable `semantic_cache` in that protected deployment. Pre-hook lookup can return a candidate through the real short-circuit carrier; the matching post-hook still verifies it. Store only after verification under EpochGuard-controlled generation/version semantics. This avoids the built-in write-order limitation without core changes.
5. **Treat built-in-cache interoperability as a separately qualified mode.** Register E before C, suppress C's writes in the pre-hook, verify existing hits before release, and invalidate stale entries through the existing management API from an authorized component. Refuse the current request on stale evidence; a subsequent request may regenerate after deletion. Do not claim automatic retry, atomic deletion, or a public verified-write callback. Allowing C to keep writing is possible only if every later read is independently gated; it does not satisfy a “verified entries only” storage invariant.
6. **Make activation operationally enforceable.** Use fixed artifact pins, inspect plugin active status/order, and pass a refusal probe before exposing inference. Restart for binary/plugin upgrades and run the smoke matrix again. Define which operators/plugins are trusted to modify protected traffic. A plugin cannot enforce its own policy if it never loaded.

## Minimal integration smoke-test design (not implemented or run)

Use an isolated Linux/amd64 environment with the pinned builder/toolchain, fresh DB-backed Bifrost data, the dynamic executable, a tiny external probe `.so`, a deterministic local OpenAI-compatible provider fixture with a request counter, and a Redis/Valkey-compatible vector store. No paid model or genuine evidence service is needed: the probe uses fixed allow/refuse/unavailable decisions and records hook names/request IDs to a local test sink. Configure the fixture through Bifrost's documented custom-provider base URL; do not replace the real plugin loader or core pipeline with mocks.

Use `/openai/v1/chat/completions` for the generic OpenAI transport path; separately qualify the native `/v1/chat/completions` path before claiming it. The route definitions are in `integrations/openai.go:590+`. A temporary provider sentinel such as `UNVERIFIED_SENTINEL` makes byte leakage observable. Test code/configuration is future work.

| Case | Setup/action | Required observation |
| --- | --- | --- |
| Native load and identity | Mount correct `.so`, enable it with `pre_builtin`, order 0 | `Init` and correct `GetName` observed; plugin status active; loaded order puts E before C; one provider call on a miss |
| Allowed provider result | Cache disabled, fixture returns sentinel, probe allows | HTTP success with expected fixture body; trace shows E pre/post and HTTP pre/post |
| Rejected provider result | Same fixture, probe refuses in typed post-hook | Non-success status and safe error; **zero sentinel bytes anywhere in client body**; no fallback call |
| Verifier unavailable | Probe timeout/unavailable path | Same no-leak refusal; does not silently pass through |
| Typed error versus ordinary error | Control probe returns ordinary Go error while preserving response; then typed refusal | Ordinary-error control demonstrates non-blocking semantics; typed refusal blocks |
| HTTP post enforcement | Control returns Go error without overwriting HTTP response; then explicitly replaces it | First control can preserve original payload; rewritten response removes sentinel and sets refusal status |
| Direct cache miss/hit | Enable `semantic_cache` with dimension 1 and a unique `x-bf-cache-key`; allow miss; wait with bounded polling for async write | Miss calls provider once; second identical request is a direct hit (`CacheDebug`/cache headers); provider counter unchanged; E post-hook still runs |
| Cached response becomes unverified | Keep cache entry/request fixed, change probe policy to refuse | Hit response blocked, no sentinel bytes, no provider call; proves enforcement on replay |
| Wrong placement control | Move probe to default `post_builtin` and repeat cache hit | LLM trace demonstrates E is skipped; test rejects this deployment ordering |
| Write-order/no-store | With pre-builtin E, reject a fresh provider response; inspect eventual C hit; then repeat using server-enforced no-store from E pre-hook | Shows default C can store before E rejects; no-store run leaves no entry after bounded settle/probe; client-supplied false no-store value cannot disable policy |
| Per-ID and per-key invalidation | Obtain actual cache ID; call real DELETE route; repeat request; repeat for URL-encoded scope key | Entry no longer reused after writes settle; provider counter increments; deletion failure is surfaced/observed |
| Pending-write/delete race | Delay store write, delete during delay, release writer | Record possible repopulation; policy/version gate still refuses stale bytes even if physical deletion lost race |
| TTL | Short TTL, populate, advance real time past expiry and request again | Cache miss and provider invocation; no assumption that TTL proves evidence validity |
| Semantic hit (follow-up qualification) | Fixture embedding endpoint emits controlled vectors; dimension >1; force semantic path | Similar prompt hits without chat-provider call; E post-hook blocks when policy changes; internal embedding bypass is accounted for |
| Unsupported modes | Send stream=true, async, passthrough and unqualified route requests | Explicit pre-execution refusal on exposed protected surfaces; no provider-side effect and no answer bytes |
| Load failure readiness | Wrong Go/shared dependency artifact, missing file/export, disabled plugin, and Init failure | Error/disabled status; demonstrate gateway can remain healthy; traffic gate refuses deployment until probe succeeds |
| Restart and concurrency | Concurrent allowed/refused requests; clean restart, then new artifact on restart | Decisions never mix request state; safe cleanup; no claim that replacing same-path code hot-reloads |

The first acceptance run must include load, provider allow/refuse, unavailable verification, cache miss/hit/refusal, placement control, write suppression, deletion, unsupported streaming, and fail-open startup detection. Semantic mode and any streaming feature are additional release gates for those capabilities.

Retain exact source/toolchain/image pins, resolved module lists, `go version -m` output for both artifacts, linkage inspection, sanitized loaded-plugin status/order, request/response captures, hook-order records, and fixture counters. Use bounded polling for asynchronous cache writes instead of assuming immediate persistence. Success means protected client-visible answer bytes were released only after the probe allowed them; plugin compilation or a healthy process alone is insufficient.

## Upstream source map

All Bifrost links below are pinned to gateway commit `e869c3f9adc96ea53c38694a21bb04a8e1085487`. The dependency-tag comparison above establishes which inspected library files match the modules actually selected by the gateway.

| Exact upstream path | Inspection anchors |
| --- | --- |
| `transports/go.mod` | Gateway module path, Go version, core/framework/cache dependency pins |
| `core/schemas/plugin.go` | HTTP carriers; Base/LLM/HTTP interfaces at 285/295/408; placement/config at 510+ |
| `core/schemas/plugin_native.go` | `LLMPluginShortCircuit` response/stream/error fields |
| `core/schemas/bifrost.go` | `BifrostError` at 2259; `AllowFallbacks`; `ErrorField`; stream control |
| `core/schemas/context.go` | Scoped context values at 518+; pause/resume/discard/end at 798+ |
| `core/bifrost.go` | Fallback control at 5812/5986; cache short-circuit at 6494+; normal post-hooks at 6621+; stream replay at 6843+; plugin runners at 9749+ |
| `framework/plugins/loader.go` | `PluginLoader` contract |
| `framework/plugins/soloader.go` | Native load, initialization, symbol/type checks |
| `framework/plugins/soplugin.go` | Dynamic wrapper dispatch and no-op hooks |
| `framework/plugins/main.go` | Optional interface helpers; library-level loading |
| `framework/streaming/gate.go` | Tracer-backed paused buffer, discard/end, buffer cap and delivery |
| `transports/bifrost-http/main.go` | Actual CLI flags, particularly `-app-dir` |
| `transports/bifrost-http/server/server.go` | OSS loader at 3451; inference middleware order at 3717+ |
| `transports/bifrost-http/server/plugins.go` | Built-in cache order, custom load failure behavior, registration |
| `transports/bifrost-http/lib/config.go` | File/DB merge at 6115+; chunk interceptor at 8074+; registration and sorting at 8522+/8616+ |
| `transports/bifrost-http/lib/ctx.go` | HTTP cache-header conversion at 565+ |
| `transports/bifrost-http/lib/responseheaders.go` | Cache debug header constants at 100+ and serialization |
| `transports/bifrost-http/handlers/middlewares.go` | Transport pre/post/header execution and body-stream exclusions |
| `transports/bifrost-http/handlers/plugins.go` | Plugin management routes and genuine-admin checks |
| `transports/bifrost-http/handlers/cache.go` | Invalidation routes, resolver, status handling |
| `transports/bifrost-http/integrations/openai.go` | Chat completion route definitions at 590+ |
| `transports/bifrost-http/integrations/router.go` | Buffered error-before-conversion, per-chunk interception, streaming output |
| `plugins/semanticcache/main.go` | Config; exported controls at 244+; read/write hooks at 379/662; async writer at 880; no-store at 902; deletion at 1022/1059 |
| `plugins/semanticcache/search.go` | Direct/semantic lookup, internal embeddings, expiry, response/stream replay |
| `plugins/semanticcache/utils.go` | Supported request types, metadata/expiry construction, persistence |
| `plugins/semanticcache/state.go`, `plugins/semanticcache/stream.go` | Per-request state and stream storage lifecycle |
| `Makefile`, `transports/Dockerfile`, `.github/workflows/scripts/build-executables.sh` | Dynamic option versus static default and release build |
| `examples/plugins/hello-world/main.go`, `examples/plugins/hello-world/Makefile` | Concrete exported native plugin functions and build examples |
| `docs/plugins/{getting-started,writing-go-plugin,building-dynamic-binary,sequencing,writing-wasm-plugin}.mdx` | Official plugin docs, deployment prerequisites, deprecated alternatives |
| `docs/features/semantic-caching.mdx`, `docs/deployment-guides/config-json/plugins.mdx` | Cache controls and provisioning documentation |

[release]: https://github.com/maximhq/bifrost/releases/tag/transports/v2.4.0
[tag-object]: https://api.github.com/repos/maximhq/bifrost/git/tags/9c6ac22ceb9794b7dafdceced5f25d93a43f18e4
[transport-mod]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/go.mod
[core-plugin]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/core/schemas/plugin.go
[native-plugin]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/core/schemas/plugin_native.go
[core-flow]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/core/bifrost.go
[error-carrier]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/core/schemas/bifrost.go
[context]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/core/schemas/context.go
[loader]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/framework/plugins/soloader.go
[wrapper]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/framework/plugins/soplugin.go
[server-plugin]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/server/plugins.go
[server]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/server/server.go
[main]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/main.go
[middleware]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/handlers/middlewares.go
[config]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/lib/config.go
[http-context]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/lib/ctx.go
[response-headers]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/lib/responseheaders.go
[router]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/integrations/router.go
[plugin-api]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/handlers/plugins.go
[cache-main]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/plugins/semanticcache/main.go
[cache-search]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/plugins/semanticcache/search.go
[cache-api]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/handlers/cache.go
[stream-gate]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/framework/streaming/gate.go
[make]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/Makefile
[docker]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/Dockerfile
[release-build]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/.github/workflows/scripts/build-executables.sh
[dynamic-doc]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/docs/plugins/building-dynamic-binary.mdx
[go-doc]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/docs/plugins/writing-go-plugin.mdx
[sequence-doc]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/docs/plugins/sequencing.mdx
[getting-started]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/docs/plugins/getting-started.mdx
[wasm-doc]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/docs/plugins/writing-wasm-plugin.mdx
[config-doc]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/docs/deployment-guides/config-json/plugins.mdx
[cache-doc]: https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/docs/features/semantic-caching.mdx
[go-plugin]: https://github.com/golang/go/blob/go1.27.3/src/plugin/plugin.go
