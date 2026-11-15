# Evaluation and qualification evidence

This is the canonical index of implemented and measured scope. [Architecture](architecture.md) defines behavior; historical reports retain execution-time results. Tests and observations below are not a benchmark of general factual accuracy, production readiness or commercial models.

## Evidence provenance

| Category | Revision and source mode | Observation and limits |
| --- | --- | --- |
| [005B compatibility and packaging](task-005b.md) | Baseline `f7a7cd6f7a386b9079e34e666920ca1296f0a36f` plus uncommitted 005B changes; simulated/offline | Current local commands and cold-input installation evidence; hosted Actions execution separately pending |
| [005A Lab](task-005a.md) | Implementation baseline `34ec0756dbf979955d2a351985eac97a39783be8`, subsequently committed in the 005B baseline; fixture provider and simulated transports | Actual gateway behind ingress, editable candidates, fault/overload/recovery and desktop/mobile presentation; no live/model calls |
| [004G-L reviewed live run](task-004gl.md#reviewed-live-qualification--november-15-2026) | `34ec0756dbf979955d2a351985eac97a39783be8`, November 15, 2026; `tavily_live` / `pypi_live`, `004g.receipt.v2` | Operator-authorized run, subsequent sanitized-record inspection; five client expectations met. Original runner collected records requiring review; it did not declare final live approval |
| [004G-S security](task-004gs.md) and [004G](task-004g.md) | Security implementation baseline `05ac78939b0efa7dc4f66669b1c1e5bf48e8be23`; fixtures/simulated transports | Request substitution, metadata projection, receipt faults, policy outcomes, plugin disable/restart and overload; current reruns in 005B report |
| [004E reviewed live run](task-004e.md) | November 14, 2026 recorded revision/environment; `tavily_live` / `pypi_live`, explicitly legacy `004d.v1` | Two exact templates and controlled provider; later preflight/measurement/verifier report inspection found five expectations met; v2 request/metadata guarantees do not apply |
| [003B historical live run](task-003b.md) | November 8, 2026 maintainer-supplied run; legacy one-policy Tavily | Full gateway test reported 18.16 seconds, five subtests; earlier 401 failures preserved, their exact cause unproven |
| [003C route audit](task-003c.md) | Pinned gateway, offline providers | Finite route/passthrough/Warp checks; background work unqualified; prerequisite/router failures are not policy enforcement |
| [002C cache experiments](task-002c.md) | Isolated controlled Redis/gateway experiment | Unsafe ordering and pending-write controls; no qualified protected cache |
| [004A claim analysis](task-004a.md), [004F planning](task-004f.md) | Agent-authored draft annotations, fake/baseline adapters | Real-model quality pending. Planning never authorizes responses |

Live observations are historical source labels, not statements of today's versions. Existing ignored local artifacts may not be available in a fresh clone; the reports explain provenance and actual commands. This task does not rerun or overwrite paid evidence. A summary record or hash is not independent reproduction of a remote call or independent HMAC revalidation when raw receipts were intentionally not retained.

## Metrics and acceptance

Client HTTP 200 means release only when the approved assistant content matches exactly and receipt/policy/evidence checks pass. HTTP 403 means tested policy contradiction. HTTP 503 can mean coverage, evidence, receipt or infrastructure refusal; those causes must not be inferred from status alone. A genuine provider 400 remains a provider error. No refusal is counted as verified factual content.

The G-L live A-E cases measure supported delivery, older contradiction, extra unsupported prose, missing plugin and genuine provider error. Recorded elapsed latency is host/client elapsed time for the protected request. First-body-chunk timing is not first model token latency or an internal stage trace. Source counts are attempted/completed application-level retrieval invocations, not independent billing events, origin fetches or freshness attestations. Each source recorded three attempted and three completed retrievals in that narrow successful run. Controlled provider counts measure fixture calls, not commercial inference cost.

Offline tests use deterministic fixture evidence or simulated HTTP transports and explicitly identify them. They exercise real native gateway/ingress deployment when the report says so; unit tests and UI component mocks have a different scope. Grammar fixtures shared across implementations can hide shared assumptions, so adversarial full-response, independent request substitution and metadata tests remain necessary. Finite corpus success is not proof that every Unicode, parser, concurrency or provider behavior is safe.

## Reproduction and CI scope

Use the [operations guide](operations.md) and [contribution checks](../CONTRIBUTING.md#validation). Lab installation needs only Docker/Git/Python; all ordinary suites are offline and source-free. G-L without `--live` is offline. Source/model live flags are never set by CI or the installation path.

The separate Actions jobs run pinned Go format/vet/unit/race/plugin compilation, locked Python verifier/claim-analysis tests, locked frontend TypeScript/build/components, and local Markdown/anchor/path/security checks. Dependency installation is online; tests in build stages use `--network=none`. Documentation validation does not contact external links or prove every technical statement. CI does not run native gateway loading, full protected lifecycle suites, paid calls or installed-browser tests. First hosted workflow execution remains pending until pushed by a maintainer; local equivalents and workflow lint results belong in [005B](task-005b.md).
