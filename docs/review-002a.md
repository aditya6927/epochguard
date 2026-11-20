# Task 002A reviewer notes

**Reviewed:** GitHub `aditya6927/epochguard`, commit `52c26167795288b9be4bd433788a55ad78308a9b`, on 2026-11-06.

**Method:** static source and test review. Docker and Go tests were *not* independently rerun by this reviewer. Runtime outcomes are described in `docs/task-002a.md` and remain evidence reported by the original development environment.

## Follow-up status

The original observations describe the reviewed revision, not current defects. This follow-up was reconciled on November 20, 2026 against `3e7041b90ceca589cf7e51c2071094cd1bf11608` and hosted check metadata. It does not rerun the original review's tests or imply these facilities existed at the reviewed commit.

| Original finding | Current disposition |
| --- | --- |
| Module declarations | **Resolved:** root and plugin manifests use `github.com/aditya6927/epochguard` and its plugin subpath |
| Nil HTTP response | **Resolved:** `HTTPTransportPostHook` explicitly checks `resp == nil` |
| Accidental ignore entry | **Resolved:** `.gitignore` no longer contains the stray `git ` line |
| Race/format checks and CI | **Implemented and hosted checks observed:** the [workflow](../.github/workflows/checks.yaml) runs pinned format/vet/unit/race/plugin compilation, Python, frontend and documentation jobs; all four jobs [succeeded November 20](https://github.com/aditya6927/epochguard/actions/runs/44689491455) at `3e7041b`. CI does not run the full native loading/lifecycle qualification |
| Missing-plugin startup | **Mitigated within protected ingress:** per-response authenticated release and readiness are implemented. Direct gateway deployments still retain this risk |
| Route/cache/fallback qualification | **Follow-up completed within finite scope:** [typed enforcement](task-002b.md), [cache hazards](task-002c.md) and [route audit](task-003c.md). Safe streaming and protected caching remain unimplemented |
| Licensing/release policy | **Project facilities present:** [Apache-2.0 LICENSE](../LICENSE), [security reporting policy](../SECURITY.md) and [contributor guide](../CONTRIBUTING.md) are tracked. [Third-party redistribution/notice clearance](third-party.md) remains separate; the security policy does not promise a private contact or response SLA |

See [architecture](architecture.md) for current boundaries and [operations](operations.md) for reproducible checks.

## Original correctness and maintainability observations

1. **Module declarations** (`go.mod`, `plugins/epochguard/go.mod`). Both used `github.com/epochguard/epochguard` rather than the published repository path `github.com/aditya6927/epochguard`. This compiled at the reviewed revision because nothing imports the root via its GitHub path, but it makes future dependency imports and downstream consumption confusing. Choose and align the canonical module path before growing the codebase.
2. **Nil-response robustness** (`plugins/epochguard/main.go`). `HTTPTransportPostHook` assumed `resp != nil`. The tested buffered route supplies a response, but explicit validation prevents a panic if a future transport/error path does not. An ordinary hook error is not a client refusal; this is only a defensive diagnostic fix.
3. **Accidental ignore entry** (`.gitignore`). The last `git ` line was not a useful repository ignore rule; remove it.
4. **Go race detector and CI**. The reviewed six-request smoke test checks behavioral isolation, not memory race freedom. Add `go test -race` for the relevant packages (with a compatible CGO toolchain), a formatting check, and CI when feasible. Record whether they ran.
5. **Deployment activation**. The negative control proves absent-plugin detection. It does *not* prevent Bifrost from serving traffic on missing-plugin startup. A future ready-to-serve control must enforce active status/order and a refusal probe before protected traffic is exposed.
6. **Route and cache qualification**. No caching/streaming/fallback safety claims are justified yet. The next milestone should exercise typed errors and no-leak assertions before implementing the verifier.
7. **Legal and documentation**. An explicit license, security policy, and contributor guide may be appropriate before an upstream-facing release. Bifrost upstream uses Apache-2.0; Apache-2.0 is a reasonable candidate for this project, but the maintainer must choose and add the actual license before promoting EpochGuard as open source. `AGENTS.md`, this review note, the architecture note and ADR-0001 are available in the review bundle.

## What is correctly scoped

- Bifrost v2.4.0 and the Go builder are pinned and checked for shared plugin compatibility.
- The HTTP/provider fixture is a test double, not a substitute for the actual Bifrost loader.
- Only one buffered route is qualified; source and docs do not represent a finished freshness system.
- Developer auth is deliberately simplified and published to the loopback-only fixture; no actual provider credentials are committed in the reviewed config.

## Original recommended test coverage

- `HTTPTransportPostHook` called with nil response: no panic; explicit diagnostic result.
- `go test -race` for the plugin and request-context tracing; verify actual execution rather than assuming safety from a mutex.
- Controlled `PostLLMHook` REJECT/UNAVAILABLE: safe error, zero provider sentinel bytes, and no unintended fallback.
- Unqualified `stream: true`: reject before any client-visible answer bytes.
- Missing or mismatched plugin: management health alone must not authorize protected traffic.
