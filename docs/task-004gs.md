# Task 004G-S: request binding and metadata hardening

Baseline: clean `main` at `05ac78939b0efa7dc4f66669b1c1e5bf48e8be23`.
Implemented November 15, 2026 (Asia/Calcutta). No commit or push.
**004G LIVE QUALIFICATION PENDING.** All source observations in these checks
are fixtures/simulated transports; no real Tavily, PyPI, Gemini or paid request.

## Decisions and trust boundary

The security review demonstrated request substitution with a retained nonce,
unverified text in provider-owned ALLOW metadata, and a missing deployed server
concurrency flag. G now requires an explicit new receipt revision, independently
checks original request bytes, and projects permitted responses before signing.
No verification grammar, policy, evidence parser, model authority or cache changes.

Inspection covered AGENTS, README, architecture, the integration spike,
004D/E/G reports, the signer/ingress, core enforcement and existing receipt,
relay, lifecycle and verifier tests. Actual pinned source was inspected under
`artifacts/003c/upstream/`: transport commit
`e869c3f9adc96ea53c38694a21bb04a8e1085487`, core v1.14.1, Go 1.27.3 Linux/amd64.

| Pinned source | Relevant behavior |
| --- | --- |
| `transport/handlers/middlewares.go:fasthttpToHTTPRequest` | Copies actual buffered `ctx.Request.Body()` into `HTTPRequest.Body`. Large/streamed paths can omit this copy; absent capture must refuse signing |
| Same file, `TransportInterceptorMiddleware` | Calls HTTP pre-hooks before inference and applies their request object back to the transport; G hashes its received body in the earliest configured plugin |
| `transport/integrations/openai.go:openAIResponseConverter` | Converts the typed provider response to the OpenAI HTTP envelope before the transport post-hook |
| `transport/handlers/middlewares.go:runTransportPostHooks` | Copies buffered response entity bytes, calls post-hooks, and applies their modified body. Ordinary hook errors do not reliably enforce refusal |
| Same file, `applyHTTPResponseToCtx` and response-header hooks | Applies body/status/headers; later headers can change. Ingress independently checks actual received entity bytes and forwards only its own safe headers |

The signer retains only request-local copied strings/digests, never pooled request
or response pointers. Request capture is required to be nonempty and at most
64 KiB. A digest header has no authority. The two-second request receipt bound,
candidate/output bounds, immutable policy identity, no-store/cache absence,
typed terminal refusals and deadline profiles remain unchanged.

## Receipt contract and compatibility

G profiles `004g` and `004g-live` accept **only** `004g.receipt.v2` and policy
`004g.v1/bounded-prose-v1`. G plugin attestation configuration must name that
revision. Startup/reconfiguration with a mismatched mode/protocol fails closed;
readiness checks the revision as well as mode, placement and activity.

Canonical payload fields, in serialization order:

| Field | Meaning |
| --- | --- |
| `version` | `004g.receipt.v2` |
| `nonce` | Ingress-generated 256-bit random nonce, lowercase hex |
| `policy_id` | `004g.v1/bounded-prose-v1` |
| `outcome` | ALLOW / REJECT / UNAVAILABLE / PROVIDER_ERROR |
| `status` | Actual HTTP status |
| `body_sha256` | SHA-256 of the final projected HTTP entity |
| `candidate_sha256` | Exact approved content's UTF-8 digest for ALLOW; empty otherwise |
| `issued_at` | Trusted Unix seconds at signing |
| `request_sha256` | SHA-256 of exact HTTP request-body bytes received by Bifrost |

The existing encoding remains unpadded base64url(payload), a dot, then unpadded
base64url(HMAC-SHA256(key, payload)). Ingress retains the bytes passed to its
HTTP client, computes their digest itself and requires exact equality. Even
equivalent JSON reserialized with additional whitespace has a different binding.
Missing/empty fields, aliases, duplicates, extra fields, malformed encoding,
old revision, cross-policy, bad MAC, nonce/body/request mismatches and stale
receipts fail closed. Existing time tolerances remain request-start minus 2s,
future tolerance 2s and maximum issuance age 20s. No replay cache is added.

Explicit B-mode configurations using `004d.v1` and the old ingress profiles keep
their original wire/envelope/error behavior. They retain the known nonce-only
request binding and provider-metadata limitations; this task does not retroactively
upgrade their historical qualification. New G profiles never fall back to them.
The existing D/E qualifications verify this compatibility, not v2 security.

## Safe G response representation

After core conversion, the signer first checks that the buffered wire body still
corresponds to its executed decision and exact approved assistant content. It
then serializes an independent minimal entity and signs **those** bytes:

```json
{"choices":[{"finish_reason":"stop","index":0,"message":{"content":"<exact approved text>","role":"assistant"}}],"object":"chat.completion"}
```

The content string is preserved exactly after JSON decoding, including supported
ASCII separators. The complete provider envelope is deliberately not preserved.
The ingress independently requires this canonical minimal ALLOW representation.
Consumers requiring provider ID, model, usage or other full OpenAI SDK fields
must account for this intentionally narrower G response contract.

| Provider-controlled channel | G boundary |
| --- | --- |
| `id`, `model`, `system_fingerprint`, `service_tier`, `created` | Not copied into the protected entity |
| `usage`, including nested keys/values | Not copied; typed/shape failures may refuse earlier |
| `extra_fields`, provider/original/resolved model strings, `routing_info` including key labels | Entire structure discarded after correspondence checks; unknown/raw representations are refused |
| Nested/unknown metadata, annotations, tool/reasoning/multimodal forms | Existing eligibility/wire checks can refuse; none can add output to the projected entity |
| Provider response headers and diagnostics | Never forwarded by ingress. G signs only its body and receipt; transport headers are not claimed as semantically verified |
| Provider error text/codes/event metadata | G retains HTTP status and an allowlisted category, replaces the message/code with fixed safe values, and drops other fields |

G provider errors use code `epochguard_provider_error` and message
`Provider request failed.`. Categories are `invalid_request_error`,
`authentication_error`, `permission_error`, `rate_limit_error`, `server_error`,
or generic `provider_error`. Genuine errors preserve their core error identity
and fallback semantics; HTTP projection happens afterward. A successful fallback
must still pass evidence checks. PROVIDER_ERROR is never a factual verdict.
REJECT/UNAVAILABLE retain fixed policy errors and ingress reconstructs them.

Length limits, JSON validity and a valid MAC alone do not establish coverage of
provider metadata. Existing legacy wire validation is used only for correspondence
before G discards that metadata. Response Content-Length is updated for the new
entity before pinned transport application. Later body tampering breaks its MAC;
later header additions cannot reach the protected client through ingress.

## Resources and test independence

Both G Compose verifier services and the default G image command explicitly use
`--limit-concurrency 32` and `--no-access-log`. A static deployment regression
checks all three commands, preventing a Compose override from removing the flag.
A manually launched G live factory must likewise use that server flag; no new
live deployment is introduced here.

Server admission covers connections/tasks, including incomplete request bodies.
The evidence pipeline independently admits at most four active requests offline
(one in the separate opt-in live factory) with no waiter queue. The existing
ingress admits sixteen requests immediately. None of these is a host CPU/memory
quota, authentication control or a claim of general resource isolation.

The real operator overload check opens forty partial-body connections before
evidence admission, requires server 503 refusal, closes them, verifies zero active
evidence work/no source invocation change and then requires a valid 200 recovery.
The new deadline control needs two sequential 3s simulated operations under the
5s shared work deadline; it must never release an answer.

Receipt unit negatives create fresh, valid MACs for wrong request bindings,
missing fields, old revisions and cross-policy bodies, independently of the
signer's structs. Metadata tests inject a distinct sentinel for each channel.
The real relay modifies the request while cloning the original nonce; its
supported replacement has a separate 200 positive control. Reserialization and
model-field changes are tested too. These controls do not derive expectations
from the prose grammar's shared fixture labels. The tests retain the existing
cross-language grammar tables; no new claim of exhaustive differential fuzzing
or real-model quality is made.

## Commands and executed evidence

From repository root in Windows PowerShell, the complete current G reproduction:

```powershell
& .venv-003a/Scripts/python.exe tests/boundedprose/qualify.py --build
```

That driver builds the pinned native/base/verifier images, starts only private
networks with no published ports or live credentials, runs client/operator and
lifecycle checks, scans runtime logs in memory for candidate/sentinel leakage,
and removes the stack and signing-key volume. Raw runtime log lines are never
written by that scan. No receipt or key is exported.

Checks executed for this remediation:

| Check | Actual outcome |
| --- | --- |
| Final native build | PASS: plugin/ingress unit tests and race checks, plugin/ingress/provider/relay vet, formatting, CLI/proxy tests and ABI-matched native binaries. 234 PASS entries including subtests across the verbose unit groups |
| Combined offline Python suite | **572 passed, 1 live test deselected, 1 existing Starlette deprecation warning; 27.01s** |
| Updated G image build | **54 passed**; includes the new deployment-command regression |
| Real G client | PASS: 54 recorded inference checks (17 HTTP 200, one 400, six 403, 30 safe 503), plus route/streaming/network denials |
| Real G operator | PASS: 41 recorded inference checks (12 HTTP 200, one 400, one 403, 27 safe 503), plus server overload and source-free readiness checks |
| Real G lifecycle | Recovery 200; concurrent restart window 56 supported 200 and 25 safe 503; final recovery 200 |
| Real D host qualification | PASS: startup, client/operator, disable, concurrent restart and recovery under explicitly legacy protocol |
| Real E host qualification, default offline mode | PASS: all standard cases, source faults and fixture-evidence/live-mode rejection; no real-source execution |
| Existing 004B/C gateway | PASS: 49 PASS entries including subtests |
| Legacy verification | PASS: 39 PASS entries; live and separate long-profile tests skipped by that selection |
| Smoke / routes | PASS: 45 / 58 PASS entries including subtests |
| Separate long-deadline profile | PASS: HTTP 200 after waiting beyond the provider's 10s network timeout in the post-hook |

Go parent/subtest counts are not independent HTTP request counts. Native units
also prove new-to-old protocol rejection, mode/protocol configuration matching,
raw request capture independent of forged digest headers, missing body refusal,
metadata projection and fresh-MAC malformed/cross-policy/request-mismatch cases.

Final G operator samples (single-run fixture timings, not performance guarantees):

| Case | HTTP | Elapsed ms | Observation |
| --- | --- | --- | --- |
| Valid supported client response | 200 | 40.279 | Exact approved assistant content; minimal entity |
| Contradicted older claim | 403 | 32.129 | No original answer; terminal |
| Valid supported relay positive control | 200 | 28.654 | Proves the replacement is otherwise eligible |
| Retained-nonce request substitution | 503 | 31.294 | No substituted answer released |
| Equivalent JSON with changed serialization | 503 | 22.891 | Strict request-byte mismatch refused |
| Changed forwarded model field | 503 | 23.923 | Same nonce cannot waive request binding |
| Shared evidence work deadline | 503 | 5030.675 | No answer; subsequent admission recovered |
| Server overload recovery | 200 | 26.264 | Partial connections closed; no evidence calls from overload |
| Genuine provider fallback | 200 | 25.345 | Exactly two provider calls; successful fallback evidence-checked |
| Terminal policy refusal with fallback configured | 403 | 25.961 | Exactly one provider call |

Each id/model/fingerprint/tier/usage/extra-fields/routing/nested sentinel case
returned a safe minimal 200 or 503; the header/raw-response/annotation controls
were refused with 503. The provider-error sentinel returned safe 400 with its
allowlisted category and fixed code/message. No sentinel was present in any
client body/header; no candidate or metadata sentinel appeared in the checked
runtime logs. Both original attack classes have regression coverage against
the real native plugin and actual ingress, rather than a mocked loader.

Final tested native image: `sha256:7820344dee00851c7090bdf5f4658596aeeb78229b1e5b9f67af7e246faf0aa4`.
Final tested G image: `sha256:b69987666e61d1ca4536ce7393ea243c4cef8dc1ba9f1653c619bb02d1e368bf`.
After cleanup only the pre-existing buildx builder container remained.

The final native build command was:
`docker buildx build --builder epochguard-002a --load -t epochguard-dev:002a -f dev/Dockerfile .`.
Verifier 004C was rebuilt with its existing Dockerfile/buildx command, then 004E
and G with `docker build -t epochguard-verifier:004e -f services/verifier/Dockerfile.004e .`
and `docker build -t epochguard-verifier:004g -f services/verifier/Dockerfile.004g .`.
The updated G driver was executed after these builds. Existing D/E and broader
regressions ran against the same security implementation; final G additionally
ran the final fallback/unique-sentinel/isolation test refinements.


The combined Python command uses the current source tree read-only and no network:

```powershell
docker run --rm --network none --mount "type=bind,source=$($PWD.Path),target=/src,readonly" --workdir /src/services/verifier -e PYTHONPATH=/src/services/verifier:/src/services/claim_analysis -e PYTHONDONTWRITEBYTECODE=1 epochguard-verifier:004g python -B -m pytest -c /src/services/verifier/pytest.ini -p no:cacheprovider /src/services/verifier/tests /src/services/verifier/tests_multiclaim /src/services/verifier/tests_gateway /src/services/verifier/tests_live /src/services/verifier/tests_prose /src/services/verifier/tests_bounded_prose /src/services/claim_analysis/tests -q
```

Existing offline compatibility/regression commands, also executed:

```powershell
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

Each Compose regression was followed by matching `down --volumes --remove-orphans`;
host drivers use `finally` cleanup. Go race results cover unit execution, not the
real gateway process. Gateway concurrency/lifecycle results are separate HTTP
observations. Logs/results are ignored local `artifacts/004gs/` plus the existing
drivers' offline reproduction directories; 004E live evidence is preserved.

## Changed files and residual risks

17 existing files edited and four added:

| Exact paths | Change |
| --- | --- |
| `plugins/epochguard/attestation.go`, `plugins/epochguard/decision.go` | Received-byte request capture, explicit protocol/mode agreement, v2 signing and safe response/error projection |
| `plugins/epochguard/security_test.go` (new) | Request capture, forged header, metadata projection, protocol/configuration and provider-error negatives |
| `internal/ingress/ingress.go`, `internal/ingress/prose_test.go` | Mandatory v2 parsing for G, independent request digest, minimal-body validation, protocol-aware isolation tests |
| `internal/ingress/security_test.go` (new) | Fresh-MAC request/receipt/metadata attacks and old-profile rejection |
| `cmd/provider-fixture/main.go`, `cmd/receipt-relay/main.go` | Explicit test-only metadata channels and retained-nonce request substitutions |
| `compose.verify.004g.yaml`, `dev/prose/gateway.json` | Explicit new receipt configuration, metadata fixture opt-in, server caps |
| `services/verifier/Dockerfile.004g`, `services/verifier/tests_bounded_prose/simulated.py` | Packaged static-check inputs and offline work-deadline fixture |
| `services/verifier/tests_bounded_prose/test_security_deployment.py` (new) | Regression for every packaged G server concurrency command |
| `tests/boundedprose/runner.py`, `tests/boundedprose/qualify.py` | Actual request/metadata/overload/fallback/deadline/log-isolation assertions and cleanup |
| `dev/Dockerfile` | Vet the modified test fixture binaries in the existing native build |
| `AGENTS.md`, `README.md`, `docs/architecture.md`, `docs/task-004g.md` | Current protocol, metadata and compatibility guarantees |
| `docs/task-004gs.md` (new) | This security decision and actual evidence |

Legacy Python policies/contracts, grammar/model/planner code, dependency locks,
old Compose/configuration files and historical D/E reports were not modified.


Trusted: host/kernel, pinned binaries, verifier/evidence policies, configured
plugins, clock, private networking, management and signing key. The private
verifier hop remains unauthenticated HTTP. This binds requests to received bytes;
it does not authenticate who may execute a gateway request, guarantee at-most-once
execution, or prevent an active private relay from repeating identical requests.
Receipt replay across ingress calls is refused by fresh nonces. No new replay or
response cache, broad authentication, origin-freshness attestation, atomic revocation
or safe streaming is introduced. Strict byte binding may refuse benign JSON
rewrites; that is intentional. Legacy D/E profiles retain their known limits.

The fixture provider, synthetic evidence and one machine's timings do not qualify
a commercial model, current live facts, production availability or general prose.
The 004F planner stays non-authorizing. **004G LIVE QUALIFICATION PENDING.**

**Decision: APPROVE for the scoped offline 004G-S remediation**, supported by
the request-substitution/metadata negatives and the unit, race and actual gateway
regressions above. Maintainer review and separately authorized live qualification
remain outstanding. Static checks also passed: 29 Markdown files, 171 local
links, 11 anchors, syntax/JSON/whitespace checks and `git diff --check`.

Recommended commit:
`fix(security): bind protected prose requests and strip provider metadata`.
No commit or push; stop for maintainer review.
