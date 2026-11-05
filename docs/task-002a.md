# Task 002A: native Bifrost plugin

Task boundary: load a minimal external plugin into the real, dynamically linked Bifrost HTTP gateway and observe its hooks during a provider request. No freshness decision, claim extraction, Tavily calls, cache, dashboard, or enforcement implementation belongs to this task.

## Files and interfaces

| File | Purpose |
| --- | --- |
| `dev/Dockerfile` | Fetches the exact gateway commit; builds gateway, external `.so`, provider fixture, and smoke binary in Linux |
| `plugins/epochguard/main.go` | Exports native symbols with Bifrost's real schema types; records execution on the request context |
| `plugins/epochguard/go.mod`, `go.sum` | Locks the shared dependencies to the gateway's complete transport module graph |
| `dev/bifrost/config.json` | Registers the plugin before built-ins and configures a local OpenAI-compatible provider |
| `dev/bifrost/config.no-plugin.json` | Same local provider without EpochGuard, used as a negative control |
| `cmd/provider-fixture/main.go` | Test HTTP provider: echoes a request-specific prompt and records how many upstream requests it received |
| `tests/smoke/smoke_test.go` | Calls the real management and inference endpoints and asserts loading, execution, and provider round trips |
| `compose.yaml` | Development gateway, provider, and test-profile smoke/control services |
| `dev/buildkitd.toml` | Optional isolated-builder DNS workaround for this development host |

The loader resolves exported package-level functions in a Go `package main`. It calls optional `Init(config any) error`, requires `GetName() string` and `Cleanup() error`, and type-checks optional hooks. EpochGuard imports `github.com/maximhq/bifrost/core/schemas` directly. It implements the three LLM hook exports and the HTTP pre/post exports; missing optional exports use the upstream dynamic wrapper's no-op defaults.

Authoritative upstream paths at commit `e869c3f9adc96ea53c38694a21bb04a8e1085487`:

- [`core/schemas/plugin.go`](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/core/schemas/plugin.go): public hook types.
- [`framework/plugins/soloader.go`](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/framework/plugins/soloader.go): symbol loading and validation.
- [`framework/plugins/soplugin.go`](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/framework/plugins/soplugin.go): dispatch and optional-hook defaults.
- [`transports/bifrost-http/server/plugins.go`](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/server/plugins.go): config-based registration.
- [`transports/bifrost-http/handlers/middlewares.go`](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/handlers/middlewares.go): HTTP pre/post hooks.

## Lifecycle and invariants

For the qualified non-streaming OpenAI transport route:

```text
POST /openai/v1/chat/completions
  HTTPTransportPreHook       -> http_pre
  PreRequestHook             -> pre_request
  PreLLMHook                 -> pre_llm
  real local provider HTTP request
  PostLLMHook                -> post_llm
  HTTPTransportPostHook      -> http_post, diagnostic response headers
  client receives the fixture answer
```

`record` appends phases to a request-owned `hookTrace` stored under a plugin-owned `BifrostContextKey`. Bifrost can create a core child context from the transport context, so replacing a string in the child does not update the parent's value. The shared trace pointer lets HTTP post-processing observe phases recorded by the core hooks. A small mutex protects the trace slice. The implementation retains neither pooled upstream context wrappers nor response pointers. There is no mutable package-global request state.

The hooks preserve the incoming request pointer, response pointer, and typed upstream error. HTTP post-processing adds only `X-EpochGuard-Plugin` and `X-EpochGuard-Hooks` response headers. These markers prove that code executed in this development setup; they are not evidence, authentication, or a verification verdict.

Configuration selects `pre_builtin`, order 0. The smoke test checks loaded membership and the active plugin's placement/order metadata instead of trusting the file alone. `/api/plugins/loaded` sorts names alphabetically; it does not expose execution order. Upstream sorting applies the placement/order metadata, and this deployment has one custom plugin. Bifrost can remain healthy after custom plugin loading fails, so `/health` is used only for startup sequencing; active status plus the real request trace are acceptance criteria.

Two upstream configuration requirements were confirmed by the first runtime test. The fixture provider's `network_config.allow_private_network: true` permits its Compose-network address; it is scoped to that provider configuration. A fresh gateway also locks `/api` until setup authentication is supplied. Compose provides a deliberately public local-development `BIFROST_SETUP_TOKEN`, and the smoke client sends it as `X-Bifrost-Setup-Token` on management requests only. These are real supported fields from [`core/schemas/provider.go`](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/core/schemas/provider.go) and [`handlers/middlewares.go`](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/handlers/middlewares.go). No gateway guard is patched out.

For this pinned OpenAI provider, the base URL is `http://provider:9000`, with no `/v1` suffix. [`core/providers/openai/openai.go`](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/core/providers/openai/openai.go) appends `/v1/chat/completions`. Supplying `/v1` in the base URL duplicates that prefix and produces a provider 404.

## Pins and build decisions

- Gateway: Bifrost HTTP `transports/v2.4.0`, commit `e869c3f9adc96ea53c38694a21bb04a8e1085487`. The Dockerfile fetches the commit and verifies `git rev-parse HEAD`. A sparse checkout downloads the transport tree without the repository's large documentation/media assets; library dependencies come from the pinned Go modules.
- Toolchain: Go **1.27.3**, `linux/amd64`, `CGO_ENABLED=1`, `GOWORK=off`, `GOTOOLCHAIN=local`, and `-trimpath` for gateway and plugin.
- Builder/runtime base: `golang:1.27.3-alpine3.24@sha256:f2c872bcee949b7be9c490efd02b48a8a2fbf947cdf533f1c58525ec9d8170fd`.
- Core `v1.14.1`, framework `v1.11.1`, semanticcache dependency `v1.7.4`, and all other selected modules remain pinned by the upstream manifest/checksums. The semantic cache plugin is not enabled.
- Dynamic gateway linking: no static linker flag and no `sqlite_static` tag. The build requires an ELF program interpreter, recording `readelf` output alongside `go version -m` and the resolved module list. Gateway compilation uses `-p=2` to bound memory use on development Docker installations.

The plugin's module graph intentionally contains dependencies it does not import. Go native plugins require matching builds of shared packages; the gateway's selected transitive dependency versions can differ from a standalone minimal plugin's selection. To avoid that mismatch, the plugin manifest is a copy of the pinned upstream transport manifest with only its module declaration changed. The build compares both manifests (excluding that declaration) and both checksum files and fails if they drift. Do not casually run `go mod tidy` in the plugin module: it would remove this alignment. Upgrade the gateway and both dependency files together.

No upstream Go source is patched. Bifrost's `go:embed all:ui` requires an input directory at compile time, so the API-only build supplies a small text asset in that generated directory. No dashboard is built or bundled. The development image retains Go tools to make artifact inspection easy; it is not intended as a minimal production image.

Source, Go modules, and base image are fixed. Alpine packages are installed from the Alpine repositories, so this is a repeatable development build, not a claim of a byte-for-byte hermetic build. Initial builds require access to Docker Hub, GitHub, Alpine mirrors, and the Go proxy/checksum service. BuildKit caches dependency downloads and compilation across rebuilds.

## Build and test

Run from the repository root. Both commands work in PowerShell and a Linux shell:

```sh
docker compose build gateway
docker compose --profile test run --rm smoke
```

The first command also runs the plugin unit test and checks Go formatting before producing the image. The second exits nonzero if an integration assertion fails. It automatically starts the provider and both gateways and waits for their health checks. Containers use fresh disposable SQLite state on first creation; rerunning smoke generates unique prompts so fixture counters cannot produce stale positive results.

If default Docker DNS fails to resolve GitHub or the Go proxy, create the isolated builder supplied here:

```sh
docker buildx create --name epochguard-002a --driver docker-container --buildkitd-config dev/buildkitd.toml
docker compose build --builder epochguard-002a gateway
docker compose --profile test run --rm smoke
```

Create the named builder once; on later runs use the build command with `--builder epochguard-002a`. The file configures public DNS for build containers only. It does not change daemon-wide DNS. Networks that require corporate DNS should supply their approved resolver instead.

After code changes, rebuild and recreate processes because Go plugins are not safely replaced by overwriting the same `.so` path:

```sh
docker compose build --builder epochguard-002a gateway
docker compose --profile test up -d --force-recreate gateway gateway-control
docker compose --profile test run --rm smoke
```

If using the default builder, omit `--builder epochguard-002a`. Inspect the gateway before cleanup:

```sh
docker compose logs gateway
docker compose exec gateway cat /app/build-info/toolchain.txt
docker compose exec gateway cat /app/build-info/gateway.txt
docker compose exec gateway cat /app/build-info/plugin.txt
docker compose exec gateway cat /app/build-info/gateway-elf.txt
docker compose exec gateway cat /app/build-info/modules.txt
docker compose --profile test down --remove-orphans
```

The named builder and its caches remain for later builds. Removing it is optional: `docker buildx rm epochguard-002a`.

## What the tests establish

| Test | Proof |
| --- | --- |
| `TestPostLLMHookPreservesError` (plugin module, build-time) | A typed upstream failure is passed through unchanged |
| `TestHookTraceSurvivesCoreChildContext` (plugin module, build-time) | Phases written in a core child context remain visible to transport post-processing |
| `TestLoadedPlugin` | Real management API lists EpochGuard as loaded and reports active status, pre-builtin placement, and order 0 |
| `TestRealProviderRequest` | A client request reaches the fixture exactly once, returns its request-specific answer, and carries the complete hook sequence |
| `TestUpstreamErrorPreserved` | A real provider 400 remains a 400; post-hooks execute on the error path |
| `TestConcurrentRequestContexts` | Six simultaneous provider requests each have the expected independent hook sequence and answer |
| `TestHealthyGatewayWithoutPluginFailsProof` | The same execution assertion rejects a real healthy gateway that serves provider responses without EpochGuard |

The client sends a forged diagnostic request header; the test requires a server-generated response sequence. The fixture counter and unique echoed prompt establish a real upstream call rather than a short-circuit. Hook log lines include the Bifrost request ID, when available, for manual inspection without logging prompt or response content.

## Executed results

Validated on 2026-11-06 (Asia/Calcutta) with Docker Desktop's Linux/amd64 engine. The following commands ran successfully after the runtime configuration corrections described above:

```sh
docker compose build --builder epochguard-002a gateway
docker compose --profile test up -d --force-recreate --wait gateway gateway-control
docker compose --profile test run --rm --no-deps smoke
```

| Check | Actual result |
| --- | --- |
| Pinned source checkout and module-manifest/checksum comparison | Passed |
| `go mod verify` | `all modules verified` |
| Go formatting checks | Passed |
| Plugin `go test -mod=readonly -trimpath -v ./...` | Both unit tests passed |
| Dynamic gateway and native `.so` builds | Passed |
| Smoke suite | All five top-level tests passed, including six concurrent-request subtests; exit code 0 |
| Host PowerShell request from README | HTTP 200; `fixture: hello from EpochGuard`; both diagnostic headers present |
| Artifact inspection | Both artifacts report Go 1.27.3 and core v1.14.1; gateway reports pinned VCS commit; plugin reports `-buildmode=plugin`; both report `-trimpath=true` |
| ELF interpreter check | `/lib/ld-musl-x86_64.so.1` present |

Observed request sequence:

```text
X-EpochGuard-Plugin: epochguard
X-EpochGuard-Hooks: http_pre,pre_request,pre_llm,post_llm,http_post
```

The no-plugin control returned the fixture's answer but had neither diagnostic header; `executionProof` rejected it as intended. Upstream-error preservation was verified through a real provider HTTP 400 as well as the unit test.

Local evidence is retained under ignored `artifacts/002a/`: `smoke.log`, gateway logs, copied build-info files, and the manual response JSON. Early failed smoke transcripts are retained separately. The initial DNS failure was resolved through the project builder; the early smoke failures identified private-provider permission, setup authentication, base URL construction, and the alphabetical loaded-name endpoint. This run qualifies the minimal native integration only.

## Go concepts demonstrated

**Exported functions and exact types.** A capitalized function such as `PreLLMHook` is visible to `plugin.Lookup`. The loader asserts its exact function signature using Bifrost's schema types. A function with a similar name or a locally copied lookalike request type would not satisfy that assertion.

**Pointers and request-scoped state.** Passing `*BifrostRequest`, `*BifrostResponse`, and `*BifrostError` through preserves their identity and avoids copying large values. A pointer to a request-owned trace allows parent/child contexts to share phase updates; replacing an immutable string in a child would not update its parent. The trace mutex protects its slice, while separate HTTP requests receive separate trace objects. Bifrost owns the context lifetime; a hook must not retain pooled values after returning.

## Limitations

Only the buffered `/openai/v1/chat/completions` path and local provider are tested here. Streaming, cache hits, native `/v1` routes, fallback behavior, other providers/modalities, production authentication, failure enforcement, and deployment readiness policies require later tasks. Bifrost's optional background catalog/network features are not acceptance criteria and can produce warnings in this API-only setup. No freshness or safety guarantee follows from these diagnostics. The negative control demonstrates detection of an absent plugin; it does not implement a production traffic gate.

Inference auth is disabled and the gateway port is published on loopback only. Management probes authenticate with the explicitly public development setup token in Compose. The fixture credential is deliberately fake. No real provider keys are needed. Configuration databases live inside disposable containers, not host bind mounts. Removing/recreating gateway containers loses that development state.

Stop after Task 002A and review the observed integration before Task 002B.
