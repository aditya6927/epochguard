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
