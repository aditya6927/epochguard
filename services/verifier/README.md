# Evidence verifier

The qualified FastAPI `/v1/verify` route implements the unchanged `003a.v1`
Python Windows release-label policy. Its Go client validates that contract before
gateway delivery. See [the policy specification](../../docs/task-003a.md) and
[live qualification limits](../../docs/task-003b.md).

`verifier.multiclaim` is a separate experimental `004b.v1` programmatic API and
offline CLI. It is **not imported by `/v1/verify`**, installed in the gateway, or
mapped to ALLOW. It shares this service's dependencies, the existing Python
policy and retrieval implementation, and the unchanged 004A schemas/alignment.
No additional deployable service is introduced.

## Supported response format

An eligible candidate contains one to eight exact sentences selected from:

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

This is a whole-response grammar, not general semantic coverage. One supported
claim cannot authorize unverified neighboring content.

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

## Run offline from the repository root

Use the existing `.venv-003a` environment, or install the pinned
`services/verifier/requirements.lock` into a Python 3.12 environment.

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
assert result.verdict == "SUPPORTED"  # experimental result, no gateway action
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

These commands make **one source request each**, without model or gateway calls,
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
[Task 004B](../../docs/task-004b.md) for executed checks and deferred integration.
