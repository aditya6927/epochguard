# Experimental Evidence Explorer

A separate loopback-only FastAPI application for one self-contained, externally checkable English factual statement. Every response is `mode=experimental-evidence`, `authorization=false`. It issues no receipts and cannot authorize protected gateway content. The protected Lab remains at port 8787; this service uses port 8791 and no shared service/network/signing volume.

The two applications are independently runnable and loopback-only: **127.0.0.1:8787** is the Verification Lab's actual protected gateway with simulated evidence/controlled provider; **127.0.0.1:8791** is this separate FastAPI/UI with simulated search/model replies by default and optionally live Tavily + Gemini. An Explorer result cannot approve arbitrary claims through protected ingress.

## Live observations and result retention

The [November 20, 2026 follow-up](../../docs/task-005k.md#november-20-2026-explorer-live-observations) reviews operator-supplied screenshots and a displayed-text transcript of a LIVE CONTRADICTED assessment for `Trump is Japan's prime minister.`: AI_EVIDENCE_ASSESSMENT, five retrieved sources, three cited sources and `authorization=false`. The operator reports completed real Tavily/Gemini execution and application structural/corroboration acceptance. The artifacts preserve the displayed result, not independently verified raw HTTP or provider attestations. Other live attempts timed out or ended incompletely; general factual accuracy, source independence and consistent availability remain unqualified. This does not qualify the protected 005E combined path.

The backend currently does **not persist successful HTTP responses or assessment history**. The page holds only the current displayed result; editing clears it and reload loses it. The later screenshots/transcript are manual operator captures. 005J logs only safe structural failure metadata, not claims, snippets or response bodies. Result export/persistence is **future work**, with no implemented export endpoint, browser save button or database. The original [005I](../../docs/task-005i.md) and [005J](../../docs/task-005j.md) reports retain their execution-time evidence and limitations.

## Safeguards and semantic limits

Strict schemas, exact claim retention, complete source-ID coverage, citation binding, verbatim snippet quotes and at least two cited publisher groups with matching model-assigned stances constrain conclusive results. Missing/invalid evidence and detected disagreement abstain. These safeguards coexist with semantic reliance on Gemini:

- **Quotation versus entailment:** a verbatim substring check prevents some invented quotations; it does not prove that the quote logically supports or contradicts the claim. Relevance and entailment remain model judgments.
- **IRRELEVANT classifications:** the disagreement check excludes sources labelled `IRRELEVANT` by the model. A truly contradictory source incorrectly given that label may be excluded from this check. Two-publisher corroboration still applies but cannot eliminate semantic errors. This is a source-inspected limitation, not a demonstrated successful exploit.
- **Freshness:** retrieval time and unverified search publication metadata are distinct. The prompt asks Gemini to consider current roles/dates, but there is no universal deterministic maximum publication age for conclusive assessments. Retrieval today does not prove current underlying information.
- **Independence:** publisher grouping and duplicate/near-copy checks are heuristics. Different groups can share ownership, syndication or underlying reporting; they do not independently establish factual authority.

## Offline startup and cleanup

Requires the existing Git, Python 3.12 and Docker Desktop Linux-container setup. No host Python packages, Node installation or credentials are required to use the page. From the repository root, in PowerShell:

```powershell
py -3.12 services/evidence_assessment/manage.py up --build
```

Open **http://127.0.0.1:8791**. Click Request assessment for the target example, Gold example for an unrelated supported claim, or Inconclusive example. All evidence/model replies are clearly marked **SIMULATED**. Unfamiliar statements have no simulated search results; this finite demonstration is not general factual accuracy. The real integration is selected only through the separate live opt-ins below.

```powershell
py -3.12 services/evidence_assessment/manage.py down
```

Cleanup removes this project's containers, network and any volumes, checks their absence, and retains images/operator credential files. Startup refuses existing project resources rather than resetting another session's call budget. A lifecycle lock prevents overlapping startup/test invocations. After an interrupted process, inspect Docker resources and confirm no owner is running before removing a stale `artifacts/005i/lifecycle.lock`. `down` needs no keys or live flags.

The helper suppresses subprocess output so paths/environment values cannot enter reports; on failure it prints only a fixed stage. Diagnose offline commands privately with `docker compose --env-file dev/lab.compose.env -f compose.explorer.yaml ps`. Never print resolved live Compose configuration.

## Reproduce offline checks

```powershell
py -3.12 services/evidence_assessment/manage.py test --build
```

This builds the Explorer image (including its selected service tests), starts the actual offline service, checks three HTTP outcomes and exact claim retention, then verifies cleanup. It is not the full historical qualification suite. Omit `--build` only when the matching image already exists; `up` leaves the service running, whereas `test` cleans its owned project. Startup/tests refuse existing project resources. `down` removes only this project's resources and retains operator credential files. Builds install public locked dependencies; test RUN steps have `--network=none`. See [CI-equivalent selections and documentation checks](../../CONTRIBUTING.md#validation) for separate Go/Python/frontend build targets; unit race detection does not instrument a running gateway.

For the frozen 19-case evaluator and focused regressions, activate a Python 3.12 virtual environment with `services/verifier/requirements.lock` and `services/evidence_assessment/requirements-extra.lock` installed. Dependency installation is a separate online setup step. From the repository root in PowerShell:

```powershell
python -B tests/evidence_assessment/evaluate.py artifacts/005i/my-new-packet-run
$env:PYTHONPATH = 'services/evidence_assessment;services/claim_analysis'
python -B -m pytest services/evidence_assessment/tests -q
python -B -m unittest discover -s tests/evidence_assessment -p test_explorer_manage.py
```

The evaluator inserts its own import paths, pins the packet digest, refuses an existing output directory and never selects live transports. Pytest needs the explicit import paths above (use the platform's path separator outside PowerShell/Windows). The lifecycle unittest uses only the standard library. These are focused selections, not every Python regression; the broader CI selection is in `dev/Dockerfile.checks`. Results go under ignored `artifacts/`; reports retain their execution revision and simulated provenance. Neither the evaluator nor the following two runners has an argparse `--help` mode; supply their documented arguments only.

### Optional browser checks

Requires Node (the Lab's locked toolchain uses 24.13.0), the Lab's npm dependencies installed with `npm ci --prefix web/lab --ignore-scripts`, and locally installed Microsoft Edge. Start the **offline** Explorer, run `node tests/evidence_assessment/browser.cjs artifacts/005i/my-new-browser-run`, then run `py -3.12 services/evidence_assessment/manage.py down`. Use a new output directory. The script uses locked Playwright, refuses a LIVE page and blocks external page requests. It checks three actual browser/HTTP outcomes plus stale-result/mobile behavior; this is simulated-provider UI plumbing, distinct from CI component tests. These optional prerequisites are not required for ordinary startup.

### Optional protected gateway smoke

`py -3.12 tests/evidence_assessment/protected_smoke.py` uses standard-library host Python and Docker, with matching, locally built `epochguard-dev:002a` and `epochguard-verifier:004g` images already present. It does not build images; use the existing [native → 004C → 004E → 004G build procedure](../../docs/compatibility.md#builder-and-abi-diagnostics) when needed. It tests five outcomes through actual protected ingress/Bifrost/plugin/Python/receipt validation with a controlled provider and simulated evidence. Its separate `epochguard-005i-protected` project refuses existing resources, records immutable image IDs and removes its own disposable signing volume. Coordinate the inherited G subnet with other active G profiles. This is an optional runtime check, not an Explorer test or prerequisite for the judge quick-start.

## Separately authorized live smoke

**005I/005J development checks made no live calls; later operator execution is recorded above.** Any new smoke still requires separate explicit authorization for one Tavily Search request and at most one Gemini assessment request. Check current provider availability/prices and billing limits yourself; no price or model default is silently chosen. Live startup performs no provider calls. A button click can incur cost, including calls that time out or are cancelled.

`EPOCHGUARD_005I_ALLOW_GEMINI=1` and `EPOCHGUARD_005I_ALLOW_TAVILY=1` are separate **technical execution opt-ins** against accidental live calls. Even if a guard/help message calls them authorization, setting them does not prove account ownership, permission to incur charges or approval of a spending amount. Live use additionally requires a deliberate operator decision, authorized account/key usage and review of current pricing, quotas and possible costs. Application reservations are planning limits, not guaranteed provider-side billing caps; timeout/cancellation can still be charged and restarting resets process-local counters. This documentation grants no permission for a new live call.

Create three distinct owner-readable private files **outside the checkout**: Gemini key, Tavily key, and a copy of [settings.example.json](settings.example.json). Key files contain only the ASCII key plus an optional newline. On POSIX use mode 0600; on Windows restrict ACLs to the operator and inspect them privately. The launcher verifies POSIX permissions; Windows ACL restriction is an operator prerequisite, not automatically attested. Set every null setting explicitly: an available Gemini model ID, current input/output USD per million token rates, search price per basic request, and request/run cost ceilings. Keep `max_requests=1`; live validation permits at most three. Both credentials remain backend-only, mounted read-only, never placed in `.env`, browser fields, tracked JSON or command arguments.

The non-root service runs as UID 10001. On Linux arrange for the three mounted files to be readable by that container UID (for example, create/edit them first, then assign the appropriate mapped owner and mode 0600). Do not make them world-readable to solve a mount failure. Rootless Docker UID mapping and Docker Desktop ACL behavior require checking the operator's local setup. Missing readability fails startup without a provider call.

In PowerShell, replace only these nonsecret path placeholders:

```powershell
$env:EPOCHGUARD_005I_ALLOW_GEMINI = '1'
$env:EPOCHGUARD_005I_ALLOW_TAVILY = '1'
$env:EPOCHGUARD_005I_SETTINGS_HOST = '<private-directory>/settings.json'
$env:EPOCHGUARD_005I_GEMINI_SECRET_HOST = '<private-directory>/gemini.key'
$env:EPOCHGUARD_005I_TAVILY_SECRET_HOST = '<private-directory>/tavily.key'
py -3.12 services/evidence_assessment/manage.py up --live --build
```

Verify the page says **LIVE**, submit the target statement once, then inspect the actual cited excerpts, dates, uncertainty and outcome. CONTRADICTED is an expectation only when two relevant independent sources actually contradict the statement at execution time; failures, conflicting evidence or insufficient corroboration must stay inconclusive. Do not edit evidence to force an expected answer. Stop with `py -3.12 services/evidence_assessment/manage.py down`, remove the five process variables and dispose of private files according to the operator's credential policy. Do not restart automatically, retry a failed request or run the offline test helper against live mode.

Budget admission reserves a maximum serialized-input bytes-as-tokens estimate (131072), the configured output ceiling and one search price **before search**. Reservations survive errors/cancellation/no-model outcomes. At most one search and one model submission per admitted claim; no retries, redirects, fallback or tools. These are per-process application planning limits, not a provider billing guarantee. Restart resets counters. The bridge is not an egress firewall: offline clients use simulated transports; live clients use only fixed provider HTTPS endpoints and ignore proxy environment variables. Do not bind this service publicly.

## Model validation diagnostics

[005J](../../docs/task-005j.md) replaces the former broad `INVALID_MODEL_OUTPUT` reason with eight fixed categories. All remain INSUFFICIENT_EVIDENCE, `authorization=false`; the response fields and successful assessment behavior are unchanged.

| Reason | Failed check |
| --- | --- |
| `MODEL_FINISH_INCOMPLETE` | A present finish reason is not STOP, including MAX_TOKENS and safety finishes |
| `MODEL_ENVELOPE_INVALID` | Malformed outer response, missing/ambiguous candidates, parts, role or usage metadata |
| `MODEL_JSON_INVALID` | Invalid, duplicate-key, nonfinite, oversized or malformed structured answer JSON |
| `MODEL_SCHEMA_INVALID` | Structured answer does not satisfy the strict local model schema |
| `MODEL_CLAIM_MISMATCH` | Model did not preserve the exact original claim |
| `MODEL_SOURCE_COVERAGE` | Per-source assessment IDs are missing, repeated or do not equal the retrieved set |
| `MODEL_CITATION_BINDING` | Citation IDs are repeated or not in the retrieved set |
| `MODEL_QUOTATION_BINDING` | Quotation is not an exact snippet substring or decisive quote is too short |

Each failure emits one bounded JSON warning through `epochguard.experimental.model_validation`. It contains only the category, an allowlisted finish reason (otherwise UNKNOWN/MISSING), bounded integer usage counts, configured output cap, source count and redacted validation field paths. Missing counts remain unknown. It never emits original claims, excerpts, raw JSON, signatures, keys, exception messages or Pydantic inputs. Unknown schema field names are `[unknown]`. Diagnostics remain backend logs; they add no browser response field or endpoint. Logging failure cannot change the refusal.

Operators can inspect these safe records privately without resolving live Compose variables:

```powershell
docker compose --env-file dev/lab.compose.env --project-name epochguard-005i -f compose.explorer.cleanup.yaml logs --no-color explorer | Select-String '005j.model-validation.v1'
```

A container built before 005J cannot retroactively reveal its old failure's finish/usage. Rebuilding/recreating a live process is deliberate operator work and resets process budgets; do not repeat a live request just to debug. Keep the default 1536-token cap pending evidence. If a separately authorized assessment records MAX_TOKENS, consider 3072 within the existing 4096 ceiling after reviewing cost admission. STOP with a schema/claim/source/citation/quote failure is not evidence that more tokens would fix it. [Offline size measurements and limitations](../../docs/task-005j.md#output-token-investigation) distinguish characters from actual token counts. No setting or thinking strategy is automatically changed.

See [architecture and measured limitations](../../docs/task-005i.md) and [packet provenance](data/README.md).
