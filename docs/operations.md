# Operations and reproducible qualification

Run commands from the repository root. These are workflows to execute deliberately, not claims of new test execution. Historical outcomes remain in the linked reports; [architecture](architecture.md) defines the current guarantees.

## Separate Experimental Evidence Explorer

`py -3.12 services/evidence_assessment/manage.py up --build` starts the isolated UI at **http://127.0.0.1:8791** with simulated Tavily/Gemini transports. `py -3.12 services/evidence_assessment/manage.py test --build` runs three actual offline HTTP demonstrations and verifies cleanup. Stop interactive use with `py -3.12 services/evidence_assessment/manage.py down`. This mode always has `authorization=false` and does not alter the Lab at 8787 or its protected stack.

The [Explorer guide](../services/evidence_assessment/README.md) documents frozen-packet evaluation, optional browser qualification and a separately authorized live smoke with private external files, independent provider opt-ins and explicit costs. No normal startup or test command makes paid calls. [005I](task-005i.md) records actual measurements and known semantic/source limitations. The existing protected five-case smoke can be reproduced with `py -3.12 tests/evidence_assessment/protected_smoke.py` after building the documented native/004G images; it uses a separate private project, records immutable local image IDs and removes its signing volume.

[005J](task-005j.md) adds safe backend model-failure diagnostics and an offline `tests/evidence_assessment/output_budget.py` size investigation. See the [diagnostic guide](../services/evidence_assessment/README.md#model-validation-diagnostics) for fixed categories and credential-free log inspection. No automatic live retry, output-cap increase, private-setting edit or container restart follows from a validation failure.

## Interactive offline Lab

Use the [Verification Lab guide](verification-lab.md) for the actual React/Go browser application and its separate loopback-only Compose stack. From PowerShell, `py -3.12 tests/lab/manage.py up --build` builds/starts it and `py -3.12 tests/lab/manage.py down` removes it. The helper bypasses `.env`; no credential or live evidence is used. The headless qualifications below remain separate from judge interaction.

## Prerequisites and build selection

Use Git, Docker Desktop in Linux-container mode (or Docker Engine on Linux), Compose v2, Buildx and Python 3.12. Native images target Linux/amd64; the qualified host is Windows x86-64. Other host architectures/emulation and a separate Linux Engine installation are untested. Initial builds download pinned source/dependencies and may take several minutes. Qualification cases use private networks and fixtures unless explicitly marked live.

The historical host qualification scripts use only Python's standard library. The separate 005C/005C-R tools reuse locked Pydantic dependencies and need the documented virtual environment. No local Go installation is required. In PowerShell use `py -3.12` for standard-library drivers; on Linux use `python3`.

The Lab launcher uses Docker's selected builder unless `--builder` is supplied. Historical qualification scripts default to a previously created `epochguard-002a` builder. Inspect `docker context show` / `docker buildx ls` and select a builder matching the active context. For Docker Desktop's Linux context:

```powershell
py -3.12 tests/boundedprose/qualify.py --build --builder desktop-linux
```

On Linux the builder may be named `default`; that literal name can conflict with the active Docker Desktop context. See [compatibility diagnostics](compatibility.md#builder-and-abi-diagnostics). If the selected builder cannot resolve GitHub or the Go module proxy, the repository provides an **optional** isolated DNS configuration:

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
| Bounded-prose live driver, offline transport mode | `py -3.12 tests/boundedproselive/qualify.py` | `artifacts/004gl/offline/` | Current request-bound v2; no live calls |
| Original protected ingress | `py -3.12 tests/protectedingress/qualify.py` | `artifacts/004d/reproduction/` | Explicitly legacy v1 |
| Exact-template multi-claim, simulated sources/faults | `py -3.12 tests/livequalification/qualify.py` | `artifacts/004e/offline/` | Explicitly legacy v1 |

Each accepts `--build --builder NAME` to build its required images. The bounded-prose runner has **no live option** and never reads evidence credentials. A normal E invocation is also offline despite its script directory name. Preserve existing live evidence before reusing the E live output directory; the driver writes fixed filenames.

Bypass `.env` when invoking the older host drivers; use a dedicated terminal and do not set live opt-ins. The comment-only environment file contains no assignments:

```powershell
$env:COMPOSE_DISABLE_ENV_FILE = '1'
$env:COMPOSE_ENV_FILES = (Join-Path $PWD.Path 'dev/lab.compose.env')
py -3.12 tests/boundedprose/qualify.py
py -3.12 tests/boundedproselive/qualify.py
py -3.12 tests/protectedingress/qualify.py
py -3.12 tests/livequalification/qualify.py
Remove-Item Env:COMPOSE_DISABLE_ENV_FILE -ErrorAction SilentlyContinue
Remove-Item Env:COMPOSE_ENV_FILES -ErrorAction SilentlyContinue
```

G-L without `--live` is simulated/offline. Run the stacks sequentially. A nonzero exit requires inspection of the named local stage and completion of cleanup before continuing. No paid rerun is part of regression.

```powershell
docker compose --env-file dev/lab.compose.env -f compose.verify.004g.yaml down --volumes --remove-orphans
docker compose --env-file dev/lab.compose.env -f compose.verify.004d.yaml down --volumes --remove-orphans
docker compose --env-file dev/lab.compose.env -f compose.verify.004e.offline.yaml down --volumes --remove-orphans
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
docker compose --env-file dev/lab.compose.env -f compose.verify.yaml build verifier-supported
docker compose --env-file dev/lab.compose.env -f compose.verify.yaml run --rm verification-tests
docker compose --env-file dev/lab.compose.env -f compose.verify.yaml down --volumes --remove-orphans

# Exact-template multi-claim mode, fixture evidence and faulty verifier records
docker buildx build --builder default --load -t epochguard-verifier:004c -f services/verifier/Dockerfile.004c .
docker compose --env-file dev/lab.compose.env -f compose.verify.004c.yaml up -d --force-recreate --wait --no-build gateway gateway-faults gateway-control
docker compose --env-file dev/lab.compose.env -f compose.verify.004c.yaml run --rm --no-deps qualification
docker compose --env-file dev/lab.compose.env -f compose.verify.004c.yaml down --volumes --remove-orphans

# Route-surface audit, including explicit unprotected controls
docker compose --env-file dev/lab.compose.env -f compose.routes.yaml up -d --wait reject control warp-control warp-reject nolog
docker compose --env-file dev/lab.compose.env -f compose.routes.yaml run --rm --no-deps route-tests
docker compose --env-file dev/lab.compose.env -f compose.routes.yaml down --volumes --remove-orphans

# Intentionally unsafe cache-ordering/invalidation experiments
docker compose --env-file dev/lab.compose.env -f compose.cache.yaml up -d --wait provider store-proxy writer reader reject safe unavailable post-reject post-allow
docker compose --env-file dev/lab.compose.env -f compose.cache.yaml run --rm --no-deps cache-tests
docker compose --env-file dev/lab.compose.env -f compose.cache.yaml down --volumes --remove-orphans

# Separate long post-hook deadline regression; build legacy verifier image above first
docker compose --env-file dev/lab.compose.env -f compose.verify.yaml -f compose.verify.timeouts.yaml up -d --force-recreate --wait gateway-supported
docker compose --env-file dev/lab.compose.env -f compose.verify.yaml -f compose.verify.timeouts.yaml run --rm --no-deps verification-tests
docker compose --env-file dev/lab.compose.env -f compose.verify.yaml -f compose.verify.timeouts.yaml down --volumes --remove-orphans
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
docker run --rm --network none --mount "type=bind,source=$($PWD.Path),target=/src,readonly" --workdir /src/services/verifier -e PYTHONPATH=/src/tests:/src/services/verifier:/src/services/claim_analysis -e PYTHONDONTWRITEBYTECODE=1 epochguard-verifier:004g python -B -m pytest -c /src/services/verifier/pytest.ini -p no:cacheprovider /src/services/verifier/tests /src/services/verifier/tests_multiclaim /src/services/verifier/tests_gateway /src/services/verifier/tests_live /src/services/verifier/tests_prose /src/services/verifier/tests_bounded_prose /src/services/verifier/tests_claim_report /src/services/claim_analysis/tests -q
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
    docker compose --env-file dev/lab.compose.env -f compose.verify.004e.yaml down --volumes --remove-orphans
    Remove-Item -LiteralPath $env:EPOCHGUARD_TAVILY_SECRET_HOST_FILE -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $secretDirectory -ErrorAction SilentlyContinue
    Remove-Item Env:EPOCHGUARD_TAVILY_SECRET_HOST_FILE, Env:EPOCHGUARD_RUN_LIVE_004E -ErrorAction SilentlyContinue
}
```

Only the verifier mounts the source secret. Do not print it, dump environments or resolved live Compose configuration, persist raw source bodies/receipts, or put secrets into source, image layers, command literals or artifacts. The runtime source credential is distinct from the disposable HMAC signing key. Process memory and temporary-file deletion are not a production secret-management or secure-erasure guarantee.

The driver starts a disposable stack, checks source-free readiness, collects one preflight, then exercises supported/older/unsupported/no-plugin/provider-error cases through ingress. It reports sanitized HTTP status, latency, claims/evidence bindings, source changes and application invocation counts. Review `preflight.json`, `measurements.json` and `report.json`; a collected run is not an independent final qualification. Source changes can make the run inconclusive; preserve the failure rather than retrying to manufacture success. Live and offline E profiles reserve the same private subnet and must not run together.

The older single-policy [live workflow](task-003b.md#reproduction) uses a different credential/deployment boundary, including an explicitly selected loopback listener. Do not mix it with the protected runtime-secret procedure. Individual [source probes](../services/verifier/README.md#optional-real-source-observations) and [Gemini diagnostics](../services/claim_analysis/README.md#opt-in-real-gemini-analysis) also require their own opt-in and never establish gateway qualification.

## Bounded-prose live qualification

**Narrow G live acceptance reviewed and met:** the November 15, 2026 operator run and subsequent sanitized-record assessment are recorded in [the dated review](task-004gl.md#reviewed-live-qualification--november-15-2026). Reproduction remains separately opted in and potentially billable; it is not needed to run the offline Lab. Its [evidence report](task-004gl.md) records exact results and measurement limits. Existing E profiles and historical live evidence are unchanged.

First build and run the new fixture-only qualification. This command has no live opt-in, egress or credential access:

```powershell
py -3.12 tests/boundedproselive/qualify.py --build --builder default
```

The driver builds the existing native/004C/004E/004G chain plus the separate `epochguard-verifier:004gl` image. It runs the five bounded-prose client cases through actual ingress/gateway/Go/Python, requires unchanged supported content in the minimal envelope, and verifies that the live-configured Go control refuses supported **fixture** evidence. Both G-L verifier commands use Uvicorn concurrency 32; evidence admission remains one active operation. The offline profile retains `fixture` source modes; its Go HTTP ceiling is 30s without the live-only remaining-work profile. It does not simulate a live source identity.

The existing [G security/lifecycle driver](../tests/boundedprose/qualify.py) separately covers v2 receipt faults, exact request substitution, metadata channels, disabled-plugin concurrency, timeout and restart recovery. Both runners clean their own stacks/key volumes. Manual G-L offline cleanup is:

```powershell
docker compose --env-file dev/lab.compose.env -f compose.verify.004gl.offline.yaml down --volumes --remove-orphans
```

**Only after separate operator authorization**, run the following in Windows PowerShell from the repository root, after building/checking the images offline. It starts a separate G live stack; it does not execute the E live runner. The existing E authorization is required along with the additional G opt-in. The key is entered into a fresh restricted temporary file; no existing credential file is read by the host driver.

```powershell
$secretDirectory = Join-Path $env:TEMP ('epochguard-004gl-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $secretDirectory -ErrorAction Stop | Out-Null
$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
icacls $secretDirectory /inheritance:r /grant:r "${currentIdentity}:(OI)(CI)F" | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not restrict the temporary secret directory.' }
$env:EPOCHGUARD_TAVILY_SECRET_HOST_FILE = Join-Path $secretDirectory 'tavily.key'
try {
    $secureKey = Read-Host 'Tavily key for this bounded G qualification' -AsSecureString
    $keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    try {
        $keyText = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
        [IO.File]::WriteAllText($env:EPOCHGUARD_TAVILY_SECRET_HOST_FILE, $keyText, [Text.UTF8Encoding]::new($false))
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
        Remove-Variable keyText, secureKey, keyPointer -ErrorAction SilentlyContinue
    }
    $env:EPOCHGUARD_RUN_LIVE_004E = '1'
    $env:EPOCHGUARD_RUN_LIVE_004G = '1'
    py -3.12 tests/boundedproselive/qualify.py --live
    if ($LASTEXITCODE -ne 0) { Write-Host 'Inspect the failed or inconclusive run; do not retry automatically.' }
} finally {
    docker compose --env-file dev/lab.compose.env -f compose.verify.004gl.yaml down --volumes --remove-orphans
    Remove-Item -LiteralPath $env:EPOCHGUARD_TAVILY_SECRET_HOST_FILE -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $secretDirectory -ErrorAction SilentlyContinue
    Remove-Item Env:EPOCHGUARD_TAVILY_SECRET_HOST_FILE, Env:EPOCHGUARD_RUN_LIVE_004E, Env:EPOCHGUARD_RUN_LIVE_004G -ErrorAction SilentlyContinue
}
```

Docker Desktop must be able to mount the file with authorized account access. Keep the E runtime-secret restrictions above: no secret literals, environment dumps, resolved live Compose output or raw receipts/source/provider bodies. The HMAC key is independently generated in a disposable volume. Do not start live and offline G-L together: they reserve the same private subnet. Only the live verifier joins the egress network; no profile publishes host ports.

The process permits at most three retrieval invocations per source, including one preflight and two factual gateway requests. Unsupported prose, missing plugin, provider errors and readiness do not require source retrieval. There is no model call, source retry, polling or automatic rerun. Changing sources can make the outcome inconclusive; never restart the verifier to reset a paid budget and manufacture success.

Each invocation creates a fresh directory under `artifacts/004gl/{offline,live}/<UTC-time>-<random>/`, preserving older runs and all E evidence. Inspect:

- `preflight.json`: validated observations before candidate generation, source/mode, version, evidence identity/hash and local observation times.
- `measurements.json`: `004gl.qualification.v1`, Git revision and harness-file digest; per-case status/outcome, exact-content indicator, request/candidate digests, elapsed/first-body-chunk timings, claims/evidence, source changes and unique-candidate provider counts.
- `observations.json`: sanitized verifier records and per-source attempted/completed invocation timings/counts. A returned page counts as completed even when parsing rejects it; these are not billing or origin-fetch counts.
- `stages.json`, `failure.json` when present, and `cleanup.json`: fixed stage/exit categories and cleanup status. Raw Docker stdout/stderr and service bodies are not saved. If the stack is available after a failure, one source-free report collection is attempted before cleanup.

Receipt protocol is fixed to `004g.receipt.v2`. Its validation outcome is inferred from ingress's authenticated release/refusal contract; the runner does not export or independently reverify raw receipts. Request hashes describe actual serialized client bytes, and ingress independently binds its forwarded bytes to Bifrost's received bytes. First-byte latency means the first decoded HTTP body chunk observed by the client, not network packet timing or an inferred component duration. Provider counts are separate for all five unique candidates; terminal contradiction must use one provider call despite a configured usable fallback.

A live runner success prints `LIVE RUN COLLECTED: independent review required`, not final qualification approval. The report retains `live_qualification_pending=true` as its collection-time state. The November 15 records have since been reviewed; the canonical assessment lives in the dated report rather than rewriting preserved runtime artifacts. A safe refusal, successful fixture run or prior E live result is not a supported G factual delivery.

## Combined model and evidence qualification

005E has an independent [offline-first procedure](task-005e.md#reproduction) and a separate live overlay requiring both model and evidence authorization. After building the documented native/verifier/model dependencies, build its isolated image and run all seven offline batches:

After the [005D-S singleton correction](task-005d-s.md), rebuild native and the complete verifier 004C → 004E → 004G → 004G-L → model → combined dependency chain. Do not use pre-fix images as corrected evidence. The offline identity batch additionally sends Python and PyPI repeated-policy candidates; each must finish independent verification, retrieve no evidence and return protected 503 without answer text. Standard two-policy support must still return 200. Source/image hashes and disposable-stack cleanup are recorded in each new suite; preserve prior qualification directories.

```powershell
docker buildx build --builder desktop-linux --load -t epochguard-combined:005e -f dev/Dockerfile.combined .
$env:PYTHONPATH = 'tests;services/verifier;services/claim_analysis'
& .venv-003a/Scripts/python.exe tests/combinedqualification/qualify.py
```

This invocation has no live opt-in or external network. It checks the actual native loader, adapter, verifier, v2 ingress, source faults, drift and failed sampling. Success creates a 24-hour source/image-bound offline suite record; it does not authorize a live call. Future separately authorized use, source/model cost configuration, private-file ACLs, artifact interpretation and manual cleanup are documented in the task report. Disposable stacks retain private networks and signing-volume cleanup.

## Diagnostics and cleanup

The [November 19, 2026 reviewed 005C-T run](task-005c-t.md#reviewed-real-model-qualification--november-19-2026) met narrow real-Gemini enforcement acceptance with simulated evidence. Its original collection-time pending fields remain unchanged; the dated review is the subsequent assessment. No repeat execution is needed to substantiate that review. The workflows below are for separately authorized future runs; real-model-plus-real-source execution remains unqualified.

005C native Gemini qualification and the separate draft claim-analysis diagnostic have their own [operator procedure](real-model-qualification.md), runtime-secret boundary, cost review and sanitized artifacts. Default real calls are zero; generation and extraction need separate explicit authorization. The implementation phase never enables paid execution. Offline generation uses the actual gateway/native loader with simulated Gemini HTTP and simulated evidence:

```powershell
& .venv-003a/Scripts/python.exe tests/modelqualification/qualify.py --build
& .venv-003a/Scripts/python.exe tests/modelqualification/analysis.py --output artifacts/005c/analysis-offline.json
```

Create the environment from the existing lockfile as shown in the guide if absent. Existing G/G-L source and receipt regressions remain separate required checks. 005C cleanup includes its disposable signing volume; the emergency cleanup manifest needs no credential or variable interpolation:

```powershell
docker compose --env-file dev/lab.compose.env -f compose.verify.005c.cleanup.yaml down --volumes --remove-orphans
```

To reproduce response-shape refusals, first rebuild native and model images as shown in the [diagnostic workflow](real-model-qualification.md#response-refusal-diagnostics-005c-r), then run the three offline batches. These commands use synthetic Gemini envelopes, retain private networks and unchanged budgets, and reject `--live`:

```powershell
foreach ($batch in 1..3) {
    & .venv-003a/Scripts/python.exe tests/modelqualification/qualify.py --shape-batch $batch
    if ($LASTEXITCODE -ne 0) { throw 'Inspect sanitized response-shape artifacts before continuing.' }
}
```

The [005C-S contract audit](task-005c-s.md) adds two conversion-collision controls, bringing the three unadapted batches to 18 cases. Signatures remain refused in that mode. Both historical live directories remain read-only evidence; these commands make no real model or origin-source requests.

The isolated [005C-T adapter](task-005c-t.md) additionally has explicit strict-mode qualification. Rebuild `epochguard-model:005c` after source changes, then run:

```powershell
docker buildx build --builder desktop-linux --load -t epochguard-model:005c -f dev/Dockerfile.model .
& .venv-003a/Scripts/python.exe tests/modelqualification/qualify.py --strict-adapter
1..6 | ForEach-Object {
    & .venv-003a/Scripts/python.exe tests/modelqualification/qualify.py --strict-adapter --adapter-batch $_
    if ($LASTEXITCODE) { throw '005C-T offline batch failed' }
}
```

These 36 original-envelope cases include the four signature-bearing policy scenarios, all known conversion collisions, malformed/ambiguous data and a signature-projected native response with the plugin missing. Each stack retains six model submissions and existing source ceilings, internal networks and disposable signing-volume cleanup. The ordinary strict run also preserves genuine provider-error and timeout distinctions. Configuration defaults to `unadapted`; `--strict-adapter` selects `strict-005ct` in generated offline settings. Future separately authorized live use requires the same explicit flag, matching trusted settings and a current source/mode-matching successful standard offline preflight. Adapter batches are offline-only and do not themselves count as live preflight. No unrelated profile enables adaptation.

Use the driver's sanitized case/build outputs to diagnose failures; ignored artifacts are local evidence, not published releases. The G runtime-log scan reads logs in memory and emits a fixed failure category rather than persisting an offending line. Do not expand diagnostic logging to candidate/provider/source bodies, receipt headers or secrets. Full CLI `--json` and evaluation exports intentionally contain supplied source text; use nonprivate fixtures or protect those exports separately.

A failed build can reflect registry/network/toolchain availability rather than an enforcement regression. Keep that failure distinct from a passing unit or gateway result. Run only the relevant matching cleanup commands, inspect their exit status and preserve meaningful failure evidence. Cleanup does not remove the shared Buildx builder or previously saved live reports.
