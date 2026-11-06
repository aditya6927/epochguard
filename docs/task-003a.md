# Task 003A — first evidence-backed verification slice

Implemented and exercised on 2026-11-06. This is a narrow policy implementation with offline end-to-end qualification, **not general factual verification or completed live Tavily qualification**. No live credential or explicit live opt-in was available in this session. No live factual verdict is claimed below.

## Supported claim and rules

The entire assistant answer must be this exact sentence, with a stable numeric version substituted:

```text
The latest stable Python 3 release for Windows listed on Python.org is X.Y.Z.
```

Policy `python-windows-latest-v1` accepts only `3.<0..99>.<0..999>` without leading zeros, suffixes, extra whitespace, explanation, or additional claims. The Go boundary additionally requires exactly one complete, plain assistant chat choice with finish reason `stop`. Tools, reasoning/assistant extensions, multimodal content, log probabilities, citations, search results, partial completions, and streaming choices are unsupported. This deliberately sacrifices coverage: finding one supported sentence inside a larger unchecked answer would not justify releasing that answer.

The sole evidence URL is [Python.org's Windows downloads page](https://www.python.org/downloads/windows/). Tavily Extract must return that exact URL, one result, no failed results, a retrieval identifier, and bounded raw text. The policy requires one exact `Python Releases for Windows` heading, one exact `Stable Releases` heading, and one stable `Latest Python 3 Release - Python <version>` line between them. An optional bullet is allowed. Missing context, prerelease labels, multiple labels, or changed layout fail closed. This is a primary-page label comparison, not arbitrary search, release-note interpretation, or a claim about all platforms.

| Comparison against the observed primary label | Service verdict / reason | Gateway outcome |
| --- | --- | --- |
| Equal | SUPPORTED / MATCHED_PRIMARY_LABEL | ALLOW, original buffered answer |
| Candidate numerically older | CONTRADICTED / OLDER_THAN_PRIMARY_LABEL | REJECT, terminal 403 |
| Candidate newer | INSUFFICIENT / CLAIM_AHEAD_OF_SOURCE | UNAVAILABLE, terminal 503; the extraction may lag |
| Missing/ambiguous evidence, unsupported claim, timeout, retrieval/verifier failure | INSUFFICIENT / specific bounded reason code | UNAVAILABLE, terminal 503 |
| Invalid HTTP status, malformed/misbound/stale/inconsistent verifier contract | No accepted verdict | UNAVAILABLE, terminal 503 |

Retrieval success and ranking cannot cause ALLOW. This path does not use a search ranking or an LLM judge. Instructions appearing in candidate or evidence text are data; no prompt interprets them. An otherwise valid older claim remains contradicted when retrieved text appends an instruction to ALLOW it.

## Trust boundaries and contract

The Go plugin remains the enforcement boundary. Provider content, client headers/prompts, and retrieved page text are untrusted. Maintainer-owned plugin configuration selects the fixed policy, verifier URL, deadline, and expected evidence mode. Clients cannot choose a verdict, evidence source URL, test endpoint, or cache-write policy. A client can supply a candidate through the controlled provider fixture; it must still satisfy the same comparison.

`services/verifier/verifier/contract.py` defines strict Pydantic models and `plugins/epochguard/http_decision.go` defines matching typed Go records. Schema version is `003a.v1`:

| Record | Fields |
| --- | --- |
| Request | `schema_version`, `policy_id`, random `request_id`, exact `candidate`, UTF-8 `candidate_sha256` |
| Claim | `kind: python_windows_latest_stable`, parsed `version`; null when unsupported |
| Response | Schema/policy/request/hash binding, `claim`, `verdict`, `reason_code`, bounded `evidence`, timezone-aware `checked_at` |
| Evidence reference | Fixed `url`, `retrieval_mode`, raw-text `content_sha256`, `retrieved_at`, `observed_at`, Tavily `retrieval_id`, `observed_version`, exact matched `excerpt` |

Evidence modes are explicitly `fixture` and `tavily_live`. Offline plugin configuration requires `test_only: true` and `evidence_mode: fixture`; the live configuration omits `test_only` and expects `tavily_live`. Go rejects a SUPPORTED/CONTRADICTED fixture record in live mode. These labels describe a trusted service's retrieval path, not cryptographic attestation. A compromised verifier can forge a record; internal network/configuration integrity remains an assumption.

The verification request ID is a fresh cryptographic nonce, independent of Bifrost's original request identity. Hash and nonce binding prevent accidental cross-request/replayed verdict acceptance. Go rejects duplicate JSON keys, unknown fields, trailing JSON, invalid policy/version, missing evidence, wrong authority, inconsistent comparison/reason/excerpt, and bad observation times before permitting a candidate. Neither raw service errors nor evidence excerpts become client refusal messages. Verifier logs contain verdict, reason, and elapsed milliseconds; candidate/page/key bodies are not logged by this code. No diagnostic header asserts verification.

`retrieved_at` and `observed_at` are currently equal: when the verifier finishes receiving the extraction. They are **not the page's publication time or Tavily's origin-fetch time**. The service permits observation age -2..60 seconds; Go additionally requires observation/check times to fall within the current verification round trip with two seconds of clock-skew tolerance. This bounds local reuse, not the age of an upstream cached copy. There is no origin freshness attestation, independent corroboration, publication-time guarantee, or durable evidence store. The hash identifies returned text; the service does not archive that text.

## Retrieval and failure policy

The current [official Tavily Extract API](https://docs.tavily.com/documentation/api-reference/endpoint/extract) was inspected before implementation. `retrieval.py` sends `POST https://api.tavily.com/extract` with Bearer credentials read from `TAVILY_API_KEY` and this fixed body:

```json
{"urls":["https://www.python.org/downloads/windows/"],"extract_depth":"basic","format":"text","timeout":3.0,"include_images":false}
```

The candidate and prompt are never sent to Tavily. There is no user-selected URL, query, reranking, or URL traversal. Redirects and environment proxy discovery are disabled. HTTP 200 with partial failures is a failure, not evidence. Duplicate JSON keys, excess results, unexpected URLs, and malformed/oversized results fail closed. The local client bounds the whole retrieval to four seconds, including streamed reads, with a 1 MiB response and 500,000-character extracted-text limit. No retries are added.

FastAPI exposes `POST /v1/verify` and a process-only `/health`. An ASGI boundary limits request bodies to 8 KiB and body receipt to two seconds. The typed candidate limit is 512 characters (Go accepts at most 512 bytes, which is equivalent for this ASCII grammar). Verification work has an independent 4.5-second deadline. The Go caller has a six-second total HTTP timeout by default, configurable only to 100..10,000 ms, and propagates its supplied context cancellation through `http.NewRequestWithContext`. It accepts only HTTP 200 JSON and at most 32 KiB of verifier response, with no redirects or proxy discovery. Connection concurrency per host is bounded to 16; this is not a production admission/rate-limit design.

The service has no durable resources per request. HTTP clients are closed after retrieval; Bifrost's borrowed response is never retained beyond synchronous `Decide`. Go shares an immutable configured source/client between calls and atomically publishes policy configuration. Invalid reconfiguration clears the previous policy and keeps the plugin installed in UNAVAILABLE mode. Parent cancellation and HTTP total deadlines are separately unit-tested. A browser disconnect is not proven to propagate from Bifrost's HTTP transport through every core context; FastAPI also does not immediately cancel all work when a downstream connection closes. Independent deadlines bound abandoned retrieval work. No claim of full disconnect propagation is made.

The offline Tavily endpoint override requires both trusted `EPOCHGUARD_TEST_MODE=1` and the exact public fake credential `local-fixture-only`. Other credentials cannot be sent to that test endpoint. Live mode uses the real fixed HTTPS URL. The private Go-to-verifier hop is plain HTTP in this disposable network; no production identity/authentication or TLS between services is implemented. Do not expose either service publicly.

## Important code paths and request walkthrough

```text
buffered POST /openai/v1/chat/completions
  -> HTTP guard and typed pre-LLM guard
  -> server CacheNoStoreKey=true (cache itself remains disabled)
  -> real provider; buffered candidate remains inside Bifrost
  -> PostLLMHook
       genuine BifrostError -> preserve it and its normal fallback policy
       success -> HTTP DecisionSource -> exact plain candidate parser
         -> FastAPI /v1/verify -> hash/parser check
         -> fixed Tavily Extract -> strict primary-label comparison
         -> typed evidence verdict -> Go binding/time/consistency checks
       ALLOW -> original response -> HTTP post diagnostics -> client
       REJECT/UNAVAILABLE -> nil response + safe terminal BifrostError -> client
```

`decision.go` selects the HTTP source through a nested `verifier` config, mutually exclusive with fixed decisions, test delays, and test cache flags. Existing fixed sources remain for 002B/002C qualification. HTTP policy always sets server no-store as defense in depth; this does not authorize cache enablement or make incorrect plugin ordering safe. All 003A configurations place EpochGuard `pre_builtin`, order 0, with no `semantic_cache` plugin, vector store, or Redis service.

`http_decision.go` parses the actual pinned core v1.14.1 response schema, serializes only the supported candidate, validates the typed response, and translates SUPPORTED/CONTRADICTED/INSUFFICIENT to ALLOW/REJECT/UNAVAILABLE. `policy.py` owns parsing and numeric evidence comparison; `retrieval.py` owns fixed-URL network access; `app.py` owns the request/deadline boundary. There is no model-generated policy or unrestricted claim extractor.

The unchanged `enforce` path preserves genuine upstream errors by pointer and does not call the verifier for them. A usable provider fallback is evaluated when it succeeds. Policy refusals return `(nil, typedBifrostError, nil)` with `AllowFallbacks: &false`, fixed messages and codes. An ordinary Go hook error is not this typed terminal refusal: pinned Bifrost can log hook errors and continue, so none is used as enforcement. HTTP hooks/headers are diagnostics and pre-dispatch request guards. A streaming request receives 400 before a provider call or SSE writer can start. No candidate is sent to the client while verification is pending.

The actual pinned schema inspected is [core chatcompletions.go](https://github.com/maximhq/bifrost/blob/2975d142abcffc5783a60201394631b5576c748f/core/schemas/chatcompletions.go). Upstream pins, module graphs, plugin ABI, and Bifrost core are unchanged. Prior error/fallback/cache source findings remain in [002B](task-002b.md), [002C](task-002c.md), and [ADR 0003](decisions/0003-protected-cache-ownership.md).

## Reproducible deployment and executed checks

`compose.verify.yaml` uses the real native loader and a real FastAPI service. Only Tavily's HTTP endpoint is substituted by a deterministic ASGI fixture. Its Docker network is internal (`docker network inspect` returned `true`), with no host ports. `provider-fixture -answer-mode claim` returns the controlled prompt as the candidate; the default `echo` mode preserves all previous tests. Fixture evidence version `3.88.7` and candidates `3.88.6`/`3.88.8` are synthetic, not factual assertions about a real Python release.

Initial isolated startup failed before inference: pinned Bifrost's model catalog attempted an external pricing download on the intentionally disconnected network. Inspection of the pinned framework's actual `modelcatalog.Config` and file loading code confirmed supported `framework.pricing` `file://` inputs for pricing, model parameters, and MCP library. The 003A configs now point to minimal local fixture catalogs under `/app/catalogs`; no Bifrost source or loader check was patched. These catalogs model only the local fixture, not paid provider pricing. Subsequent complete startup and acceptance runs passed. The failure is retained in local artifacts rather than hidden.

Commands executed from the repository root (output redirection omitted here):

```sh
docker compose build --builder epochguard-002a gateway
docker buildx build --builder epochguard-002a --load -t epochguard-verifier:003a services/verifier
docker compose -f compose.verify.yaml up -d --force-recreate --wait provider evidence-fixture verifier-supported verifier-missing verifier-ambiguous verifier-timeout verifier-failure gateway-supported gateway-missing gateway-ambiguous gateway-timeout gateway-failure gateway-malformed
docker compose -f compose.verify.yaml run --rm --no-deps verification-tests
docker compose -f compose.verify.yaml down --remove-orphans
docker compose --profile test up -d --force-recreate --wait provider gateway gateway-control gateway-reject gateway-unavailable
docker compose --profile test run --rm --no-deps smoke
docker compose --profile test down --remove-orphans
docker compose --profile test config --quiet
docker compose -f compose.verify.yaml config --quiet
git diff --check
```

The Python image build executes `python -m pytest -q`. The Go image build executes formatting checks, `go test -mod=readonly -trimpath -v ./...`, `go test -race -p=2 -mod=readonly -trimpath ./...`, the native plugin build, and fixture/test binary builds. The original pinned gateway/module layers were reused unchanged; the modified plugin tests ran afresh. Python's base image is digest-pinned; direct and transitive Python versions are pinned in `requirements.lock` (not wheel hashes). Go remains 1.27.3 Linux/amd64, shared with the gateway.

| Check | Actual final result |
| --- | --- |
| Python offline image tests | **26 passed, 1 live deselected, 1 warning in 0.60s** |
| Plugin unit tests | **17 top-level passed**, package `ok ... 0.163s` |
| Plugin race detector | `ok ... 1.229s`, exit 0, no reported races |
| Native plugin/fixture/integration binary builds and formatting | Exit 0 |
| Real 003A gateway acceptance | **6 top-level tests, 31 subtests passed**, final `PASS`, exit 0 |
| Existing 002B real gateway smoke regression | **10 top-level tests, 35 subtests passed**, final `PASS`, exit 0 |
| Live test guard without opt-in/network/credentials | **1 skipped, 26 deselected, 1 warning in 0.40s**; no live qualification |
| Default/offline/live Compose configuration validation | Exit 0; live override checked with a temporary fake environment value and `--quiet`, not a printed key |
| `git diff --check` and both disposable stack cleanups | Exit 0; no containers from either test stack left running |

The warning is Starlette's deprecation of its current HTTPX TestClient integration; it is not suppressed. Live selection is deliberately separate in `pytest.ini`; no offline test is disabled. Cache-proxy unit checks still pass in the native build (reused unchanged); the isolated 002C Redis lifecycle suite was not rerun for 003A.

Offline acceptance observations from the final run:

| Candidate / experiment | HTTP | Provider delta | Evidence fixture delta | First byte / total ms |
| --- | --- | --- | --- | --- |
| Supported current fixture label | 200 | 1 | 1 | 379 / 379 |
| Older contradicted | 403 | 1 | 1 | 245 / 245 |
| Newer than observation | 503 | 1 | 1 | 242 / 242 |
| Missing primary label | 503 | 1 | 1 | 160 / 160 |
| Ambiguous labels | 503 | 1 | 1 | 137 / 137 |
| Extraction timeout | 503 | 1 | 1 | 4095 / 4095 |
| Extraction HTTP failure | 503 | 1 | 1 | 242 / 243 |
| Malformed verifier response | 503 | 1 | 1 malformed-verifier call | 154 / 154 |
| Unsupported claim | 503 | 1 | 0 | 2 / 3 |
| Additional unchecked/instruction text | 503 | 1 | 0 | 2 / 2 |
| Genuine upstream errors (six gateways) | 400 preserved | 1 each | 0 | 9..21 |
| Primary error, successful supported fallback | 200 | 2 | 1 | 230 / 231 |
| Primary error, successful older fallback | 403 | 2 | 1 | 235 / 235 |
| Primary error, successful ahead fallback | 503 | 2 | 1 | 230 / 230 |
| Unsupported stream (six gateways) | 400 | 0 | 0 | 0..1 |

These are individual local fixture measurements, **not live Tavily latency, performance percentiles, or a production SLA**. Supported/contradicted fixture extraction deliberately waits 200 ms; the allowed response's first byte arrives after that wait. The timeout fixture sleeps six seconds and is cut off by the four-second retrieval deadline. Repeated runs need not reproduce exact timings.

Observed direct hook trace is `http_pre,pre_request,pre_llm,post_llm,http_post`. The genuine fallback path is `http_pre,pre_request,pre_llm,post_llm,pre_llm,post_llm,http_post`. A supported request logs `verification_verdict=SUPPORTED reason=MATCHED_PRIMARY_LABEL`; an older candidate logs CONTRADICTED/OLDER_THAN_PRIMARY_LABEL; timeouts log INSUFFICIENT/RETRIEVAL_TIMEOUT. `cache_at_post=none` accompanies these requests, and management inspection separately confirms no semantic-cache plugin is loaded.

Every direct decision test requests two usable fallbacks. Provider counters remain at one; fallback-path counters stop at two after the genuine primary failure. No refusal tries another model. Forged ALLOW/bypass/verified/no-store-false headers and a raw-response request cannot bypass the policy. The no-answer assertion inspects serialized HTTP status/headers and the entire body for the exact candidate, fixture completion ID, private sentinel, `choices`, and `raw_response` fields. ALLOW is a positive control proving the detector sees an actual provider answer; legacy no-plugin/SSE controls also remain. Unit tests independently probe malformed/duplicate/oversized/misbound/verdict-inconsistent/fixture-as-live responses, unsupported shapes, total timeout, and parent cancellation.

Actual evidence reference captured by `TestVerifierEvidenceRecord` (explicitly offline):

```json
{
  "url": "https://www.python.org/downloads/windows/",
  "retrieval_mode": "fixture",
  "content_sha256": "6bf3dbc50a36589213958cd9b44990bf92e074bc4befcfac5324eab6ee853bfc",
  "retrieved_at": "2026-11-06T17:33:40.591634Z",
  "observed_at": "2026-11-06T17:33:40.591634Z",
  "retrieval_id": "offline-supported-4",
  "observed_version": "3.88.7"
}
```

Ignored `artifacts/003a/` retains build/startup/test/runtime logs, copied toolchain metadata, network inspection, and downloaded pinned upstream source. `gateway-build-final.log`, `verifier-build-final.log`, `verification.log`, and `regression-smoke.log` contain the final executions. PowerShell redirection may label Docker's stderr progress as `NativeCommandError`; the reported test/build exit status and final PASS lines, not that wrapper label, determine success.

## Opt-in live qualification

`tests/test_live.py::test_live_tavily_evidence_metadata` makes two real Extract calls: one derives a current candidate from the actual primary label, then the service retrieves independently and emits an evidence record. It never freezes a live version as a permanent expected fact. It allows a matched/older/ahead comparison if the label changes between calls, and requires real `tavily_live` metadata. Strict layout or API incompatibility fails the live test; it must be investigated rather than silently relaxed.

With a real key already in the shell's `TAVILY_API_KEY` environment, explicitly run:

```sh
docker run --rm -e EPOCHGUARD_RUN_LIVE_TAVILY=1 -e TAVILY_API_KEY epochguard-verifier:003a python -m pytest -m live -s -o cache_dir=/tmp/pytest-cache
```

The key is passed by environment name, not written into a command value or repository file. Output contains public evidence metadata only. This live test was **not executed with credentials** in this session. Its opt-in guard was executed without network/credentials using `docker run --rm --network none -e PYTEST_ADDOPTS= epochguard-verifier:003a python -m pytest -m live -q -o cache_dir=/tmp/pytest-cache`; result: **1 skipped, 26 deselected, 1 warning in 0.40s**. A skip is not live integration evidence.

An optional live gateway deployment is supplied for manual follow-up:

```sh
docker compose -f compose.verify.yaml -f compose.verify.live.yaml up -d --wait gateway-supported
# loopback-only gateway: http://127.0.0.1:8081/openai/v1/chat/completions
docker compose -f compose.verify.yaml -f compose.verify.live.yaml down --remove-orphans
```

It requires `TAVILY_API_KEY`, permits outbound retrieval, uses the live evidence-mode config, and still uses the local candidate-provider fixture. Start only `gateway-supported`; do not run offline synthetic acceptance expectations against live evidence. The inherited evidence-fixture service starts as a dependency but is not used by live retrieval. This deployment was configuration-checked only, not live-qualified. Do not print resolved Compose configuration containing a live key.

## Remaining limits and review boundary

- ALLOW means this exact candidate matched the unique extracted primary label under this explicit policy. It does not establish general truth, installability, absence of newer announcements, publication freshness, or validity of provider metadata such as IDs/token counts. Extraction content, Tavily, Python.org, TLS, and clocks are trusted only within the stated assumptions; source compromise/vendor caching/layout changes remain risks.
- No live latency, real extraction-format compatibility, quota behavior, or live factual outcome was established here. API-contract mocks and the real local network path do not substitute for the opt-in live test.
- The qualified provider remains the deterministic local OpenAI-compatible fixture. Production providers, tools, multi-choice outputs, direct SDK/alternate transports, additional plugins, safe streaming delivery, and asynchronous jobs remain unqualified. Genuine upstream error bodies retain upstream semantics; they are not successful answers or factual verdicts.
- The verifier is stateless; there is no durable decision/evidence log, final protected cache, invalidation/revalidation worker, PostgreSQL, Redis ownership, dashboard, Tavily search/LLM verifier, or autonomous verification. The built-in cache remains disabled in 003A and the default deployment. ADR 0003 remains the proposed future cache design.
- The original `compose.yaml` intentionally remains the 002B **test-only fixed ALLOW** example, not the new verifier deployment. Switching to the narrow source is explicit in the separate 003A config.
- Missing/failed native plugin loading can still leave Bifrost healthy and serving; integration tests detect it, but no external startup readiness gate exists. Health is not authorization or verifier readiness. Inference/service/management authentication and secret distribution are development-only. The live gateway is loopback-bound; the offline stack exposes no host ports.
- The race detector covers plugin unit execution, not an instrumented full gateway. Unit cancellation proves the source respects its supplied context; transport disconnect propagation, load saturation, and production performance are not qualified.

Stop after Task 003A for review. Recommended commit, **not created**: `feat(verification): enforce narrow Python release evidence verdicts`.
