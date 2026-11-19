# Evaluation and qualification evidence

This is the canonical index of implemented and measured scope. [Architecture](architecture.md) defines behavior; historical reports retain execution-time results. Tests and observations below are not a benchmark of general factual accuracy, production readiness or commercial models.

## Evidence provenance

| Category | Revision and source mode | Observation and limits |
| --- | --- | --- |
| [005B compatibility and packaging](task-005b.md) | Baseline `f7a7cd6f7a386b9079e34e666920ca1296f0a36f` plus uncommitted 005B changes; simulated/offline | Dated local commands and cold-input installation evidence; hosted execution was pending at report time, with subsequent baseline checks recorded below |
| [Hosted baseline Actions](https://github.com/aditya6927/epochguard/actions/runs/43752637258) | Commit `5bf1a0b81b1abf9afb7e4519990342c496aadc7b`; check-run metadata inspected during 005C | Python, Go, documentation and frontend checks completed successfully. This is subsequent baseline evidence, not hosted execution of uncommitted 005C changes or native gateway qualification |
| [005A Lab](task-005a.md) | Implementation baseline `34ec0756dbf979955d2a351985eac97a39783be8`, subsequently committed in the 005B baseline; fixture provider and simulated transports | Actual gateway behind ingress, editable candidates, fault/overload/recovery and desktop/mobile presentation; no live/model calls |
| [004G-L reviewed live run](task-004gl.md#reviewed-live-qualification--november-15-2026) | `34ec0756dbf979955d2a351985eac97a39783be8`, November 15, 2026; `tavily_live` / `pypi_live`, `004g.receipt.v2` | Operator-authorized run, subsequent sanitized-record inspection; five client expectations met. Original runner collected records requiring review; it did not declare final live approval |
| [004G-S security](task-004gs.md) and [004G](task-004g.md) | Security implementation baseline `05ac78939b0efa7dc4f66669b1c1e5bf48e8be23`; fixtures/simulated transports | Request substitution, metadata projection, receipt faults, policy outcomes, plugin disable/restart and overload; current reruns in 005B report |
| [004E reviewed live run](task-004e.md) | November 14, 2026 recorded revision/environment; `tavily_live` / `pypi_live`, explicitly legacy `004d.v1` | Two exact templates and controlled provider; later preflight/measurement/verifier report inspection found five expectations met; v2 request/metadata guarantees do not apply |
| [003B historical live run](task-003b.md) | November 8, 2026 maintainer-supplied run; legacy one-policy Tavily | Full gateway test reported 18.16 seconds, five subtests; earlier 401 failures preserved, their exact cause unproven |
| [003C route audit](task-003c.md) | Pinned gateway, offline providers | Finite route/passthrough/Warp checks; background work unqualified; prerequisite/router failures are not policy enforcement |
| [002C cache experiments](task-002c.md) | Isolated controlled Redis/gateway experiment | Unsafe ordering and pending-write controls; no qualified protected cache |
| [004A claim analysis](task-004a.md), [004F planning](task-004f.md) | Agent-authored draft annotations, fake/baseline adapters | Real-model quality pending. Planning never authorizes responses |
| [005C native model path and draft evaluation](task-005c.md) | Baseline `5bf1a0b81b1abf9afb7e4519990342c496aadc7b` plus 005C implementation; simulated provider/evidence | Native Gemini conversion and protected release controls; separate frozen 18-case draft comparison. Real-model gateway and analysis calls were pending at that report's revision |
| [005C-R refusal investigation](task-005c-r.md) | Baseline `4a45673d16946b466e77e975a95954efdd1d4d14`; preserved operator run with real Gemini and simulated evidence | Four provider HTTP 200 responses, four UNAVAILABLE refusals, zero recorded verifier pipeline requests. Connectivity and safe non-release only; exact response shape was not recorded. New diagnostics/fixtures remain non-authorizing |
| [005C-S signature contract audit](task-005c-s.md) | Baseline `0f5296ae9e7de2509d3781684a9e85e277b9439f`; November 18 live diagnostics and synthetic converter controls | The diagnostic run confirmed exact intended text with signatures and pre-verifier refusal. Actual pinned conversion collisions prevent a safe typed-only eligibility change; real-model ALLOW/REJECT qualification was not met at that audit |
| [005C-T pre-conversion adapter](task-005c-t.md) | Baseline `3cd8592c97ebd2725a551893fdbf5d49f5406a55`; simulated native HTTP and simulated evidence | Original implementation tested strict original-envelope validation/projection, actual pinned converter/native loader and existing Go/Python/v2/ingress. Real-model qualification was pending at implementation time; subsequent review follows |
| [005C-T reviewed real-model run](task-005c-t.md#reviewed-real-model-qualification--november-19-2026) | November 19, 2026; revision `87d877c43f3ab46d9d62d279e457f16b8df9c0c3`, run `20261119T092712Z-6d95a336`; real `gemini-3.5-flash-lite`, `strict-005ct`, simulated evidence | **Narrow real-model enforcement qualification met:** four completed HTTP 200 generations, four completed independent verifier records, all six expected protected outcomes; exact supported text released, contradiction and unsupported text withheld. Sanitized-record review, no repeated calls; collection-time pending fields preserved |

The separate [005D reporting evaluation](task-005d.md) at baseline `2b09cb68806493019cbd1680373f71fa42a44c80` uses 23 fixed synthetic cases, the existing grammar/evidence pipeline and the actual independent Go validator. It checks 100/0/null scores, source/time/binding failures, stable order and non-authorizing diagnostic mutations. This is offline reporting evaluation, not an additional real-model or real-source qualification. Historical November 15/19 observations can be inspected without rescoring missing provenance or retrieving current data.

The [005E combined harness](task-005e.md) adds a seven-batch offline wiring/fault qualification using simulated Gemini HTTP and fixture source transports. A separately opted-in live implementation is available, but no combined live result is collected or approved. The existing November 15 real-source and November 19 real-model reviews remain independent executions; the real-model/real-evidence row below remains unqualified.

The four qualification combinations are distinct:

| Provider | Evidence | Status |
| --- | --- | --- |
| Controlled | Simulated | Existing G/G-L/Lab; 005C adds native Gemini transport simulation |
| Controlled | Real | Narrow reviewed November 15 G-L source qualification; historical observations |
| Real model | Simulated | Narrow successful [November 19 strict-adapter qualification](task-005c-t.md#reviewed-real-model-qualification--november-19-2026), reviewed from sanitized records. Two November 18 refusals remain preserved; tightly controlled prompts, fixed policies and bounded grammar only |
| Real model | Real | Not executed or qualified; no automatic combined mode |

The November 15 real-source run used a controlled provider; the November 19 real-model run used simulated evidence. They are separate executions and do not establish real-model-plus-real-source qualification. Four generations do not establish statistical reliability or arbitrary language understanding.

005C uses the unchanged 004A/004F analysis pipeline. Its [review packet](../tests/modelqualification/data/README.md) was newly authored from required categories and frozen before model execution, without held-out tuning. All labels remain agent drafts. Metrics count failed analyses as misses and show denominator, failures, all omissions, dynamic recall, exact-span and classification scores; independent-audit metrics also show unaccounted risk, unsupported mappings, false completeness and abstentions. Gemini cells remain null until actual execution. Real inference alone would not establish general factual correctness, PS06 compliance or per-claim freshness scoring; 005D is separate.

Live observations are historical source labels, not statements of today's versions. Existing ignored local artifacts may not be available in a fresh clone; the reports explain provenance and actual commands. This task does not rerun or overwrite paid evidence. A summary record or hash is not independent reproduction of a remote call or independent HMAC revalidation when raw receipts were intentionally not retained.

## Metrics and acceptance

Client HTTP 200 means release only when the approved assistant content matches exactly and receipt/policy/evidence checks pass. HTTP 403 means tested policy contradiction. HTTP 503 can mean coverage, evidence, receipt or infrastructure refusal; those causes must not be inferred from status alone. A genuine provider 400 remains a provider error. No refusal is counted as verified factual content.

The G-L live A-E cases measure supported delivery, older contradiction, extra unsupported prose, missing plugin and genuine provider error. Recorded elapsed latency is host/client elapsed time for the protected request. First-body-chunk timing is not first model token latency or an internal stage trace. Source counts are attempted/completed application-level retrieval invocations, not independent billing events, origin fetches or freshness attestations. Each source recorded three attempted and three completed retrievals in that narrow successful run. Controlled provider counts measure fixture calls, not commercial inference cost.

Offline tests use deterministic fixture evidence or simulated HTTP transports and explicitly identify them. They exercise real native gateway/ingress deployment when the report says so; unit tests and UI component mocks have a different scope. Grammar fixtures shared across implementations can hide shared assumptions, so adversarial full-response, independent request substitution and metadata tests remain necessary. Finite corpus success is not proof that every Unicode, parser, concurrency or provider behavior is safe.

## Reproduction and CI scope

Use the [operations guide](operations.md) and [contribution checks](../CONTRIBUTING.md#validation). Lab installation needs only Docker/Git/Python; all ordinary suites are offline and source-free. G-L without `--live` is offline. Source/model live flags are never set by CI or the installation path.

The separate Actions jobs run pinned Go format/vet/unit/race/plugin compilation, locked Python verifier/claim-analysis tests, locked frontend TypeScript/build/components, and local Markdown/anchor/path/security checks. Dependency installation is online; tests in build stages use `--network=none`. Documentation validation does not contact external links or prove every technical statement. CI does not run native gateway loading, full protected lifecycle suites, paid calls or installed-browser tests. First hosted workflow execution remains pending until pushed by a maintainer; local equivalents and workflow lint results belong in [005B](task-005b.md).
