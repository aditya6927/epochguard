# Real-model qualification (005C)

## Reviewed qualification status

**Narrow real-model enforcement qualification met**, reviewed November 19, 2026 from the existing sanitized operator-collected records. Run `20261119T092712Z-6d95a336` used revision `87d877c43f3ab46d9d62d279e457f16b8df9c0c3`, `gemini-3.5-flash-lite`, `strict-005ct` and simulated evidence. Four real HTTP 200 generations reached completed independent Python verification; all six protected client expectations met. The supported answer was released unchanged; the older, unsupported and paraphrased answers were withheld. [Exact provenance, correspondence checks and limits](task-005c-t.md#reviewed-real-model-qualification--november-19-2026).

The original implementation was qualified offline, and both November 18 real-model attempts safely refused before this adapter existed. Those reports and the successful run's collection-time `PENDING INDEPENDENT REVIEW` / `COLLECTED; NOT APPROVED` fields remain unchanged. The dated review records the subsequent assessment; another paid run is not required to substantiate it. Real-model-plus-real-source execution remains unqualified, and this run does not qualify arbitrary prose, model-analysis quality, freshness or production use. The procedure below remains available for separately authorized future runs with unchanged opt-ins and budgets.

## Design assessment

Baseline: `5bf1a0b81b1abf9afb7e4519990342c496aadc7b`, initially clean. The smallest supported generation path is native Gemini chat completion in core `v1.14.1`, through the existing pinned transport, native EpochGuard hooks and protected ingress. The existing claim-analysis REST adapter is a separate integration. No model, extractor or resource relay becomes a release authority.

Source inspection: transport `e869c3f9adc96ea53c38694a21bb04a8e1085487`, its `transports/go.mod`, core tag `core/v1.14.1` (`providers/gemini/{gemini,chat,utils}.go`, `schemas/{provider,secretvar}.go`), and framework tag `framework/v1.11.1` (`configstore/tables/key.go`). Native Gemini uses `/models/{model}:generateContent`, `x-goog-api-key`, configurable base URL and deadline. `max_completion_tokens` converts to `generationConfig.maxOutputTokens`. `max_retries: 0` stays zero. `SecretVar.UnmarshalJSON` resolves `env.NAME`; reference-backed database values retain the reference. There is no assumed file-secret API. A qualification-only launcher reads a private runtime file into the gateway process environment; tracked configuration holds only the reference.

The isolated profile uses simulated Python.org/PyPI evidence, unchanged `004g.v1` / `bounded-prose-v1`, nine forms, independent parsers, receipt `004g.receipt.v2` and minimal response projection. A fixed-host resource relay bounds native Gemini HTTP execution and records sanitized invocation/usage information. Requests and genuine provider HTTP failures pass unchanged. Default `unadapted` mode also passes successful responses unchanged. Explicit `strict-005ct` mode validates the complete original response before pinned conversion, then constructs a minimal native STOP envelope retaining the exact decoded visible text and removing validated metadata. It refuses unsupported shapes rather than repairing output. The relay cannot verify claims, mint receipts or select policies. Only that relay has egress in live mode. Offline mode has no egress, credentials or model calls.

Ingress has one explicit qualification option admitting bounded `max_completion_tokens` for native Gemini requests without fallback. Existing profiles keep their existing request language. Internal source-free readiness retains the controlled canary provider and consumes no model budget. Missing-plugin and provider-error controls also use the controlled provider, separately labeled. Live inference requires a successful offline preflight and separate explicit authorization. Completion of implementation is not permission to incur cost.

The review dataset is a new synthetic draft packet. Evaluation reuses the unchanged 004A prompt/schema/alignment, Gemini provider, 004F Analyzer, independent auditor and metrics. Failed cases stay in every denominator. Original 004A/004F datasets and historical results remain unchanged. No held-out labels are opened for tuning.

## Offline preflight

Use the existing Python 3.12 virtual environment and locked dependencies. No new dependency or model SDK is needed. From the repository root:

```powershell
py -3.12 -m venv .venv-003a
& .venv-003a/Scripts/python.exe -m pip install -r services/verifier/requirements.lock
& .venv-003a/Scripts/python.exe tests/modelqualification/qualify.py --build
& .venv-003a/Scripts/python.exe tests/modelqualification/analysis.py --output artifacts/005c/analysis-offline.json
```

Reuse the environment if already present. `--build` builds the native gateway/plugin, verifier C/E/G/G-L dependency chain, then the separate model relay/client image. Build downloads public dependencies; native test stages are network-disabled. The offline stack uses the actual native Gemini conversion, native plugin loader, ingress and verifier with simulated provider HTTP and source transports. It is **controlled provider + simulated evidence**, with zero real inference. No live environment flag changes this default selection. The Lab and ordinary CI never receive provider credentials.

The four generation intentions are exact supported fixture labels, an older Python version, extra unsupported factual prose (including forged policy/URL/hash text), and a paraphrase outside the finite language. The offline stack also exercises native Gemini HTTP failure and timeout, missing plugin and a controlled-provider error. It saves every case and counts no fixture as real inference. Existing G supplies broader request-substitution, receipt replay/downgrade/mismatch/age/malformed, metadata, partial coverage, lifecycle and overload controls; G-L supplies simulated source-failure/binding controls. Run those suites as listed in [operations](operations.md#protected-offline-qualifications); a 005C fixture pass does not replace them.

## Authorized model-to-gateway run

**Future paid runs require separate authorization.** The preserved first operator run made four real HTTP 200 round trips but all four answers were safely refused, with no recorded verifier pipeline work; see [005C-R](task-005c-r.md). The subsequent successful strict-adapter run is assessed above. This documentation review authorizes no further paid run. Obtain separate operator approval before any later use of the following procedure. Use an exact Gemini model supporting native `generateContent` text output and independently verify its current availability, tier and input/output/thought-token rates. The [example settings](../dev/model/settings.example.json) intentionally contain invalid null rates; no historical model or guessed price is selected automatically. Review provider-side spending limits as well.

The qualification admits at most **four** real HTTPS submission attempts, no retries, fallback, tools, source calls, streaming or schema repair. Each native prompt is fixed and below 4,096 bytes; the relay limits the converted request to 8,192 bytes and the raw response to 65,536 bytes. Output limits are 128–1,024 tokens (default 256); provider total deadline is 15 seconds, native network deadline 20 seconds, ingress 44 seconds and each client exchange 48 seconds. The relay admits work only within a 300-second process lifetime and uses the remaining lifetime as a total request deadline. The client role has a 250-second process ceiling. The full gateway is still not claimed to have a qualified global execution deadline.

The runner and relay independently enforce configuration bounds and planning-budget admission. Maximum planning reservation is `(8192 + 1024) * input_rate / 1e6 + output_limit * output_rate / 1e6` per attempt, multiplied by the configured maximum attempts. The relay reserves actual admitted payload bytes plus 1,024 rather than the worst-case 8,192 bound. Failures/cancellation retain reservations. These estimates depend on operator rates and pessimistic byte/token assumptions; they are not a hard billing guarantee or invoice. Usage absent from a response, including failed calls, remains null. Thought tokens are included when the provider reports total tokens. The provider may bill work after a client timeout.

Use a fresh restricted directory outside the repository, never a key already on the host. Keep the dedicated terminal private. This procedure does not put the key in arguments or tracked JSON. Replace the preflight path with the successful report from this exact source tree; source changes invalidate it. No resolved Compose configuration is printed.

```powershell
$secretDirectory = Join-Path $env:TEMP ('epochguard-005c-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $secretDirectory -ErrorAction Stop | Out-Null
$currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
icacls $secretDirectory /inheritance:r /grant:r "${currentIdentity}:(OI)(CI)F" | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not restrict the private directory.' }
$secretFile = Join-Path $secretDirectory 'provider.key'
$settingsFile = Join-Path $secretDirectory 'gateway-settings.json'
try {
    $configuration = @{
        model = Read-Host 'Exact authorized Gemini model ID'
        max_requests = 4
        output_tokens = 256
        input_usd_per_million = [double](Read-Host 'Current input USD per million tokens')
        output_usd_per_million = [double](Read-Host 'Current output/thought USD per million tokens')
        max_request_usd = [double](Read-Host 'Maximum planning USD per request (up to 10)')
        max_run_usd = [double](Read-Host 'Maximum planning USD per run (up to 25)')
    }
    $reservation = ((9216 * $configuration.input_usd_per_million) + (256 * $configuration.output_usd_per_million)) / 1000000
    Write-Host ('Maximum admitted planning reservation: USD ' + ($reservation * $configuration.max_requests))
    $approved = Read-Host 'After reviewing rates and provider spending limits, type AUTHORIZE FOUR CALLS'
    if ($approved -cne 'AUTHORIZE FOUR CALLS') { throw 'Live run not authorized.' }
    [IO.File]::WriteAllText($settingsFile, ($configuration | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
    $secureKey = Read-Host 'Dedicated qualification API key' -AsSecureString
    $keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    try {
        [IO.File]::WriteAllText($secretFile, [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer), [Text.UTF8Encoding]::new($false))
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
        Remove-Variable secureKey, keyPointer -ErrorAction SilentlyContinue
    }
    $preflightReport = Read-Host 'Path to successful matching offline report.json'
    $env:EPOCHGUARD_RUN_MODEL_005C = '1'
    & .venv-003a/Scripts/python.exe tests/modelqualification/qualify.py --live --settings $settingsFile --secret-file $secretFile --offline-preflight $preflightReport
    if ($LASTEXITCODE -ne 0) { Write-Host 'Inspect sanitized artifacts; no automatic retry.' }
} finally {
    Remove-Item Env:EPOCHGUARD_RUN_MODEL_005C -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $secretFile, $settingsFile -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $secretDirectory -ErrorAction SilentlyContinue
}
```

Docker Desktop must mount the file using the authorized account; do not broaden ACLs to work around mount failures. The runner bypasses `.env`, strips inherited model/source credentials, rejects credential files inside the repository, refuses an existing qualification project and removes task-owned containers/networks/signing volumes in `finally`. It never restarts the relay to reset a paid budget. An interrupted host process may require manual cleanup before deleting its secret. For that case, select only this project's resources:

```powershell
docker compose --env-file dev/lab.compose.env -f compose.verify.005c.cleanup.yaml down --volumes --remove-orphans
```

The cleanup manifest identifies only this project's resources and has no startable service, variable interpolation or credential. Preserve artifacts first and inspect cleanup's exit status. Never stop unrelated projects. The runtime secret is mounted only in the gateway; a launcher exports it only inside that process. Bifrost loads the native `env.*` reference, sends the key on the private relay hop, and the relay forwards only that key to a fixed HTTPS host. The relay is trusted with this in-memory header and untrusted provider content. Gateway diagnostics are suppressed because arbitrary upstream error logging is not qualified. Neither relay nor client logs raw bodies. Receipt keys remain in their separate disposable private volume. Trusted host/root/process inspection, ordinary file deletion and container isolation are not production secret management or secure erasure.

## Inspecting gateway evidence

Each run creates a new `artifacts/005c/{offline,live}/<UTC-time>-<random>/` directory. Inspect `report.json`, `observations.json`, `stages.json` and `failure.json` when present. No existing run is overwritten. Report source revision plus source digest identify the executed working implementation; HEAD alone does not describe uncommitted changes.

New runs also collect qualification-only native stages. Diagnostics change the source digest, so an older offline preflight cannot admit a later live run. Rebuild native/model images and collect a matching ordinary offline qualification first. Shape-only batches are not successful ordinary live preflight records.

`report.json` distinguishes intended scenario, whether observed provider text matched that intention, actual client outcome, answer release, exact content digest, timing and relay attempts. `observations.json` includes sanitized verifier candidate hashes, coverage, verdicts and fixture source records. The relay observes grammar/usage without authorizing anything. A submission attempt with a transport error does not prove remote inference; an HTTP response confirms a provider round trip but does not independently establish billing. Counts are application observations. The simulated timeout is a mock transport exception; existing ingress tests separately cover a response that stalls while buffered.

Model compliance is uncertain. Unsupported wording in the intended supported case must remain UNAVAILABLE. A different supported response can be safely released if the actual checks pass, but does not satisfy that intended case. No output is repaired, reconstructed or replayed into a fixture. Model reasoning parts, tool calls or other unsupported envelopes may safely fail the existing plugin contract. A live collection never declares final qualification: inspect actual provider round trips, matching exact response hashes, independent verifier records, intended/observed differences and client outcomes before assessing **NARROW REAL-MODEL QUALIFICATION MET**. No real-model qualification is currently claimed.

## Response-refusal diagnostics (005C-R)

The first real-provider report is preserved unchanged at `artifacts/005c/live/20261118T193532Z-771f9f45/`. Its null text hashes do not prove no text, truncation, or thinking-only generation. The old observer ignored text when parts had extra fields, and the exact finish/part structure was not saved. A signature-bearing text part is one source-demonstrated mechanism: native Bifrost converts the signature to reasoning metadata and EpochGuard refuses its assistant union before evidence checks. This hypothesis is not a retroactive diagnosis of the original run.

The relay now reports `response_structure` with capped candidate/part counts and allowlisted structural fields, categorized finish reasons, visible/thinking-only/empty-text flags and grammar applicability. Visible text can be recognized alongside metadata, but original parts are never normalized or concatenated. `reported_output_tokens_without_usable_candidate` means reported output consumption without a single nonempty stopped visible text part; it is not a billing claim or Go eligibility decision. Signature contents, thinking text and arbitrary field/reason values are never exported.

The Go stage trace uses trusted `qualification_diagnostics: true` only with fixture prose and bound v2 attestation. It writes fixed enums and request digests to a 0600 gateway tmpfs file, capped at 64 KiB/16 stages per exchange, and the host collects it with private Docker exec. No protected response/header or public endpoint exposes it. `native_stages` joins the actual ingress request digest to candidate/finish/annotation refusal, verifier attempt/response and policy-validation stages. A completed HTTP hop still needs body/contract validation. Missing diagnostics fail collection, never authorize release. Ordinary profiles default off, and gateway general logs remain suppressed.

Rebuild both artifacts before using the new diagnostic profile; a stale native plugin cannot provide these observations:

```powershell
docker buildx build --builder epochguard-002a --load -t epochguard-dev:002a -f dev/Dockerfile .
docker build --load -t epochguard-model:005c -f dev/Dockerfile.model .
& .venv-003a/Scripts/python.exe tests/modelqualification/qualify.py
foreach ($batch in 1..3) {
    & .venv-003a/Scripts/python.exe tests/modelqualification/qualify.py --shape-batch $batch
    if ($LASTEXITCODE -ne 0) { throw 'Inspect sanitized artifacts; do not continue after a failed batch.' }
}
```

Use the builder belonging to the intended Docker context; the name above is the inspected local builder. The 18 synthetic envelopes include missing/empty output, truncation, thinking/signatures, extra metadata/grounding annotations, malformed JSON, unsupported prose, exact support and contradiction, plus two 005C-S conversion-collision controls. Three disposable batches keep the existing per-process budgets. They have no egress, credentials, real model calls or origin-source fetches, and cannot be combined with `--live`. Their successful results do not establish what the historical model actually returned.

Inspect `client.json`, `observations.json`, `report.json` and process `stages.json`; the last is orchestration, while `native_stages` contains the Go boundaries. Root-cause uncertainty and exact offline outcomes belong in the [diagnostic report](task-005c-r.md). Any future real-model run still requires separate authorization and independent review, with no automatic model, thinking or output-limit change.

The later run `20261118T205130Z-06b231a3` preserves the exact visible text, STOP and single text/signature part, establishing its signature-related refusal. The [005C-S audit](task-005c-s.md) withholds a typed-only exception: the converter can produce identical typed responses after discarding file data or a second native candidate. Original part/candidate restrictions cannot be recovered from encrypted reasoning-detail fields alone. [005C-T](task-005c-t.md) supplies explicit original-envelope validation before conversion; shared Go eligibility stays strict. Both November 18 runs remain immutable. The subsequently reviewed November 19 strict-adapter run met narrow real-model enforcement acceptance with simulated evidence.

## Strict original-envelope adapter (005C-T)

The trusted qualification setting `response_mode` is `unadapted` by default; its only other value is `strict-005ct`. The [exact accepted field/size contract](task-005c-t.md#accepted-native-contract) is deliberately narrower than Gemini's full schema. It permits one non-thinking text part, optionally carrying one bounded canonical standard-base64 signature, in one STOP model candidate. It validates admitted usage/identity/timestamp metadata before dropping it. Unsupported fields, aliases and extra output refuse even when empty. Raw response bodies, text and signatures remain only in memory.

Use the [offline strict commands](operations.md#diagnostics-and-cleanup) before any later separately authorized live execution. A future live strict run requires both `--strict-adapter` and `"response_mode": "strict-005ct"` in its trusted operator settings, along with all existing live flags, credentials and budgets. Its offline preflight must be a successful standard strict run with the current qualification source digest and matching mode. Old or unadapted preflights cannot enable strict adaptation. Shape/adapter batches cannot run live. This documentation does not authorize a paid run.

Strict-mode HTTP 200 originals produce an `adapter` diagnostic with fixed validation/refusal category, original/projected response hashes, original/projected UTF-8 text hashes, signature-presence flag and exact text equality. Refused originals have no projected digest. Original provider HTTP status and invocation accounting remain visible separately from the final client outcome. A structural refusal returns a sanitized 502 provider-output failure to Bifrost, never an evidence contradiction. Provider non-200 failures bypass adaptation and preserve their failure identity. Independent verifier stages/results and protected client outcomes remain separately recorded. These correspondence observations trust the relay adapter; neither a digest nor a provider signature independently proves origin, freshness or correctness. No signature or original provider metadata reaches the protected client.

## Claim-analysis evaluation

The separate [18-case review packet](../tests/modelqualification/data/README.md) is synthetic and draft-labeled. It was authored and frozen before any new model results. It is not blind gold. `--require-human-reviewed` fails until independently reviewed versioned data exists. Deterministic 004A baseline and 004F auditor comparisons can run offline. Gemini alone and Gemini combined with the auditor remain missing measurements until actual execution. Fake adapters and historical diagnostics do not fill those cells.

The diagnostic sends each entire untrusted response to the existing Gemini provider, `004a.prompt.v2`, `004a.identification.v1`, exact alignment and strict canonical checks. The existing 004F Analyzer/auditor and scoring are reused. Classification and all-omission counts supplement the existing metrics. Every case remains in the denominator, including alignment errors, provider failures, budget refusals and uncertain/unsupported plans. Failures and abstentions are separate; valid JSON does not establish correctness or completeness. Exported summaries contain code-point offsets/classifications/uncertainty, fixed diagnostics and measurements, without raw model replies or duplicated source text.

After **separate approval for up to 18 analysis calls**, use a fresh restricted file/key procedure as above. Write a nonsecret settings JSON matching existing `claim_analysis.gemini.ModelSettings`: explicit `model`, `max_requests: 18`, `timeout_seconds` (0.1–60), `max_output_tokens` (128–8192), input/output rates and per-request/run planning caps. Review pessimistic reservation for the entire prompt, schema, candidate bytes plus 1,024 and maximum output tokens. Gateway generation and claim extraction are separate billing paths. Only then:

```powershell
$env:EPOCHGUARD_RUN_ANALYSIS_005C = '1'
$env:EPOCHGUARD_ALLOW_MODEL_CALLS = '1'
try {
    & .venv-003a/Scripts/python.exe tests/modelqualification/analysis.py --live --settings $settingsFile --secret-file $secretFile --max-requests 18 --output artifacts/005c/analysis-live.json
} finally {
    Remove-Item Env:EPOCHGUARD_RUN_ANALYSIS_005C, Env:EPOCHGUARD_ALLOW_MODEL_CALLS -ErrorAction SilentlyContinue
}
```

Supply settings/key paths from that separately authorized secure procedure and remove those task-owned files in its outer `finally`. This diagnostic reads only that explicit key, never `GEMINI_API_KEY`. It calls the existing provider implementation without retries. Existing per-call deadlines and maximum attempts bound model work to at most `max_requests * timeout_seconds` plus local analysis. Budget-exhausted cases stay explicit failures. No source retrieval occurs, no plan reaches the gateway, and no report can authorize release. Independent human review and fresh Gemini execution remain pending. 005D per-claim freshness scores, general factual verification, real-model plus real-source execution and production readiness are outside this milestone.
