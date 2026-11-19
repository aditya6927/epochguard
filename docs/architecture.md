# Architecture and security contracts

See [compatibility](compatibility.md) for the exact supported build/ABI boundary, [security](security.md) for attacker/trust assumptions and [evaluation](evaluation.md) for offline, live and experimental evidence.

EpochGuard buffers AI gateway answers, checks fixed evidence policies, and refuses responses whose required claims cannot be authorized. Its current protected surface is one non-streaming chat route and a finite claim language. It is not a general factual verifier or a production authentication system.

## Capabilities and evidence status

| Mode / component | Implementation and qualification |
| --- | --- |
| `004g.v1` / `bounded-prose-v1` | Implemented; **narrow live acceptance reviewed and met** on November 15, 2026, using real sources and a controlled provider. Nine sentence forms, independent Go/Python parsing, request-bound receipt v2 and minimal response projection. [Inspected evidence](task-004gl.md#reviewed-live-qualification--november-15-2026) |
| `004b.v1` / `multi-claim-templates-v1` | Implemented; exact two-template language. Narrow November 14, 2026 **live** source qualification through legacy protected ingress, assessed from maintainer-authorized reports; controlled provider, v1 receipt |
| `003a.v1` / `python-windows-latest-v1` | Legacy single-template endpoint; narrow November 8, 2026 **live** gateway qualification from maintainer-supplied execution evidence |
| `004a.v1` identification and `004f.prose-plan.v1` planning | Experimental; non-authorizing, draft datasets, independent model-quality qualification pending |
| 005C native Gemini qualification | **Narrow real-model enforcement qualification reviewed and met** November 19, 2026: `gemini-3.5-flash-lite`, strict pre-conversion adaptation, simulated evidence, four model cases and six expected client outcomes. Shared typed eligibility remains strict. Real-model plus real-source execution and draft analysis quality remain unqualified. [Reviewed scope](task-005c-t.md#reviewed-real-model-qualification--november-19-2026) |
| EpochGuard-owned protected cache / atomic revocation | Proposed in [ADR 0003](decisions/0003-protected-cache-ownership.md); not implemented |

The live multi-claim runner printed `LIVE RUN COLLECTED: independent result review required`. Subsequent inspection found its five client expectations met; three attempted/completed application-level retrievals per source were recorded, not billing or origin-fetch counts. See [004E evidence](task-004e.md), [legacy live evidence](task-003b.md) and [current security regression evidence](task-004gs.md). These reports qualify their stated revisions and finite test cases, not arbitrary provider/model compatibility or production readiness.

## Components and responsibilities

| Component | Responsibility and owned state |
| --- | --- |
| [Protected ingress](../internal/ingress/ingress.go) | Route/body admission, retained forwarded bytes, fresh nonce, complete upstream buffering, independent receipt/body checks and safe client release |
| Pinned Bifrost HTTP gateway | Provider dispatch, conversion to HTTP response, plugin pipeline and management. Management/background execution is outside the protected answer route |
| [Go plugin](../plugins/epochguard/) | Typed request guard, synchronous evidence decision, independent grammar/contract validation, terminal refusals, response projection and signing |
| [Python verifier](../services/verifier/) | Strict request/result schemas, bounded grammar parsing, fixed evidence retrieval, source parsing, comparisons and deterministic aggregation |
| [Claim analyzer](../services/claim_analysis/) and [prose planner](../services/verifier/verifier/prose/) | Optional proposals, exact quote alignment, independent bounded audit and evaluation; never an authorization authority |
| Fixture provider, relays and qualification runners | Test-only controlled candidates, faults, observations and assertions; not production components |

The native build pins Bifrost HTTP `transports/v2.4.0` at `e869c3f9adc96ea53c38694a21bb04a8e1085487`, core `v1.14.1`, framework `v1.11.1`, semantic cache `v1.7.4`, and Go `1.27.3` Linux/amd64. Host/plugin module graphs and build flags match. The gateway is dynamically linked; stock static gateway binaries cannot load this `.so`. [Integration findings](bifrost-integration-spike.md) and [ADR 0001](decisions/0001-native-bifrost-plugin.md) explain this compatibility boundary. No Bifrost core fork is required.

## Local presentation boundary

The [Verification Lab](verification-lab.md) adds a React/TypeScript UI and a Go standard-library backend in front of the unchanged protected ingress. The backend has two fixed ingress targets, constructs the provider request with the exact editor text and presents only validated minimal response shapes. It is not an alternative verifier and never consumes planner output. Only the Lab publishes a loopback port; its host-entry/client networks provide no browser route to private gateway, verifier, provider or management services. Existing simulated G transports support repeated interaction; G-L's one-shot/three-call qualification instrumentation is not used for the interactive service. The diagram shown in the UI is conceptual, with only browser round-trip latency measured.

## Request and response flow

```mermaid
sequenceDiagram
    participant C as Client
    participant I as Protected ingress
    participant G as Bifrost + Go plugin
    participant P as Provider
    participant V as Python verifier
    participant S as Fixed evidence sources
    C->>I: Buffered chat request
    I->>G: Retained body bytes + fresh nonce
    Note over G: Capture digest of received HTTP body
    G->>P: Qualified provider request
    P-->>G: Candidate or genuine provider failure
    G->>V: Candidate, trusted ID and binding
    V->>S: Fixed-URL bounded retrievals
    S-->>V: Untrusted source bodies
    V-->>G: Typed claims, evidence and verdicts
    Note over G: Independently validate; project final entity; sign
    G-->>I: Buffered HTTP response + receipt
    Note over I: Verify protocol, MAC, request, outcome and entity
    I-->>C: Exact approved content or safe refusal/error
```

1. Ingress admits only buffered `POST /openai/v1/chat/completions`, with bounded bodies and a fresh 256-bit nonce. It forwards no client headers; client-supplied nonce/digest/bypass/auth/management headers have no authority.
2. The earliest configured Go HTTP pre-hook captures the digest of Bifrost's actual received body. The pinned transport copies buffered `ctx.Request.Body()` into `HTTPRequest.Body`; absent, empty or oversized capture cannot authorize a bounded-prose receipt.
3. HTTP and typed core guards refuse unsupported request modes. For a successful eligible provider candidate, `PostLLMHook` waits synchronously for verification. No answer is released during that wait.
4. Python derives the required claims and performs sequential evidence checks. Go independently reconstructs the complete grammar, validates strict result bindings/evidence and recomputes aggregation.
5. REJECT/UNAVAILABLE return nil response and a typed terminal `BifrostError` with `AllowFallbacks=false`. Ordinary Go hook errors and diagnostic headers are not enforcement mechanisms.
6. After Bifrost converts the typed response to its HTTP entity, the transport post-hook verifies correspondence with the executed decision, projects permitted metadata, and signs the final entity bytes. Ingress buffers and validates the actual received entity before release.

The request-owned trace is shared between transport and core contexts and protected by a mutex. It retains copied bounded strings/digests, not pooled request/response pointers. Immutable policy snapshots are atomically published; an absent policy cannot ALLOW. Signing also requires the same policy still active. Each fallback replaces the prior attempt's attestation state.

## Claim language and evidence validation

Three private verifier endpoints have separate contracts:

| Endpoint | Contract | Candidate language |
| --- | --- | --- |
| `POST /v1/verify` | `003a.v1` | One exact Python Windows release-label sentence |
| `POST /v1/verify/multiclaim` | `004b.v1` | One to eight sentences from two exact templates |
| `POST /v1/verify/prose` | `004g.v1` | One to eight sentences from nine exact ASCII forms |

Trusted process configuration selects the mode, evidence source mode and policy. Inference headers, prompts and model output cannot choose them. The [verifier guide](../services/verifier/README.md#supported-response-languages) specifies exact syntax, separators, version bounds and examples.

Bounded prose binds original text/digest/spans separately from reconstructed canonical comparison sentences. Python derives mappings from original text; Go independently rederives the whole original/canonical relationship, including count, order, offsets, IDs and hashes, before checking the embedded two-policy evidence result. A COMPLETE grammar parse establishes coverage only within that finite syntax. It does not prove general semantic completeness or the correctness of a model's claim selection.

| Policy | Fixed observation and checks |
| --- | --- |
| `python-windows-latest-v1` | Tavily Extract of `https://www.python.org/downloads/windows/`; require expected stable Windows context and a unique primary `Latest Python 3 Release - Python V` label |
| `pypi-requests-reported-v1` | GET `https://pypi.org/pypi/requests/json`; require exact `info.name == "requests"`, canonical numeric `info.version`, and boolean `info.yanked == false` |

Candidates are not sent to Tavily. PyPI descriptions/links are ignored; no source body can select a URL, policy or instruction. Retrieval disables redirects and environment proxies, limits bodies to 1 MiB and uses fixed deadlines. Malformed/duplicate/nonfinite JSON, wrong identity/context, ambiguous labels or unsupported version shapes cannot authorize release.

An equal numeric version is SUPPORTED; an older candidate is CONTRADICTED; an ahead-of-observation candidate is INSUFFICIENT because the source may lag. Observation times must satisfy the local -2..60-second window. They measure receipt of extracted content, not origin publication time, fetch age, installability, compatibility or security.

Evidence binds the configured URL, `fixture` / `tavily_live` / `pypi_live` mode, retrieval ID, raw-content hash, observed version and times. Go validates evidence-identity consistency; trusted Python validates raw bodies and computes the hash. A hash or source-mode label alone cannot prove that a remote source was consulted. Fixture evidence is refused in configured live mode.

## Decisions, failures and provider metadata

| Outcome | Protected behavior |
| --- | --- |
| All required claims SUPPORTED | ALLOW / 200, exact approved assistant content |
| Independently validated CONTRADICTED claim | REJECT / 403, no answer, no policy fallback |
| Uncertain coverage, invalid binding/result, unavailable evidence, timeout or transport failure | UNAVAILABLE / 503, no answer |
| Missing/invalid receipt, absent/disabled/reconfigured plugin or changed entity | Ingress 503, no unvalidated upstream body |
| Genuine provider failure | Preserve failure and core fallback semantics; bounded-prose HTTP error projection retains status and an allowlisted category |

No voting, confidence average or partial answer release is used. In the template mode, a validated contradiction can still refuse with an absent neighbor; missing results never authorize ALLOW. Bounded-prose validation requires an explicit result for every mapping, including insufficient outcomes, before accepting the aggregate.

For bounded prose, the final ALLOW entity is this minimal structure:

```json
{"choices":[{"finish_reason":"stop","index":0,"message":{"content":"<exact approved text>","role":"assistant"}}],"object":"chat.completion"}
```

The decoded assistant content string is preserved exactly, including admitted ASCII separators. The entire provider envelope is not preserved. Provider-controlled `id`, `model`, `created`, `system_fingerprint`, `service_tier`, usage, extra fields, routing information and nested metadata are discarded. Unknown/raw/annotation/tool/reasoning/multimodal shapes may be refused earlier. Ingress independently requires the minimal representation and does not forward upstream response headers or diagnostics. SDKs requiring full OpenAI envelope metadata need a separate compatibility decision.

Genuine provider failures retain their core error pointer/fallback behavior. In bounded-prose HTTP output, their code/message become `epochguard_provider_error` / `Provider request failed.`; the category is allowlisted or `provider_error`. A successful fallback candidate must pass evidence checks. This error channel is not verified factual content. Explicitly legacy profiles retain their original envelope/error reflection limits.

## Receipt authentication and protocol isolation

[Signer](../plugins/epochguard/attestation.go) and [ingress validator](../internal/ingress/ingress.go) implement distinct configured protocols:

| Profiles | Required protocol / policy | Request and metadata guarantee |
| --- | --- | --- |
| `004g`, `004g-live` | `004g.receipt.v2` / `004g.v1/bounded-prose-v1` | Exact received/forwarded request-body digest plus minimal response projection |
| Original D and explicitly legacy E | `004d.v1` / `004b.v1/multi-claim-templates-v1` | Nonce/response binding only; no original request-body digest, original metadata behavior |

There is no downgrade or automatic v2 upgrade for legacy profiles. Their historical live qualification does not demonstrate v2 security. Retained-nonce substitution and provider-metadata limitations remain material to legacy deployments.

Canonical payload fields, in serialization order:

| Field | Binding |
| --- | --- |
| `version` | Exact configured receipt protocol |
| `nonce` | Ingress-generated 32 random bytes, lowercase hex |
| `policy_id` | Exact mode/policy identity |
| `outcome` | ALLOW, REJECT, UNAVAILABLE or PROVIDER_ERROR |
| `status` | Actual HTTP status |
| `body_sha256` | Final HTTP entity digest |
| `candidate_sha256` | Exact approved content's UTF-8 digest on ALLOW; empty otherwise |
| `issued_at` | Trusted Unix seconds at signing |
| `request_sha256` | **v2 only**, digest of exact HTTP request body received by Bifrost |

Encoding is unpadded base64url(payload), `.`, unpadded base64url(HMAC-SHA256(key, payload)). The key is 32 bytes loaded from a bounded runtime hex secret file. Ingress independently hashes its retained forwarded bytes; the signer hashes actual received bytes, never a caller-supplied digest header. Equivalent JSON reserialization changes the binding and is deliberately refused.

Validation requires canonical fields/types/order/encoding, constant-time MAC equality, exact protocol/policy/nonce/status/body/candidate/request correspondence, issuance no earlier than request-start minus 2s, no more than 2s in the future and age at most 20s. Unknown/missing/duplicate/aliased fields, malformed encodings, old/cross-policy records, tampering and stale/replayed receipts fail closed. Ingress never exposes a receipt or signing key to clients.

Fresh nonces prevent substitution across ingress exchanges. This is not request authentication or at-most-once gateway execution: a trusted-network actor can repeat identical upstream requests. No replay database or cache is implemented. A compromised signer/key/host/verifier defeats the boundary.

## Readiness, deployment and trust

`GET /ready` checks active/enabled/loaded plugin state, `pre_builtin` placement/order 0, configured mode/protocol and cache absence, then requires an authenticated refusal for a fixed unsupported-grammar canary. Current bounded-prose and E live readiness consume zero source calls. Original D uses its legacy supported fixture probe. Readiness establishes Go enforcement participation and refusal, not verifier/source health or successful factual verification; each response still needs its own receipt.

Protected qualification profiles publish no host ports. Only ingress bridges internal client and private networks; gateway, management, provider and verifier are private. Only the explicitly selected E or G-L real-source verifier joins an egress network and mounts the Tavily runtime secret. Egress attachment is not a destination firewall. Receipt keys are generated by a network-disabled init job and mounted read-only only into ingress/signers. Test setup credentials are not production authentication.

Trusted dependencies include host/kernel, pinned binaries, configured plugins, clock, verifier/source policies, TLS roots, management, secret files and network isolation. The private Go-to-Python HTTP hop has no independent authentication. Diagnostic `X-EpochGuard-*` headers are neither freshness evidence nor authorization. [Operations](operations.md) documents exact profile selection and credential boundaries.

## Resource limits and cancellation

| Boundary | Offline multi-claim / bounded prose | Fixed live composition |
| --- | --- | --- |
| Candidate / verifier request / verifier response | 8,192 code points and 32,768 UTF-8 bytes / 64 KiB / 256 KiB | Same bounds; G additionally ASCII-only |
| Ingress body receipt / response buffer | 64 KiB within 2s / 256 KiB | Same |
| Pipeline admission | Four active requests, no waiter queue | One active request |
| Retrieval / shared work | 4s per retrieval / 5s work | Tavily API 19s, total 20s; PyPI 4s; per-claim ceiling 20.5s / 26s work |
| Go evidence HTTP call | 6s in protected offline profiles | 30s |
| Remaining decision work | Context-bound configured timeout | At most 40s from HTTP pre-hook start |
| Ingress upstream / server write | 8s / 15s | 44s / 48s; external qualification client 52s |
| Ingress active requests | 16 immediate slots by default, no waiter queue | Same default |
| G Uvicorn admission | 32 connections/tasks in image and both Compose verifier commands | 32 in the isolated G-L live qualification command |

The legacy single-claim endpoint retains its own bounds/timeouts, including a 512-byte Go candidate limit; do not apply the multi-claim defaults to it. Pipeline instances are shared per event loop; creating one per request would defeat admission bounds. Claims run sequentially under the shared deadline. Retrievers close per-call clients/responses; cancellation releases admission. Server connection/task admission is distinct from evidence-work admission and does not guarantee host CPU/memory isolation.

The pinned gateway has no qualified global HTTP execution deadline. The provider fixture's 10s network timeout does not bound synchronous post-hook verification. Go context/deadline checks and ingress buffering bound release, but immediate transport disconnect propagation, scheduler cancellation and production provider lifetimes are not fully qualified. No timer may retain/cancel a pooled Bifrost root context after its hook lifetime. There are no automatic retrieval or qualification retries; configured provider fallback remains a separate mechanism.

The isolated G-L qualification profile adds private one-shot preflight and bounded observation endpoints around the unchanged G pipeline, reusing E's `ObservedPipeline`, source budgets and runtime-secret boundary. `compose.verify.004gl.yaml` and `tests/boundedproselive/qualify.py --live` require both `EPOCHGUARD_RUN_LIVE_004E=1` and `EPOCHGUARD_RUN_LIVE_004G=1`. Default invocation selects `compose.verify.004gl.offline.yaml`, fixture-mode retrievers and private networks with no egress. It never relabels a fixture as live; a separate live-configured Go control refuses supported fixture records. G-L offline Go uses the same 30s HTTP ceiling without the live-only 40s decision profile; the live configuration and factory are checked separately. Receipt, grammar and release contracts are unchanged. The separately authorized November 15 real-source run subsequently met the narrow acceptance checks on inspected records; the runner itself only collected results. This does not broaden the grammar, source policies, provider or production boundary. See [operations](operations.md#bounded-prose-live-qualification) and [offline qualification evidence](task-004gl.md).

## Non-authorizing analysis

005C adds an [isolated real-model qualification workflow](real-model-qualification.md). The native Gemini provider in pinned core `v1.14.1` sends its actual request through a fixed-host resource relay. Default `unadapted` mode forwards admitted response bytes unchanged. Explicit trusted `strict-005ct` mode validates the complete bounded native HTTP 200 envelope before conversion and constructs a minimal STOP response with exactly the original decoded text, omitting only validated metadata. It rejects additional/unknown output rather than selecting or repairing it. Genuine non-200 provider errors remain unchanged on this hop. The relay owns attempt reservations, deadlines, size limits and sanitized observations. It cannot authorize release or select sources. Only the live relay has egress; evidence stays simulated. A runtime-file launcher supplies Bifrost's supported process-local `env.*` credential reference, without embedding a key in tracked JSON or Compose environment configuration. Gateway diagnostics are suppressed in this profile; the relay is trusted with the private credential header and provider bodies in memory.

005C-R adds bounded structural relay observations and private request-stage telemetry, without expanding eligible responses. A nonempty native Gemini thought signature becomes assistant reasoning metadata; the current plain-candidate contract refuses that union. This mechanism can be tested offline, but the original live run did not retain enough structure to establish its exact cause. Null relay hashes never prove absent visible text. The trusted qualification-only flag requires fixture prose and v2 attestation. Fixed stage enums/request digests are written once to a 0600 gateway tmpfs file (64 KiB cap, 16 stages per exchange), collected only through private operator exec, and never exposed through client headers or release fields. Ordinary profiles keep this output disabled. Sink errors cannot authorize an answer or change its receipt.

The later `20261118T205130Z-06b231a3` run records exact visible text with a single STOP text/signature part and confirms that refusal boundary. The [005C-S audit](task-005c-s.md) finds that the same typed signature representation can also result from an added file-data part, an extra native candidate or a detached signature. The converter loses that original structure. No typed signature exception is implemented. [005C-T](task-005c-t.md) instead validates original structure before this loss. Its relay adapter is newly trusted for complete structural accounting and exact text correspondence. Original/projected response and text digests are sanitized process observations, not independent cryptographic provenance. Go/Python grammar, evidence authority, v2 signing and the minimal protected client envelope remain unchanged. An opaque signature establishes no correctness, freshness or origin authority.

The optional ingress `ModelQualification` setting is valid only with `004g-live`. It admits an explicit `max_completion_tokens` integer from 128 to 1,024 on native Gemini requests, refuses fallback and requires the bound on Gemini requests. Existing profiles retain their prior request fields. The relay independently requires the trusted exact model, fixed prompts and configured output bound; no caller can increase spending by selecting another model or native parameter. Forwarded request bytes still receive the unchanged v2 binding. Controlled readiness/provider-failure/missing-plugin requests remain distinct, credential-free controls. Default Lab and CI never select live inference.

The claim analyzer aligns globally unique exact source quotes to strict `004a.v1` Unicode code-point spans. Missing/ambiguous/reordered/overlapping quotes fail; there is no fuzzy repair or inferred replacement. Valid spans do not prove that all claims were identified correctly.

The prose planner emits `004f.prose-plan.v1`, `authorization=false` and `semantic_completeness=NOT_PROVEN`. PLAN_READY means bounded planning, never ALLOW. Original model propositions/classifications cannot choose evidence policies or waive checks. G enforcement independently parses its finite language and never consumes planning records.

The 112-case identification collection and 66-case prose collection are synthetic agent-authored drafts, not human-reviewed gold. Baseline/fake-provider diagnostics do not qualify model quality. A later ten-call Gemini diagnostic is operator-reported against draft labels, not an independently qualified benchmark. See the [analyzer guide](../services/claim_analysis/README.md) and [prose evaluation scope](../services/verifier/reports/prose-v1/README.md).

The separate [005C packet](../tests/modelqualification/data/README.md) contains 18 newly authored synthetic drafts, frozen before model execution. Its diagnostic reuses 004A prompt/schema/alignment, the existing Gemini adapter, 004F Analyzer/auditor and metrics. All failures stay in the denominator. Real Gemini comparisons remain missing until separately authorized execution; draft metrics never establish independent model accuracy or release authorization.

## Cache findings and proposed design

Built-in semantic caching remains disabled in default/protected profiles. [Real cache experiments](task-002c.md) found:

- With `pre_builtin`, the cache serializes/queues writes before EpochGuard evaluates the candidate; physical storage can precede a later rejection.
- With `post_builtin`, misses can be refused before writing, but cache hits skip EpochGuard's LLM hooks.
- Trusted server no-store suppresses writes, including allowed responses, while preserving reads. It is not verified cache admission.
- Both deletion APIs removed settled entries, but a held older asynchronous writer repopulated an absent entry after deletion succeeded. TTL/deletion do not establish logical revocation.

[ADR 0003](decisions/0003-protected-cache-ownership.md) proposes owned verified admission and generation-aware logical revocation. No protected cache, durable evidence archive or logically atomic revocation is implemented.

## Unsupported surfaces and residual risks

The [route audit](task-003c.md) tested finite raw/encoded targets, registered passthrough prefixes, alternate entry points and configured Warp chat. No provider-answer bypass was reproduced with the plugin active in that matrix. Some router/prerequisite failures occur before enforcement and must not count as policy refusals. Warp interactive chat reaches the core guard but wraps refusal in HTTP 200 JSON/SSE; background jobs can skip plugins entirely.

Management/log/history APIs, background execution, direct SDK calls, A2A/gRPC, realtime, streaming/async delivery and arbitrary routes/providers remain outside the qualified answer boundary. Direct Bifrost without ingress can serve unchecked content if the plugin fails to load. Management/configuration and sibling plugins remain trusted.

Production TLS/client/tenant authentication, key rotation, stock-gateway compatibility, general prose, arbitrary sources, origin freshness, safe streaming, host resource isolation, atomic network delivery and production performance/availability need separate design and qualification. Current fixture timings are not service guarantees. See [operations](operations.md) for reproducible scoped tests rather than treating these boundaries as deployment approval.
