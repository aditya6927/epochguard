# Experimental Evidence Explorer

A separate loopback-only FastAPI application for one self-contained, externally checkable English factual statement. Every response is `mode=experimental-evidence`, `authorization=false`. It issues no receipts and cannot authorize protected gateway content. The protected Lab remains at port 8787; this service uses port 8791 and no shared service/network/signing volume.

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
docker build --target python -t epochguard-checks:005i-python -f dev/Dockerfile.checks .
docker build --target go -t epochguard-checks:005i-go -f dev/Dockerfile.checks .
py -3.12 scripts/check_docs.py
```

The first command starts the actual service, checks three HTTP outcomes and exact claim retention, then verifies cleanup. Builds install public locked dependencies; test RUN steps have `--network=none`. Python checks include existing verifier/claim-analysis suites and the new assessment tests. Go checks retain pinned format/vet/unit/race execution; race detection does not instrument the running gateway.

For the frozen packet evaluator, use a private virtual environment with `services/verifier/requirements.lock` and `services/evidence_assessment/requirements-extra.lock` installed, then:

```powershell
python -B tests/evidence_assessment/evaluate.py artifacts/005i/my-new-packet-run
python -B -m unittest discover -s tests/evidence_assessment -p test_explorer_manage.py
```

The evaluator inserts its service import paths, pins the packet digest and refuses an existing output directory. It never enables live transports. Optional real-browser checks reuse the existing Lab's locked Playwright installation and local Edge: start the offline Explorer, run `node tests/evidence_assessment/browser.cjs artifacts/005i/my-new-browser-run`, then run `manage.py down`. The browser script refuses a live service and blocks external page requests. This is UI plumbing evidence only.

## Separately authorized live smoke

**No live call was executed during implementation.** Obtain separate explicit authorization to make one Tavily Search request and at most one Gemini assessment request. Check current provider availability/prices and billing limits yourself; no price or model default is silently chosen. Live startup performs no provider calls. A button click can incur cost, including calls that time out or are cancelled.

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

See [architecture and measured limitations](../../docs/task-005i.md) and [packet provenance](data/README.md).
