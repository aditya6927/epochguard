# 005G — Published-checkout installation and judge demo qualification

## Tested source and installation

The published GitHub commit **`871a7cbe55782a4a514c036cdcf31a413dba57f7`** passed the full Lab build/start/test/cleanup lifecycle on November 19, 2026. All five judge outcomes were observed through the real Lab → protected ingress → pinned Bifrost/native plugin → Python verifier path. One inaccurate UI help description was subsequently corrected and retested; authorization behavior did not change.

An independent HTTPS clone was obtained from `https://github.com/aditya6927/epochguard.git`, not copied/exported from the development checkout. The server also supplied the exact requested commit through an explicit fetch. Initial checkout verification found 401 tracked files, no changes, a separate `.git` object store and no object alternates. Git tree: `a766f72a72d14aba884ecf10861b11dfd4bbe146`.

Actual clone commands, from the development directory:

```powershell
git -c credential.helper= clone --no-checkout --depth 1 https://github.com/aditya6927/epochguard.git artifacts/005g/fresh-published-871a7cb
cd artifacts/005g/fresh-published-871a7cb
git -c credential.helper= fetch --depth 1 origin 871a7cbe55782a4a514c036cdcf31a413dba57f7
git checkout --detach 871a7cbe55782a4a514c036cdcf31a413dba57f7
```

All build contexts and application source paths resolved inside that clone. Initially absent image tags used prefix `epochguard-005g-pub-871a7cb`; the native image, verifier 004C/004E/004G dependency chain and Lab image were built in order. Explicit namespaced parent arguments prevented fallback to preexisting EpochGuard images. Existing Docker layers, BuildKit and public dependency caches were retained. This was **not** an empty-daemon, fresh-builder or cache-free qualification.

Host prerequisites actually checked:

| Component | Observed environment |
| --- | --- |
| Host | Windows 11 x64, build `10.0.26300` |
| Git / host Python | `2.50.0.windows.1` / `3.12.4` |
| Docker context / engine | `desktop-linux` / `29.6.2`, Linux x86_64 |
| Compose / Buildx | `5.3.1` / `0.35.0-desktop.2` |
| Selected native/004C builder | Existing `epochguard-002a`, docker-container driver on `desktop-linux`, BuildKit `0.34.2` |
| Derived/Lab builds | Docker's selected `desktop-linux` builder; local namespaced parents available |
| Optional browser-test tools | Node `24.13.0`, npm `11.6.2`, installed Edge `157.0.4341.60` |
| Native runtime/toolchain | Existing pin: Go `1.27.3`, Linux/amd64, dynamic gateway and matching plugin graph |

No host Go, host Node installation or API key is required for ordinary Lab startup. Host Node/Edge were used only for the existing optional browser checks. Public source/package downloads were permitted during installation; no live model or evidence API was invoked.

## Actual lifecycle and demonstration results

From the independent checkout:

```powershell
py -3.12 tests/lab/manage.py test --build --builder epochguard-002a --image-prefix epochguard-005g-pub-871a7cb --project-name epochguard-005g-pub-a --test-port 18857
```

The unmodified published checkout passed **21 inference checks**, **3 navigation checks** and **9 fault/recovery/network records**, including a **16-request burst: 4 allowed, 12 safely refused**. The five presets ran three times; custom input, contradictory preset/content substitutions, explicit whitespace and unsupported text were also exercised. Removing verifier/gateway service availability withheld content; restoration recovered ALLOW. Readiness, private-service isolation and loopback-only Lab publication were checked by the existing suite.

| Judge scenario | Actual protected outcome | Content |
| --- | --- | --- |
| Supported claims | ALLOW / 200 | Exact approved candidate delivered |
| Outdated Python beside supported requests claim | REJECT / 403 | Withheld |
| Additional unsupported assertion | UNAVAILABLE / 503 | Withheld |
| Missing EpochGuard behind protected ingress | INGRESS_REFUSED / 503 | Withheld |
| Genuine controlled-provider failure | PROVIDER_ERROR / 400 | Withheld; sanitized failure |

The browser phase used a second owned project at the application's fixed documented origin, after the first test stack was removed:

```powershell
npm.cmd ci --prefix web/lab --ignore-scripts --no-fund
py -3.12 tests/lab/manage.py up --image-prefix epochguard-005g-pub-871a7cb --project-name epochguard-005g-browser
npm.cmd run test:browser --prefix web/lab -- --reporter=json
py -3.12 tests/lab/manage.py down --image-prefix epochguard-005g-pub-871a7cb --project-name epochguard-005g-browser
```

Both existing **headless Edge tests passed**, with zero skipped, unexpected or flaky results: desktop five-outcome/custom-input behavior and mobile layout/keyboard/grammar/JSON inspection. They used real API responses, not component mocks. New screenshots are confined to the independent clone's ignored `artifacts/005a/`; historical screenshots in the original checkout were untouched. Desktop/mobile captures were inspected. A supplemental real-browser observation explicitly confirmed that editing an approved candidate removes both the old released content and approval badge before the next request; the edited unsupported answer subsequently returned 503 without content.

A supplemental real header-injection control returned safe **INGRESS_REFUSED / 503**, exposed no provider/internal headers or synthetic private values, and retained only the eight permitted Lab result fields. Restoring the provider control recovered exact ALLOW / 200. No receipt/key material was exported. The actual missing-service/provider-error cases likewise did not fall back to unprotected delivery.

After the help correction below, a second complete lifecycle ran with the same isolated images/project and test port, omitting `--build`. It again passed **21 inference + 3 navigation + 9 fault/recovery/network records**, including the **4 allowed / 12 refused** burst, restart/recovery and final cleanup.

## Reproduced issue and minimal correction

There was no published installation/build blocker. The running Lab's help still said “one to eight claims” and described duplicate policy/version pairs, predating singleton-policy enforcement. The observed UI text and an actual two-version same-policy 503 refusal were recorded before correction.

Only two strings in `web/lab/src/App.tsx` changed: help now states **one assertion per policy, two admitted claims total, unchanged transport bound eight**, and explains that repeated policies are refused across versions/paraphrases. The original published lifecycle was completed before this one-file overlay. The corrected source was copied into the independent checkout, only its isolated Lab image was rebuilt/recreated, and the component/browser/repeatability checks then passed. The published commit itself still contains the older wording; this report distinguishes its successful installation from the separately tested local correction.

The first one-off observation helper needed a base URL to match relative Playwright response URLs. A supplemental header probe initially assumed ALLOW instead of accepting the observed safe ingress refusal. These local helper failures/logs were retained; they were not installation defects, skipped tests or reasons to weaken enforcement.

## Regression evidence, resources and limits

| Check | Actual result |
| --- | --- |
| Published launcher: `py -3.12 -m unittest discover -s tests/lab -p test_manage.py` | 7 passed, including existing-project preservation and environment/error handling |
| Bounded-prose/gateway Python suites from the independent checkout | 196 passed in a network-disabled container using the namespaced 004G image |
| Documentation-tool tests: `py -3.12 -m unittest discover -s scripts -p 'test_*.py'` | 2 passed |
| Corrected Lab Docker frontend stage | TypeScript/production build and 8 component tests passed; test-stage networking disabled |
| Native plugin, Lab and ingress Go checks | Fresh format/vet/unit/race checks passed with `-count=1` and test-stage networking disabled |
| Documentation/link and changed-file whitespace checks | Passed |

The Python command selected `services/verifier/tests_bounded_prose` and `services/verifier/tests_gateway` using the existing read-only checkout mount and explicit `PYTHONPATH`. Fresh Go checks appended a test-only stage to the published native Dockerfile: `docker buildx build --builder epochguard-002a --target checks-005g -f ../native-checks.Dockerfile .`. The local Dockerfile and full logs are retained. Race instrumentation covers unit execution, not the running gateway. No unrelated historical gateway matrices were rerun.

Evidence is under `artifacts/005g/`: `checkout.json`, `published-lifecycle.log`, `repeat-lifecycle.log`, `browser-results.json`, `help-before.json`, `help-after.json`, `response-projection.json`, test/build logs and sanitized `report.json`. `published-images.json` records all five original immutable IDs; `corrected-images.json` records the final set. Only the Lab image changed, from `df6d26b7b11a…` to `3b0f5b93b26c…`; gateway/verifier IDs were unchanged. The help overlay's normalized SHA-256 is recorded separately.

Each owned project used the existing eight-service manifest, three networks and disposable receipt-key volume. Only the Lab published a port: `127.0.0.1:18857` for API lifecycle tests or `127.0.0.1:8787` for the browser phase. Gateway, verifier, provider and management ports remained unpublished. Final Docker-label inspection found **zero containers, networks or volumes for both owned projects**. Five isolated image tags and the preexisting builder/caches were retained; nothing was pruned. An audit verified **377 historical evidence/report files unchanged**, including 005F labels/public evidence/results and November live qualifications.

Coverage is limited to this Windows/Docker Desktop Linux/amd64 environment and installed headless Edge. Separate Linux/macOS/ARM, emulation, other browsers, cache-free installation, public dependency availability and production deployment remain unqualified. Component mocks are presentation tests; the independent real-stack/browser checks establish the stated finite demo outcomes. The Lab entry bridge is not an egress firewall; private source transports are explicitly simulated, and browser page requests were restricted to loopback.

Changed repository files: `web/lab/src/App.tsx` (help text only) and this report. Grammar, evidence policy, native decisions, receipt v2, protected release, adapters, existing qualifications and 005F data/results were preserved.

## Judge quick-start

Use Git, Python 3.12 and Docker Desktop with Linux containers, Compose and Buildx. From a new directory:

```powershell
git clone https://github.com/aditya6927/epochguard.git
cd epochguard
py -3.12 tests/lab/manage.py up --build
```

Open **http://127.0.0.1:8787**. Run Supported claims, Older Python, Extra assertion, Missing plugin and Provider failure; edit a candidate to observe the actual protected result. The provider is controlled and evidence is simulated. Stop the stack and remove its signing volume with `py -3.12 tests/lab/manage.py down`.

The launcher uses Docker's selected builder. If an explicit builder is necessary, inspect `docker context show` / `docker buildx ls` and choose one on the intended context; do not assume a builder literally named `default`. First builds need public dependency access. The [Lab guide](verification-lab.md) and [compatibility diagnostics](compatibility.md#builder-and-abi-diagnostics) remain the maintained procedures. For the exact installation qualified here, check out the published commit above; the UI-help correction is a separately tested patch, not a claim of publication or production readiness.
