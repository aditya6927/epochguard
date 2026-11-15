# EpochGuard — coding-agent working agreement

This repository is both a hackathon project and a long-term engineering portfolio project. Make changes that can be explained, tested, reproduced, and reviewed by the maintainer.

## Current status

- **Bounded-prose enforcement (Task 004G):** the isolated `004g.v1` / `bounded-prose-v1` mode admits exactly nine ASCII sentence forms under independent full-response Go/Python parsing, existing two-policy evidence checks and a policy-specific protected receipt. 004G-S hardening requires `004g.receipt.v2`: exact forwarded request-body binding, mandatory protocol matching and a minimal signed envelope that preserves only approved assistant content. Legacy B/D/E receipts remain explicitly configured `004d.v1` and retain their old limitations. See `docs/task-004gs.md`. Offline qualification uses simulated source transports and the real fixture provider/native gateway/ingress. `004G LIVE QUALIFICATION PENDING`. The 004F planner and model remain non-authorizing. Existing 003A/004B/004E modes retain their behavior; see `docs/task-004g.md`.

- **Current qualification (Task 004E):** the maintainer-authorized November 14, 2026 live run met the narrow protected multi-claim acceptance checks, based on subsequent inspection of the preflight, measurements and verifier reports. The real ingress → Bifrost → Go → 004B verifier path used `tavily_live` Python.org Windows and `pypi_live` requests observations. Two supported claims were delivered unchanged (200); older contradiction (403), unsupported content (503), missing plugin (503) and genuine provider error (400) met all five client expectations. The runner printed `LIVE RUN COLLECTED: independent result review required`, not a final live PASS; the report assessment is recorded in `docs/task-004e.md`. Each source recorded three attempted/three completed application-level retrievals, not independent billing or origin-fetch counts. This qualifies two fixed exact-template policies with a controlled provider and the 004D receipt boundary, not general prose, a commercial LLM or production readiness. Existing `003a.v1` behavior remains unchanged; caching stays disabled.
- **Historical qualification (Task 003B):** narrow live Bifrost → Go → FastAPI → Tavily qualification is complete on the maintainer-supplied November 8, 2026 rerun: full `TestLiveGatewayQualification` passed in 18.16s with all five subtests. Supported delivery, older terminal 403 without answer leakage, unsupported refusal, upstream errors, streaming refusal, and plugin placement/cache absence were checked. Earlier blocked 401 attempts are preserved; their exact credential-mismatch cause is not proven. See `docs/task-003b.md`. This covers one explicit policy with the local provider fixture, not general verification or production readiness; live retrieval counts for that run remain unavailable. Default and verification deployments keep caching disabled; the default Compose example still uses fixed test decisions.
- **Not yet implemented or qualified:** general factual/freshness verification, origin freshness attestation, an EpochGuard-owned protected cache, logically atomic revocation, safe streaming delivery and production authentication/readiness. Isolated protected ingress and its independent readiness check exist (004D/004E); they are not a production-wide gate. The private gateway-to-verifier HTTP hop lacks independent authentication, and pinned Bifrost has no qualified global execution deadline.
- The diagnostic `X-EpochGuard-*` headers are **not** evidence of response freshness or a security authorization mechanism.
- The explicitly legacy authenticated `004d.v1` receipt binds responses to request nonces and outcomes, but not original request bodies. G now requires `004g.receipt.v2`, binds original request bytes and strips provider metadata before signing. It does not attest origin freshness; direct deployments without the ingress remain vulnerable to missing-plugin delivery. See `docs/task-004d.md`.
- **Route boundary audit (Task 003C):** real gateway tests cover registered passthrough prefixes, raw/encoded targets, alternate inference entry points and configured Warp chat. No provider-answer bypass was reproduced on those paths. API routes skip HTTP transport hooks; Warp chat is refused by the core request-type guard but returns HTTP 200 with an error body/event. Router redirects and prerequisite failures are not EpochGuard enforcement. Warp background work explicitly skips plugins and remains unqualified. See `docs/task-003c.md`; do not describe the plugin as an all-route firewall.
- **Experimental claim analysis (Task 004A):** `services/claim_analysis/` adds a separate strict span schema, sentence baseline, bounded opt-in Gemini adapter and evaluation CLI. Its 112 examples/184 factual annotations are agent-authored drafts, not human-reviewed gold; real-model quality remains pending. Baseline fresh-evidence recall is inadequate. This package is not imported by `/v1/verify` and never returns a release verdict. See `docs/task-004a.md` before changing its rules/splits or claiming quality.

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

Build the native gateway image first. The Python image runs offline tests during build. Only an explicitly selected legacy live test/deployment may use `TAVILY_API_KEY`; 004E uses a verifier-only runtime secret file and explicit live opt-in. Never print resolved live Compose configuration. A fixture evidence record must not be accepted as live evidence or described as a real factual observation.

For the opt-in live gateway suite, start only `gateway-supported` with `compose.verify.yaml` plus `compose.verify.live.yaml`, then run `verification-tests` with `-e EPOCHGUARD_RUN_LIVE_TAVILY=1 --no-deps`. This runner gets no Tavily key and dynamically derives its candidate version from a direct verifier observation. Expect up to three extraction calls on a successful run; do not retry failed live assertions to manufacture a pass. See `docs/task-003b.md` for exact commands and retrieval-observability limits.

The offline route audit uses `docker compose -f compose.routes.yaml up -d --wait reject control warp-control warp-reject nolog`, then `docker compose -f compose.routes.yaml run --rm --no-deps route-tests`. Build the native gateway image first. Stop it with `docker compose -f compose.routes.yaml down --volumes --remove-orphans`. No host ports or live keys are used. Its no-EpochGuard controls, native observer and Warp Redis vector backend are test-only; this does not enable the semantic response cache or qualify background jobs.

The current protected multi-claim offline reproduction is
`& .venv-003a/Scripts/python.exe tests/livequalification/qualify.py --build` in
PowerShell. The unchanged 004D lifecycle suite is
`& .venv-003a/Scripts/python.exe tests/protectedingress/qualify.py` after building
its images. Both use isolated networks with no host ports/live credentials and
remove their stacks/signing-key volumes. See `docs/task-004d.md` and
`docs/task-004e.md`. The separate `--live` run requires explicit
`EPOCHGUARD_RUN_LIVE_004E=1` and a temporary runtime Tavily secret file; it has a
maximum of three retrieval invocations per source. Readiness is source-free.
Never retry paid qualification to manufacture success or confuse simulated
transport failures with real-source observations.

The isolated bounded-prose offline runner is `& .venv-003a/Scripts/python.exe tests/boundedprose/qualify.py --build` in PowerShell. It runs the actual native gateway, source/receipt adversaries, concurrent disable and restart, then removes its networks/key volume. It has no live option and never reads evidence credentials.

## Source layout and ownership

- `services/verifier/verifier/bounded_prose/`, `tests_bounded_prose/`, `plugins/epochguard/prose.go`: new versioned original/canonical contract, deterministic parsing and evidence composition. `tests/boundedprose/`, `compose.verify.004g.yaml`, `dev/prose/` own its offline protected deployment and lifecycle qualification. Go never consumes 004F planning records.

- `plugins/epochguard/`: Go native plugin and its unit tests.
- `services/verifier/`: unchanged 003A legacy endpoint, bounded Tavily client and FastAPI service; `verifier/multiclaim/` owns the experimental two-policy grammar, comparisons, aggregation and trusted live factory. `tests_multiclaim/`, `tests_gateway/` and `tests_live/` cover those boundaries, offline fault controls and the source-budget/client runner.
- `internal/ingress/`, `cmd/protected-ingress/`: buffered release, per-response receipt validation, trusted deadline profiles and source-free live readiness; `plugins/epochguard/attestation.go` owns signing.
- `services/claim_analysis/`: experimental claim identification and evaluation only; reuses the verifier dependency lock. Set `PYTHONPATH=services/claim_analysis` and run Python `-m pytest -c services/claim_analysis/pytest.ini services/claim_analysis/tests -q`. Paid calls require explicit `EPOCHGUARD_ALLOW_MODEL_CALLS=1`, model/key/rates and a bounded request budget. Never describe fake-adapter output as model quality or pending annotations as human reviewed.
- `cmd/provider-fixture/`: controlled upstream provider test double.
- `tests/smoke/`: gateway end-to-end acceptance tests.
- `tests/verification/`, `compose.verify.yaml`: real gateway/service qualification with deterministic evidence fixtures.
- `tests/multiclaim/`, `compose.verify.004c.yaml`: real Go/gateway multi-claim enforcement with deterministic evidence and private negative controls.
- `tests/protectedingress/`, `compose.verify.004d.yaml`: protected client/operator tests, receipt attacks, runtime disable and real restart/lifecycle qualification.
- `tests/livequalification/`, `compose.verify.004e{,.offline}.yaml`, `dev/live/`: bounded host qualification, private gateway configs and separate real-source/simulated deployments. `services/verifier/tests_live/runner.py` submits client cases through ingress; `verifier/multiclaim/deployment.py` owns live retrieval and safe private observations.
- `tests/cachelifecycle/`, `cmd/cache-store-proxy/`: isolated real cache qualification and deterministic Redis write scheduling.
- `tests/routesurface/`, `tests/routeobserver/`, `cmd/route-provider-fixture/`, `compose.routes.yaml`: isolated raw HTTP route qualification, native hook observation and synthetic provider controls.
- `dev/`, `compose.yaml`: pinned gateway build and development deployment.
- `docs/`: upstream findings, executed test evidence, design decisions, and later product specifications.

Commit message examples: `test(gateway): cover missing HTTP response`, `docs: record gateway integration decisions`, `feat(gateway): enforce buffered response decisions`.
