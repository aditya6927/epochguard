# ADR 0003: own verified cache admission and logical revocation

Status: proposed for maintainer review after Task 002C experiments, 2026-11-06. This records a design direction; the protected cache is not implemented.

## Context and experimental evidence

Task 002C used the pinned real Bifrost gateway, native loader, semantic-cache v1.7.4, and Redis Stack. [Executed evidence](../task-002c.md) establishes:

- `pre_builtin` makes EpochGuard participate in cache-hit post-hooks, but the cache serializes and queues provider results before EpochGuard evaluates them. Redis can already contain an answer while its eventual REJECT decision is pending.
- `post_builtin` permits provider refusal before a cache write, but cache hits skip EpochGuard's LLM hooks and can deliver the answer despite configured REJECT.
- Server-set `CacheNoStoreKey` prevents new built-in writes while retaining reads. It also prevents caching allowed responses: there is no post-verification admission path in this tested arrangement.
- Both supported deletion APIs remove existing entries in quiescent tests. Neither is a write barrier: a controlled already-pending asynchronous write repopulated the entry after successful invalidation and an observed absent backend state.

## Decision

Keep the built-in cache disabled in the default protected development deployment. Treat optional pre-builtin enforcement plus server no-store as a narrowly qualified read/recheck experiment, not a production protected cache.

For a future protected cache, EpochGuard should own admission and logical revocation. Proposed requirements, not implemented here:

1. Admit an answer only after its evidence has passed an explicit policy. Keep candidate bytes private until that decision completes.
2. Bind an entry to trusted caller/tenant scope, normalized request and response digests, provider/model and relevant parameters, policy version, evidence identity/version, and verification expiry. A client-selected cache bucket is not a trusted identity.
3. Use a generation/version or tombstone mechanism with atomic backend comparison at admission. A writer working under an invalidated generation must not make the old candidate returnable, even if it finishes after physical deletion.
4. Check current generation, policy, evidence validity, and expiry at read/release time. Define the release/invalidation concurrency boundary and test it explicitly; version labels alone do not provide atomicity.
5. Make physical deletion a cleanup operation, with observable failures. Logical validity must not depend on successful enumeration/deletion of every physical entry.
6. Reverify or refuse stale/ambiguous candidates; do not label a hit, TTL, similarity score, or deletion acknowledgment as evidence of freshness. Preserve typed no-fallback refusals and upstream errors.

## Alternatives considered

| Alternative | Trade-off |
| --- | --- |
| Built-in cache disabled | Current choice; avoids unverified built-in writes and cache-hit bypass at the cost of no response reuse |
| One pre-builtin plugin with unrestricted built-in writes | Reproduced unsafe admission ordering |
| One post-builtin plugin | Reproduced enforcement bypass on hits |
| Pre-builtin plugin with server no-store | Demonstrated read-time refusal and write suppression; cannot populate an allowed-only cache itself |
| Two coordinated enforcement plugins on opposite sides of cache | Could check hits early and provider candidates before cache writes; not implemented/tested. Adds decision sharing and ordering obligations, and still needs a revocation protocol for pending writes |
| Delete rejected entries after the fact | Cannot undo earlier serialization/writes or prevent demonstrated late repopulation; physical deletion is not authorization |

## Consequences and revisit conditions

The current milestone adds qualification tooling and test-only controls, not cache storage ownership or real freshness verification. A future implementation must choose a backend capable of the required atomic operations and test writer/invalidation/reader races, identity isolation, evidence changes, restarts, outages, and additional response routes. Revisit this ADR if upstream provides an applicable admission/revocation contract or the deployment adds other cache layers.
