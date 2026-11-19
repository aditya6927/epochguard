# Evidence verifier

This service supplies bounded evidence records to native Go enforcement. It does not release gateway responses itself. Trusted deployment configuration selects the contract; client text cannot choose policies or evidence modes.

| Private endpoint | Contract / language | Qualification |
| --- | --- | --- |
| `POST /v1/verify` | `003a.v1`, one Python Windows template | Legacy narrow live qualification |
| `POST /v1/verify/multiclaim` | `004b.v1`, two exact templates, up to eight claims | Narrow live qualification with controlled provider and explicitly legacy v1 protected receipts |
| `POST /v1/verify/prose` | `004g.v1` / `bounded-prose-v1`, nine exact ASCII forms | Narrow November 15, 2026 live acceptance reviewed and met with controlled provider and v2 ingress; [assessment](../../docs/task-004gl.md#reviewed-live-qualification--november-15-2026) |

[Architecture](../../docs/architecture.md) defines the trust/receipt contracts; [operations](../../docs/operations.md) provides fresh-clone builds, isolated regressions and explicitly gated live workflows. The credential-free bounded-prose demonstration uses only a standard-library host runner:

```powershell
py -3.12 tests/boundedprose/qualify.py --build --builder default
```

It uses simulated sources and a controlled provider, not live observations. Current G profiles require request-bound receipt v2 and project a minimal HTTP response preserving the exact approved assistant content. Legacy profiles retain v1 behavior and its request/metadata limitations.

The November 14, 2026 maintainer-authorized exact-template run used actual Tavily/Python.org and PyPI through ingress, Go and Python with a controlled provider. Subsequent inspection found all five client expectations met; the runner collected results rather than declaring final live PASS. Its maximum/recorded three application retrievals per source are not billing or origin-fetch counts. See [the dated assessment](../../docs/task-004e.md). This does not qualify G live operation, arbitrary prose, a commercial LLM or production readiness.

`verifier.multiclaim` is not imported by the legacy `/v1/verify` endpoint. The experimental root-context images include the sibling claim-analysis schema package; the original legacy Docker context remains independent. `verifier.bounded_prose` invokes the existing two-policy evidence engine using independently reconstructed canonical sentences, while separately binding original text/spans. Go rederives those mappings and never consumes 004F planning records.

## Local claim-level reporting (005D)

`verifier.claim_report` emits `005d.claim-report.v1` JSON and optional static HTML for a local operator. It is separate from every HTTP endpoint and enforcement decision. A complete existing `004g.v1` result is revalidated with the current Python schemas, grammar and evidence comparison contract. Each recognized claim receives an ordered evidence-linked entry: 100 for valid SUPPORTED, 0 for valid older-version CONTRADICTED and null for uncertain, invalid, expired or absent evidence. Scores are evidence-relative snapshots, not probabilities, model confidence or origin-freshness attestations. They cannot authorize delivery or prove Go/HMAC validation.

Use the existing locked environment, with no credentials or service connection:

```powershell
$env:PYTHONPATH = 'services/verifier;services/claim_analysis'
& .venv-003a/Scripts/python.exe -m verifier.claim_report --input artifacts/operator-result.json --kind bounded-result --evidence-profile fixture --output artifacts/operator-claims.json --html artifacts/operator-claims.html
```

The input must already exist; this inspector performs no verification/retrieval call and does not generate an input result. For existing G-L/005C sanitized `observations.json`, use `--kind qualification --record-index 0` and the recorded source profile (`fixture` or `live`). The November 19 real-Gemini run used `fixture` evidence; the November 15 source run used `live`. Historical exports omit required original mappings, comparison flags and evaluation time, so these derived reports retain recorded source observations with null scores/age and `NOT_RECORDED`. No historical file is modified or silently refreshed. Numeric reports require a complete original Python result; local input provenance remains trusted, not cryptographically authenticated.

The input, JSON output and HTML output are each bounded to 65,536 bytes; output creation refuses existing files and input aliases. Reports preserve only candidate/evidence digests and bounded structured metadata. `evaluated_at` is the original verifier `checked_at`, while `generated_at` is report creation time. Application observation age uses the existing -2..60-second window; tolerated future observations have null age and an explicit time status. Origin publication time is unavailable. See [the exact schema, fixed evaluation and commands](../../docs/task-005d.md). The unchanged nine-form grammar admits one to eight claims; unsupported neighboring prose prevents partial numeric scoring.

## Experimental natural-language planning

`verifier.prose` is the separate [004F analysis experiment](../../docs/task-004f.md).
It reuses 004A ModelExtractor/Gemini proposals, exact source alignment and cost
controls, then independently audits original-text risk units and closed policy
paraphrases. It emits `004f.prose-plan.v1` with `authorization=false` and
`semantic_completeness=NOT_PROVEN`. PLAN_READY means bounded planning only; it
cannot be used as gateway ALLOW. No gateway mode, app route, 004B contract or
evidence policy is changed. Optional shadow comparison accepts injected offline
fixtures only and never overrides unresolved coverage.

Create the [local Python environment](../../docs/operations.md#python-development-and-offline-checks) first, then run from the repository root:

```powershell
$env:PYTHONPATH = 'services/verifier;services/claim_analysis'
& .venv-003a/Scripts/python.exe -m verifier.prose analyze --engine baseline --text-file services/verifier/examples/prose/mapped.txt
& .venv-003a/Scripts/python.exe -m verifier.prose analyze --engine fake-model --text-file services/verifier/examples/prose/omitted.txt --fake-reply services/verifier/examples/prose/omitted.fake.json --shadow-fixtures
& .venv-003a/Scripts/python.exe -m verifier.prose evaluate --split dev --output artifacts/004f/baseline-dev.json
```

Human output omits candidate text; `--json` and explicit evaluation exports include
source-bound records. The separate 66-case [draft collection](data/prose-v1/README.md)
and [offline reports](reports/prose-v1/README.md) preserve failures, omissions and
false-complete metrics. **MODEL QUALITY QUALIFICATION PENDING**; fake-provider
tests are not model-quality evidence. The [planning report](../../docs/task-004f.md#optional-operator-run-model-diagnostic) gives a separately opted-in diagnostic procedure (at most ten selected calls). A later ten-call Gemini diagnostic is operator-reported against draft labels, not an independently qualified benchmark; it does not establish semantic completeness or release authority.

## Supported response languages

The legacy `003a.v1` endpoint accepts only the first sentence below and retains its 512-byte Go candidate bound. The `004b.v1` multi-claim mode accepts one to eight sentences from these two templates:

```text
The latest stable Python 3 release for Windows listed on Python.org is 3.X.Y.
The version reported for requests by the PyPI JSON API is X.Y.Z.
```

Replace version placeholders with canonical decimal numbers without leading
zeros or suffixes. Python retains its existing `3.<0..99>.<0..999>` grammar;
PyPI supports only three components, each 0..999. Pre/dev/post releases,
epochs, local versions, abbreviated versions and general PEP 440 normalization
are outside this policy. No dependency change is needed for this numeric subset.

The parser accepts ASCII space, tab, CR and LF around/between sentences, but
preserves every input character and exact Unicode code-point offset. Sentences
must be separated by whitespace. Internal whitespace, case and punctuation are
exact. Repeated identical sentences, Markdown, lists, extra clauses, prose,
instructions, Unicode lookalikes and all unrecognized content make coverage
UNCERTAIN and stop evidence work. Different versions of one policy are separate
required claims, never deduplicated. Empty/non-factual-only input is insufficient.

The `004g.v1` bounded-prose language adds exactly these seven forms (`V` obeys the same policy-specific numeric bounds):

```text
Python.org currently lists Python V as its latest stable Windows release.
Python.org lists Python V as its latest stable Windows release.
Python.org lists V as the latest stable Windows release.
Python.org lists Python V as its latest stable release for Windows.
PyPI reports requests version V.
The PyPI JSON API reports requests version V.
According to the PyPI JSON API, the version of requests is V.
```

G accepts only ASCII, one to eight sentences and SP/TAB/CR/LF separators, with exact internal wording/case/punctuation. A duplicate policy/version is refused even if expressed by a different form. Different versions remain separate required claims. There is no greeting, opinion or nonfactual exception. Negations, qualifiers, Unicode punctuation, Markdown and unsupported extra prose cannot pass. Original content is never normalized for client delivery; only a separately bound newline-joined canonical comparison is sent to the two-policy engine.

This is a whole-response grammar, not general semantic coverage. One supported claim cannot authorize unverified neighboring content.

## Evidence and decisions

Trusted code selects the fixed registry; neither candidates nor 004A output can
choose URLs, packages or policy identifiers.

| Policy | Source and validation |
| --- | --- |
| `python-windows-latest-v1` | Existing fixed-URL Tavily Extract of `https://www.python.org/downloads/windows/`; reuse the original context/unique primary-label parser and numeric comparison without changing `003a.v1` behavior |
| `pypi-requests-reported-v1` | GET only `https://pypi.org/pypi/requests/json`; require HTTP 200 JSON, exact project identity `info.name == "requests"`, canonical `info.version`, and boolean `info.yanked == false` |

PyPI's [official JSON API documentation](https://docs.pypi.org/api/json/) defines
the project metadata endpoint. This policy observes its reported version; it
does not check installability, distribution contents, vulnerability status,
compatibility, or every historical release. Yanked/missing/invalid metadata is
insufficient. Unused metadata, including descriptions and links, is ignored;
no URL from the body is followed. Duplicate keys and nonfinite JSON are rejected.

Both policies return SUPPORTED for an equal observed version, CONTRADICTED for a
numerically older candidate, and INSUFFICIENT for an ahead-of-source candidate.
An ahead claim is not established by this observation; source lag must not be
converted into a contradiction. A malformed, ambiguous, wrong-source, expired,
unavailable or timed-out observation cannot support or contradict a claim.
Observations must be within -2..60 seconds of the trusted clock. These times are
local receipt times, not origin publication/fetch-age attestations.

Whole-response aggregation is pure and deterministic:

1. Failed extraction, binding or coverage returns INSUFFICIENT.
2. Invalid, duplicate, reordered, unknown or misbound results invalidate the set.
3. An independently validated CONTRADICTED claim takes precedence over
   insufficient or absent neighboring results.
4. SUPPORTED requires a nonempty complete required set, exactly one matching
   result per claim, and every result SUPPORTED with satisfied evidence rules.
5. Every remaining case is INSUFFICIENT. There is no voting or confidence average.

The absent-neighbor contradiction rule describes the 004B contract. G's outer contract additionally requires an explicit evidence result for every original mapping, including insufficient results. Missing results invalidate that record; they cannot become ALLOW or an accepted G aggregate.

## Run offline from the repository root

Create the Python 3.12 environment using [operations setup](../../docs/operations.md#python-development-and-offline-checks) before running these CLIs. The environment is gitignored and is not supplied by a clone. For regression execution, use the network-disabled container command there; the commands below are local CLI/focused-test entry points.

```powershell
$env:PYTHONPATH = 'services/verifier;services/claim_analysis'
& .venv-003a/Scripts/python.exe -m verifier.multiclaim
& .venv-003a/Scripts/python.exe -m verifier.multiclaim --json
& .venv-003a/Scripts/python.exe -m pytest -c services/verifier/pytest.ini services/verifier/tests_multiclaim -q
```

On Linux, use `PYTHONPATH=services/verifier:services/claim_analysis` and the
appropriate Python executable. No Gemini or Tavily credential is used. The
offline CLI never reads a live-source setting.

Expected demo outcomes (all synthetic fixtures, not live-source qualification):

```text
A: SUPPORTED       # Python + requests both match
B: CONTRADICTED    # requests candidate older than observation
C: INSUFFICIENT    # requests evidence unavailable
D: INSUFFICIENT    # extra assertion omitted by a supplied extraction
E: CONTRADICTED    # evidence instructions cannot override the older comparison
F: INSUFFICIENT    # unexpected evidence URL
```

`--request path.json` reads a bounded strict `004b.v1` request against the same
synthetic evidence (`3.88.7` and `2.88.7`); it never selects real retrieval.
`--json` intentionally exports full typed records including the supplied
candidate and extraction. It is an artifact export, not diagnostic logging.
Default summaries and input-error messages contain no candidate/evidence text.

## Programmatic API and extraction

```python
from verifier.multiclaim.demo import scenario

pipeline, request = scenario("A")  # explicit fixture sources
result = await pipeline.verify(request)
assert result.verdict == "SUPPORTED"  # this direct API call takes no gateway action
```

Construct `Pipeline(python_source, pypi_source, fixture=False)` with trusted
retrievers for application-owned live operation. The caller supplies a trusted
request identifier and the exact candidate's UTF-8 SHA-256 through `Request`;
these are bindings, not authentication. The offline helper `make_request` is
convenience code, not an ingress identity provider. `Request.model_json_schema()`
and `Result.model_json_schema()` expose the strict versioned contract.

Without an optional extraction, the independent grammar constructs canonical
004A spans. To exercise 004A, supply `Request.extraction` or
`verify(request, extractor=ModelExtractor(provider))`, but never both. A model
extractor runs only after grammar qualification and within the shared deadline.
Gemini retains its existing explicit opt-in and cost/request controls. A baseline
adapter can return `(baseline.analyze(input), None)`.

Schema validity, extraction success, source binding, coverage, policy dispatch,
evidence sufficiency and aggregation are separate checks. 004A must return the
same ordered IDs, full source spans and FACTUAL/DYNAMIC/REQUIRED classifications
as the grammar. Omissions and NON_FACTUAL labels cannot waive checks. An aligned
fragment cannot stand in for a whole recognized assertion. Untrusted normalized
propositions, temporal references and uncertainty annotations do not select
policies or verdicts. The original extraction is retained without rewriting it.
004A alone has no completeness guarantee and cannot authorize delivery.

## Resources, ownership and trust

Reuse one Pipeline per event loop. It owns only an active-request count, bounded
to four by default (trusted configurable 1..16); admission has no waiter queue.
Each request processes at most eight claims sequentially, with a shared default
five-second work deadline and four-second per-retrieval ceiling. No retries,
background tasks, retained candidates, evidence cache or asynchronous writes are
introduced. Caller cancellation propagates and releases admission. Excess work
returns insufficient per-claim results immediately. Creating a new Pipeline per
request would defeat the shared admission bound and is not the intended lifecycle.
The separate 004E factory uses one shared admission slot, a 26-second work
deadline, fixed per-source budgets and bounded qualification telemetry; the
[004E report](../../docs/task-004e.md) specifies that live profile. These do not
change the defaults described here.

The caller owns retrievers. Each built-in HTTP retriever closes its per-call
client/response, refuses redirects and proxy discovery, and bounds evidence to
1 MiB. The API bounds candidates to 8,192 code points/32,768 UTF-8 bytes, optional
extractions to eight claims; the CLI bounds request JSON to 65,536 bytes. Invalid
programmatic input raises validation errors; applications must handle them
without logging their input-bearing Pydantic details. CLI validation messages
are sanitized. Runtime exceptions become fixed insufficient reason codes;
cancellation propagates instead of becoming a success. The existing Python
policy emits only its existing allowlisted diagnostics.

Evidence references retain source, mode, retrieval ID, content digest, observed
version and local timestamps, without raw bodies. Hashes and timestamps do not
authenticate sources. The Python runtime, clock, registry, fixture/live setting,
retrievers, TLS trust and configuration remain trusted. There is no durable
evidence archive or signed record. Fixture mode cannot satisfy live mode.

## Optional real-source observations

These separately opted-in commands make **one source request each**, without model or gateway calls,
with no retries. They validate and print bounded evidence metadata only. They
have not been run for Task 004B acceptance. PyPI needs no credential; Python's
Tavily request requires an operator-provided `TAVILY_API_KEY` and may be billable.
No test endpoint/mode is allowed for the live Python probe.

```powershell
$env:PYTHONPATH = 'services/verifier;services/claim_analysis'
$env:EPOCHGUARD_RUN_LIVE_004B = '1'
& .venv-003a/Scripts/python.exe -m verifier.multiclaim.live --source pypi
# Only after supplying TAVILY_API_KEY securely:
& .venv-003a/Scripts/python.exe -m verifier.multiclaim.live --source python
Remove-Item Env:EPOCHGUARD_RUN_LIVE_004B
```

PyPI is bounded to a four-second retrieval/five-second probe; Python to
19-second Tavily/20-second retrieval/22-second probe. Individual source
observations do not qualify whole-response live verification. See
[Task 004B](../../docs/task-004b.md) for the original independent API qualification.

## Experimental gateway qualification

The separate root-context `Dockerfile.004c` includes the verifier and sibling
`claim_analysis` package with the same pinned dependencies. Its factory composes
`POST /v1/verify/multiclaim` alongside the unchanged `/v1/verify` route. The
original verifier Dockerfile/context/image remain available without 004A imports.
Both modes use the existing native Go enforcement; the configuration
`verifier.mode: "004b.v1"` explicitly selects the experimental contract and exact
endpoint. Omitted mode and explicit `003a.v1` select the legacy path. Mode is not
read from inference headers, prompt or candidate content.

The experimental endpoint accepts strict 004B JSON within 64 KiB and a two-second
body deadline, reuses `Pipeline.verify()`, revalidates the result and caps it at
256 KiB before sending. Disconnects cancel work and release admission. Runtime
errors have fixed safe diagnostics; malformed input errors never echo candidate
or Pydantic input details. The packaged server limits concurrency to 32, while
Pipeline admits at most four active evidence checks with no waiter queue. The
004C factory requires explicit test mode plus a fixed fixture case and does not
read live credentials. The separately selected 004E live factory constructs its
trusted fixed retrievers; live evidence is not enabled by the 004C image's default
factory or an inference request.

Go preserves the existing plain buffered response eligibility checks and applies
the 004B text limits instead of 003A's 512-byte limit. Its independent validator
checks canonical complete JSON shape, nonce/hash/candidate binding, exact
template coverage, Python code-point spans, IDs/policies/versions, extraction
agreement, evidence modes/URLs/times/reasons/comparisons and evidence identity
consistency. It recomputes aggregation and rejects disagreement. SUPPORTED maps
to original-response ALLOW, CONTRADICTED to terminal 403, and INSUFFICIENT or
contract/transport failure to terminal 503. An independently validated
contradiction can retain 403 with an absent neighboring result; missing results
can never yield ALLOW. Go validates consistency within a trusted verifier hop;
metadata and hashes cannot prove a remote source was consulted.

Build and run this isolated gateway profile using [the operations commands](../../docs/operations.md#other-isolated-gateway-regressions). The same guide covers the protected D/E/G drivers and their cleanup.

The internal-only stack publishes no ports, contains no live API keys and keeps
semantic caching disabled. Gateway configuration databases live in per-container
tmpfs and cannot survive a restart. The real fixture provider uses its existing
verbatim-answer mode plus explicit test-only shape controls. A test-only fault
relay starts with real endpoint results, then corrupts records for rejection
tests. Only the runner's separate control endpoint selects faults; inference
text/headers cannot select them. Neither the relay nor the no-plugin gateway is
a protected production component. The no-plugin control deliberately releases
unchecked content to demonstrate the missing-plugin startup limitation.

The original 004C qualification covers exact templates with synthetic evidence
and a controlled provider. It does not itself qualify live multi-claim
verification, verifier-hop authentication, external startup readiness, streaming,
arbitrary routes, general prose or caching.
See [Task 004C](../../docs/task-004c.md) for the exact guarantees, executed results,
regression commands and remaining boundaries. The separate
[004D ingress qualification](../../docs/task-004d.md) and
[004E live assessment](../../docs/task-004e.md) establish their later narrow
boundaries; verifier-hop authentication and production readiness remain unqualified.
