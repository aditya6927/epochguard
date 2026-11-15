# Operations and reproducible qualification

Run commands from the repository root. These are workflows to execute deliberately, not claims of new test execution. Historical outcomes remain in the linked reports; [architecture](architecture.md) defines the current guarantees.

## Prerequisites and build selection

Use Git, Docker Desktop in Linux-container mode (or Docker Engine on Linux), Compose v2, Buildx and Python 3.12. Native images target Linux/amd64; other hosts require working emulation. Initial builds download pinned source/dependencies and may take several minutes. Qualification cases use private networks and fixtures unless explicitly marked live.

The three host qualification scripts use only Python's standard library. No virtual environment or local Go installation is needed to run them. In PowerShell use `py -3.12`; on Linux use `python3`.

The scripts default to a previously created `epochguard-002a` builder. On a fresh clone, explicitly select Docker's default builder:

```powershell
py -3.12 tests/boundedprose/qualify.py --build --builder default
```

If the default builder cannot resolve GitHub or the Go module proxy, the repository provides an **optional** isolated DNS configuration:

```powershell
docker buildx create --name epochguard-002a --driver docker-container --buildkitd-config dev/buildkitd.toml
docker buildx inspect epochguard-002a --bootstrap
py -3.12 tests/boundedprose/qualify.py --build --builder epochguard-002a
```

That configuration uses public resolvers; use an organization-approved resolver configuration where required. Do not recreate or remove an existing builder without checking who owns it.

The bounded-prose driver builds this dependency chain:

| Image | Dockerfile / context | Build method |
| --- | --- | --- |
| `epochguard-dev:002a` | `dev/Dockerfile`, repository root | Buildx with selected builder and `--load` |
| `epochguard-verifier:004c` | `services/verifier/Dockerfile.004c`, repository root | Buildx with selected builder and `--load` |
| `epochguard-verifier:004e` | `services/verifier/Dockerfile.004e`, repository root | `docker build`, using local 004C base tag |
| `epochguard-verifier:004g` | `services/verifier/Dockerfile.004g`, repository root | `docker build`, using local 004E base tag |

Derived images must be built in the daemon that holds the local base tags; a container builder may instead try to pull those unpublished tags. The native Dockerfile runs Go formatting, vet, unit/race checks and builds the actual gateway/plugin and test binaries. Python image builds run their packaged offline suites. Unit race checks do not instrument the running gateway.

## Protected offline qualifications

All three stacks below publish no ports, need no evidence credentials and use disposable signing-key volumes. Run them sequentially. Drivers stop/remove their stacks and key volumes in `finally`; if a host process is killed, run the matching cleanup manually.

| Qualification | Command after images exist | Outputs | Contract |
| --- | --- | --- | --- |
| Bounded prose and security/lifecycle regressions | `py -3.12 tests/boundedprose/qualify.py` | `artifacts/004g/qualification/` | Current request-bound v2 |
| Original protected ingress | `py -3.12 tests/protectedingress/qualify.py` | `artifacts/004d/reproduction/` | Explicitly legacy v1 |
| Exact-template multi-claim, simulated sources/faults | `py -3.12 tests/livequalification/qualify.py` | `artifacts/004e/offline/` | Explicitly legacy v1 |

Each accepts `--build --builder default` to build its required images. The bounded-prose runner has **no live option** and never reads evidence credentials. A normal E invocation is also offline despite its script directory name. Preserve existing live evidence before reusing the E live output directory; the driver writes fixed filenames.

```powershell
docker compose -f compose.verify.004g.yaml down --volumes --remove-orphans
docker compose -f compose.verify.004d.yaml down --volumes --remove-orphans
docker compose -f compose.verify.004e.offline.yaml down --volumes --remove-orphans
```

These commands remove only the selected Compose project's resources, including its disposable signing key. See [G security evidence](task-004gs.md), [D lifecycle evidence](task-004d.md) and [E source-fault evidence](task-004e.md) for asserted cases and recorded results. G tests include retained-nonce request substitution, metadata sentinels, receipt faults, source failures, overload/recovery, disabled-plugin concurrency and real restarts. Finite fixture coverage is not a general security proof.

## Other isolated gateway regressions

Build `epochguard-dev:002a` first, using the protected runner or this command:

```powershell
docker buildx build --builder default --load -t epochguard-dev:002a -f dev/Dockerfile .
```

The fixed-decision development smoke suite is **not factual verification**. Its primary gateway is loopback-bound; other listed isolated suites have no host ports. Pair each startup/run with cleanup even if an assertion fails.

```powershell
# Native loader, fixed decisions and negative controls
docker compose --profile test up -d --force-recreate --wait provider gateway gateway-control gateway-reject gateway-unavailable
docker compose --profile test run --rm --no-deps smoke
docker compose --profile test down --volumes --remove-orphans

# Legacy single-policy verification with an HTTP evidence fixture
docker compose -f compose.verify.yaml build verifier-supported
docker compose -f compose.verify.yaml run --rm verification-tests
docker compose -f compose.verify.yaml down --volumes --remove-orphans

# Exact-template multi-claim mode, fixture evidence and faulty verifier records
docker buildx build --builder default --load -t epochguard-verifier:004c -f services/verifier/Dockerfile.004c .
docker compose -f compose.verify.004c.yaml up -d --force-recreate --wait --no-build gateway gateway-faults gateway-control
docker compose -f compose.verify.004c.yaml run --rm --no-deps qualification
docker compose -f compose.verify.004c.yaml down --volumes --remove-orphans

# Route-surface audit, including explicit unprotected controls
docker compose -f compose.routes.yaml up -d --wait reject control warp-control warp-reject nolog
docker compose -f compose.routes.yaml run --rm --no-deps route-tests
docker compose -f compose.routes.yaml down --volumes --remove-orphans

# Intentionally unsafe cache-ordering/invalidation experiments
docker compose -f compose.cache.yaml up -d --wait provider store-proxy writer reader reject safe unavailable post-reject post-allow
docker compose -f compose.cache.yaml run --rm --no-deps cache-tests
docker compose -f compose.cache.yaml down --volumes --remove-orphans

# Separate long post-hook deadline regression; build legacy verifier image above first
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml up -d --force-recreate --wait gateway-supported
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml run --rm --no-deps verification-tests
docker compose -f compose.verify.yaml -f compose.verify.timeouts.yaml down --volumes --remove-orphans
```

The cache suite deliberately demonstrates unsafe admission/repopulation behavior. It does not enable or qualify protected caching. [Route](task-003c.md), [cache](task-002c.md) and [timeout](task-003a.md#2026-11-07-follow-up-configurable-live-timeouts) reports retain exact test evidence.

## Python development and offline checks

For local CLI use, create the explicitly ignored environment rather than assuming it exists:

```powershell
py -3.12 -m venv .venv-003a
& .venv-003a/Scripts/python.exe -m pip install -r services/verifier/requirements.lock
$env:PYTHONPATH = 'services/verifier;services/claim_analysis'
& .venv-003a/Scripts/python.exe -m verifier.multiclaim
& .venv-003a/Scripts/python.exe -m verifier.prose analyze --engine baseline --text-file services/verifier/examples/prose/mapped.txt
```

On Linux use `python3 -m venv .venv-003a`, `.venv-003a/bin/python`, and `PYTHONPATH=services/verifier:services/claim_analysis`. The sibling claim-analysis requirements reference the same lockfile. See [verifier APIs](../services/verifier/README.md) and [analysis CLI/evaluation](../services/claim_analysis/README.md) for contracts and exports.

Run the combined offline Python regression suite in a network-disabled container after building the G image. The read-only mount checks the current source tree rather than only the image snapshot:

```powershell
docker run --rm --network none --mount "type=bind,source=$($PWD.Path),target=/src,readonly" --workdir /src/services/verifier -e PYTHONPATH=/src/services/verifier:/src/services/claim_analysis -e PYTHONDONTWRITEBYTECODE=1 epochguard-verifier:004g python -B -m pytest -c /src/services/verifier/pytest.ini -p no:cacheprovider /src/services/verifier/tests /src/services/verifier/tests_multiclaim /src/services/verifier/tests_gateway /src/services/verifier/tests_live /src/services/verifier/tests_prose /src/services/verifier/tests_bounded_prose /src/services/claim_analysis/tests -q
```

The checked-in pytest selection excludes live tests. No evidence/model credentials are passed. Linux users should substitute their shell's absolute repository path for `$($PWD.Path)`. Do not enable live markers or remove network isolation in an offline regression run.

## Explicit legacy real-source qualification

The existing real-source driver qualifies **exact templates with legacy v1 receipts**, not current bounded-prose v2. It uses a controlled provider and actual Tavily/Python.org and PyPI. The [November 14 assessment](task-004e.md#maintainer-live-qualification--november-14-2026) is historical evidence; rerunning can incur cost and may fail safely as sources change.

Only run the following after separate operator authorization, offline checks, image builds and preservation of previous `artifacts/004e/live/` results. There is no automatic live step. The maximum is **three application-level retrieval attempts per source**, including one preflight and two factual gateway requests. There are no source retries, model calls or paid fault injections. These bounds do not independently measure billing or origin fetches.

Use PowerShell on Windows. The example creates a private temporary directory before writing the secret, disables inherited access and grants the current Windows identity access. Docker Desktop must be able to mount that file using the authorized account; do not loosen it to broad user groups to work around mount errors.

```powershell
$secretDirectory = Join-Path $env:TEMP ('epochguard-004e-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $secretDirectory -ErrorAction Stop | Out-Null
$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
icacls $secretDirectory /inheritance:r /grant:r "${currentIdentity}:(OI)(CI)F" | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not restrict the temporary secret directory.' }
$env:EPOCHGUARD_TAVILY_SECRET_HOST_FILE = Join-Path $secretDirectory 'tavily.key'
try {
    $secureKey = Read-Host 'Tavily key for this bounded run' -AsSecureString
    $keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    try {
        $keyText = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
        [IO.File]::WriteAllText($env:EPOCHGUARD_TAVILY_SECRET_HOST_FILE, $keyText, [Text.UTF8Encoding]::new($false))
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
        Remove-Variable keyText, secureKey, keyPointer -ErrorAction SilentlyContinue
    }
    $env:EPOCHGUARD_RUN_LIVE_004E = '1'
    py -3.12 tests/livequalification/qualify.py --live
    if ($LASTEXITCODE -ne 0) { Write-Host 'Inspect the collected failure; do not retry automatically.' }
} finally {
    docker compose -f compose.verify.004e.yaml down --volumes --remove-orphans
    Remove-Item -LiteralPath $env:EPOCHGUARD_TAVILY_SECRET_HOST_FILE -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $secretDirectory -ErrorAction SilentlyContinue
    Remove-Item Env:EPOCHGUARD_TAVILY_SECRET_HOST_FILE, Env:EPOCHGUARD_RUN_LIVE_004E -ErrorAction SilentlyContinue
}
```

Only the verifier mounts the source secret. Do not print it, dump environments or resolved live Compose configuration, persist raw source bodies/receipts, or put secrets into source, image layers, command literals or artifacts. The runtime source credential is distinct from the disposable HMAC signing key. Process memory and temporary-file deletion are not a production secret-management or secure-erasure guarantee.

The driver starts a disposable stack, checks source-free readiness, collects one preflight, then exercises supported/older/unsupported/no-plugin/provider-error cases through ingress. It reports sanitized HTTP status, latency, claims/evidence bindings, source changes and application invocation counts. Review `preflight.json`, `measurements.json` and `report.json`; a collected run is not an independent final qualification. Source changes can make the run inconclusive; preserve the failure rather than retrying to manufacture success. Live and offline E profiles reserve the same private subnet and must not run together.

The older single-policy [live workflow](task-003b.md#reproduction) uses a different credential/deployment boundary, including an explicitly selected loopback listener. Do not mix it with the protected runtime-secret procedure. Individual [source probes](../services/verifier/README.md#optional-real-source-observations) and [Gemini diagnostics](../services/claim_analysis/README.md#opt-in-real-gemini-analysis) also require their own opt-in and never establish gateway qualification.

## Bounded-prose live status

**004G LIVE QUALIFICATION PENDING.** A gated Python live factory exists, reusing E's fixed sources, runtime-secret boundary and budgets plus a separate G opt-in. No tracked G live Compose deployment or qualification driver exists. Do not repoint the E live runner and claim it tested G's grammar, request-bound receipt or metadata projection. A separately reviewed harness and separately authorized real-source run are required.

## Diagnostics and cleanup

Use the driver's sanitized case/build outputs to diagnose failures; ignored artifacts are local evidence, not published releases. The G runtime-log scan reads logs in memory and emits a fixed failure category rather than persisting an offending line. Do not expand diagnostic logging to candidate/provider/source bodies, receipt headers or secrets. Full CLI `--json` and evaluation exports intentionally contain supplied source text; use nonprivate fixtures or protect those exports separately.

A failed build can reflect registry/network/toolchain availability rather than an enforcement regression. Keep that failure distinct from a passing unit or gateway result. Run only the relevant matching cleanup commands, inspect their exit status and preserve meaningful failure evidence. Cleanup does not remove the shared Buildx builder or previously saved live reports.
