# Task 002C: real cache lifecycle qualification

Executed on 2026-11-06 (Asia/Calcutta), using Docker Desktop Linux/amd64 and the real pinned Bifrost gateway/native plugin loader. This is a qualification milestone, not an implementation of the EpochGuard-owned verified cache. No freshness evidence, Tavily, verification service, dashboard, or safe streaming implementation is included.

## Results and acceptance boundary

The experiments reproduced both placement hazards and the pending-write invalidation race. Early EpochGuard enforcement refused cached candidates before client delivery. Server-enforced no-store suppressed new writes while retaining reads. The default `compose.yaml` continues to have **no built-in cache enabled**. Unsafe controls exist only in `compose.cache.yaml`, which publishes no host ports.

| Experiment | Actual observation |
| --- | --- |
| Direct miss then hit, early placement | Same cache ID; `cache_hit=false` then `true`, hit type `direct`; provider counter stayed 1; EpochGuard LLM hooks ran on both requests |
| Direct miss then hit, late placement | Provider counter stayed 1; EpochGuard ran on miss but its LLM hooks were absent on hit |
| Warm cached candidate under REJECT/UNAVAILABLE | Safe 403/503, complete early trace, `cache_at_post=hit`, no answer markers, no provider or fallback calls beyond the single seeding call |
| Early REJECT with built-in writes permitted | Redis contained the candidate while the trusted delayed decision/client response was still pending; final response was a safe 403; another early request refused the stored hit |
| Late REJECT on cold/warm cache | Cold provider answer refused before any cache write; after an independent ALLOW seeder populated it, a hit returned HTTP 200 with the answer and skipped EpochGuard's LLM hooks: an explicitly unsafe negative control |
| Server no-store with client `x-bf-cache-no-store: false` | Repeated misses; zero observed HSET attempts and no physical entry; cached reads still worked and were refused under rejecting policies |
| Delete by ID | Only selected entry disappeared; next read missed and incremented provider counter; sibling entries survived |
| Delete by key, including URL-encoded spaces/slashes/colon | Both entries in that bucket disappeared; another bucket survived; subsequent read misses and explicit refills confirmed behavior |
| Held async write versus either invalidation API | Client completed while HSET was held; deletion returned 200 and Redis was absent; releasing the already-pending write restored a hit with provider counter unchanged |

ALLOW in every experiment is a deterministic fixture, **not verified freshness**. A cache hit, TTL, diagnostic header, or successful deletion is never described as a factual verification decision. Forged verification headers are not returned as verification markers. The unsafe late-placement response is documented as an enforcement bypass, not accepted as protected behavior.

## Pinned source inspected

No Bifrost core source, module manifests, or dependency versions were modified. Exact downloaded source is retained locally under ignored `artifacts/002c/upstream/`; references below are immutable upstream commits.

| Component | Pin / relevant source |
| --- | --- |
| Gateway | HTTP v2.4.0, `e869c3f9adc96ea53c38694a21bb04a8e1085487` |
| Core | v1.14.1, `2975d142abcffc5783a60201394631b5576c748f`; [buffered short-circuit and hook runners](https://github.com/maximhq/bifrost/blob/2975d142abcffc5783a60201394631b5576c748f/core/bifrost.go) |
| Semantic cache | v1.7.4, `8410bc47c3ee99464ebd5f46b7bab1bc429b278a`; [main.go](https://github.com/maximhq/bifrost/blob/8410bc47c3ee99464ebd5f46b7bab1bc429b278a/plugins/semanticcache/main.go), [search.go](https://github.com/maximhq/bifrost/blob/8410bc47c3ee99464ebd5f46b7bab1bc429b278a/plugins/semanticcache/search.go), [state.go](https://github.com/maximhq/bifrost/blob/8410bc47c3ee99464ebd5f46b7bab1bc429b278a/plugins/semanticcache/state.go), [utils.go](https://github.com/maximhq/bifrost/blob/8410bc47c3ee99464ebd5f46b7bab1bc429b278a/plugins/semanticcache/utils.go) |
| Framework | v1.11.1, `9e4f5db754307cebb248301bb88341c94b3d497e`; [Redis implementation](https://github.com/maximhq/bifrost/blob/9e4f5db754307cebb248301bb88341c94b3d497e/framework/vectorstore/redis.go) |
| Registration | [server/plugins.go](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/server/plugins.go): built-in cache receives order 7 |
| HTTP cache controls | [lib/ctx.go](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/lib/ctx.go): cache headers are parsed before core hooks |
| Invalidation | [handlers/cache.go](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/transports/bifrost-http/handlers/cache.go): actual DELETE routes and path decoding |
| Setup documentation | [Semantic caching](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/docs/features/semantic-caching.mdx), [Redis/Valkey](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/docs/integrations/vector-databases/redis.mdx) |

Source findings: a vector store is mandatory even for direct-only mode. Cache key/default key, supported request type, and request ID are required. Direct lookup hashes normalized request/parameters plus bucket, identity scope, provider and model settings. Exact hits return `LLMPluginShortCircuit.Response`; core runs post-hooks only for the executed pre-hook prefix. Request state is keyed by Bifrost request ID and cleared/reaped separately from stored cache entries.

On a miss, the cache post-hook stamps miss metadata, checks no-store, serializes the response **synchronously**, then launches its writer using owned bytes and a detached background context bounded by `CacheSetTimeout` (30s). A later plugin discarding its response pointer cannot retract that serialized snapshot. Ordinary cache/backend failures generally log and fall through to the provider or leave the write absent; this cache is not a verifier.

## Isolated deployment and trusted controls

`compose.cache.yaml` starts the existing deterministic provider, Redis Stack, a transparent test store proxy, and seven real gateways. Each gateway has a separate disposable config database and a read-only, committed configuration file under `dev/bifrost/cache/`.

| Service | EpochGuard placement | Decision | Server no-store |
| --- | --- | --- | --- |
| `writer` | pre_builtin | ALLOW | false |
| `reader` | pre_builtin | ALLOW | true |
| `reject` | pre_builtin | REJECT, trusted 2000ms test delay | false: unsafe-write control |
| `safe` | pre_builtin | REJECT | true |
| `unavailable` | pre_builtin | UNAVAILABLE | true |
| `post-allow` | post_builtin | ALLOW | false: order probe |
| `post-reject` | post_builtin | REJECT | false: unsafe-hit control |

All configurations use the same `EpochGuard002C` namespace, `dimension: 1`, `ttl: "30m"`, and provider/model partitioning. No embedding provider/model is configured, so only exact direct caching is exercised. The test client supplies `x-bf-cache-type: direct` and a unique bucket plus unique prompt for each experiment. Shared namespace/configuration lets separate trusted-policy processes inspect the **same** candidate without a client-controlled decision switch.

Redis Stack is `redis/redis-stack-server:7.4.0-v8@sha256:798ab84d9f266936b034ab11c4d04a2b8e4b441884c5aa7d17ac951eefdf742a`, platform Linux/amd64. Its image manifest selected the amd64 digest `sha256:39adcbb083b240642cd5738a75c4959c0393ef2a40fa545f2e1c7b55798eeda4`. Actual `INFO server` reported Redis 7.4.7; `MODULE LIST` reported search module version `21020` (2.10.20). Ordinary Redis without the required `FT.*` search commands is insufficient for this backend's namespace setup.

The writer becomes healthy before the other gateways start, avoiding a concurrent first-time `FT.CREATE` race. `/health` is sequencing only: the tests independently require active plugins and exercise real cache behavior. The management API reports EpochGuard's custom placement/order but omits those fields for the active built-in cache. The source's built-in order is corroborated by actual core debug traces, not invented API fields.

The new `cache_no_store` and `test_decision_delay_ms` options come only from trusted plugin configuration and require `test_only: true`; delays outside 0..2000ms are rejected. No inference header or prompt selects either option. The delayed fixture respects context cancellation. Tests forge ALLOW/bypass/verified headers and request raw provider responses; the configured refusal and server no-store remain authoritative. Management authentication uses the existing public **local-development-only** setup token. This network and its controls must not be exposed as a production service.

## Observed hook execution and counters

The following are actual core debug events, restricted to EpochGuard (`E`) and semantic cache (`C`); other built-ins are omitted here. Raw per-container logs are retained in `artifacts/002c/`.

```text
pre_builtin, direct miss: E.Pre -> C.Pre -> provider -> C.Post -> E.Post
pre_builtin, direct hit:  E.Pre -> C.Pre [short circuit] -> C.Post -> E.Post
post_builtin, miss:       C.Pre -> E.Pre -> provider -> E.Post -> C.Post
post_builtin, hit:        C.Pre [short circuit] -> C.Post
```

From the final writer log (2026-11-06T14:22:08Z), the first miss and hit each contain:

```text
running pre-hook for plugin epochguard
running pre-hook for plugin semantic_cache
running post-hook for plugin semantic_cache
running post-hook for plugin epochguard
```

The corresponding request-owned diagnostic states were `cache_at_post=miss` and `cache_at_post=hit`. For the `post-allow` miss the core logged `C.Pre, E.Pre, E.Post, C.Post` and EpochGuard saw `cache_at_post=none`; on its following hit only `C.Pre, C.Post` appeared.

| Path | Actual HTTP hook trace | Provider calls after miss / hit |
| --- | --- | --- |
| Early ALLOW miss/hit | `http_pre,pre_request,pre_llm,post_llm,http_post` on both | 1 / 1 |
| Late ALLOW miss | Full trace above | 1 |
| Late ALLOW or REJECT hit | `http_pre,pre_request,http_post` | Unchanged |
| Early REJECT/UNAVAILABLE hit | Full trace, safe refusal, cache-at-post `hit` | 1 total, including seed |

One final direct pair had ID `00e20443-ecbc-5574-bb93-a4a33dfec493`: first `cache_hit=false`, then `cache_hit=true`, hit type `direct`; provider calls remained 1. Miss metadata alone is not storage proof: the no-store tests also received intended write IDs while `EXISTS` stayed false.

## Experiments and actual outcomes

### Previously cached candidate and write-before-refusal

`TestCachedCandidateRefusedBeforeDelivery` seeds each unique identity through the real ALLOW writer, polls Redis until the entry exists, then requests the same candidate through early REJECT/UNAVAILABLE. Refusals contain no fixture sentinel, answer prefix, completion ID, `choices`, or raw-response field. The provider counter remains 1 despite explicit usable fallbacks. The read-only ALLOW control still returns a direct hit, proving refusal did not silently delete/regenerate the entry.

`TestRejectedProviderAnswerWasStored` first makes one no-store ALLOW calibration request to learn the actual cache ID. Its second provider call runs under early REJECT with a trusted 2s decision delay. Before that client's response completes, the test observes real Redis `EXISTS=true`. The eventual HTTP result is 403 with no answer markers. Another REJECT request sees the cached candidate and refuses it; a read-only ALLOW control returns the same stored answer. Counter: **1 calibration -> 2 after rejected provider call -> still 2 after both hit probes**. The proxy observes exactly one HSET.

This establishes more than a scheduled write: the candidate was physically stored while the synchronous decision was pending. Serialization/queueing necessarily occurred in `C.Post`, before `E.Post` made its decision. The client refusal protects delivery in the early-placement configuration, but does not protect built-in cache admission.

### Incorrect placement and server write suppression

The late REJECT control first refuses a cold provider answer. After calibration and refusal, the counter is 2, no HSET has been observed, and the entry stays absent. An independent ALLOW seed increments it to 3. The next late REJECT request returns HTTP 200 with the cached answer, counter still 3, and no EpochGuard LLM hooks. The answer-marker detector intentionally identifies that response as leaked/unprotected. This is the required negative control, not a route supported for protected deployment.

`PreLLMHook` sets the actual exported `semanticcache.CacheNoStoreKey` to `true` when trusted configuration requires it. Transport header parsing has already run; a client's false value cannot overwrite this later server value. This does not disable reads. Three server no-store policies (ALLOW, REJECT, UNAVAILABLE) each make a calibration plus two repeated requests: provider count **3**, all misses, zero HSET attempts, physical entry absent throughout a bounded 600ms observation window. Warm-cache tests separately prove reads still work and rejecting policies still refuse them.

The finite observation window alone is not proof of perpetual absence. It is combined with the exact source branch returning before serialization/writer launch, repeated misses, and proxy auditing; positive writer controls prove that the observer detects real writes. Built-in cache reads do not create new entries on hits.

### Supported invalidation APIs, scope, and explicit refill

Tests authenticate and call the actual endpoints:

```text
DELETE /api/cache/clear/{cacheId}
DELETE /api/cache/clear-by-key/{url.PathEscape(cacheKey)}
```

For each API, two settled entries share a bucket and a third belongs to a sibling bucket. ID deletion removes only its target. Key deletion removes both same-bucket entries, including a bucket whose spaces/slashes/colon require URL encoding; the sibling remains. Backend `EXISTS` is checked, then read-only client probes establish the expected misses/hits and provider increments. This is stronger than accepting a 200 deletion response.

For the main deleted identity, provider counts are **1 seed -> 2 read-only miss -> 3 explicit ALLOW refill -> still 3 on the next hit**. Refilling is a new provider operation followed by the ordinary async write, not automatic regeneration inside a rejected post-hook.

### Deterministic pending-write/invalidation race

`cmd/cache-store-proxy` is transport instrumentation, not a cache or plugin-loader mock. It forwards Redis command and reply bytes unchanged. It recognizes HSET metadata for the selected test bucket and can pause that command **before** forwarding it to the real backend. Separate read-only `EXISTS` inspection goes directly to Redis; it does not populate entries.

For **both** invalidation APIs, the test performs:

```text
arm HSET hold for unique bucket
-> real provider request returns buffered ALLOW response (counter 1)
-> observe HSET held, forwarded=0, Redis entry absent
-> supported DELETE returns 200; Redis remains absent
-> release the already-pending HSET
-> bounded poll sees Redis entry present
-> read-only direct hit; provider counter still 1
-> early REJECT/no-store reader refuses that hit with no answer bytes
```

The client response completing while its HSET is held proves asynchronous persistence. No fresh provider request occurs between deletion and repopulation. The race intentionally invalidates an absent entry with an outstanding writer; the separate settled-entry deletion experiment establishes real deletion of existing entries. Neither successful endpoint is a barrier against this older pending work. The demonstrated failure is controlled scheduling, not a claim about its natural production frequency.

The proxy's hold is capped at 8s, below the test Redis read timeout (12s), context timeout (15s), and cache writer deadline (30s). Tests release holds during cleanup. Command parsing preserves binary bulk strings and pipeline boundaries; unit tests cover both and malformed frames. Replies, including RESP3, are copied as bytes. Audit maps store scope/key/counters, not response bodies; all process state is disposable.

### TTL and other unsafe behavior

The configured TTL is 30 minutes and all lifecycle probes complete without waiting for expiration. The pinned Redis `Add` stores hashes with `expires_at` metadata, not a physical Redis expiry. A sampled live entry returned Redis `PTTL=-1` while its `expires_at` field was `1793976728`. The cache checks logical expiry on lookup and can delete expired candidates asynchronously. This is storage lifetime behavior, not evidence freshness, and this task does not qualify expiration as revocation.

`ClearCacheForKey` can log per-entry deletion errors yet return nil after its backend `DeleteAll` succeeds; source inspection establishes that additional limitation. No backend partial-deletion failure was injected here. Concurrent readers that already hold a candidate, other storage backends, semantic similarity mode, multiple cache layers, process crashes, write retries/outages, and arbitrary plugin combinations remain unqualified. No global atomic-invalidation claim is made.

## Go paths, ownership, and future cache recommendation

The existing typed enforcement path remains authoritative: successful buffered candidates synchronously call `DecisionSource`; REJECT/UNAVAILABLE return `(nil, terminalBifrostError, nil)`, and genuine provider errors retain their original pointer/fallback policy. `cache_no_store` adds a pre-hook context write only. The new bounded delayed source is test-only, uses a timer/select on context cancellation, and does not retrieve evidence or call a verifier service.

The request-owned trace adds only a mutex-protected string snapshot of cache metadata at EpochGuard's post-hook. Its new `X-EpochGuard-Cache-At-Post` header and log are diagnostics, not authorization. No pooled response pointer is retained. The immutable policy uses the existing atomic publication model. The built-in cache itself owns its serialized response bytes and per-request state; its asynchronous writer outlives the hook chain and is why a later nil response cannot retract admission.

Alternatives are: disable the built-in cache; keep early enforcement and server no-store for read/recheck only; introduce coordinated early/late enforcement boundaries (not tested here); or make EpochGuard own verified cache admission and logical revocation. Experiments justify [ADR 0003](decisions/0003-protected-cache-ownership.md): keep the default built-in cache disabled, and design a future cache with evidence/policy-bound entries, trusted identity, read-time validity checks, and atomic generation/version checks preventing stale writers from making invalidated candidates returnable. Physical deletion should be cleanup, not authorization. That cache is deliberately not implemented in 002C.

## Exact commands and executed checks

From repository root, with Docker Desktop Linux containers running:

```sh
docker compose build --builder epochguard-002a gateway
docker compose -f compose.cache.yaml pull redis
docker compose -f compose.cache.yaml up -d --force-recreate --wait provider store-proxy writer reader reject safe unavailable post-reject post-allow
docker compose -f compose.cache.yaml run --rm --no-deps cache-tests
docker compose -f compose.cache.yaml down --volumes --remove-orphans

docker compose --profile test up -d --force-recreate --wait provider gateway gateway-control gateway-reject gateway-unavailable
docker compose --profile test run --rm --no-deps smoke
docker compose --profile test down --remove-orphans

docker compose -f compose.cache.yaml config --quiet
git diff --check
```

The `up` command also starts Redis through dependencies. The initial run prestarted Redis separately using `docker compose -f compose.cache.yaml up -d --wait redis`. The builder name remains the existing DNS-workaround builder; the normal default build command also applies if that workaround is unnecessary. Recreate gateway processes after changes to plugin code. For later test reruns, identities are unique and write polling is bounded, so prior fixture counts or physical entries cannot supply a stale positive result.

| Executed check | Actual result |
| --- | --- |
| Plugin `go test -mod=readonly -trimpath -v ./...` in final image build | All 13 top-level tests passed, including prior enforcement tests and new no-store/delay checks |
| Plugin `go test -race -p=2 -mod=readonly -trimpath ./...` | `ok ... 1.108s`, exit 0; plugin unit execution only |
| Store proxy `go test -mod=readonly -trimpath -v ./cmd/cache-store-proxy` | Both tests passed; final rebuild reused Go's successful test result cache |
| Formatting, native `.so`, provider/proxy binaries, smoke/cache test binaries, dynamic ELF check | Image build exit 0 |
| Unchanged pinned gateway/source/module-alignment/verification layers | Existing successful build-cache layers reused; manifests/checksums unchanged |
| Real cache suite | **9 top-level tests, 22 subtests passed**, no failures/skips; final `PASS`, exit 0 |
| Complete unchanged Task 002B smoke suite against final plugin | **10 top-level tests, 35 subtests passed**, no failures/skips; final `PASS`, exit 0; original 002A controls included |
| Both Compose configuration checks and `git diff --check` | Exit 0 |
| Cache stack cleanup (including disposable volumes) and normal regression stack cleanup | Exit 0; experiment containers/networks removed after evidence capture |

The first cache run failed only the assertion expecting built-in placement/order in the management response. The active cache's fields were omitted. After correcting that assertion, retaining active-status checks and actual trace/order tests, and adding the bounded decision-delay observation, the image was rebuilt and the entire cache suite passed. No tests were disabled or replaced with mocks.

Local ignored evidence under `artifacts/002c/` includes initial/final build and startup logs, `cache-initial.log`, final `cache.log`, per-gateway logs, Redis image/module/TTL evidence, copied build identities, and pinned source. `regression-002b.log` records the full normal smoke suite against the same final plugin image with cache disabled. Both disposable stacks were removed after evidence capture. No required Task 002C checks were left unrun; the unqualified behaviors listed above are outside this experiment's scope.

Stop after Task 002C for review. Recommended commit: `test(cache): qualify Bifrost cache lifecycle and enforcement ordering`. No commit is created automatically.
