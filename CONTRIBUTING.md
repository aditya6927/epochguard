# Contributing to EpochGuard

EpochGuard checks a deliberately finite response language against two fixed evidence policies. Changes must be explainable, reproducible and scoped to an explicit contract. Read [architecture](docs/architecture.md), [compatibility](docs/compatibility.md) and [security](docs/security.md) before modifying enforcement.

## Setup

Use Git, Python 3.12, Docker with Linux/amd64 support, Compose v2 and Buildx. The [Lab installation](docs/compatibility.md#install-and-load) builds all required images from source. No API key or pre-existing virtual environment is needed. Run only offline profiles during ordinary development. Do not load `.env`, mount source credentials or run paid qualifications as part of tests.

```powershell
py -3.12 tests/lab/manage.py test --build
```

The test removes the stack/signing volume. Builder selection and sanitized failure diagnosis are described in [compatibility](docs/compatibility.md#builder-and-abi-diagnostics). Local frontend development additionally needs Node 24.13.0/npm; the Docker build supplies that toolchain otherwise.

## Code ownership and contracts

| Area | Responsibility |
| --- | --- |
| `plugins/epochguard/` | Native Bifrost hooks, independent parsing, evidence-result validation, typed refusals and signing |
| `internal/ingress/` | Buffered release, readiness and independent receipt/request validation |
| `services/verifier/verifier/` | Fixed-source retrieval, strict evidence validation, version comparison and finite claim coverage |
| `services/claim_analysis/` | Experimental, non-authorizing planning and evaluation |
| `internal/lab/`, `web/lab/` | Local presentation and fixed protected requests; no verification authority |
| `tests/`, `dev/`, Compose files | Private qualification stacks, controlled providers and negative controls |

Inspect actual pinned Bifrost source before relying on a hook or configuration field. Gateway and plugin must retain the same Go toolchain and module graph. An ordinary hook error is not an enforcement refusal. Use the existing typed error/short-circuit contracts and test the real gateway.

Policy changes need an explicit versioned language/source contract, independent Go/Python parsing where applicable, full-response coverage and negative controls. Test mixed supported/contradicted/unavailable claims, missing results, malformed input, source identity/context and evidence bindings. Retrieved bodies and model output remain untrusted. A planner, confidence score, header or cache hit must never authorize release.

Security-sensitive changes require retained-nonce request-substitution, receipt replay/downgrade/policy-binding and metadata sentinel tests; absent/disabled/restarted plugin controls; exact approved content preservation; and timeout/overload/fallback/no-leak checks. Do not enable built-in caching, streaming, arbitrary sources or routes implicitly. Keep private services unpublished and credentials out of source, logs and artifacts.

## Validation

The same steps as CI can be run locally. Public dependency installation has network access; Go/Python/frontend test execution inside these build stages has none:

```powershell
docker build --target go -f dev/Dockerfile.checks .
docker build --target python -f dev/Dockerfile.checks .
docker build --target frontend -f dev/Dockerfile.lab .
py -3.12 -m unittest discover -s scripts -p 'test_*.py'
py -3.12 scripts/check_docs.py
```

For actual native loading and protected lifecycle checks, run the [operations suites](docs/operations.md#protected-offline-qualifications), including G and G-L offline. CI compiles a `.so`; it does not replace these gateway qualifications. The [evaluation index](docs/evaluation.md) separates locally executed commands from the first pending hosted CI run.

## Pull requests

Describe the concrete problem, resulting behavior, contract changes, test commands actually executed and remaining limitations. Include relevant negative controls and update canonical documentation; preserve historical evidence with its original scope. Keep unrelated refactors separate. Record dependencies/toolchain changes explicitly and rerun native ABI/load checks when they change. Do not describe fixture evidence as live or draft annotations as human-reviewed gold.

There is no chosen repository license yet. The [third-party audit](docs/third-party.md) describes the pending maintainer decision and dependency obligations. Contributions and upstream submission need an agreed licensing basis before distribution. Do not submit credentials or private vulnerability details in public pull requests; see [SECURITY.md](SECURITY.md).
