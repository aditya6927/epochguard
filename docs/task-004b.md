# Task 004B: evidence-backed multi-claim verification

Implemented and checked November 12–13, 2026 (Asia/Calcutta), starting from clean
`main` at `9747ab6`. No commit or push was made. This is an executable,
non-authorizing experiment; the existing qualified gateway remains `003a.v1`.
No live model, Tavily evidence, or PyPI evidence call was made for this task.

## Requirement and minimal design

One verified claim must never authorize a response containing unverified
neighboring claims. The new `004b.v1` API requires independently established
whole-response coverage and deterministic evidence checks for every required
assertion. It introduces no service, gateway integration or cache behavior.

Inspection covered AGENTS, README, the integration spike, architecture,
003A/B/C and 004A/hardening notes, existing verifier contracts/policy/retrieval/
settings/tests, 004A schema/model/alignment/baseline/evaluation/Gemini code,
Go HTTP client/decision validation and the Docker/Compose regression setup.
The working tree was clean and HEAD matched the requested starting commit.

Reused unchanged:

- `verifier.policy.verify`, its Python claim/primary-label parsers and reasons;
  `verifier.retrieval` Page, Tavily client and strict duplicate-key utility.
- `claim_analysis.schema` input bounds, canonical Claim/Extraction and exact
  binding; the existing ModelExtractor and identification alignment when opted in.
- The existing dependency lock, local Python environment, pinned native gateway
  build and real smoke/verification runners. No Bifrost API or hook is changed.

New boundaries under `services/verifier/verifier/multiclaim/`:

| File | Responsibility |
| --- | --- |
| `contract.py` | Strict requests, source-bound claims, evidence references, results and consistency validation |
| `coverage.py` | Complete-response grammar and fixed policy registry; rejects any unaccounted content |
| `retrieval.py` | Fixed-package, size/deadline-bounded PyPI HTTP retrieval |
| `policies.py` | Evidence identity/mode/size validation, unchanged Python policy adapter, PyPI parsing/comparison |
| `pipeline.py` | Optional extraction validation, resource ownership, claim work and pure aggregation |
| `demo.py`, `__main__.py` | Six real-code fixture scenarios and bounded offline request-file CLI |
| `live.py` | Explicitly opted-in, single-request source observation probes |
| `__init__.py` | Experimental package boundary; no qualified-route import |

New tests are `services/verifier/tests_multiclaim/{conftest,test_pipeline,
test_resources,test_cli}.py`, outside the qualified verifier's test directory.
This keeps its existing Docker context/tests independent of the optional 004A
import path. Documentation changes are this report, the new component
`services/verifier/README.md`, and small README/architecture boundary updates.
Existing Go, verifier, analyzer, schemas, datasets, evaluation reports,
dependencies, Dockerfiles and Compose configurations are unchanged.

## Data flow and contract

```text
Original candidate + trusted caller request ID + exact UTF-8 SHA-256
  -> strict bounded input
  -> independent full-response grammar and source-order claim IDs
  -> trusted canonical 004A extraction OR optional 004A extraction
       -> schema validation -> exact binding -> grammar agreement
  -> trusted policy dispatch
  -> independent source observations (sequential, bounded, no retries)
  -> deterministic claim comparisons and evidence references
  -> pure whole-response aggregation
  -> 004b.v1 record (no gateway action)
```

The grammar runs before optional model work, allowing an early fail-closed
response for unsupported content without a paid extraction. This intentionally
changes the order of the conceptual pipeline to avoid unnecessary model calls;
the grammar independently supplies the complete required set. All required spans
are still bound and compared against any supplied extraction before retrieval.

`Request` carries fixed schema `004b.v1`, fixed bundle policy
`multi-claim-templates-v1`, trusted caller `request_id`, full `candidate`, its
SHA-256 and optional canonical `004a.v1` extraction. A mismatched hash returns
INSUFFICIENT before retrieval. A JSON/input-schema failure is rejected rather
than producing a successful verification record. Unknown fields/enums and
noncanonical identifiers are rejected. Request-file JSON also rejects duplicate
keys/nonfinite constants before model validation.

Each `BoundClaim` retains the canonical original source span, complete response
digest, fixed policy ID and parsed version. Each `ClaimResult` carries verdict,
fixed reason, `evidence_requirements_satisfied`, and at most one evidence
reference. Metadata records evidence ID, fixed URL, retrieval mode/ID, content
digest, observed version and timezone-aware receipt/observation times. Evidence
IDs hash source/mode/retrieval ID/content digest; they are identifiers, not
signatures. No raw evidence body enters this result contract.

`Result` retains full candidate/hash/ID/policy, extraction status, binding status,
validated extraction where available, separate coverage status/reason/required
IDs, bounded claim results, whole verdict and trusted `checked_at`. Its validator
rechecks complete grammar coverage, result bindings/comparison consistency and
aggregation. Schemas are available through Pydantic `model_json_schema()`;
neither old contract/schema artifact is changed.

The API trusts application ownership of request identity, retrievers, policy
configuration and clock. The offline CLI's supplied ID is not authenticated.
There is no network authorization consumer for this wire record. Hashes and
times alone do not prove authenticity, and a forged record from a compromised
trusted verifier remains outside this security boundary.

## Exact supported claims and evidence sources

| Policy | Exact assertion | Evidence |
| --- | --- | --- |
| `python-windows-latest-v1` | `The latest stable Python 3 release for Windows listed on Python.org is 3.X.Y.` | Existing fixed Tavily Extract of `https://www.python.org/downloads/windows/` and its unique primary label/context |
| `pypi-requests-reported-v1` | `The version reported for requests by the PyPI JSON API is X.Y.Z.` | GET only `https://pypi.org/pypi/requests/json`; `info.name`, `info.version`, boolean `info.yanked` |

Python's allowed version range and full comparison behavior are reused without
alteration. PyPI permits exactly three canonical numeric components, each 0..999,
with no leading zeros. Unsupported PEP 440 forms fail closed rather than being
normalized. Package `requests`, endpoint and policy IDs are fixed in code.

The [official PyPI JSON API documentation](https://docs.pypi.org/api/json/)
was consulted for the project metadata endpoint and its version/name/yanked
fields. Validation uses this required projection of the real envelope; other
metadata is untrusted and ignored. It does not follow body links or rely on the
deprecated releases map. Missing/wrong project identity, missing or non-boolean
yanked status, a yanked observation, malformed version/JSON or duplicate keys is
insufficient. No LLM parses evidence or supplies a factual verdict.

Both policies require the exact source identity and expected fixture/live mode,
bounded valid structure and a local observation age of -2..60 seconds. The
original Python headings/context/unique-label requirements remain intact. Equal
versions produce SUPPORTED; a numerically older candidate is CONTRADICTED; an
ahead-of-source candidate is INSUFFICIENT because the observation may lag. For
the ahead case evidence acquisition requirements are satisfied, but the evidence
does not establish the claim. Failure results have no evidence reference.

These are source observations under explicit policies, not general truth,
publication-age, package security or installation guarantees. Separate claims
may be observed at different times; there is no simultaneous source snapshot.
Fixture versions `3.88.7`/`2.88.7` are synthetic and remain fixture mode.

## Coverage and aggregation

The complete-response grammar supports one to eight exact plain-text templates
with ASCII space/tab/CR/LF around and between sentences. Internal wording,
punctuation and spacing are exact; no normalization occurs. Each full sentence
gets an ordered `c001`.. ID and original code-point offsets. Repeated identical
sentences are refused; different asserted versions remain separate claims.

Unrecognized content, including an extra clause or sentence, instructions,
opinions, Markdown/lists, quoted wrappers, Unicode lookalikes and unsupported
claim types, returns UNCERTAIN coverage and no evidence work. This does not solve
semantic coverage for unrestricted prose. Early refusal can leave extraction and
binding NOT_RUN; the record does not claim those checks passed.

Optional 004A extraction must pass its original schema and exact source binding,
then match the entire ordered trusted set with full spans and
FACTUAL/DYNAMIC/REQUIRED labels. A valid extraction that omits a claim or labels
one NON_FACTUAL conflicts with coverage. Normalized propositions and other
untrusted annotations never choose policy or waive evidence. An explicitly
invoked extractor must return a valid extraction; failure/None never switches to
the grammar-only success path. A model is not required for the trustworthy
template-only path and cannot independently authorize a response.

The pure `aggregate(required, results, coverage, checked_at)` function enforces:

| Condition | Result |
| --- | --- |
| Failed/uncertain coverage, extraction or binding | INSUFFICIENT |
| Invalid result schema, unknown policy, wrong binding, duplicate/reordered result or invalid observation | INSUFFICIENT |
| Independently validated contradiction with otherwise valid result set | CONTRADICTED, even with insufficient/absent neighboring results |
| Nonempty complete required set, exactly one matching supported result per claim | SUPPORTED |
| Missing result, insufficient claim, empty/non-verifiable response, all other cases | INSUFFICIENT |

An invalid contradicted result cannot establish precedence. Invalid sets are
discarded conservatively. Missing results can never shrink the required set or
count as successful checks. There is no voting, average confidence, or
single-claim shortcut. Result validation repeats these rules before export.

## Ownership, deadlines and error handling

One Pipeline belongs to one event loop and is reused across requests. It owns a
small admission count, default four/configurable 1..16, with immediate refusal
of excess requests and no pending waiter queue. A request has at most eight
claims; retrieval is sequential, so there is at most one in-flight source call
per admitted request. A default five-second shared deadline includes optional
extraction and all retrieval; each retrieval also has a four-second ceiling.
No automatic retries, evidence sharing, caches or write tasks are introduced.

Candidate limits are 8,192 code points and 32,768 UTF-8 bytes. The CLI reads at
most 65,537 bytes to detect the 65,536-byte JSON limit before decoding. Optional
extraction/results have eight-claim bounds; evidence bodies are at most 1 MiB;
metadata strings/IDs/versions are bounded. Built-in clients close responses and
their per-call clients, refuse redirects/proxy discovery and enforce operation
deadlines. Caller-provided retrievers remain trusted application dependencies.

Per-claim retrieval failure yields a typed insufficient result and does not
hide successful or contradicted neighbors. Shared timeout cancels unfinished
work and supplies insufficient results for the remaining required claims.
External cancellation propagates without a verdict and frees admission in
`finally`. Model failure and extraction/binding conflicts stop evidence work.
No request/response objects or candidates are retained after the call.

Runtime failures use fixed reason codes. Existing Python-policy diagnostics
remain sanitized; the new code emits no raw exception/body/candidate logs.
Revalidation suppresses Pydantic serializer warnings for deliberately corrupted
model instances so input-bearing warning strings cannot become diagnostics.
CLI input errors are fixed text. Programmatic validation errors remain typed
exceptions and callers must not log their input-bearing details. Explicit CLI
`--json` is a full artifact export, including the input candidate/extraction.

## Security tests and demonstrations

The final new suite contains **149 offline tests**, with external sockets blocked
and Gemini/Tavily opt-in/credentials removed by its fixture. It covers:

| Invariant | Tests |
| --- | --- |
| No unsupported neighboring content can pass | `test_unaccounted_content_never_retrieves`, `test_claim_limit_does_not_shorten_required_set`, six vertical scenarios |
| Spans/IDs/extraction cannot silently waive checks | `test_extraction_separate_binding_and_coverage_checks`, `test_actual_004a_model_adapter_and_baseline`, `test_wrong_hash_prevents_retrieval` |
| All required results matter; contradictions must be valid | Nine-case aggregation truth table, invalid-results matrix, independent-contradiction precedence, whole-record consistency tests |
| Evidence identity/structure/freshness must be checked | Evidence matrix for both policies, invalid PyPI envelopes/version semantics, ahead-of-source and fixture/live separation |
| Retrieval status/redirect/body/transport failures cannot support | Full application test through real Tavily/PyPI HTTP clients with MockTransport, PyPI HTTP failure matrix; existing Tavily partial-failure tests rerun |
| Resource failure cannot produce support | Per-call/shared/model deadlines, external cancellation, 20 concurrent requests with a two-request limit, invalid budget tests |
| Instructions and diagnostics cannot control policy/leak raw failures | Evidence manipulation demo, normalized-proposition injection, extraction label conflict, sanitized runtime/CLI error tests |

From repository root:

```powershell
$env:PYTHONPATH = 'services/verifier;services/claim_analysis'
& .venv-003a/Scripts/python.exe -m verifier.multiclaim
& .venv-003a/Scripts/python.exe -m verifier.multiclaim --json
```

Observed summary output (each case runs actual input/coverage/policy/aggregation
code; verdicts are not hardcoded):

```text
A: SUPPORTED; coverage=COMPLETE/EXACT_TEMPLATES; claims=SUPPORTED,SUPPORTED; mode=fixture
B: CONTRADICTED; coverage=COMPLETE/EXACT_TEMPLATES; claims=SUPPORTED,CONTRADICTED; mode=fixture
C: INSUFFICIENT; coverage=COMPLETE/EXACT_TEMPLATES; claims=SUPPORTED,INSUFFICIENT; mode=fixture
D: INSUFFICIENT; coverage=UNCERTAIN/UNRECOGNIZED_CONTENT; claims=none; mode=fixture
E: CONTRADICTED; coverage=COMPLETE/EXACT_TEMPLATES; claims=SUPPORTED,CONTRADICTED; mode=fixture
F: INSUFFICIENT; coverage=COMPLETE/EXACT_TEMPLATES; claims=SUPPORTED,INSUFFICIENT; mode=fixture
```

D supplies an exactly bound extraction omitting the third factual sentence; the
independent grammar refuses before model/extraction acceptance or retrieval.
Separate omission and NON_FACTUAL tests use grammar-valid candidates to exercise
the later extraction-conflict boundary. E appends instructions to Python evidence
and PyPI description metadata; the actual older requests claim stays contradicted.
F has an unexpected URL and cannot establish the requests claim.

## Executed checks

Logs are ignored under `artifacts/004b/`. All commands below were executed from
the repository root; no paid credentials were read or printed.

```powershell
$env:PYTHONPATH = 'services/verifier'
& .venv-003a/Scripts/python.exe -m pytest -c services/verifier/pytest.ini services/verifier/tests -q
$env:PYTHONPATH = 'services/claim_analysis'
& .venv-003a/Scripts/python.exe -m pytest -c services/claim_analysis/pytest.ini services/claim_analysis/tests -q
$env:PYTHONPATH = 'services/verifier;services/claim_analysis'
& .venv-003a/Scripts/python.exe -m pytest -c services/verifier/pytest.ini services/verifier/tests_multiclaim -q

docker buildx build --builder epochguard-002a --progress plain --target qualification-unit --no-cache-filter qualification-unit -f artifacts/004a-hardening/Dockerfile.unit .
docker buildx build --builder epochguard-002a --progress plain --load -t epochguard-dev:002a -f dev/Dockerfile .
docker compose -f compose.verify.yaml build verifier-supported
docker compose --profile test up -d --force-recreate --wait provider gateway gateway-control gateway-reject gateway-unavailable
docker compose --profile test run --rm --no-deps smoke
docker compose --profile test down --remove-orphans
docker compose -f compose.verify.yaml run --rm verification-tests
docker compose -f compose.verify.yaml down --remove-orphans
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml up -d --wait gateway-supported
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml run --rm --no-deps verification-tests
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml down --remove-orphans

docker run --rm --network none --mount 'type=bind,source=C:\Users\Aditya Bhardwaj\OneDrive\Desktop\epochguard,target=/project,readonly' --workdir /project -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=services/verifier:services/claim_analysis --entrypoint python epochguard-verifier:003a -m pytest -p no:cacheprovider -c services/verifier/pytest.ini services/verifier/tests_multiclaim -q
git diff --check
```

The ignored qualification Dockerfile is the existing unmodified full
`dev/Dockerfile` plus its `qualification-unit` stage. After module verification
it runs a network-disabled cache-mounted RUN: `test -z "$(gofmt -l .)" && go vet
-mod=readonly ./... && go test -count=1 -mod=readonly -trimpath -v ./... && go test
-count=1 -race -p=2 -mod=readonly -trimpath ./...`. It uses the repository-pinned
Go 1.27.3 Linux/amd64 toolchain; the race detector covers plugin units, not the
real gateway process. The gateway image uses the real native plugin loader.

| Check | Actual result |
| --- | --- |
| Existing verifier suite, Windows | 65 passed, one explicitly deselected live test; 6.02s; existing Starlette/httpx warning |
| Existing claim-analysis suite, Windows | 176 passed; 4.12s |
| Final 004B suite, Windows | 149 passed; 0.92s |
| Final 004B suite, network-disabled Linux/read-only source mount | 149 passed; 3.81s |
| Fresh Go unit checks | 22 top-level / 64 subtests passed; 0.227s |
| Fresh race detector | Passed; 1.258s, no race report |
| Formatting and `go vet` | Passed in the fresh qualification stage |
| Native gateway image | Built successfully; its existing build checks also passed/cached |
| Existing verifier image | Built successfully; Linux build ran 65 passed / one live deselected; 4.73s |
| Real gateway smoke | 10 top-level / 35 subtests passed |
| Real offline gateway/service verification | 8 top-level / 31 subtests passed |
| Separate long-deadline profile | Passed in 12.56s; HTTP 200, first-byte/total 12,547ms; provider/retrieval deltas 1/1 |
| Offline demo and typed JSON export | All six expected outcomes; JSON CLI and result round trips also tested |
| Whitespace check | `git diff --check` exited 0 |

Initial sandbox Docker inspection could not access its configuration/engine;
escalated inspection confirmed Docker Desktop was stopped. Starting the existing
Desktop environment restored the pinned builds. All task-owned stacks were
removed after tests; the pre-existing BuildKit builder was left running.

A development test attempting to forge an HTTP response's request URL through
MockTransport failed (134 passed / one failed): httpx replaces that synthetic
request with the actual fixed outgoing request. That invalid simulation was
removed; actual fixed-request assertions, redirect refusal and wrong-Page-source
tests remain. Final review also added the explicit extractor-returning-None
failure guard and its regression. No failed live assertions were retried, and no
enforcement condition was weakened. Intermediate runs/logs remain local.

The short gateway runner explicitly skips its opt-in live and separate long
tests; the latter was executed separately above. The verifier live marker was
explicitly deselected. No live qualification, route-audit rerun or isolated
cache-lifecycle rerun is claimed. These unchanged route/cache experiments were
outside this task's requested regression set. Optional single-source live probe
commands and exact budgets are documented in the
[component README](../services/verifier/README.md#optional-real-source-observations).
They require `EPOCHGUARD_RUN_LIVE_004B=1` and were not executed.

Final scope checks confirmed two existing documentation changes and fifteen new
files. All pre-existing code, configuration, schemas, datasets and reports remain
unchanged. Python syntax, trailing whitespace, final newlines, balanced Markdown
fences, 55 local documentation links/anchors and `git diff --check` passed. The
check command was `& .venv-003a/Scripts/python.exe artifacts/004b/final_check.py`.

## Remaining integration and production limits

The new result never becomes gateway ALLOW. A separately specified and qualified
Go-side `004b.v1` consumer would need its own independent binding/schema/policy/
mode/freshness/aggregation validation and enforcement acceptance tests. Qualified
`003a.v1` nonce/hash checks, terminal refusals, provider errors, streaming guards,
cache-disabled settings and hook ordering are unchanged.

General prose verification/semantic coverage, human-reviewed extraction quality,
live multi-claim qualification, origin freshness, durable evidence/provenance,
protected cache admission/revocation, safe streaming, production authentication,
tenant isolation and external readiness enforcement remain unresolved. The
verifier/runtime/clock/configuration/source TLS are trusted, records are unsigned,
and upstream sources or extracted snapshots can be stale or compromised. Bounded
local observations are not a claim about continuous or future correctness.

Recommended conventional commit, not created:
`feat(verifier): add bounded evidence-backed multi-claim verification`.

Stop at Task 004B for maintainer review; no deployment, commit or push.
