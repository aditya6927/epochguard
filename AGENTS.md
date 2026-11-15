# EpochGuard coding-agent working agreement

Make changes that can be explained, tested, reproduced and reviewed. The canonical capability and security status is in [architecture](docs/architecture.md); executable workflows are in [operations](docs/operations.md). Historical task reports describe their tested revisions, not necessarily current behavior.

## Engineering invariants

1. Inspect the **actual pinned upstream source** before using or changing Bifrost contracts. Never invent hooks, flags, exported types or cache APIs. The native host and plugin must share the pinned Linux/amd64 toolchain and module graph.
2. Preserve true provider failures and request identity. Use demonstrated typed `BifrostError` / short-circuit mechanisms; ordinary Go hook errors do not reliably prevent release. Policy refusals must remain terminal without fallback; successful provider fallbacks must be verified.
3. A response is verified only after evidence passes an explicit policy. Diagnostic `X-EpochGuard-*` headers, valid JSON, hashes, HMACs and grammar coverage alone do not prove factual correctness or arbitrary semantic completeness.
4. Hold protected answers until all required checks finish. Missing/disabled plugins, malformed or mismatched records, incomplete coverage, unavailable evidence, cancellation and timeouts must not authorize delivery. Keep exact approved assistant content; follow the configured response-envelope contract.
5. Preserve protocol isolation: bounded-prose profiles require request-bound `004g.receipt.v2`; explicitly legacy D/E profiles retain `004d.v1`. Do not silently downgrade or claim legacy profiles inherited v2 guarantees. Readiness is source-free and does not establish source health.
6. Treat retrieved content, model output and provider metadata as untrusted. The 004F planner remains non-authorizing. No supported claim may authorize unaccounted neighboring content. Never label fixtures as live evidence or draft annotations as human-reviewed gold.
7. Keep built-in caching disabled in protected deployments. Cache post-hook ordering and asynchronous writes can bypass enforcement or repopulate deleted entries; deletion is not a write barrier. Isolate cache experiments and consult [ADR 0003](docs/decisions/0003-protected-cache-ownership.md).
8. Never embed credentials, private source text, raw receipts or secret-bearing diagnostics in tests, logs, examples or commits. The published setup token is local-development-only. Do not print resolved live Compose configuration.
9. Keep no-auth development gateways on loopback. Protected qualification profiles must retain private networks and no published gateway, verifier or management ports. Do not describe the plugin as an all-route firewall; streaming, background and alternate transports remain outside qualification.
10. Keep live/paid calls separately opted in, bounded and free of automatic retries. Offline fault/regression tests must remain network-disabled. Observation times are not origin-freshness attestations; application retrieval counts are not billing counts.
11. Scope changes to the requested milestone. No production-readiness claim, new policy, cache or authentication redesign follows implicitly from a local test pass. Do not overwrite unrelated work.
12. Record actual commands and outcomes. Never claim a check passed unless that exact command ran; distinguish source inspection, mock transport tests, real gateway execution and independently reviewed evidence.

## Contributor workflow

1. Inspect git status, HEAD and applicable instructions before editing. Read README, architecture, the [integration spike](docs/bifrost-integration-spike.md) and relevant task report. Reconcile concurrent changes or use an isolated worktree.
2. State the requirement, minimal design and correctness invariants. Verify upstream contracts and ownership/lifetimes before implementation.
3. Implement a small coherent change with meaningful tests and negative controls. Never substitute a mocked plugin loader for the real gateway suite.
4. Run appropriate checks from [operations](docs/operations.md). Native image builds run Go format/vet/unit/race checks; race detection covers unit execution, not the actual gateway process. Python and gateway evidence are separate checks.
5. Explain changes, error handling, trade-offs, actual results and unrun checks. Update canonical architecture/decision documentation for material design changes; preserve historical evidence and provenance.
6. Stop at the requested milestone for maintainer inspection. Do not automatically commit or push.

## Documentation rules

Public documentation contains factual architecture, usage, testing, compatibility and security information. Do **not** copy recommended commit messages, stop-for-review messages, working-tree status or agent sign-offs into public Markdown reports. If a commit recommendation is requested, put it in the final agent response only. Preserve significant failed experiments, fixture/live distinctions, measurement methodology and tested revisions.

## Source ownership

| Area | Owner paths |
| --- | --- |
| Native enforcement and signing | `plugins/epochguard/` |
| Buffered protected release | `internal/ingress/`, `cmd/protected-ingress/` |
| Evidence APIs and bounded grammar | `services/verifier/verifier/`, including `multiclaim/` and `bounded_prose/` |
| Non-authorizing analysis | `services/claim_analysis/`, `services/verifier/verifier/prose/` |
| Real gateway qualification | `tests/boundedprose/`, `tests/protectedingress/`, `tests/livequalification/`, `tests/multiclaim/`, `tests/verification/`, `tests/smoke/` |
| Isolated route/cache experiments | `tests/routesurface/`, `tests/routeobserver/`, `tests/cachelifecycle/`, corresponding `cmd/` fixtures |
| Build and deployment | `dev/`, `compose*.yaml`, `services/verifier/Dockerfile*` |
| Draft data and measurements | Component `data/` and `reports/`; follow their review/split rules before editing |

Qualification outputs belong in ignored `artifacts/`. Keep credential files out of the repository. Follow each profile's cleanup procedure, including signing-key volumes.
