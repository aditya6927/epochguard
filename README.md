# EpochGuard

Task 002A establishes a native Go plugin running inside the real Bifrost HTTP gateway. It observes request/response hooks and returns diagnostic headers. It does not verify claims, enforce freshness, implement caching, or include a dashboard.

The upstream investigation is in [docs/bifrost-integration-spike.md](docs/bifrost-integration-spike.md). Build details, acceptance tests, and limitations are in [docs/task-002a.md](docs/task-002a.md).

Requires Docker Desktop running Linux containers (or Docker Engine on Linux) and Docker Compose. No host Go installation or paid provider API key is required. Run from this repository root:

```sh
docker compose build gateway
docker compose --profile test run --rm smoke
```

On this development host, default Docker DNS could not resolve GitHub. If that happens, use the isolated builder commands in [the build notes](docs/task-002a.md#build-and-test); after creating that builder, replace the build command with `docker compose build --builder epochguard-002a gateway`.

The smoke service starts a local provider fixture, a gateway with EpochGuard, and a second gateway without the plugin as a negative control. It checks plugin status/order, a real provider round trip, upstream-error preservation, concurrent request isolation, and detection of the absent plugin. A healthy gateway alone does not satisfy the test.

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
docker compose --profile test up -d --force-recreate gateway gateway-control
docker compose --profile test run --rm smoke
```

For a request from PowerShell after starting the stack:

```powershell
$body = @{ model = 'fixture/epochguard-test'; stream = $false; messages = @(@{ role = 'user'; content = 'hello from EpochGuard' }) } | ConvertTo-Json -Depth 4
$result = Invoke-WebRequest -UseBasicParsing -Uri http://localhost:8080/openai/v1/chat/completions -Method Post -ContentType application/json -Body $body
$result.Headers
$result.Content
```

Expected diagnostic headers are `X-EpochGuard-Plugin: epochguard` and `X-EpochGuard-Hooks: http_pre,pre_request,pre_llm,post_llm,http_post`. These headers report hook execution; they are not a freshness verdict.
