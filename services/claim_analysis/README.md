# Experimental claim analysis

Identify assertions and their temporal requirements without verifying them or authorizing response release. This package is independent of FastAPI `/v1/verify`, Bifrost and Tavily. It reuses Pydantic/httpx from the existing lockfile. See [annotation rules](ANNOTATION.md), [JSON schema](schema-004a.v1.json) and [the qualification report](../../docs/task-004a.md).

The dataset has 112 synthetic draft examples and 184 factual assertions. **Independent human review is pending.** The real Gemini REST adapter exists, but its model quality has not been measured. Fake outputs exercise plumbing only. Baseline measurements and error records are in [reports](reports/).

Use Python 3.12 and the existing lockfile. From the repository root in PowerShell (reuse `.venv-003a` if it already exists):

```powershell
python -m venv .venv-003a
& .\.venv-003a\Scripts\python.exe -m pip install -r services/claim_analysis/requirements.txt
$env:PYTHONPATH = 'services/claim_analysis'
& .\.venv-003a\Scripts\python.exe -m pytest -c services/claim_analysis/pytest.ini services/claim_analysis/tests -q
& .\.venv-003a\Scripts\python.exe -m claim_analysis evaluate --engine baseline --split heldout --output artifacts/004a/baseline-heldout.json
```

Linux/macOS use `.venv-003a/bin/python` and prefix commands with `PYTHONPATH=services/claim_analysis`. Evaluation writes JSON and a text summary with per-group metrics, per-response analyses/failures, critical misses, input and implementation hashes, usage and latency. `--require-human-reviewed` refuses the current drafts. To expand annotations, append new stable IDs; do not blindly regenerate over human-reviewed edits using `data/build_v1.py`.

## Reproducible demonstrations

Run each name in `mixed`, `version`, `implicit`, `historical`, `adversarial`:

```powershell
$name = 'implicit'
& .\.venv-003a\Scripts\python.exe -m claim_analysis analyze --engine baseline --text-file "services/claim_analysis/demos/$name.txt"
& .\.venv-003a\Scripts\python.exe -m claim_analysis analyze --engine fake --text-file "services/claim_analysis/demos/$name.txt" --fake-reply "services/claim_analysis/demos/$name.fake.json"
```

The second command passes a **scripted fixture** through the strict model-output path; it is not a real model demonstration or quality comparison. `implicit` shows the sentence baseline abstaining where a semantic extractor should recognize a changing coaching role. `version` uses an ordinary deliberately old-version assertion without the 003A template: identification marks the need for evidence, not whether the version is actually current. `historical` refers to 2018 rather than the present. `adversarial` classifies instructions as data and unresolved reference as uncertainty. Neither engine returns ALLOW or a truth verdict.

## Opt-in real Gemini analysis

The adapter uses the documented `generateContent` REST API with structured JSON output, a fixed HTTPS host, one candidate, no tools and no retries. Select a model supporting this API/schema subset. Quota and model compatibility are not established by a subscription or coding-agent access. Candidate text goes to the configured model provider; do not use private text without separate authorization.

For one expressly opted-in request, obtain an API key and current rates from the provider. Do not paste the key into chat or put it in a command literal:

```powershell
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'Gemini API key' -AsSecureString)).Password
$env:EPOCHGUARD_CLAIM_MODEL = Read-Host 'Exact Gemini model ID (gemini-...)'
$env:EPOCHGUARD_CLAIM_INPUT_USD_PER_MILLION = Read-Host 'Input USD per million tokens for this model/tier'
$env:EPOCHGUARD_CLAIM_OUTPUT_USD_PER_MILLION = Read-Host 'Output USD per million tokens for this model/tier'
$env:EPOCHGUARD_ALLOW_MODEL_CALLS = '1'
& .\.venv-003a\Scripts\python.exe -m claim_analysis analyze --engine gemini --text-file services/claim_analysis/demos/implicit.txt
Remove-Item Env:GEMINI_API_KEY, Env:EPOCHGUARD_ALLOW_MODEL_CALLS
```

Defaults: 30-second total deadline (validated 0.1–60), 4,096 output tokens (128–8,192), one request. Trusted environment overrides: `EPOCHGUARD_CLAIM_TIMEOUT_SECONDS`, `EPOCHGUARD_CLAIM_MAX_OUTPUT_TOKENS`, `EPOCHGUARD_CLAIM_MAX_REQUEST_USD` (default 0.25, maximum 10), `EPOCHGUARD_CLAIM_MAX_RUN_USD` (default 1, maximum 25). CLI `--max-requests` is bounded 1–100. Input: 8,192 code points/32,768 UTF-8 bytes; provider JSON and extracted JSON: 65,536 bytes; at most 64 units. Failed/cancelled calls consume their request and planning-cost reservation.

Cost admission uses a pessimistic prompt-byte/token planning estimate plus output limit at **operator-supplied rates**. It is not a provider billing guarantee; rate mistakes, token accounting and pricing tiers require an independent provider-side spending limit. Reported token totals include thought tokens when supplied; estimates are not invoices. Unknown usage is null, not zero. The API schema is reduced to the documented supported subset; all strict span/category checks run locally afterward. No JSON repair or automatic retry is attempted.

The held-out file currently has 47 nonempty valid responses eligible for model calls. To evaluate it deliberately, configure credentials/rates/opt-in above and run:

```powershell
& .\.venv-003a\Scripts\python.exe -m claim_analysis evaluate --engine gemini --split heldout --max-requests 47 --output artifacts/004a/gemini-heldout.json
```

Review the entire-run planning budget first. Insufficient budgets produce explicit failures, not baseline substitutions or invented successful results. Compare the real report with the frozen baseline report only after human annotation review and actual execution. Do not tune against this held-out file and call it held-out again.

## Gemini schema compatibility diagnostic

The maintainer observed HTTP 400 for the original generation schema and HTTP 200 after removing generation-side `maxItems` (64 claims, six uncertainty entries). That reduced-schema diagnostic failed local validation, while a separate standalone generation passed. This supports request acceptance for the reduced schema, not reliable extraction or model quality. The strict Pydantic schema, counts, span checks and output/token/deadline limits remain enforced locally. The [follow-up report](../../docs/task-004a.md#safe-model-validation-diagnostics-2026-11-09) separates the supplied live evidence from the offline diagnostic tests.

Export the exact original and changed provider schemas with no key, opt-in or network calls:

```powershell
$env:PYTHONPATH = 'services/claim_analysis'
& .\.venv-003a\Scripts\python.exe -m claim_analysis.schema_diagnostic --output artifacts/004a-gemini-schema/offline
```

For an explicitly authorized **two-request** live comparison, from repository root:

```powershell
$env:PYTHONPATH = 'services/claim_analysis'
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'Gemini API key' -AsSecureString)).Password
$env:EPOCHGUARD_CLAIM_MODEL = 'gemini-3.5-flash-lite'
$env:EPOCHGUARD_CLAIM_INPUT_USD_PER_MILLION = Read-Host 'Current input USD per million tokens for this model/tier'
$env:EPOCHGUARD_CLAIM_OUTPUT_USD_PER_MILLION = Read-Host 'Current output USD per million tokens for this model/tier'
$env:EPOCHGUARD_ALLOW_MODEL_CALLS = '1'
try {
    & .\.venv-003a\Scripts\python.exe -m claim_analysis.schema_diagnostic --live --max-requests 2 --output artifacts/004a-gemini-schema/live
} finally {
    Remove-Item Env:GEMINI_API_KEY, Env:EPOCHGUARD_ALLOW_MODEL_CALLS -ErrorAction SilentlyContinue
}
```

The tool uses fixed synthetic text and records schema hashes, HTTP statuses, strict local validation outcome, safe failure codes, latency and available usage. It does not print keys, headers, raw provider output or error messages. Existing request/cost reservations and validated timeout/output settings apply to the whole comparison. Auth/rate/server errors or a timeout stop subsequent probes; there are no retries. HTTP 200 alone establishes request acceptance, not a valid extraction or factual verification. Exit 0 on a live run requires the default `no_max_items` variant to pass strict local analysis. Original HTTP 400 is a comparison result. Dry exports always retain `live_qualification_pending: true`.

If the changed schema still returns 400, keep the same key/model/rate setup and explicitly probe **one factor at a time**:

```powershell
& .\.venv-003a\Scripts\python.exe -m claim_analysis.schema_diagnostic --live --variants no_max_items no_numeric_bounds --max-requests 2 --output artifacts/004a-gemini-schema/numeric
```

Replace `no_numeric_bounds` with `no_titles`, `nullable_type_union`, or `inline_refs` for separate comparisons. Each variant starts from `no_max_items`, not the preceding experiment. These alternatives are diagnostic-only; a passing alternative never changes normal adapter behavior or relaxes local validation. The default remains unqualified and the live command exits 1 if only an alternative succeeds. No automatic schema fallback or full-dataset/model evaluation is performed.

## Safe validation failure details

Diagnostic rows retain `failure_code`, `http_status`, `http_accepted`, and `strict_analysis_valid`, and add `failure_details` (null on success). Normal analysis/evaluation failure codes remain unchanged. Details never authorize an answer and do not repair output.

| Stage | Meaning / representative code |
| --- | --- |
| `PROVIDER_TRANSPORT` | Connection/transport failure, timeout, or unexpected provider exception |
| `PROVIDER_HTTP` | Non-200 response; `HTTP_FAILURE`; inspect the existing HTTP status field |
| `PROVIDER_ENVELOPE` | Invalid outer API JSON/content/usage, size bound, or incomplete generation |
| `MODEL_JSON` | Invalid/incomplete model JSON, duplicate keys, nonfinite numbers or invalid encoding |
| `MODEL_SCHEMA` | Missing/extra fields, wrong type/category, length/count constraint or cross-field inconsistency |
| `SOURCE_BINDING` | ID sequence, overlapping spans, out-of-range end, or source substring mismatch |
| `EMPTY_ANALYSIS` | No claims on a nonempty input |
| `CONTROL` | Opt-in, configuration or request/cost budget guard |

For example, `CLAIM_DYNAMIC_REQUIRES_FRESH` at `$.claims[0].fresh_evidence` identifies an invalid dynamic/evidence combination. `BINDING_RANGE` at `$.claims[0].end` means the end offset exceeds the original response length; `BINDING_TEXT_MISMATCH` means the supplied offsets/source text do not match. Neither diagnostic proposes a repaired value. A cross-field rule may point to the whole claim when several fields are involved.

Reports contain at most four issues. `error_count` is capped at 64, and `truncated` marks omitted issues. Field names are allowlisted; unknown keys become `<unknown>`, indices outside 0–63 become `[*]`, and path depth/length are capped. Pydantic messages, `input`, context and URLs are not serialized. No candidate/model text, credentials, request headers, provider error bodies or arbitrary exception messages are retained in failure metadata.

To repeat **only the reduced-schema diagnostic** after setting the same trusted model/key/rates and `EPOCHGUARD_ALLOW_MODEL_CALLS=1` as above:

```powershell
$env:PYTHONPATH = 'services/claim_analysis'
& .\.venv-003a\Scripts\python.exe -m claim_analysis.schema_diagnostic --live --variants no_max_items --max-requests 1 --output artifacts/004a-validation-diagnostics/live-reduced
```

This performs at most one model call and preserves the existing timeout, token and cost guards. Use a new output directory to preserve older evidence. The old generic failure cannot be diagnosed retroactively; a fresh run may generate different output. No live request was made while implementing these diagnostics.

## Evaluation records with validation diagnostics

`claim_analysis evaluate` also adds `failure_details` to each per-case record, using the existing `AnalysisFailure.diagnostic.to_dict()` sanitizer and taxonomy above. Public `reason` codes remain unchanged. Details are null for successful analyses, invalid inputs, baseline failures without metadata, or an `AnalysisFailure` without diagnostics. Failed model records still have `extraction: null`; scoring and existing successful extraction/gold-example fields are unchanged. The new diagnostic field includes no raw candidate/model text, credentials, provider bodies or Pydantic input values.

To rerun exactly development cases `eg004a-0001`, `eg004a-0007`, `eg004a-0019`, first copy their original JSONL lines into a fresh artifact directory. This leaves the repository dataset and labels unchanged:

```powershell
$env:PYTHONPATH = 'services/claim_analysis'
$runDirectory = Join-Path 'artifacts/004a-evaluation-diagnostics' ('three-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force $runDirectory | Out-Null
$requestedIds = @('eg004a-0001', 'eg004a-0007', 'eg004a-0019')
$selectedRows = @(Get-Content -LiteralPath services/claim_analysis/data/v1/dev.jsonl -Encoding UTF8 | Where-Object { ($_ | ConvertFrom-Json).case_id -in $requestedIds })
if ($selectedRows.Count -ne 3) { throw 'Expected exactly three development cases.' }
$subsetPath = Join-Path (Get-Location) (Join-Path $runDirectory 'dev-three.jsonl')
$reportPath = Join-Path $runDirectory 'gemini-three.json'
[IO.File]::WriteAllLines($subsetPath, [string[]]$selectedRows, [Text.UTF8Encoding]::new($false))
```

Then explicitly authorize up to **three** model requests using the same model and current trusted rates; no automatic retries or schema/prompt changes are introduced:

```powershell
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'Gemini API key' -AsSecureString)).Password
$env:EPOCHGUARD_CLAIM_MODEL = 'gemini-3.5-flash-lite'
$env:EPOCHGUARD_CLAIM_INPUT_USD_PER_MILLION = Read-Host 'Current input USD per million tokens for this model/tier'
$env:EPOCHGUARD_CLAIM_OUTPUT_USD_PER_MILLION = Read-Host 'Current output USD per million tokens for this model/tier'
$env:EPOCHGUARD_ALLOW_MODEL_CALLS = '1'
try {
    & .\.venv-003a\Scripts\python.exe -m claim_analysis evaluate --engine gemini --split dev --dataset "$subsetPath" --max-requests 3 --output "$reportPath"
} finally {
    Remove-Item Env:GEMINI_API_KEY, Env:EPOCHGUARD_ALLOW_MODEL_CALLS -ErrorAction SilentlyContinue
}
(Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json).records | Select-Object case_id, status, reason, failure_details | ConvertTo-Json -Depth 8
```

Existing process-configured timeout/token/per-request and entire-run cost guards still apply, so fewer than three requests may dispatch if a budget fails. The final view selects only case IDs/status/reasons/sanitized details. A fresh generation can differ from a previous failure; historical reports cannot be backfilled from generic reason codes. No live requests were made while adding this report field.
