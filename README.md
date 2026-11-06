# EpochGuard

Task 003A adds a Python/FastAPI verification service behind the native Go enforcement plugin. One exact claim about the latest stable Python 3 Windows release listed on Python.org is compared with fixed-URL Tavily Extract evidence. Supported, contradicted, and insufficient evidence map to ALLOW, terminal REJECT, and terminal UNAVAILABLE. This is a narrow policy, not general factual verification. Offline end-to-end tests pass; the opt-in live Tavily test has not been run with credentials. See [Task 003A](docs/task-003a.md) for the grammar, evidence contract, executed tests, and limitations.

Task 002B established synchronous enforcement inside the real Bifrost HTTP gateway using controlled, **test-only** ALLOW / REJECT / UNAVAILABLE decisions. The original `compose.yaml` below retains that test setup; use the separate 003A deployment to exercise evidence comparison.

Task 002C qualifies the real built-in cache lifecycle in an isolated test deployment. It reproduces unsafe write ordering, a cache-hit enforcement bypass under incorrect placement, and pending writes repopulating invalidated entries. **The default deployment still has caching disabled.** The future EpochGuard-owned verified cache is not implemented.

The upstream investigation is in [docs/bifrost-integration-spike.md](docs/bifrost-integration-spike.md). Enforcement behavior is in [Task 002B](docs/task-002b.md); cache experiments, observed traces/counters, exact commands, and limitations are in [Task 002C](docs/task-002c.md). [Task 002A](docs/task-002a.md) records the original loader qualification. The EpochGuard-owned protected cache and dashboard remain unimplemented.

Run the 003A offline verification qualification after building the native gateway image:

```sh
docker compose build gateway
docker compose -f compose.verify.yaml build verifier-supported
docker compose -f compose.verify.yaml run --rm verification-tests
docker compose -f compose.verify.yaml down --remove-orphans
```

Use `--builder epochguard-002a` on the build commands if required by this host's DNS setup. The Python image build runs 26 offline tests; the gateway acceptance suite exercises the real plugin loader, FastAPI, and a deterministic Tavily HTTP fixture on an internal network without host ports. No paid API key is needed. Synthetic release numbers in these tests are not real factual evidence. Built-in caching remains disabled. [The live test instructions](docs/task-003a.md#opt-in-live-qualification) require explicit opt-in and an environment-provided Tavily key; observation timestamps do not prove origin freshness.

Requires Docker Desktop running Linux containers (or Docker Engine on Linux) and Docker Compose. No host Go installation or paid provider API key is required. Run from this repository root:

```sh
docker compose build gateway
docker compose --profile test run --rm smoke
```

On this development host, default Docker DNS could not resolve GitHub. If that happens, use the isolated builder commands in [the build notes](docs/task-002a.md#build-and-test); after creating that builder, replace the build command with `docker compose build --builder epochguard-002a gateway`.

The smoke service starts a local provider fixture and four real gateways: ALLOW, REJECT, UNAVAILABLE, and a no-plugin negative control. It checks loading/order, real provider round trips, safe refusals with no answer bytes, terminal fallback behavior, provider-error preservation, pre-dispatch streaming rejection, concurrent request isolation, and usable fallback/SSE controls. A healthy gateway alone does not satisfy the test. The image build runs plugin unit tests and the race detector.

Inspect hook output and build information:

```sh
docker compose logs gateway
docker compose exec gateway cat /app/build-info/toolchain.txt
docker compose exec gateway cat /app/build-info/gateway-elf.txt
docker compose exec gateway cat /app/build-info/plugin.txt
```

Stop and remove this development stack when finished:

```sh
docker compose --profile test down --remove-orphans
```

The API is bound to `127.0.0.1:8080`. Inference authentication is disabled; management probes use a public development setup token defined in Compose. The only configured provider is the local fixture. Container data is disposable. Recreate the gateway after rebuilding plugin code:

```sh
docker compose build gateway
docker compose --profile test up -d --force-recreate --wait provider gateway gateway-control gateway-reject gateway-unavailable
docker compose --profile test run --rm --no-deps smoke
```

For a request from PowerShell after starting the stack:

```powershell
$body = @{ model = 'fixture/epochguard-test'; stream = $false; messages = @(@{ role = 'user'; content = 'hello from EpochGuard' }) } | ConvertTo-Json -Depth 4
$result = Invoke-WebRequest -UseBasicParsing -Uri http://localhost:8080/openai/v1/chat/completions -Method Post -ContentType application/json -Body $body
$result.Headers
$result.Content
```

Expected diagnostic headers are `X-EpochGuard-Plugin: epochguard` and `X-EpochGuard-Hooks: http_pre,pre_request,pre_llm,post_llm,http_post`. These headers report hook execution; they are not a freshness verdict.

The loopback gateway uses the test-only ALLOW configuration so the example still returns the fixture answer. REJECT and UNAVAILABLE run only on the internal test network. Decisions come from plugin configuration, never request headers or prompts. Protected inference is limited to buffered `POST /openai/v1/chat/completions`; streaming and asynchronous modes are refused. Production authentication and an external readiness gate remain unimplemented, so this development stack must remain local.

Run the separate cache qualification after building the image:

```sh
docker compose -f compose.cache.yaml up -d --wait provider store-proxy writer reader reject safe unavailable post-reject post-allow
docker compose -f compose.cache.yaml run --rm --no-deps cache-tests
docker compose -f compose.cache.yaml down --volumes --remove-orphans
```

This stack uses a digest-pinned Redis Stack backend, publishes no host ports, and includes deliberately unsafe negative controls. Its test proxy can pause real cache writes to reproduce invalidation races; it is not a production component. Server `cache_no_store` suppresses writes but retains reads. Neither this flag, a cache hit, nor successful physical deletion is a freshness verdict. [ADR 0003](docs/decisions/0003-protected-cache-ownership.md) records the proposed future admission/revocation design.
