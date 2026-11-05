# EpochGuard — coding-agent working agreement

This repository is both a hackathon project and a long-term engineering portfolio project. Make changes that can be explained, tested, reproduced, and reviewed by the maintainer.

## Current status

- **Qualified so far (Task 002A):** a dynamically linked Bifrost HTTP v2.4.0 gateway loads the external Go plugin and runs its hooks for buffered `/openai/v1/chat/completions` requests sent to the local provider fixture.
- **Not yet implemented:** freshness verification, Tavily integration, response refusal, a protected response cache, cache invalidation, safe streaming, production authentication, and an external readiness gate.
- The diagnostic `X-EpochGuard-*` headers are **not** evidence of response freshness or a security authorization mechanism.

## Constraints and invariants

1. Inspect the *actual pinned upstream source* before using or changing Bifrost plugin contracts. Do not invent hooks, flags, exported types, or cache APIs.
2. Preserve true provider errors and request identity. Never report a failed operation as successful.
3. No response may be described as verified unless its evidence has been checked under an explicit policy. Logging or adding a header is not verification.
4. For future enforcement, use the actual typed `BifrostError` / short-circuit mechanisms demonstrated in upstream code. Ordinary Go hook errors must not be assumed to block responses.
5. Account for cache ordering and asynchronous writes. Do not enable the built-in semantic cache for protected traffic until its interaction with EpochGuard has been tested.
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
docker compose --profile test up -d --force-recreate --wait provider gateway gateway-control
docker compose --profile test run --rm --no-deps smoke
docker compose --profile test down --remove-orphans
```

Go plugin unit tests run inside `dev/Dockerfile` during the image build. Running `go test -race` against the plugin is a follow-up check, not a completed 002A qualification. Do not substitute a mocked plugin loader for the real gateway smoke test.

## Source layout and ownership

- `plugins/epochguard/`: Go native plugin and its unit tests.
- `cmd/provider-fixture/`: controlled upstream provider test double.
- `tests/smoke/`: gateway end-to-end acceptance tests.
- `dev/`, `compose.yaml`: pinned gateway build and development deployment.
- `docs/`: upstream findings, executed test evidence, design decisions, and later product specifications.

Commit message examples: `test(gateway): cover missing HTTP response`, `docs: record gateway integration decisions`, `feat(gateway): enforce buffered response decisions`.
