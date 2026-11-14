# Task 004D: protected ingress and deployment integrity

Implemented and qualified offline on November 14, 2026 (Asia/Calcutta), starting
from clean `main` at `257946d`. The protected client entry point now refuses
unchecked responses when EpochGuard is absent or disabled. This applies to the
new isolated profile, not every Bifrost route/deployment. No commit, push, live
Tavily/PyPI/Gemini call or public deployment was performed.

## Invariant, scope and threat model

**No successful, unverified provider answer may be released through this
protected entry point.** Every inference response is buffered and checked for
authenticated evidence of the current request's enforcement decision. Readiness
or unsigned diagnostic headers cannot authorize release.

The attacker may control client methods, raw targets, headers (including case
variants/duplicates), JSON bodies and candidate instructions. Tests also model
missing/disabled/failed plugins, bad configuration, unavailable verifiers,
transport failures and a relay that can mutate or replay gateway responses
without the signing key. These must not turn an unchecked answer into client
HTTP 200. The supported inference surface is only buffered JSON
`POST /openai/v1/chat/completions`, with the exact 004B template policies and
plain response format qualified by 004C. `GET /ready` returns a fixed readiness
result; all management and alternate inference paths are denied.

Trusted: the host/kernel and Docker network isolation, pinned gateway/native
plugin and ingress binaries, secret provisioning, clock, deployment/operator
configuration, private management access and existing verifier/evidence policies.
HMAC does not solve compromised processes/hosts, leaked keys, malicious
administrators, an untrusted verifier or origin freshness. The private
gateway-to-verifier hop remains unauthenticated. This is not production client
authentication, encryption, a general proxy, safe streaming or protected caching.

## Pinned lifecycle findings

Inspection covered AGENTS, README, architecture, the integration spike, Tasks
003B/C/004B/C, all plugin enforcement/HTTP/guard code, existing Go tests, 004C
Compose/configuration and gateway/route qualification. HEAD and status were
checked before editing. Actual cached upstream sources were inspected under
`artifacts/003c/upstream/`: transport commit
`e869c3f9adc96ea53c38694a21bb04a8e1085487`, core v1.14.1, matching framework/native
loader and Go 1.27.3 Linux/amd64 build graph. No Bifrost core or hook is invented.

| Source / behavior | Consequence |
| --- | --- |
| `transport/server/plugins.go:loadCustomPlugins`, framework `plugins/soloader.go` | Disabled plugins are skipped; load/Init failures can leave a healthy server without enforcement. EpochGuard's own Init already retains hooks with an unavailable policy on bad configuration; a separate failing-Init `.so` qualifies the loader failure case |
| `transport/handlers/plugins.go`, `server/server.go:ReloadPlugin/RemovePlugin` | Private management can disable/remove a plugin at runtime; startup checks alone are insufficient |
| `transport/handlers/middlewares.go:TransportInterceptorMiddleware/runTransportPostHooks/fasthttpResponseToHTTPResponse` | Buffered post-hooks receive copied entity-body bytes; streaming/large-body paths can omit them. An ordinary post-hook error applies the current response and is not a reliable refusal |
| Same middleware's `runTransportResponseHeadersHooks` and later middleware | Headers may still change after post-hooks; the post-hook snapshot is not assumed to be final wire output |
| Existing core `PostLLMHook/enforce` and typed `BifrostError` | Genuine provider failures can be distinguished from policy refusals before transport conversion; refusal still discards answers and disables fallback |

The implementation therefore does not rely on a post-hook error to block
delivery. It signs a checked buffered snapshot, then the independent ingress
compares the authenticated digest with the entity bytes/status it actually
received. Later mutation causes refusal. No-body/streamed paths cannot produce
a release receipt. HTTP framing is not signed; the complete decoded HTTP entity
body is, with automatic content decompression disabled and encoded replies denied.

## Implemented flow and receipt

```text
Client network -> ingress: strict route/body/admission checks, replace all headers
  -> fresh random nonce -> private Bifrost -> existing typed enforcement
  -> request-owned final outcome / verified candidate or genuine error fields
  -> HTTP post-hook checks content correspondence and current policy identity
  -> HMAC receipt over status + body digest + outcome + nonce + policy + time
  -> ingress buffers actual body, authenticates receipt and validates bindings
  -> unchanged ALLOW / safe 403 or 503 / authenticated genuine provider error
```

Plugin configuration adds an optional `attestation` object with protocol
`004d.v1` and a trusted `secret_file` path. It is accepted only with the explicit
`004b.v1` HTTP verifier mode, never a fixed decision source. Missing/invalid
configuration or credentials clears active policy and cannot issue a receipt.
No secret value is stored in configuration/Git or printed. All existing profiles
omit this object and retain their prior behavior.

The ingress creates a cryptographically random **256-bit nonce** per round trip
and forwards only its own nonce, JSON content type and identity encoding header.
Client nonce, receipt, raw-response, bypass, management and other headers are
not forwarded. The plugin captures a request-owned pointer to the immutable
active policy. Each fallback replaces the previous outcome. Signing requires
the same policy still active, so removal or reconfiguration cannot reuse an old
decision/key snapshot. Only bounded copied strings/integers are retained; no
pooled Bifrost response/error object is retained after the core hook.

For ALLOW, post-hook parsing requires one plain terminal assistant message whose
content exactly equals the candidate allowed by the existing 004B source.
Unknown/duplicate/aliased body fields, raw payloads and other answer forms cannot
be signed. Bounded protocol metadata remains metadata, not additional verified
claims. For a genuine provider error, the final error code/type/message and
status must match bounded fields copied from the original non-Bifrost provider
error. Policy refusals use their existing typed outcomes. Signing never follows
merely seeing a loaded plugin or an HTTP success status.

The internal header is `X-EpochGuard-Internal-Receipt`:

```text
base64url_without_padding(canonical_JSON_payload)
    + "." + base64url_without_padding(HMAC-SHA256(secret, payload_bytes))
```

Its canonical JSON fields, in order, are:

| Field | Binding |
| --- | --- |
| `version` | `004d.v1` |
| `nonce` | This ingress call's fresh 64-character lowercase hex nonce |
| `policy_id` | `004b.v1/multi-claim-templates-v1` |
| `outcome` | `ALLOW`, `REJECT`, `UNAVAILABLE` or `PROVIDER_ERROR` |
| `status` | Exact upstream HTTP status |
| `body_sha256` | SHA-256 of the complete buffered HTTP entity body |
| `candidate_sha256` | Exact allowed assistant text digest for ALLOW; empty otherwise |
| `issued_at` | Trusted Unix seconds at signing |

The ingress uses constant-time `hmac.Equal`, strict base64 decoding, exact
canonical JSON (no unknown/duplicate/alias/missing fields), fixed version/policy,
exact nonce/status/body binding and valid outcome/status pairs. ALLOW also
requires the assistant content to match its candidate digest. Receipt time must
fall within request-start minus two seconds through receipt-check plus two
seconds, and receipt age cannot exceed twenty seconds. Fresh unpredictable
nonces prevent replay across requests/concurrent calls without an unbounded
global replay cache. Receipts have a 2,048-character bound.

The tiny signer and verifier wire structs are independently defined in the two
existing Go module boundaries, without changing the gateway/plugin dependency
graph or adding crypto libraries. Unit attacks and real gateway qualification
test their interoperability. Hashes identify bytes; the HMAC authenticates the
configured signer, not source truth, source consultation or publication age.

## Release, bounds and ownership

| Authenticated result | Client behavior |
| --- | --- |
| ALLOW + HTTP 200 | Original buffered entity body unchanged |
| REJECT + HTTP 403 | Fixed safe policy refusal, preserving code/type/message |
| UNAVAILABLE + HTTP 503 | Fixed safe unavailable refusal |
| Eligible PROVIDER_ERROR + HTTP 400..599 | Original authenticated error status/body |
| Missing/invalid receipt, transport failure or unqualified error shape | Generic fixed ingress 503; upstream body discarded |

Unsupported requests get a safe local refusal (400, or 413 for body receipt
failure/oversize). Provider errors that cannot be authenticated under the narrow
shape become ingress 503, never success. Error text is not a factual verification
result. Core provider-error pointer identity and fallback semantics remain
unchanged. Authenticated policy errors are reconstructed from plugin-owned safe
fields so rejected provider content cannot leak via refusal metadata.

The ingress buffers before any answer/status release. Limits: 64 KiB request,
256 KiB upstream entity body, two-second body receipt, eight-second shared
request context and transport timeout, sixteen active requests with immediate
overload refusal, and bounded server read/header/write/idle timeouts. The body
read deadline is cleared after successful receipt so it does not become an
accidental two-second verification deadline. All upstream responses close on
every path; cancellation propagates through the HTTP request context. Inference
POST replay/redirect/proxy discovery/automatic decompression are disabled. There
is no unchecked retry, alternate gateway/model, cache or streaming release.

Only safe ingress-owned headers are returned. Internal receipt/nonce and legacy
diagnostic headers, cookies and arbitrary upstream headers are not forwarded.
No response/candidate/evidence/credential or arbitrary transport exception is
written to new diagnostic logs. The signing key is immutable process-owned
memory; each request's trace/digests/body are released after its synchronous call.

## Readiness, lifecycle and network separation

`GET /ready` performs fresh bounded checks, without a cached ready flag:

1. Reachable gateway, using health only as a reachability check.
2. Loaded EpochGuard, active/enabled state, pre_builtin/order zero, expected
   verifier mode and attestation protocol, semantic cache absent.
3. A controlled fixture request returning authenticated ALLOW evidence.

Management uses the local-development setup token only on the private network;
it is never forwarded from or returned to clients. Readiness expresses current
eligibility; **every** inference still needs its own receipt even after readiness
was successful. Bad management state cannot enable a response without a MAC.
The server can start before Bifrost and safely refuse until it becomes available.

`compose.verify.004d.yaml` creates distinct internal `client` and `private`
networks, with no host ports. Only ingress instances bridge them. Gateways,
provider, verifier fixtures, management and relays are private-only. The client
runner is attached only to `client`; the operator runner is attached only to
`private` for explicit test controls and unsafe comparison probes. Clients were
unable to connect by private service names or the known gateway IP `10.77.14.10`.
The gateway's static address is outside the private automatic allocation range.
Existing 003A/004C deployments remain unchanged, without this topology or secret.

An isolated initialization job generates a random fixture key into a Docker
volume, with file owner 10001 and mode 0600. Signer/ingress mount it read-only;
clients and test relays never mount it. Initialization preserves an existing
valid key across dependency/container restarts. Another independently generated
file supplies the wrong-key control. No real/development signing secret is
committed. Full qualification cleanup destroys the task's fixture volume.
This is a test provisioning arrangement, not production key rotation/management.

Runtime tests first established readiness, then used the pinned private plugins
API to disable EpochGuard while four requests were in flight. Direct Bifrost
then returned unchecked content, while ingress refused it and readiness became
503. Restarting Bifrost reset its tmpfs configuration database, reloaded the
file configuration and recovered authenticated delivery with the same key.
Four concurrent clients also spanned an actual stop/start: the reproducible run
observed **536 supported / 38 safe refusals / recovered=true** in 30.10s. An
earlier manually controlled final-binary run observed 380/231/recovered=true in
30.21s. These are fixture observations, not throughput benchmarks.

## Security qualification and outcomes

| Real gateway case | Actual protected outcome |
| --- | --- |
| Two supported independent claims | HTTP 200, original answer unchanged |
| Contradicted requests claim | Terminal 403 without answer leakage |
| Uncovered assertion / missing evidence / unavailable or timed-out verifier | Safe 503; authenticated unavailable retained where applicable |
| No plugin, failed Init, failed load, invalid configuration | Ingress 503 and not-ready, despite a reachable gateway |
| Runtime disable after readiness | Subsequent unchecked direct answers refused at ingress |
| Wrong key / missing receipt / fake diagnostic markers | Ingress 503 |
| Wrong MAC, mutated body/status, old nonce/receipt, wrong policy/version, duplicate receipt | Ingress 503 |
| Partial, stalled or oversized upstream response | Ingress 503; no partial answer release |
| Genuine fixture provider error | Original authenticated HTTP 400/error body |
| Primary error then contradicted usable fallback | Terminal 403; exactly two provider calls |
| Streaming, async, tools, unsupported APIs/management/methods/encoded targets/type | Local denial; no unchecked output |
| Direct access from client network | Private listeners unreachable, including by known IP |

Tests include signed valid-MAC wrong-version/policy/outcome/binding payloads,
duplicate/case-variant JSON, time windows, malformed base64/signatures, receipt
replay across concurrent requests, spoofed/duplicate internal headers, bounded
admission, cancellation, invalid keys/configuration, post-decision content
mutation, reconfiguration between hooks and idempotent key initialization.
Independent unsafe controls confirm direct no-plugin/disabled gateways really
can deliver unchecked answers; the protected entry points refuse those bytes.
The relays select faults only through separate private test control APIs, never
from inference headers/prompts, and cannot access the signing key.

## Files created and changed

Modified: `plugins/epochguard/{main.go,decision.go}` for additive configuration
and request-owned outcome/signing calls; `dev/Dockerfile` for the new standard-Go
components/tests and native failure control; README and architecture boundaries.

New implementation: `plugins/epochguard/attestation.go`,
`internal/ingress/ingress.go`, `cmd/protected-ingress/main.go`.

New tests/fixtures: adjacent Go unit tests; `cmd/receipt-relay/main.go` (explicit
test-only post-receipt relay); `tests/initfailure/main.go` (deliberate native Init
failure); `tests/protectedingress/{ingress_test.go,qualify.py}`;
`compose.verify.004d.yaml`; five `dev/ingress/gateway*.json` configs and the
synthetic probe text. The lifecycle driver runs Docker from the host; no Docker
socket or daemon credentials are mounted in any container. This report is the
only new documentation file.

The factual 003A/004A/004B contracts, policies, grammar, Go 004B validator,
request/hash checks, typed `enforce`/refusal functions, caching configuration,
live profile and all pre-existing deployment/configuration/test files remain
unchanged. Module/dependency manifests and Bifrost source are unchanged.

## Reproduce and executed checks

From repository root, with Docker Desktop Linux containers, Compose and host
Python available (the driver uses only Python's standard library):

```powershell
& .venv-003a/Scripts/python.exe tests/protectedingress/qualify.py --build
```

This exact command was executed successfully. It builds both pinned images,
starts ingress before gateway, checks startup refusal, brings up private
fixtures/gateways, runs client/operator attacks, disables the plugin, restores
configuration by restart, runs concurrent restart/recovery, and always removes
the 004D stack/networks/generated fixture-key volume. Existing images can be
used by omitting `--build`. Logs are under ignored
`artifacts/004d/reproduction/`.

Core Docker phases executed by that driver are independently runnable:

```powershell
docker buildx build --builder epochguard-002a --load -t epochguard-dev:002a -f dev/Dockerfile .
docker buildx build --builder epochguard-002a --load -t epochguard-verifier:004c -f services/verifier/Dockerfile.004c .
docker compose -f compose.verify.004d.yaml up -d ingress
docker compose -f compose.verify.004d.yaml run --rm --no-deps qualification-client /app/protectedingress.test '-test.run=^TestClientStartupOffline$' '-test.v' '-test.timeout=60s'
docker compose -f compose.verify.004d.yaml up -d --wait gateway gateway-control gateway-invalid gateway-initfail gateway-loadfail receipt-relay ingress-faults ingress-unsafe ingress-badkey ingress-unavailable
docker compose -f compose.verify.004d.yaml run --rm --no-deps qualification-client
docker compose -f compose.verify.004d.yaml run --rm --no-deps qualification-operator
docker compose -f compose.verify.004d.yaml run --rm --no-deps qualification-operator /app/protectedingress.test '-test.run=^TestOperatorDisable$' '-test.v' '-test.timeout=60s'
docker compose -f compose.verify.004d.yaml down --volumes --remove-orphans
```

The driver additionally orchestrates stop/start while the concurrent observer is
active; it never mounts a Docker socket into test services. It resets only the
task-owned 004D fixture profile. All live APIs remain unused.

Exact regression commands executed:

```powershell
$env:PYTHONPATH = 'services/verifier'
& .venv-003a/Scripts/python.exe -m pytest -c services/verifier/pytest.ini services/verifier/tests -q
$env:PYTHONPATH = 'services/claim_analysis'
& .venv-003a/Scripts/python.exe -m pytest -c services/claim_analysis/pytest.ini services/claim_analysis/tests -q
$env:PYTHONPATH = 'services/verifier;services/claim_analysis'
& .venv-003a/Scripts/python.exe -m pytest -c services/verifier/pytest.ini services/verifier/tests_multiclaim services/verifier/tests_gateway -q
docker buildx build --builder epochguard-002a --progress plain --target qualification-unit --no-cache-filter qualification-unit -f artifacts/004d/Dockerfile.unit .
docker compose --profile test up -d --force-recreate --wait provider gateway gateway-control gateway-reject gateway-unavailable
docker compose --profile test run --rm --no-deps smoke
docker compose --profile test down --remove-orphans
docker compose -f compose.verify.yaml run --rm verification-tests
docker compose -f compose.verify.yaml down --remove-orphans
docker compose -f compose.verify.004c.yaml up -d --force-recreate --wait --no-build gateway gateway-faults gateway-control
docker compose -f compose.verify.004c.yaml run --rm --no-deps qualification
docker compose -f compose.verify.004c.yaml down --volumes --remove-orphans
docker compose -f compose.routes.yaml up -d --wait reject control warp-control warp-reject nolog
docker compose -f compose.routes.yaml run --rm --no-deps route-tests
docker compose -f compose.routes.yaml down --volumes --remove-orphans
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml up -d --wait gateway-supported
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml run --rm --no-deps verification-tests
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml down --remove-orphans
git diff --check
```

`artifacts/004d/prepare_unit.py` constructs the ignored fresh qualification
Dockerfile by appending a target to the actual final `dev/Dockerfile`. It runs
plugin module verification, then network-disabled cache-mounted `gofmt`, `go
vet`, `go test -count=1 -mod=readonly -trimpath -v ./...`, and
`go test -count=1 -race -p=2 -mod=readonly -trimpath ./...` in the plugin module.
The root-module stage separately checks formatting/vet for ingress, CLI, relay
and gateway tests, then fresh unit and race tests for ingress/key initialization.
The regular native build also runs its plugin and ingress tests/race checks.

| Final check | Actual result |
| --- | --- |
| Fresh plugin unit suite | 31 top-level / 107 subtests; passed, 0.246s |
| Fresh plugin race detector | Passed, 1.303s; no race report |
| Fresh ingress + key-initialization units | 9 top-level / 26 subtests (8 ingress tests + 1 key test); passed, 0.524s / 0.004s |
| Fresh ingress/key race detector | Passed, 1.553s / 1.014s; no race report |
| Formatting and vet | Passed for plugin and new root components/tests |
| Real protected client suite | 4 top-level / 18 subtests passed |
| Real private operator adversarial suite | 4 top-level / 19 subtests passed |
| Startup, runtime disable, recovery and concurrent restart | All passed as separately selected lifecycle phases |
| Existing Python verifier | 65 passed; one live test explicitly deselected; 5.92s; existing Starlette warning |
| Existing 004A | 176 passed; 2.42s |
| Existing 004B + 004C endpoint | 168 passed (149 + 19); 4.12s |
| Existing smoke | 10 top-level / 35 subtests passed |
| Existing 003A gateway/service | 8 top-level / 31 subtests passed |
| Existing 004C gateway | 7 top-level / 42 subtests passed |
| Existing 003C routes | 4 top-level / 54 subtests passed |
| Existing long-deadline profile | Passed in 12.60s; HTTP 200, first byte 12,585ms / total 12,586ms; provider/retrieval deltas 1/1 |
| Full host-side `qualify.py --build` reproduction | Passed through final recovery and cleanup |

Race results cover unit execution, not the live Bifrost/ingress processes. The
short 003A runner explicitly skips its live and separate long test; the latter
was executed separately. The Python live marker remains explicitly deselected.
No live qualification or isolated cache-lifecycle rerun is claimed.

Development failures were retained under `artifacts/004d/`: Docker Desktop was
initially stopped; the first cancellation fixture failed/hung because it did
not consume its upstream HTTP body before waiting for disconnect. The initial
build was cancelled after identifying its exact task-owned Docker processes;
the corrected fixture consumes the body and explicitly cancels the client.
One startup test command stopped in Go flag parsing due an unquoted dotted
PowerShell flag; the corrected command made the intended assertions. The first
full stack had an IP allocation collision, causing supported/refusal/readiness
assertions to fail because the protected gateway never started. Reserving the
static gateway address outside automatic allocation fixed that deployment
defect. Requalification after those corrections passed; no assertion was weakened
or live failure retried to manufacture success.

The tested/reproduced native image is
`sha256:91ff1bc8c099b5939531e0917b63170bb2f130a7ac26349ec2fc683265a28b6c`.
Plugin SHA-256 is
`e4e78b585bd55ac0a1f2478874fdb277fb43e28540613c84caa02ad07b811bba`.
The reproduction build and regression image had identical gateway, plugin,
ingress and qualification-runner binary hashes. These identify local tested
artifacts, not published releases. Task-owned stacks and fixture-secret volumes
were removed; only the pre-existing BuildKit builder remains running.

The final scope audit passed: five existing files modified and eighteen files
added. Existing verification contracts, policies, grammar, validators, deployment
profiles and tests remain unchanged; the typed refusal/enforcement functions are
byte-identical to the starting revision. Syntax, JSON, whitespace, final newlines,
Markdown fences, all 54 local documentation links and `git diff --check` passed.
The final isolated Compose configuration also passed `config --quiet`.

## Remaining boundaries and review

This protects the configured ingress route under the stated trust assumptions,
including when the plugin disappears. Direct legacy deployments and private
administrative access are not transformed into protected public entry points.
General prose, additional policies/providers, live multi-claim evidence, origin
freshness, malicious/compromised verifier protection, production TLS/client auth,
secret rotation, broader routes/background work, safe streaming and protected
caching remain outside qualification. MACs do not make an untrusted host or
verifier trustworthy. Unsupported error shapes may become generic ingress 503.
Network failure after a fully validated response starts writing to the client
does not provide atomic network delivery; upstream partial bodies were held and
refused before any answer release.

Recommended conventional commit, not created:
`feat(ingress): require authenticated enforcement receipts`.

Stop at Task 004D for maintainer review. No commit or push.
