# Task 004C: controlled multi-claim gateway qualification

Executed November 14, 2026 (Asia/Calcutta), starting from clean `main` at
`0551c25`. The isolated experimental native gateway path is implemented and
qualified offline. No commit, push, live Tavily/PyPI/Gemini call or public
deployment was made. The existing `003a.v1` deployment remains the default.

## Design and inspected boundaries

The requirement is to enforce 004B results through the real pinned Bifrost
plugin while independently checking coverage, bindings, evidence consistency
and aggregation in Go. Python's top-level SUPPORTED or COMPLETE cannot authorize
an answer by themselves. One supported claim cannot authorize unchecked content.

Inspection covered AGENTS, README, architecture, the integration spike,
003A/B/C, 004A/hardening and 004B notes; plugin hooks, configuration, diagnostics,
HTTP client/parser/validator and tests; the entire 004B implementation; FastAPI,
dependency/image boundaries; provider fixture; Compose configurations and
smoke/verification/long/route tests. Pinned exported upstream files under
`artifacts/003c/upstream/` were read, including core `schemas/plugin.go`,
`schemas/chatcompletions.go`, `schemas/bifrost.go`, `core/bifrost.go` and the
framework native wrapper. They are from the cached module/build graph, not
current upstream HEAD: transport commit `e869c3f9adc96ea53c38694a21bb04a8e1085487`,
core v1.14.1 and matching host/plugin manifests, Go 1.27.3 Linux/amd64.

No hook, Bifrost core or ABI is invented or changed. `PostLLMHook` still calls
the existing synchronous `enforce()`. Native typed errors with
`AllowFallbacks=false` discard the answer and stop fallback. Genuine provider
errors retain identity and their original fallback behavior.

```text
Client -> buffered Bifrost -> existing fixture provider (verbatim candidate)
  -> EpochGuard PostLLMHook -> explicitly configured 004b.v1 DecisionSource
  -> nonce + full candidate + UTF-8 SHA-256 -> /v1/verify/multiclaim
  -> existing Pipeline.verify -> exact grammar -> two fixed fixture policies
  -> typed 004b.v1 result -> independent Go wire/coverage/evidence/aggregation
  -> original response (200) OR nil response + terminal 403/503
```

## Files and reuse

Existing files changed:

| File | Change |
| --- | --- |
| `plugins/epochguard/http_decision.go` | Optional trusted mode discriminator; factor original response-shape checks into shared `bufferedCandidate`, retaining 003A's exact text parser and 512-byte bound |
| `plugins/epochguard/decision.go` | Explicit source selection; unchanged `enforce`, provider errors, terminal refusal and server no-store behavior |
| `cmd/provider-fixture/main.go` | Default-off `-qualification-004c` controls for empty/multiple/partial/tool/block/metadata provider responses; existing echo/claim behavior preserved |
| `dev/Dockerfile` | Include shared conformance fixtures before plugin tests; compile/copy the new native gateway qualification runner |
| `README.md`, `docs/architecture.md`, `services/verifier/README.md` | Current boundary, isolated commands, independent validation and limitations |

New files:

- `plugins/epochguard/multiclaim.go`, `multiclaim_test.go`: independent grammar,
  complete strict wire parser, validator, HTTP source and focused tests.
- `services/verifier/verifier/multiclaim/app.py`: experimental endpoint factory,
  body/disconnect boundary, pipeline reuse and validated result serialization.
- `services/verifier/Dockerfile.004c`: separate root-context experimental image.
- `services/verifier/tests_gateway/{conftest.py,test_endpoint.py,fault_relay.py}`:
  offline endpoint/conformance tests and isolated test-only corruption relay.
- `tests/conformance/004b-{grammar,A,B,C}.json`: frozen positive/negative grammar
  vectors and Python result records read by both implementations.
- `tests/multiclaim/gateway_test.go`: real HTTP/native-plugin acceptance runner.
- `compose.verify.004c.yaml` and
  `dev/bifrost/multiclaim/{gateway,gateway-faults,gateway-control}.json`:
  isolated fixtures, protected gateways and explicit unsafe no-plugin control.
- This report.

The 003A Python app/policy/contracts/retrieval/settings/tests, original verifier
Dockerfile and every pre-existing Compose/profile/configuration remain
unchanged. 004A source/schemas/data/reports, the 004B contracts/policies/pipeline
and prior qualification notes are unchanged. No dependency is added.

## Python endpoint and packaging

`app.create_app(pipeline)` composes `/v1/verify/multiclaim` alongside the original
app without modifying `/v1/verify`. It parses JSON through the existing strict
duplicate-key/nonfinite checker and `004b.v1` Request. Unknown fields and modes,
malformed JSON, wrong types and unsupported encodings/content types are refused
with sanitized errors. A hash mismatch returns the pipeline's insufficient
record without retrieval. The endpoint neither selects policies from input nor
invokes a model.

Body receipt has a two-second/64 KiB boundary, including chunked requests. A
disconnect watcher cancels application work and is itself cancelled/joined on
completion or external cancellation. Pipeline's existing admission counter,
maximum four active requests, sequential maximum eight claims, five-second work
deadline and four-second retrieval ceiling are reused. There is no waiter queue,
retry, cache, background verification or retained request state. The packaged
Uvicorn server also bounds concurrent connections/tasks to 32. Built-in source
objects are owned by the shared per-process Pipeline; its calls retain only
request-local records. Validation and serialization complete before response
bytes are sent; results over 256 KiB fail closed. Runtime failures log fixed
allowlisted metadata, never raw exceptions, candidate or evidence bodies.

The original build context cannot copy sibling `services/claim_analysis`, which
004B imports. `Dockerfile.004c` therefore uses the repository root, the same
pinned Python base/dependency lock, and selective COPY instructions for both
packages, tests and conformance fixtures. It runs the 149 existing 004B tests plus
19 new endpoint/conformance cases during build. It copies no credentials,
annotation reports, artifacts or datasets. The original narrow image still
builds from `services/verifier` and runs its original tests.

The packaged `fixture_app` requires `EPOCHGUARD_TEST_MODE=1` and an explicit
allowlisted `EPOCHGUARD_004C_FIXTURE_CASE` (A/C/E/F). It injects 004B's existing
deterministic fixture retrievers. It does not read live API keys or implicitly
select live sources. Future live use requires explicit trusted application
construction with fixed retrievers; no such deployment is qualified here.

## Exact Go validation guarantees

Trusted `verifier.mode` selects the source: omitted or `003a.v1` retains the old
path; `004b.v1` requires the exact `/v1/verify/multiclaim` endpoint and an explicit
`fixture` or `live` evidence mode. Fixture configuration also requires existing
`test_only: true`. Mixed fixed-decision settings, unknown modes, wrong endpoints,
wrong mode names or invalid timeouts reject configuration and clear prior active
policy. A request cannot change mode, source, endpoint or budget. There is no
request-time fallback from 004B to 003A or fixed decisions.

Eligibility reuses the original pinned plain buffered assistant-message checks:
one terminal chat choice, no tools/reasoning/extensions/content blocks,
stream/partial choice, citations/search/videos or unsupported response shape.
004B additionally refuses mixed response-union variants, provider filter/extra
metadata, diagnostics and stop annotations requiring another policy. Its text
limit is 8,192 Unicode code points and 32,768 UTF-8 bytes, with valid UTF-8 and
004A-compatible control-character restrictions. 003A retains its exact original
candidate language and bound. A gateway case with 8,192 characters proves the
new mode does not accidentally inherit the 512-byte limit.

The new parser is separate from the unchanged canonical 003A parser. Before
typed decoding it walks the declared typed shape and requires every canonical
field at every level, even booleans whose zero value could hide omission. It
rejects exact/escaped duplicate keys, case aliases, unknown fields, null scalar
or array substitutions, wrong container/scalar types, trailing JSON, excessive
nesting (depth eight), arrays over eight and strings over 8,192 code points.
Evidence and annotation arrays have their additional semantic bounds. HTTP must
be 200 JSON; the entire result is at most 256 KiB. The shared client disables
redirects/proxies, limits connections to 16, bounds total duration and propagates
the supplied context. Response bodies close on every outcome. Random 128-bit
nonces and SHA-256 bind this synchronous call to its complete candidate.

Go independently scans every character of the full candidate. The grammar is
identical to 004B's fixed Python Windows and requests PyPI templates, ASCII
space/tab/CR/LF around/between sentences, canonical numeric versions and maximum
eight unique assertions. Repetition, Markdown, extra clauses/assertions,
instructions and Unicode lookalikes are refused. Go explicitly converts byte
positions to Python Unicode code-point offsets; accepted templates/whitespace
are ASCII, while unrecognized Unicode fails coverage. Nineteen shared vectors
and three Python records guard cross-language drift.

For complete coverage, Go derives ordered IDs, source text, spans, policy,
version and whole-candidate digest itself. Coverage-required IDs and the full
canonical extraction must agree. Binding must be VALID; extraction must be
TRUSTED_GRAMMAR or VALIDATED. Optional extraction annotations are bounded and
schema-checked but cannot select policy or waive an assertion. Every reported
claim must match a derived claim exactly and appear once in increasing order.

For each evidence-bearing claim, Go checks the fixed policy URL, configured
mode (`fixture`, or policy-specific `tavily_live`/`pypi_live` in future live
configuration), ID/digest formats, evidence-ID consistency, canonical observed
version, equal receipt/observation times, current-round-trip time window and
maximum age 60 seconds. Observation cannot follow check time; start/end clock
skew is bounded by two seconds. It validates the evidence-requirements flag and
derives the numeric comparison and exact reason/verdict: equal supports, older
contradicts, ahead is insufficient. No-evidence claims require INSUFFICIENT,
false evidence satisfaction and an allowlisted failure reason.

Go then recomputes aggregation. Only the complete nonempty required set with
every result supported can ALLOW. Valid independent contradiction takes
precedence over insufficient or absent neighboring results. Missing results
cannot be successful checks; invalid results invalidate the contract rather
than supplying contradiction precedence. Go/Python disagreement is contract
failure/503. Unknown grammar is accepted only as the matching early insufficient
coverage refusal, never as authorization.

These checks establish consistency within a configured trusted-verifier
boundary. They cannot prove the remote source was consulted, authenticate a
compromised verifier, or make a digest/timestamp into a signed attestation.

## Isolated deployment and observed gateway results

`compose.verify.004c.yaml` uses the real native image/plugin, existing controlled
provider, four statically configured fixture verifier instances, a test-only
fault relay, two protected gateways and a no-plugin gateway. Network inspection
returned `internal: true`; gateway port bindings were `{}`. There are no public
ports, real API keys, built-in semantic cache or fixed-ALLOW source on protected
gateways. Gateway databases live under per-container tmpfs `/tmp` and cannot
survive restart; the loaded-plugin/order/cache checks are performed at runtime.

The relay only forwards to an allowlist of fixture verifier services. A separate
runner control endpoint selects fault/fixture target; inference headers, prompt
and candidate do not. Normal records come from the actual endpoint/pipeline
before test corruption. HTTP-failure/malformed/oversize controls intentionally
return no valid record. The relay and no-plugin control are test infrastructure,
not production deployment patterns or additional verification microservices.

| Gateway scenario | Actual outcome |
| --- | --- |
| A: two matching independent claims | HTTP 200; candidate unchanged; provider delta 1 |
| B: matching Python, older requests claim | Terminal 403; no answer leak; provider delta 1 |
| C: requests evidence unavailable | Terminal 503; no answer leak; provider delta 1 |
| D: hidden third factual assertion | Terminal 503; no answer leak; provider delta 1 |
| E: evidence instructions to bypass policy | Older requests claim remains terminal 403; no leak; provider delta 1 |
| F: wrong evidence source identity | Terminal 503; no leak; provider delta 1 |

The final runner passed **seven top-level tests / 42 subtests**. It also checks:

- 23 bad-contract/transport modes: missing/duplicate/reordered claim results,
  forged SUPPORTED, inconsistent observed version, hash/nonce mismatch, stale
  observation, case alias, escaped nested duplicate, unknown policy, failed
  extraction/binding, incorrect required set, wrong evidence mode/ID, wrong
  contract for the configured mode, HTTP 500, malformed JSON, timeout, missing
  required flag, null flag and oversized response. All yield terminal 503.
- A valid contradiction with the supported neighbor removed still gives 403,
  proving cross-language aggregation precedence without permitting incomplete
  support. Ahead versions, repetition, Unicode content and over-limit responses
  refuse; a maximal-length eligible candidate is released unchanged.
- Empty/multiple/partial/tool/block/metadata provider controls all produce 503.
  Unsupported completion route and streaming refuse before dispatch/SSE.
- Genuine provider errors remain 400 and can use a valid fallback. A subsequent
  rejected fallback candidate stops the chain (two provider calls total).
- Eight concurrent delayed verifications return correctly after the delay with
  exactly eight provider calls. Go's trusted 1.5-second relay deadline refuses a
  four-second stalled verifier despite forged timeout/mode/bypass headers.
- Direct endpoint records contain both expected policies, exact authority URLs
  and fixture modes. Runtime management checks require the native plugin active
  at pre_builtin/order zero and semantic cache absent.
- The missing-plugin negative control returns unchecked content with HTTP 200.
  A healthy gateway is not inherently protected without the plugin.

Security-to-test mapping: Go `TestMultiGrammarConformance` and
`TestMultiRecordConformance` cover independent coverage/contracts and precedence;
`TestMultiTamperingFailsEnforcement` and `TestMultiCanonicalJSON` cover semantic
and wire corruption; HTTP/bounds/configuration/mixed-union tests cover the source
boundary. Python's endpoint tests cover strict inputs, schema/hash/mode refusal,
chunked and stalled body bounds, startup configuration, conformance and disconnect
cleanup. The existing 149 004B tests retain policy, extraction, aggregation,
deadline, concurrency and safe-diagnostic coverage. The real gateway tests above
exercise actual typed enforcement, terminal fallback and no-answer checks.

## Reproduction and executed validation

From repository root, with Docker Desktop running:

```powershell
docker buildx build --builder epochguard-002a --progress plain --load -t epochguard-dev:002a -f dev/Dockerfile .
docker buildx build --builder epochguard-002a --progress plain --load -t epochguard-verifier:004c -f services/verifier/Dockerfile.004c .
docker compose -f compose.verify.004c.yaml config --quiet
docker compose -f compose.verify.004c.yaml up -d --force-recreate --wait --no-build gateway gateway-faults gateway-control
docker compose -f compose.verify.004c.yaml run --rm --no-deps qualification
docker compose -f compose.verify.004c.yaml down --volumes --remove-orphans
```

Exact Python and regression commands executed:

```powershell
$env:PYTHONPATH = 'services/verifier'
& .venv-003a/Scripts/python.exe -m pytest -c services/verifier/pytest.ini services/verifier/tests -q
$env:PYTHONPATH = 'services/claim_analysis'
& .venv-003a/Scripts/python.exe -m pytest -c services/claim_analysis/pytest.ini services/claim_analysis/tests -q
$env:PYTHONPATH = 'services/verifier;services/claim_analysis'
& .venv-003a/Scripts/python.exe -m pytest -c services/verifier/pytest.ini services/verifier/tests_multiclaim services/verifier/tests_gateway -q

docker buildx build --builder epochguard-002a --progress plain --target qualification-unit --no-cache-filter qualification-unit -f artifacts/004c/Dockerfile.unit .
docker buildx build --builder epochguard-002a --progress plain --load -t epochguard-verifier:003a -f services/verifier/Dockerfile services/verifier
docker compose --profile test up -d --force-recreate --wait provider gateway gateway-control gateway-reject gateway-unavailable
docker compose --profile test run --rm --no-deps smoke
docker compose --profile test down --remove-orphans
docker compose -f compose.verify.yaml run --rm verification-tests
docker compose -f compose.verify.yaml down --remove-orphans
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml up -d --wait gateway-supported
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml run --rm --no-deps verification-tests
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml down --remove-orphans
docker compose -f compose.routes.yaml up -d --wait reject control warp-control warp-reject nolog
docker compose -f compose.routes.yaml run --rm --no-deps route-tests
docker compose -f compose.routes.yaml down --volumes --remove-orphans
git diff --check
```

The ignored qualification Dockerfile is the final `dev/Dockerfile` followed by
`FROM build AS qualification-unit`, module download/verification, and a fresh
network-disabled, cache-mounted RUN of `test -z "$(gofmt -l .)" && go vet
-mod=readonly ./... && go test -count=1 -mod=readonly -trimpath -v ./... && go test
-count=1 -race -p=2 -mod=readonly -trimpath ./...` in the plugin directory.
`artifacts/004c/prepare_unit.py` constructs it. This avoids a host Go dependency
and uses the actual pinned module graph. The regular image independently builds
the real gateway and `.so` together and checks their matching manifests.

| Check | Actual final result |
| --- | --- |
| Fresh Go unit tests | 29 top-level / 97 subtests passed; 0.206s |
| Fresh Go race detector | Passed, 1.319s; no race report; plugin units only |
| Go formatting/vet | Passed in the fresh qualification stage |
| Native image | Built; existing build unit/race checks also passed |
| Existing verifier suite, Windows | 65 passed, one live test explicitly deselected; 5.38s; existing Starlette warning |
| Original-context verifier image | Built; 65 passed, one live deselected during Linux build; 4.98s |
| Existing 004A suite, Windows | 176 passed; 2.56s |
| Existing 004B + new endpoint suite, Windows | 168 passed (149 + 19); 3.57s |
| Final experimental image's Linux tests | 168 passed; 4.08s |
| Final real 004C gateway suite | 7 top-level / 42 subtests passed |
| Existing smoke | 10 top-level / 35 subtests passed |
| Existing 003A real gateway/service | 8 top-level / 31 subtests passed |
| Existing separate long profile | Passed in 12.58s; HTTP 200, first byte 12,554ms / total 12,565ms; provider/retrieval deltas 1/1 |
| Existing 003C routes | 4 top-level / 54 subtests passed |

The short gateway runner explicitly skips live qualification and its separately
selected long test; the latter was executed separately. Python's live marker
remains explicitly deselected. No live qualification or cache-lifecycle rerun is
claimed. Logs/build failures/intermediate runs are preserved locally under
ignored `artifacts/004c/`. No failed live assertions were retried or weakened.

Docker Desktop was initially stopped; the initial inspection failed until the
existing Desktop environment was started. The first experimental image test
failed (165 passed / one failed) because fixture lookup assumed a deeper source
path. Lookup now searches actual parent directories and works in both packaging
layouts; the corrected image passed. An initial Compose attempt consequently
also failed to build that image. Neither failure involved an enforcement bypass.
An initial successful gateway run was followed by final checks after adding the
mixed-union guard and explicit contradiction-precedence case. No native gateway
assertion failed, and no mock plugin loader was substituted.

Runtime image identity matched the final local native image:
`sha256:dc6ddc4dcca46a485420516a3ede53194a3e9b6d563b72d9a4988f90699aec92`.
Final experimental Python image:
`sha256:50c651efb13bace47dea8610cd03cfb9e2d3b3e51a6472da85a7af688abd6408`.
These are local tested artifacts, not published releases. All task-owned stacks
were removed after execution; the pre-existing builder remains available.

Final scope checks found seven modified and seventeen new paths. All protected
pre-existing Python implementation/contracts/tests, schemas/data/reports and
Compose profiles stayed unchanged. The original Go 003A semantic validator and
canonical parser, and the typed refusal/enforcement functions, matched their
starting contents exactly. Python syntax, JSON syntax, trailing whitespace,
final newlines, Markdown fences, 56 local documentation links/anchors and
`git diff --check` passed. These checks and exact test-count extraction were run
with `& .venv-003a/Scripts/python.exe artifacts/004c/final_check.py`. Final Docker
inspection showed only the pre-existing BuildKit builder still running.

## Compatibility and unqualified paths

The default and verification 003A Compose files/configs, Python endpoint and
contract remain unchanged. Go's original candidate parser, canonical JSON
parser and verdict validator remain authoritative for that mode. Shared response
eligibility preserves its original checks, proven by all existing regressions.
The plugin still preserves genuine provider-error identity, waits synchronously,
uses typed terminal refusal, rejects streaming, suppresses server cache writes
and keeps caching disabled in the qualified deployments.

This qualifies only exact-template buffered chat with synthetic evidence and a
controlled provider. General prose/semantic coverage, live multi-claim evidence,
real provider compatibility, origin freshness, signed/authenticated verifier
records, tenant isolation, production authentication, external readiness gating,
protected caching/revocation and safe streaming remain unimplemented or
unqualified. Existing API/background/Warp/alternate-transport limitations from
003C remain; this is not an all-route firewall. Go cannot authenticate an
untrusted verifier or prove source retrieval from metadata. Browser-to-core
cancellation propagation is not newly qualified; supplied Go contexts and the
Python endpoint's disconnect behavior are bounded/tested separately.

Recommended conventional commit, not created:
`feat(gateway): qualify experimental multi-claim verification`.

Stop at Task 004C for maintainer review. No commit or push.
