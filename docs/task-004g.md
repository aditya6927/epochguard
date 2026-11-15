# Task 004G: protected bounded-prose gateway enforcement

**Security follow-up:** [Task 004G-S](task-004gs.md) supersedes the original receipt and ALLOW-envelope behavior described by this milestone. Current G profiles require `004g.receipt.v2` with exact request-body binding and a minimal response envelope. Original assistant content remains unchanged. The execution results below are historical 004G results; current remediation evidence is in the security report.

Starting tree: clean `main` at `fd0fb7a1ab4a53b13853aacbc958aa0464bff9cb`.
Implemented and checked November 15, 2026 (Asia/Calcutta). No commit or push.
**004G LIVE QUALIFICATION PENDING.** The gateway demonstrations use synthetic
observations, simulated source transports and the controlled provider fixture;
no real Tavily, PyPI or Gemini call was made. Model quality remains pending.

## Requirement and baseline guarantees

Release requires eligible buffered provider output, complete original-response
parsing, every supported factual mapping independently reconstructed in Go,
supporting evidence for every required claim, and an authenticated receipt
accepted by the protected ingress. Unknown content cannot be waived by an
extractor, normalization, supported neighbor or planner result.

Inspection covered README, AGENTS, architecture, the integration spike and
004B–004F notes; the prose mapper/audit/schema/pipeline, complete multiclaim
pipeline/policies/contracts/app/deployment, Go enforcement/HTTP source/receipt
code, ingress/CLI, provider and existing qualification drivers/tests. Cached
actual upstream source under `artifacts/003c/upstream/` was inspected for the
hook/error contract, loader failures and HTTP buffering/context behavior.
The pin remains transport commit `e869c3f9adc96ea53c38694a21bb04a8e1085487`,
core v1.14.1, matching native module graph and Go 1.27.3 Linux/amd64.
No new upstream hook, flag, exported type or ABI is introduced.

Before this change:

| Boundary | Existing guarantee retained |
| --- | --- |
| Whole response | 004B admits 1–8 exact template sentences; extra content prevents support. Eligible buffered chat excludes tools, partial/multiple choices, mixed response unions and unqualified annotations |
| Policy/evidence | Two fixed policies, URLs, canonical versions and source-mode checks; deterministic equal/older/ahead comparisons; identity/content-digest bindings and fresh observation bounds |
| Enforcement | Synchronous native post-hook; terminal typed 403/503 discards provider output and disables fallback. Genuine provider errors preserve identity/category and existing fallback behavior |
| Deadlines | Offline Python work 5s/retrieval 4s, Go 6s, ingress 8s. 004E has its separate fixed hierarchy below; pinned Bifrost has no qualified global HTTP deadline |
| Receipt | HMAC `004d.v1`, fresh 256-bit nonce, actual entity-body/status digest, ALLOW candidate digest, policy identity, request/time/replay bounds, unchanged buffering before release |
| Readiness/deployment | 004D management plus authenticated positive fixture probe; 004E source-free authenticated negative canary. Private gateway/management, cache disabled, unsupported routes denied at ingress |

The legacy `003a.v1` and exact-template `004b.v1` grammars, Python policies and
contracts are unchanged. The 004E live result remains its own historical scope.

## Complete request flow and ownership

```text
client -> isolated ingress: request bounds / route / admission / fresh nonce
 -> private real Bifrost -> controlled provider -> eligible original candidate
 -> native post-hook -> 004g.v1 original candidate + hash + fresh request ID
 -> private /v1/verify/prose -> complete ASCII grammar + original span mappings
 -> canonical comparison candidate -> unchanged bounded 004B pipeline
 -> fixed Python/Tavily and requests/PyPI comparisons -> strict nested result
 -> Go independently reparses original + reconstructs canonical candidate
 -> unchanged Go evidence validator + whole-result decision
 -> terminal refusal OR unchanged candidate -> original-body HMAC receipt
 -> ingress buffers actual body, checks MAC/nonce/policy/status/hashes/times
 -> byte-preserved allowed entity OR safe refusal / genuine provider error
```

`verifier.bounded_prose` is a separate package. It reuses only 004F's finite
mapping patterns/canonical formatting, not the risk heuristics, proposals,
planner Result or ModelExtractor. Python verifies the original request hash,
then derives all mappings directly from original text. Canonical sentences are
joined with one newline solely for existing evidence comparison. The original
candidate remains separately bound throughout; it is never replaced on release.

One shared 004B pipeline owns retrievers, bounded immediate admission (four
active requests offline), sequential claim retrieval and the work deadline.
Requests/results are local to the call; cancellation propagates and releases
admission in `finally`. There is no queue, candidate persistence, cache, retry
or background verification. The existing middleware bounds body receipt to
64 KiB/two seconds and joins its disconnect/work tasks. Serialization is checked
before sending, with a 256 KiB output limit. The packaged Uvicorn process bounds
concurrency to 32; ingress retains its own immediate 16-request admission.

The Go source reuses the existing immutable HTTP transport and full provider
eligibility checks. Its explicit mode branch handles only the new contract;
the old mode follows its original path. The strict JSON walker is factored
without changing its old eight-level limit; the nested 004G envelope permits
ten levels. Exact required field names/types, duplicate/unknown fields, null
positions, arrays of at most eight, UTF-8, size and trailing data are checked.
Default operational output contains fixed categories/IDs, not candidate text,
source envelopes, credentials or signed receipts.

## Exact grammar

Only these nine full case-sensitive sentences are admitted (`V` is a canonical
numeric version):

```text
The latest stable Python 3 release for Windows listed on Python.org is V.
The version reported for requests by the PyPI JSON API is V.
Python.org currently lists Python V as its latest stable Windows release.
Python.org lists Python V as its latest stable Windows release.
Python.org lists V as the latest stable Windows release.
Python.org lists Python V as its latest stable release for Windows.
PyPI reports requests version V.
The PyPI JSON API reports requests version V.
According to the PyPI JSON API, the version of requests is V.
```

Python versions are `3.<0..99>.<0..999>`. PyPI versions have three components
each `0..999`. Leading zeros, suffixes and normalization are forbidden.
One to eight sentences may be separated/surrounded by ASCII space, tab, CR or LF.
Internal sentence spaces/punctuation are literal. Every other byte must belong
to a recognized sentence. ASCII-only authorization makes Python code-point
offsets and Go byte offsets identical. A repeated policy/version assertion,
including another paraphrase of it, is refused rather than silently deduplicated.

No greeting, Markdown, quotation, nonfactual whitelist, explanation, conditional,
historical or negated statement is admitted. For example, both these refuse:

```text
Python.org currently lists Python 3.15.2 as its latest stable Windows release and it is safe.
Python.org currently lists Python 3.15.2 as its latest stable Windows release.
Thanks.
```

This is finite sentence-form verification, not unrestricted natural-language
or semantic verification. `PLAN_READY` is not ALLOW; no planner state is read.
The endpoint has no extraction or normalized-proposition input field.

## Versioned contract and validation responsibilities

Endpoint: private `POST /v1/verify/prose`, JSON only. Contract: `004g.v1`.
Policy: `bounded-prose-v1`. [Exported schema](../services/verifier/schema-004g.v1.json)
also requires the runtime cross-field checks described here.

Request fields are `schema_version`, `policy_id`, `request_id`, `candidate` and
`candidate_sha256`. Inputs retain the 8,192-character/32,768-byte outer bounds;
only ASCII candidates up to 8,192 bytes can authorize. Mismatched hashes or
malformed input return sanitized 422, not a verification success.

The response repeats those bindings and adds:

- `coverage`: COMPLETE or UNCERTAIN; `reason_code`: BOUNDED_GRAMMAR,
  UNRECOGNIZED_CONTENT, REPEATED_CLAIM, CLAIM_LIMIT or NO_CLAIMS.
- `mappings`: original ordered `c001`…`c008`, exact sentence/start/end,
  fixed policy ID, numeric version and canonical comparison sentence.
- `verification`: unchanged typed `004b.v1` Result for the independently
  reconstructible canonical candidate, or null for unrecognized input.

Python Result validation recomputes the grammar/mappings, binds canonical text,
hash and request ID, validates the nested old contract and requires every ordered
claim result, including explicit insufficient-evidence records.

Go independently reconstructs the entire original response, every mapping,
canonical text/hash, and required result count/order. It never trusts COMPLETE
alone. Its existing `validateMulti` then rechecks request/response identity,
extraction/source bounds, per-policy versions, expected URL and fixture/live
mode, retrieval ID, content-digest syntax, evidence identity derived from
URL/mode/retrieval-ID/content digest, timestamp equality/freshness, comparisons
and aggregation. Evidence must be observed no earlier than call-start minus
two seconds and no later than checked/current bounds; age remains at most 60s.
Go receives metadata, not raw evidence content: the trusted Python retriever
parses source bodies and computes their hashes. This is consistency validation,
not independent origin attestation or authentication of the private HTTP hop.

All equal and evidenced -> ALLOW. A valid older required claim -> terminal
REJECT (403), even alongside another insufficient claim. Ahead-of-source,
missing/invalid evidence, malformed contract, omitted/reordered/duplicate results
or unrecognized original content -> UNAVAILABLE (503). No partial answer release.

## Receipt and readiness isolation

Following 004G-S, G uses `004g.receipt.v2` and additionally signs
`request_sha256`, derived from the exact HTTP body received by Bifrost. Ingress
compares it with its retained forwarded bytes. G never accepts a legacy receipt.
Configured immutable enforcement policy selects the signed `policy_id`:

| Profile | Accepted receipt identity |
| --- | --- |
| Existing 004D / 004E | `004b.v1/multi-claim-templates-v1` only |
| New `004g` / `004g-live` | `004g.v1/bounded-prose-v1`, protocol `004g.receipt.v2` only |

No client policy selector is introduced. MAC, unpredictable per-request nonce,
body/status/candidate hash, canonical receipt encoding, request-start minus two
seconds, future tolerance two seconds and maximum issuance age 20s are unchanged.
Signing requires the same configured policy still active at the HTTP post-hook.
Every fallback attempt replaces request-local state. Missing/disabled plugin,
later response mutation, mixed candidate or absent body capture cannot produce
an accepted ALLOW. Internal receipt/diagnostic headers are stripped on release. G projects successful
entities to fixed `object`/choice/role/finish fields and the exact approved content.
Provider IDs, model labels, fingerprints, service tier, usage, extra fields and
routing metadata are removed. G provider errors retain HTTP status and an
allowlisted category with a fixed safe message; they are not factual verdicts.
Explicit legacy B/D/E configurations retain their original wire behavior and
do not acquire these new guarantees.

Both G profiles use the existing fixed negative canary and require an authenticated
UNAVAILABLE 503, plus actual loaded/active/enabled plugin placement/order/mode,
receipt protocol and absence of the loaded semantic cache. Readiness neither
retrieves evidence nor claims source health. The offline test compares private
source invocation counters before/after readiness. Client-only tests cannot
connect to gateway, verifier, management or provider networks.

## Deployment and cleanup

Prerequisites: Linux Docker Desktop, Compose, the named buildx builder described
in README and the existing `.venv-003a` Python environment. No API keys.
From repository root in Windows PowerShell:

```powershell
& .venv-003a/Scripts/python.exe tests/boundedprose/qualify.py --build
```

The driver builds native, 004C, 004E and 004G images; derived Python images use
the daemon's local base tags. It starts only internal networks with no published
ports, runs client/operator checks, disables enforcement, restores it, performs
a real concurrent restart window and always attempts cleanup. Outputs are under
ignored `artifacts/004g/qualification/`. `--build` may download pinned build
dependencies; this is distinct from live evidence/model execution. Without
`--build`, the driver uses the already-built images.

For manual inspection of this explicitly synthetic test stack:

```powershell
docker compose -f compose.verify.004g.yaml up -d --wait verifier-old ingress ingress-unsafe ingress-cross-g ingress-cross-b ingress-old ingress-faults
docker compose -f compose.verify.004g.yaml run --rm --no-deps qualification-client
docker compose -f compose.verify.004g.yaml down --volumes --remove-orphans
```

The private simulated-source control and receipt mutation relay are test-only.
The signing key is randomly initialized in a disposable volume and never given
to the provider, verifier, mutation relay or client test runner. The setup token
is explicitly local-development-only. Do not publish any fixture/private ports.

## Live composition boundary

The default image/Compose/driver never select live sources. A separate Python
factory `verifier.bounded_prose.deployment:live_app` requires **both**
`EPOCHGUARD_RUN_LIVE_004G=1` and the reused 004E credential boundary:
`EPOCHGUARD_RUN_LIVE_004E=1`, `EPOCHGUARD_004E_PROFILE=live` and a bounded
`EPOCHGUARD_TAVILY_SECRET_FILE` runtime file. Existing fixture/source/endpoint/
package/policy/timeout override prohibitions apply. No environment API key,
fixture fallback, retries or Gemini are used. The process budget is three
retrieval invocations per source, including failed invocations; restarting
resets a qualification budget and must not be used to manufacture live success.

It constructs only fixed Tavily/Python.org and requests/PyPI real retrievers,
with `fixture=False`, one active request and the existing hierarchy:
Tavily API 19s < transport 20s; PyPI 4s; shared work 26s; Go verifier 30s
with trusted `004e-live` timeout profile and 40s remaining decision cap;
`004g-live` ingress 44s; server write 48s; a future runner must allow 52s.
Receipt age still starts at issuance, not request start, and is not increased.

No live G Compose qualification/measurement driver is supplied or executed.
A future operator run must privately observe source versions dynamically,
separately report statuses/evidence/invocation counts/latency and distinguish the
fixture provider from a real model. The November 14 observations are never used
as current live assertions. **004G LIVE QUALIFICATION PENDING.**

## Tests and actual outcomes

Final checks and runtime observations are recorded below. Logs are ignored
local artifacts; historical 004B–004F reports and live artifacts were preserved.

| Executed check | Actual outcome |
| --- | --- |
| Final native image build (`dev/Dockerfile`) | PASS: formatting, explicit plugin vet, plugin unit tests (159 PASS entries including subtests), plugin race, ingress vet/unit/race, key CLI and proxy tests; real gateway/plugin/test binaries built |
| Network-disabled combined Python suite | **571 passed, 1 live test deselected, 1 existing Starlette deprecation warning, 16.52s** |
| New G image build tests | **53 passed, 0.77s** |
| Existing 004C image build tests | **168 passed, 3.93s** |
| Existing 004E image build tests | **33 passed, 0.99s** |
| Final G protected qualification | PASS: client 54 recorded inference checks; operator 21; recovery/final recovery one each; restart window 82 |
| Existing 004D host driver | PASS: startup, client/operator, disable, recovery, concurrent real restart and final recovery |
| Existing 004E host driver, default offline selection | `004E offline qualification passed; LIVE QUALIFICATION PENDING` (message is for this offline rerun, not a retraction of historical 004E live evidence) |
| 004B/004C real gateway suite | PASS: 49 PASS entries including subtests |
| Legacy verification suite | PASS: 39 PASS entries; live and separate long-profile tests skipped by this selection |
| Existing smoke suite | PASS: 45 PASS entries including subtests |
| Existing route suite | PASS: 58 PASS entries including subtests |
| Separate long-deadline suite | PASS: 12.70s test; HTTP 200 after 12,690ms, one provider and one retrieval invocation |

Go counts include parent tests and subtests, not independent request counts.
Race checks execute unit code, not the real gateway process. The 571 Python
checks include all 176 existing 004A tests, 76 existing 004F tests, legacy and
004B/C/E tests, and 53 new G tests. Live/model calls remained disabled.

Final G measurements from `artifacts/004g/qualification/client.log`:

| Real protected gateway case | HTTP | Elapsed ms | Delivery |
| --- | --- | --- | --- |
| A: supported two-paraphrase response | 200 | 36.571 | Original candidate UTF-8 bytes match |
| B: Python 3.15.1 against fixture 3.15.2 | 403 | 24.303 | Terminal refusal, no candidate leakage |
| Missing plugin | 503 | 256.126 | Ingress refusal |
| Valid 004B receipt presented to G ingress | 503 | 213.033 | Cross-policy refusal |
| Valid G receipt presented to older ingress | 503 | 27.064 | Cross-policy refusal |
| Older protected profile positive control | 200 | 27.187 | Original candidate preserved |
| Genuine provider error without fallback | 400 | 42.014 | `fixture upstream failure` category preserved |

All nine individual supported forms returned 200. Unsupported grammar checks
returned 503. The 16-request concurrent mixed matrix returned only the allowed
200/403/503 outcomes and preserved each successful request's exact candidate;
no unsupported or contradicted request became 200. The complete client run
recorded 17 HTTP 200, one 400, six 403 and 30 503 responses. Seven independent
simulated source faults each returned 503 (22.217?34.311ms). Operator checks
recorded one valid receipt-control 200 and twenty safe 503 responses, including
all four requests overlapping runtime disable. Active Python work was zero
before cleanup. The real restart window recorded 58 HTTP 200 and 24 safe 503,
then final recovery returned 200. These are single-run fixture measurements,
not latency guarantees, live source observations or model benchmarks.

The runner compares released candidate bytes. Ingress separately authenticates
the hash of the complete actual gateway entity body, preserving that entity on
ALLOW; the provider's raw HTTP envelope is not asserted identical to Bifrost's
serialization. No component timing is inferred by subtracting client durations.

Commands actually executed from repository root (PowerShell):

```powershell
# Final native image: units, race, vet, formatting and ABI-matched binaries
docker buildx build --builder epochguard-002a --load -t epochguard-dev:002a -f dev/Dockerfile .
# Refreshed baseline and new verifier images; each runs its offline build checks
docker buildx build --builder epochguard-002a --load -t epochguard-verifier:004c -f services/verifier/Dockerfile.004c .
docker build -t epochguard-verifier:004e -f services/verifier/Dockerfile.004e .
docker build -t epochguard-verifier:004g -f services/verifier/Dockerfile.004g .
# Exact combined offline Python source check (no credentials forwarded)
docker run --rm --network none --mount "type=bind,source=$($PWD.Path),target=/src,readonly" --workdir /src/services/verifier -e PYTHONPATH=/src/services/verifier:/src/services/claim_analysis -e PYTHONDONTWRITEBYTECODE=1 epochguard-verifier:004g python -m pytest -c /src/services/verifier/pytest.ini -p no:cacheprovider /src/services/verifier/tests /src/services/verifier/tests_multiclaim /src/services/verifier/tests_gateway /src/services/verifier/tests_live /src/services/verifier/tests_prose /src/services/verifier/tests_bounded_prose /src/services/claim_analysis/tests -q
& .venv-003a/Scripts/python.exe tests/boundedprose/qualify.py
& .venv-003a/Scripts/python.exe tests/protectedingress/qualify.py
& .venv-003a/Scripts/python.exe tests/livequalification/qualify.py
docker compose -f compose.verify.004c.yaml run --rm qualification
docker compose -f compose.verify.yaml run --rm verification-tests
docker compose --profile test up -d --force-recreate --wait provider gateway gateway-control gateway-reject gateway-unavailable
docker compose --profile test run --rm --no-deps smoke
docker compose -f compose.routes.yaml up -d --force-recreate --wait reject control warp-control warp-reject nolog
docker compose -f compose.routes.yaml run --rm --no-deps route-tests
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml up -d --force-recreate --wait gateway-supported
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml run --rm --no-deps verification-tests
```

Each Compose regression was followed by its matching
`down --volumes --remove-orphans`; the host drivers clean up in `finally`.
Final `docker ps` showed only the pre-existing buildx builder container.
Static scope checks passed: 24 new files and 10 existing edits, Python AST/JSON
validation, exported-schema equality, all 28 Markdown files / 168 local links /
11 anchors, and `git diff --check`. Legacy Python/model/planner code, dependency
locks, old configurations and historical task reports are unchanged.

Tested native image: `sha256:cc1e7ea59cb139c00df7ad89e32e5fd90e0e1cdceb4c5cbbfc515c90303d0329`.
Tested G image: `sha256:544905ed528fd6b64bee7e2201f5b0067ff3e5f44dff22033be63572fba92dca`.
Build and existing regression logs are under ignored `artifacts/004g/`;
004D/E drivers also write their normal offline reproduction paths.


The fixture gateway suite includes all nine individual sentence forms; A's two
supported paraphrases; B's older Python contradiction; ninth-claim overflow;
unsupported neighbor/compound; greetings, Markdown/quotes, negation, tense,
modality, source/project/qualifier changes, version suffixes, case changes,
Unicode/unknown tails and instructions. It asserts no original answer in every
refusal, and supplies fallback on policy cases to check terminal behavior.
Provider-error control omits fallback so the original 400 remains observable.

It also covers missing plugin, source-free readiness, direct private-network
denial, unsupported routes/streaming, genuine cross-policy receipts in both
directions using the same key, MAC/body/status-envelope mutation, replay,
missing/duplicate receipts, independent simulated Tavily/PyPI faults, concurrent
mixed requests, concurrent disable, active-work cleanup and real restart recovery.
Fresh-MAC wrong nonce/old issuance/cross-policy negatives additionally run in
ingress unit tests; an unchanged old-suite regression covers other envelope faults.

Development checks initially found an unavailable pytest async marker, an image
fixture-path assumption, a provider-error test accidentally enabling fallback,
and a missing test-relay startup dependency. The tests/driver were corrected;
acceptance conditions and enforcement were not loosened. All qualification
reruns were offline. No failed live run was retried.

## Files and remaining limits

| Paths | Responsibility |
| --- | --- |
| `services/verifier/verifier/bounded_prose/{grammar,contract,pipeline,app,deployment}.py` | Original-response parsing/bindings, strict nested evidence contract, separate fixture/live factories |
| `services/verifier/tests_bounded_prose/`, `schema-004g.v1.json` | Offline grammar/contract/endpoint/resource controls, simulated source transports, exported schema |
| `plugins/epochguard/prose.go`, `prose_test.go` | Independently authored Go grammar, mapping/evidence validation, mode/HTTP controls |
| `plugins/epochguard/{decision,multiclaim,attestation}.go` | Explicit source dispatch, reusable strict wire walker/transport and policy-bound receipt signing |
| `internal/ingress/{ingress,prose_test}.go`, `cmd/protected-ingress/main.go` | Fixed policy profiles, source-free readiness and unchanged receipt security checks |
| `tests/conformance/004g-*.json` | 35 shared grammar vectors and three frozen synthetic result records |
| `tests/boundedprose/`, `compose.verify.004g.yaml`, `dev/prose/` | Reproducible isolated real-gateway/client/operator/lifecycle qualification |
| `services/verifier/Dockerfile.004g`, `dev/Dockerfile` | Separate offline image and explicit native plugin vet in existing build checks |
| README, AGENTS, architecture, verifier README, this report | Current boundaries, reproduction and evidence status |

Compared with 004E, the new mode adds seven finite paraphrases, explicit original
to canonical span mappings and a separate receipt policy identity. The two
evidence policies and trust assumptions are the same. 004E retains its narrow
live qualification; G has offline qualification only. Neither authorizes general
prose, model-selected subsets or safe streaming.

The host/kernel/network isolation, pinned gateway/plugin/ingress, verifier,
clock, operators and signing key are trusted. The verifier hop remains private
unauthenticated HTTP. Compromised trusted processes, malicious administrators,
origin freshness, source publication times and commercial LLM quality are not
solved by the receipt. Semantic cache remains disabled; there is no protected
cache, atomic revocation, production authentication/readiness, new evidence
policy, unbounded extraction or durable evidence store. Direct gateway exposure
still bypasses the ingress deployment-integrity boundary.

Recommended commit:
`feat(gateway): enforce bounded prose with independent claim validation`.
Stop for maintainer review; no commit or push was performed.
