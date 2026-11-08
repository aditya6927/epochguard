# EpochGuard — coding-agent working agreement

This repository is both a hackathon project and a long-term engineering portfolio project. Make changes that can be explained, tested, reproduced, and reviewed by the maintainer.

## Current status

- **Current qualification (Task 003B):** the maintainer reports a passing credentialed FastAPI + Tavily policy test. The opt-in real gateway runner is implemented; active plugin placement/cache absence and live unsupported/error/streaming controls passed. Complete live gateway qualification is **blocked**: deployed retrieval received Tavily 401 and a post-recreation attempt still returned RETRIEVAL_FAILURE. Supported/older live gateway assertions did not run; the maintainer requested that blocked result be recorded. See `docs/task-003b.md`. Offline enforcement and separate cache experiments are preserved. Default and verification deployments keep caching disabled; the default Compose example still uses fixed test decisions.
- **Not yet implemented:** general factual/freshness verification, origin freshness attestation, an EpochGuard-owned protected cache, logically atomic revocation, safe streaming delivery, production authentication, and an external readiness gate.
- The diagnostic `X-EpochGuard-*` headers are **not** evidence of response freshness or a security authorization mechanism.

## Constraints and invariants

1. Inspect the *actual pinned upstream source* before using or changing Bifrost plugin contracts. Do not invent hooks, flags, exported types, or cache APIs.
2. Preserve true provider errors and request identity. Never report a failed operation as successful.
3. No response may be described as verified unless its evidence has been checked under an explicit policy. Logging or adding a header is not verification.
4. For future enforcement, use the actual typed `BifrostError` / short-circuit mechanisms demonstrated in upstream code. Ordinary Go hook errors must not be assumed to block responses.
5. Account for cache ordering and asynchronous writes. Task 002C proves that early enforcement can follow a built-in cache write, late enforcement can be skipped on a hit, and deletion is not a write barrier. Keep cache experiments isolated; this qualification does not authorize unrestricted built-in cache writes for protected deployment.
6. Treat retrieved web content and LLM responses as untrusted data. Do not allow content from either to bypass an enforcement decision.
7. Never embed API keys, auth tokens, or private source code in tests, log output, examples, or commits. The known test setup token is explicitly **local-development-only**.
8. Never expose the fixture's no-auth HTTP gateway beyond loopback. Streaming, passthrough, asynchronous, and other unqualified routes are not protected.
9. Keep changes scoped to the current milestone; do not silently implement future phases.
10. No claim of tests passing unless the exact command was executed and the outcome recorded.

## Workflow for each task

1. Read `README.md`, `docs/bifrost-integration-spike.md`, and the latest task note.
2. State the requirement, the proposed minimal design, and key correctness invariants.
3. Implement a small coherent change with tests (including negative controls where needed).
4. Run relevant checks, record *actual* outputs, and describe tests that could not run.
5. Explain important code paths, ownership/lifetimes, error handling, and trade-offs in plain language.
6. Update architecture/decision docs for material design changes; recommend one precise conventional commit.
7. Stop at the requested milestone for maintainer review.

## Existing build and test commands

```sh
# Docker Desktop / Linux; from repository root
# Use --builder epochguard-002a if the default builder cannot resolve GitHub.
docker compose build gateway
docker compose --profile test up -d --force-recreate --wait provider gateway gateway-control gateway-reject gateway-unavailable
docker compose --profile test run --rm --no-deps smoke
docker compose --profile test down --remove-orphans
```

Go plugin unit tests and `go test -race` run inside `dev/Dockerfile` during the image build. The race detector covers unit execution, not the real gateway process. Do not substitute a mocked plugin loader for the real gateway smoke test.

The isolated cache lifecycle suite uses the same built image and has no host ports:

```sh
docker compose -f compose.cache.yaml up -d --wait provider store-proxy writer reader reject safe unavailable post-reject post-allow
docker compose -f compose.cache.yaml run --rm --no-deps cache-tests
docker compose -f compose.cache.yaml down --volumes --remove-orphans
```

It contains explicitly unsafe ordering/write controls and a test-only Redis transport gate. Consult `docs/task-002c.md` and ADR 0003 before changing cache behavior. No client header or prompt may select a decision, enable server writes, or shorten a server-enforced decision delay.

The isolated 003A verification suite uses no host ports or live API credentials:

```sh
docker compose -f compose.verify.yaml build verifier-supported
docker compose -f compose.verify.yaml run --rm verification-tests
docker compose -f compose.verify.yaml down --remove-orphans
```

Build the native gateway image first. The Python image runs offline tests during build. Only an explicitly selected live test/deployment may use `TAVILY_API_KEY`; never print resolved live Compose configuration. A fixture evidence record must not be accepted as live evidence or described as a real factual observation.

For the opt-in live gateway suite, start only `gateway-supported` with `compose.verify.yaml` plus `compose.verify.live.yaml`, then run `verification-tests` with `-e EPOCHGUARD_RUN_LIVE_TAVILY=1 --no-deps`. This runner gets no Tavily key and dynamically derives its candidate version from a direct verifier observation. Expect up to three extraction calls on a successful run; do not retry failed live assertions to manufacture a pass. See `docs/task-003b.md` for exact commands and retrieval-observability limits.

## Source layout and ownership

- `plugins/epochguard/`: Go native plugin and its unit tests.
- `services/verifier/`: narrow typed evidence policy, bounded Tavily client, FastAPI service, and offline/opt-in live tests.
- `cmd/provider-fixture/`: controlled upstream provider test double.
- `tests/smoke/`: gateway end-to-end acceptance tests.
- `tests/verification/`, `compose.verify.yaml`: real gateway/service qualification with deterministic evidence fixtures.
- `tests/cachelifecycle/`, `cmd/cache-store-proxy/`: isolated real cache qualification and deterministic Redis write scheduling.
- `dev/`, `compose.yaml`: pinned gateway build and development deployment.
- `docs/`: upstream findings, executed test evidence, design decisions, and later product specifications.

Commit message examples: `test(gateway): cover missing HTTP response`, `docs: record gateway integration decisions`, `feat(gateway): enforce buffered response decisions`.
