# Task 005B: compatibility and release-engineering qualification

Baseline: `f7a7cd6f7a386b9079e34e666920ca1296f0a36f`, initially clean. Work is uncommitted; no push, live-source/model request, Bifrost upgrade or repository-license selection is performed. Execution: November 15-16, 2026, Windows PowerShell, Docker Desktop Linux containers, Python 3.12.

## Design and compatibility audit

The [compatibility matrix](compatibility.md) records the supported dynamic extension mechanism, exact pinned source/toolchain/module/libc boundary and unsupported distributions. Actual pinned loader symbol casts, transport raw-body capture, response conversion/post-hook order, placement and typed refusals were inspected. Current official documentation is pinned separately from the qualified source. No enforcement grammar, source policy, receipt format/cryptography, model authority or cache behavior changes.

The API-only embed asset is generated build input; a Dockerfile assertion verifies no tracked upstream source modification. Dynamic ELF inspection, exact host/plugin module comparisons and real gateway loading are retained. The Lab image's native base and verifier derivative bases now accept explicit build arguments solely to qualify an isolated fresh image namespace; defaults and protected runtime configuration retain their behavior.

## Installation findings

The reported native first-stage failure reproduced with `--builder default`: `ERROR: use docker --context=default buildx to switch to context default`. The active context was `desktop-linux`; the literal `default` builder belonged to another context. This occurs before compilation. It explains the reproduced symptom but the original user's discarded stderr is unavailable, so its exact historical cause is unproven.

The launcher now omits explicit builder selection by default, preserves explicit `--builder`, identifies each Dockerfile/start/cleanup stage and classifies fixed actionable errors without reflecting process output. Tests cover secret-like sentinels, builder selection, credential stripping, timeout, failed cleanup and preserving existing projects. Nested pytest caches are excluded from Docker contexts after an actual Windows access-denied failure in the new Python CI build. Dependencies remain public downloads and no live credential is read.

Cross-site exact-root GET document navigation is permitted with the expected Fetch Metadata mode/destination. Wrong Host/Origin, iframes, cross-site API/static requests, queries and state-changing calls remain refused; tests ensure navigation cannot dispatch upstream. Three corresponding real HTTP checks also pass.

An isolated second Lab initially failed because its fixed private subnet overlapped the operator's existing Lab. The Lab now uses Docker-allocated private addresses instead of fixed IPAM/static gateway IP; service DNS names, internal networks and trust boundaries remain unchanged. Real inspection confirms both edge/private networks are internal and only the Lab has a loopback mapping. This change is confined to the Lab, not the protected qualification profiles.

## Executed checks

Ignored artifacts under `artifacts/005b/` retain local build/stage logs, source manifests and sanitized measurements separately from paid live records. Raw build diagnostics remain local and are not publication artifacts. No credential, raw receipt or source body is collected by the harness.

| Check | Command | Result |
| --- | --- | --- |
| Launcher unit tests | `py -3.12 -m unittest discover -s tests/lab -p test_manage.py` | 7 passed |
| Documentation checker negative controls | `py -3.12 -m unittest discover -s scripts -p 'test_*.py'` | 2 passed |
| Pinned Go CI equivalent | `docker buildx build --builder epochguard-002a --target go -f dev/Dockerfile.checks .` | Passed format, vet, unit, race and native plugin compilation; actual gateway separately qualified |
| Locked combined Python CI equivalent | `docker build --target python -f dev/Dockerfile.checks .` | Final rerun: 615 passed, one live test deselected, one warning, 9.64 seconds; 7 launcher tests and 2 documentation-checker tests passed |
| Frontend CI equivalent | `docker build --no-cache --target frontend -f dev/Dockerfile.lab .` | TypeScript/production build and 8 component tests passed with fresh execution |
| Cold-input build/test/stop | `py -3.12 tests/lab/manage.py test --build --builder epochguard-005b-cold --image-prefix epochguard-cold-005b --project-name epochguard-cold-005b --test-port 18787` | All five images built; 21 inference, 3 navigation and 9 fault/recovery/network records passed; 16-request burst: 4 allowed, 12 safely refused; final build/start/test/cleanup cycle passed |
| 004D ingress lifecycle | `py -3.12 tests/protectedingress/qualify.py` | Passed, including disable/restart/concurrent refusal and recovery; explicitly legacy receipt v1 |
| 004E source-fault qualification | `py -3.12 tests/livequalification/qualify.py` | Passed offline, including simulated source failures; explicitly legacy receipt v1 |
| 004G security/lifecycle | `py -3.12 tests/boundedprose/qualify.py` | Passed: altered request with retained nonce, metadata/receipt adversaries, terminal/fallback behavior, faults, overload, disable/restart and recovery; runtime logs contained no candidate/metadata sentinel |
| G-L offline | `py -3.12 tests/boundedproselive/qualify.py` | Passed; separate simulated-source run `20261115T190905Z-582139a5`; no live flags or source keys |
| Documentation and Actions lint | `py -3.12 scripts/check_docs.py`; `rhysd/actionlint:1.7.12`, network-disabled with only workflow mounted | Passed; 40 Markdown files, 265 local links, 40 anchor references and 40 canonical path/command references |
| Native final build | `docker buildx build --builder epochguard-002a --load -t epochguard-dev:002a -f dev/Dockerfile .` | Passed with network-disabled Go test stages; recorded Go 1.27.3 Linux/amd64, CGO=1, musl interpreter, matching core/framework versions |

Cold-input method: an allowlisted public source export, no `.git`, venv, node_modules, ignored evidence, credential files or prebuilt artifacts; an initially empty Buildx builder; previously absent `epochguard-cold-005b-*` image tags; explicit native/verifier parent tags, preventing fallback to existing EpochGuard images. The host retains unrelated images and public base-image caches. This is a fresh dependency namespace/source export, not a new Docker daemon or independently cloned remote commit containing these uncommitted changes. The export manifest identifies input file hashes. Existing paid evidence is untouched.

The initial controller was deliberately interrupted before container startup when an operator's existing Lab was discovered. It was resumed with an isolated project and loopback test port; dependency/compiler cache from that interrupted attempt was retained. The operator's existing containers were not stopped or recreated. The harness now checks project ownership before building/cleanup, and interactive startup cannot select the test-only port. No new accepted browser origin or public service exposure was added.

After the subnet fix, isolated tests passed using the cold-built images. The final complete build/start/test/cleanup invocation also passed after build tests were explicitly network-disabled. Only initial dependency/source compilation started with an empty builder; the final confirmation reused the resulting cache. This is not described as a cache-free one-pass installation or an empty-daemon test.

All four host gateway suites ran with `COMPOSE_DISABLE_ENV_FILE=1` and `COMPOSE_ENV_FILES` selecting the tracked comment-only Lab environment file. Offline pending markers printed by the historical runners do not supersede the separately reviewed November 15 live assessment. No live run was repeated.

Cleanup inspection found zero containers, networks or volumes for each task-owned project: cold Lab, 004D, 004E offline, 004G and G-L offline. The task-created cold builder was removed; images and the pre-existing builder were retained. The original Lab's seven containers remained running with their original creation age. SHA-256 hashes of the four saved live records are unchanged.

## Security review and residual evidence gaps

No new enforcement-authority, receipt or grammar path was introduced. The meaningful runtime change is the exact-root navigation exception; independent HTTP/unit negative controls show it does not dispatch inference or admit cross-site APIs/frames. Test-only alternate connection ports preserve the fixed application Host/Origin and cannot be used for interactive `up`. Project ownership preflight prevents accidental test takeover; concurrent privileged Docker operators must still coordinate names.

The original first-build failure's precise historical stderr is missing. Current reproduction proves the builder/context mismatch, not every past installation failure. The fresh-input source export and isolated image namespace preserve existing host images; a completely empty daemon or separate remote clone of these uncommitted changes was not tested. Hosted Actions and other Bifrost releases/platforms remain untested. Browser automation was not rerun in 005B; frontend components and real navigation HTTP were executed, while desktop/mobile browser evidence remains the dated 005A result.

The private verifier hop remains unauthenticated, keys/host/configuration trusted, revocation non-atomic, global gateway execution deadlines unqualified and built-in caching disabled. Shared fixture assumptions and finite parser/concurrency cases are not a proof against every adversary. License selection and complete binary/image third-party notice clearance remain maintainer decisions before distribution.

## CI and release scope

Four independent, credential-free Actions jobs use SHA-pinned checkout, read-only contents permission, disabled persisted credentials and bounded timeouts. Go/Python/frontend test stages have networking disabled after dependency installation. No `pull_request_target`, secret use, deployment, release or live call is configured. Actual native gateway and browser/lifecycle suites remain local qualifications; remote runner reliability is not claimed. Hosted Actions execution is pending because this task does not push.

Licensing is pending. [Third-party inventory and recommendation](third-party.md) explicitly distinguish package metadata from complete binary/image redistribution clearance. Upstream contribution is a proposal, not acceptance. Production authentication, verifier-hop authentication, arbitrary routes/streaming, global gateway deadlines and atomic revocation remain outside the qualification.

## Changed-file inventory

| Area | Exact files |
| --- | --- |
| CI and checks | `.github/workflows/checks.yaml`, `dev/Dockerfile.checks`, `scripts/check_docs.py`, `scripts/test_check_docs.py` |
| Installation/build | `.dockerignore`, `compose.lab.yaml`, `dev/Dockerfile`, `dev/Dockerfile.lab`, `services/verifier/Dockerfile.004c`, `services/verifier/Dockerfile.004e`, `services/verifier/Dockerfile.004g` |
| Lab and regressions | `internal/lab/lab.go`, `internal/lab/lab_test.go`, `tests/lab/manage.py`, `tests/lab/smoke.py`, `tests/lab/test_manage.py` |
| Canonical documentation | `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `docs/architecture.md`, `docs/operations.md`, `docs/verification-lab.md`, `docs/compatibility.md`, `docs/security.md`, `docs/evaluation.md`, `docs/third-party.md`, `docs/task-005b.md` |
| Historical maintenance | `docs/decisions/0001-native-bifrost-plugin.md` clarifies supported dynamic installation; `docs/task-004a-hardening.md` and `docs/task-004b.md` replace private workstation paths with the equivalent current-directory expression, preserving recorded results |

## Assessment

**APPROVE for the stated pinned, local integration and documentation scope**, with the fresh-input test method and pending hosted-CI/license decisions stated above. This is not approval for production deployment, image redistribution, upstream acceptance or other gateway versions. The compatibility and enforcement acceptance checks ran against real private gateways; no security check was weakened to make installation pass.

Suggested repository description: "Evidence-backed, fail-closed response verification for Bifrost, with request-bound receipts and a local verification lab." Suggested topics: `bifrost`, `ai-gateway`, `llm`, `verification`, `golang`, `security`, `tavily`. Repository settings were not changed.
