# 005F — Controlled gate-versus-unprotected-gateway evaluation

## Scope and method

Baseline: `dc1ed88bfec47141a83337e4b888d915a72f3408`, plus the benchmark files below. Execution: November 19, 2026. This is a controlled offline measurement, not a new authorization feature or a real-world factual-detection accuracy benchmark.

The [frozen packet](../tests/gatecompare/data/README.md) contains 24 synthetic candidates with authored input labels and expected outcomes, fixed before gateway execution. Labels are external to the verifier and are not computed from its grammar or observed decisions. They are agent-authored expectations, not independently human-reviewed gold. Synthetic source labels are Python `3.15.2` and requests `2.34.2`; they do not describe current releases.

Each candidate was submitted unchanged through both real running paths:

- **A:** client → unprotected pinned Bifrost → controlled provider, with EpochGuard absent.
- **B:** client → protected ingress → pinned Bifrost/native EpochGuard → Python verifier → receipt-v2 validation at ingress. The missing-plugin control instead targets ingress backed by gateway A.

The two gateway configurations differ only by the configured EpochGuard plugin. Both retain Bifrost's built-ins (`compat`, `governance`, `model-catalog-resolver`, `prompts`, `routing`, `telemetry`); runtime inventories must differ only by EpochGuard, with no semantic cache. This is an **unprotected Bifrost comparison**, not direct-provider HTTP delivery. Direct-provider latency was not measured. Both paths share the same actual controlled provider, which emits the supplied synthetic candidate verbatim. Expected labels never enter its response logic.

Three sequential repetitions per case produced **72 matched pairs / 144 measured requests**. Pair order alternated A/B and B/A. Each path received identical serialized request bytes; every delivered assistant string matched the original candidate byte-for-byte. Provider counters confirmed one provider request per measured path request, and unprotected requests invoked no verifier sources. Two warmups per path and readiness were excluded from metrics but retained separately. There were no automatic inference retries.

## Measured outcomes

All 24 cases produced their specified outcomes in all three repetitions. Counts below are candidate-level; request-level counts are three times these values.

| Metric / labelled cohort | Unprotected A | Protected B |
| --- | --- | --- |
| Known unsafe answers delivered | 8 / 8 | **0 / 8** |
| Admitted supported answers delivered correctly | 6 / 6 | **6 / 6** |
| Safe but unnecessary refusals | 0 / 5 | **5 / 5** |
| Unknown/inconclusive answers delivered | 4 / 4 | **0 / 4** |
| All labelled-correct answers delivered | 12 / 12 | 6 / 12 |
| Missing-plugin protection refusals | 0 / 1 | **1 / 1** |

The five unnecessary refusals are correct but policy-unsupported content: two paraphrases, a harmless courtesy and two same-value policy repeats. This is retrospective fixture truth, not a grammar enforcement error. The separately reported missing-plugin refusal is necessary protection, even though that control's candidate is labelled correct. Three faulted-evidence cases and one unassessed future-release neighbor remain unknown/inconclusive; withholding them does not prove them false.

| Category | Cases | Protected observations across three repetitions |
| --- | --- | --- |
| Supported single/two-policy answers, including reversed order and whitespace | 6 | 18 × ALLOW / 200 |
| Outdated single-policy versions | 2 | 6 × REJECT / 403 |
| Mixed supported/outdated answers | 2 | 6 × REJECT / 403 |
| Correct unrecognized paraphrases | 2 | 6 × UNAVAILABLE / 503 |
| Unsupported neighbors: two false, one unknown, one harmless | 4 | 12 × UNAVAILABLE / 503 |
| Repeated singleton policies: two inconsistent, two same-value | 4 | 12 × UNAVAILABLE / 503 |
| Unavailable/malformed evidence | 3 | 9 × UNAVAILABLE / 503 |
| Missing EpochGuard plugin behind protected ingress | 1 | 3 × INGRESS_REFUSED / 503 |

Overall B outcomes were 18 ALLOW, 12 REJECT, 39 UNAVAILABLE and 3 INGRESS_REFUSED. A delivered all 72 requests with HTTP 200. The eight known unsafe cases comprise four outdated/mixed answers, two false neighbors and two inconsistent policy assertions. Only the older-version comparisons received authenticated source-contradiction outcomes; grammar refusals do not establish semantic falsity.

Measured source invocations were **A: Python 0, PyPI 0; B: Python 24, PyPI 27**. Counts include failed simulated source HTTP attempts, not billing or origin requests. Two extra protected Python warmups bring process totals to Python 26/PyPI 27. The provider observed 149 generations: 144 measured, four warmups and one readiness canary. Readiness invoked zero evidence sources.

## Matched latency

The client timed each complete HTTP response with `perf_counter_ns`, using separate persistent clients with the same connection settings. Source-control and counter reads were outside the timer. Quantiles use nearest rank; added latency is computed **B minus A for each pair before quantiling**, retaining negative values if observed.

| Cohort | A p50 / p95 | B p50 / p95 | Matched added p50 / p95 |
| --- | --- | --- | --- |
| All 72 pairs | 2.139 / 3.357 ms | 5.321 / 7.967 ms | **2.989 / 5.661 ms** |
| Supported cases only, 18 pairs | 2.374 / 3.542 ms | 6.647 / 8.860 ms | **4.044 / 6.449 ms** |

These are observed local **path-level differences**, including ingress, buffering, verification, signing/receipt checks, transport and scheduling effects. They are not pure plugin overhead. The all-case distribution includes fast refusals; the supported subset still mixes one- and two-source requests. A single Windows/Docker Desktop Linux/amd64 run with simulated source transports, no model inference and three repetitions does not predict production, network-source or real-model latency. Per-case categories and every individual nanosecond measurement are retained for recomputation; no confidence interval or statistical reliability claim is made.

## Artifacts and reproduction

Successful run: `artifacts/005f/20261119T143411Z-8a3b5091/`.

| File | Content |
| --- | --- |
| `measurements.json` | All 72 pairs: case/repetition/order, actual statuses/outcomes, content-release flags, request/content/response hashes, source/provider counters and raw per-path/matched nanoseconds; readiness and warmups |
| `report.json` | Denominators, category metrics/latencies, source revision/digests, immutable image IDs and completed cleanup |
| `gateway.json`, `gateway-control.json`, `isolation.json` | Exact public fixture configurations and verified two internal networks / zero published ports |
| `stages.json`, `cleanup.json` | Actual commands/stage results and removal of owned containers, networks and signing volume |

Frozen LF-normalized dataset SHA-256: `00bc7980901364e475e7dbeeaedbd4118da8348af8f0e915d9925d936edbefa9`. Selected-source SHA-256: `db54ecfd58684b5ab0c035ddbfd4593dc6e234af207344ed0d6579bd449ef34f`. Running Python/source-packet digest: `4c118a481c3391e95576a36fe441db78e8147811dd8b0378d16c0dedf2f0e23a`; the host verified it against the checkout. These identify tested code/data, not factual authority. Image IDs are:

- Native: `sha256:2242e765036451f4fcc3a2fb251550f4b319ad5c2461939acd7870feb571d5c0`.
- Verifier 004G: `sha256:6db87cc3b9512d6aa4e2ca4cabca9efcd7352d1a1678bdad3d0051992ce74328`.
- Benchmark/verifier runtime: `sha256:2c63e176dc2acc5750ff06ea43cd9eb9f917511952a595e96e3edd72fb456b80`.

From the repository root, with Docker Linux containers and Python 3.12:

```powershell
py -3.12 tests/gatecompare/qualify.py --build --builder epochguard-002a
```

Select an available Buildx builder or omit `--builder`. `--build` rebuilds the documented native → verifier 004C → 004E → 004G chain; the benchmark image always rebuilds from its local 004G base. Public pinned dependencies may be needed during initial builds. There are no new dependencies. The successful collection used `py -3.12 tests/gatecompare/qualify.py` after the dependency build. Default repetitions are three; `--repetitions 1` through `5` is bounded and recorded. Each run creates a new ignored artifact directory, pins image IDs, checks running Python sources and cleans in `finally`. Existing project resources or an ownership lock cause refusal rather than deletion.

Recompute summaries from retained individual measurements without running any gateways:

```powershell
py -3.12 -c "import json,sys;sys.path.insert(0,'tests');from gatecompare.benchmark import load_dataset,summarize;v=json.load(open('artifacts/005f/20261119T143411Z-8a3b5091/measurements.json'));print(json.dumps(summarize(load_dataset(),v['measurements'],v['repetitions']),indent=2))"
```

The benchmark has no live option. All runtime networks are internal and all service ports unpublished. It reuses the existing simulated G source controls and normal authorization pipeline. The trusted measurement client joins private/client networks to read counters and invoke baseline A; this is not a new client-isolation qualification. The only generated secret is the disposable fixture receipt key, never exported. No real credentials, raw receipts, private source bodies or live-provider outputs are collected.

## Validation and limits

The initial `--build` attempt (`20261119T143022Z-06e15ab8`) and diagnostic attempt (`20261119T143205Z-35827725`) both stopped before collecting any pairs: the initial check incorrectly assumed that configured `plugins=[]` meant an empty loaded inventory. The pinned gateway also loads built-ins. The corrected check requires matching built-ins, EpochGuard solely on B and no semantic cache. Both failed runs and their successful cleanup remain retained; the frozen dataset/labels were unchanged. The successful run was not selected by latency.

Final Python regressions: **1,169 passed, one intentionally deselected live test**, one existing FastAPI/httpx deprecation warning. This includes 43 benchmark tests for frozen labels, arithmetic/denominators, quantiles, exact request/content binding, incomplete or mismatched records, built-in inventory, credential-environment filtering and ownership protection. Execution used the existing network-disabled container pattern:

```powershell
docker run --rm --network none --mount "type=bind,source=$($PWD.Path),target=/src,readonly" --workdir /src/services/verifier -e PYTHONPATH=/src/tests:/src/services/verifier:/src/services/claim_analysis -e PYTHONDONTWRITEBYTECODE=1 epochguard-verifier:004g python -B -m pytest -c /src/services/verifier/pytest.ini -p no:cacheprovider /src/services/verifier/tests /src/services/verifier/tests_multiclaim /src/services/verifier/tests_gateway /src/services/verifier/tests_live /src/services/verifier/tests_prose /src/services/verifier/tests_bounded_prose /src/services/verifier/tests_live_g /src/services/verifier/tests_claim_report /src/services/claim_analysis/tests /src/tests/modelqualification /src/tests/combinedqualification /src/tests/gatecompare -q --tb=short
```

Go formatting, vet, fresh unit and race tests passed for the native plugin and all local ingress/command packages, with pinned Go 1.27.3 Linux/amd64. Fresh execution used `-count=1` and network-disabled stages appended to the existing native build in `artifacts/005f/regressions.Dockerfile`: `docker buildx build --builder epochguard-002a --target go-regressions -f artifacts/005f/regressions.Dockerfile .`. The actual command/output is retained in `go-regressions.log`; the normal dependency build also enforces the existing native checks. Race instrumentation covers unit tests, not the measured gateway process. Documentation/link validation, its two tool regression tests and tracked/new-file whitespace checks passed.

A separate audit recomputed all summaries and verified **301 historical run/report files unchanged**, including November 15/19 live evidence and prior 005E qualifications. An independent Docker-label audit found zero benchmark containers, networks or volumes and no owner lock. Supporting logs/audits are under `artifacts/005f/`.

Changed files are confined to `tests/gatecompare/{benchmark,qualify,test_benchmark,__init__}.py`, its `Dockerfile`, `compose.yaml`, frozen `data/{candidates.json,README.md}`, this document and the compact evaluation-index summary. Production authorization, grammar, evidence retrieval/parsing, receipts, ingress and Gemini adaptation are unchanged. Existing qualifications were not rerun or reinterpreted as new live evidence.

The result demonstrates the finite release boundary's benefit and cost under controlled labels: it withholds known unsafe/unknown fixture answers and retains admitted support, while also withholding correct language outside policy. It does not establish arbitrary semantic consistency, real-world accuracy, real-source freshness, production readiness or combined live-model/live-evidence qualification.
