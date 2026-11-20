# Bifrost compatibility

EpochGuard is a native Go extension of Bifrost, using its supported dynamic-plugin installation mechanism. A dynamically built gateway is a supported Bifrost installation; the default static release is a different distribution that cannot load this plugin. This qualification covers the HTTP API, without the upstream dashboard.

The [005D-S security correction](task-005d-s.md) changes candidate admission independently in Python and Go without changing pinned Bifrost contracts, policy identifiers, sentence forms or receipt protocols. Each policy is now limited to one assertion per candidate. Existing pre-fix images must be rebuilt together with their verifier and qualification dependencies before using the corrected evidence.

## Qualified baseline

| Component or configuration | Assessment | Boundary |
| --- | --- | --- |
| Bifrost HTTP `transports/v2.4.0` | VERIFIED | Source `e869c3f9adc96ea53c38694a21bb04a8e1085487`; real native loader and buffered OpenAI chat route |
| Core / framework / semanticcache module | VERIFIED | `v1.14.1` / `v1.11.1` / `v1.7.4`; full transport module graph mirrored by the plugin |
| Go / target / libc | VERIFIED | Go `1.27.3`, CGO enabled, Linux/amd64, Alpine 3.24 musl; gateway and plugin built together |
| Native loader exports | VERIFIED | `Init(any) error`, `GetName() string`, `Cleanup() error`; optional transport/core hooks match pinned loader casts |
| `pre_builtin`, order `0` | VERIFIED | Public configuration, before built-ins; protected profiles disable cache and inference logging |
| Protected bounded completions | VERIFIED | `004g.v1`, nine forms, v2 request-bound receipt; ALLOW, refusal and lifecycle controls in [evaluation](evaluation.md) |
| Windows Docker Desktop host | VERIFIED | Linux containers; Windows does not execute the `.so` itself |
| Separate Linux Engine host / emulated host installation | NOT TESTED | The runtime and test stages are Linux/amd64; this qualification's host driver ran on Windows x86-64 |
| Static Bifrost release or stock static image | UNSUPPORTED | Cannot load Go `.so`; rebuild dynamically using the supported procedure |
| Windows native `.so` execution | UNSUPPORTED | Go native plugins do not support Windows |
| macOS, Linux/arm64, glibc builds | NOT TESTED | Upstream support does not constitute EpochGuard qualification |
| Other Bifrost versions, current `dev` | NOT TESTED | Rebuild both artifacts and rerun contracts, security and gateway tests before claiming compatibility |
| Existing upstream plugins added to protected stack | REQUIRES INVESTIGATION | Ordering, request mutation, response conversion, logging and cache behavior can alter this boundary |
| Streaming, arbitrary routes, background tasks, protected caching | UNSUPPORTED | Outside the qualified protected release contract |
| Native Gemini generation / 005C | NARROW REAL-MODEL ENFORCEMENT QUALIFIED; SIMULATED EVIDENCE | [November 19 review](task-005c-t.md#reviewed-real-model-qualification--november-19-2026): `gemini-3.5-flash-lite`, `strict-005ct`, four real model cases and six expected protected outcomes. Default unadapted mode and strict typed eligibility remain. Other models/configurations and real-model plus real-source execution are unqualified |

## Upstream sources and build equivalence

Upstream guidance inspected on November 15-16, 2026: [plugin getting started](https://github.com/maximhq/bifrost/blob/a3cd2b5b73466ba581ea5abcba8484353e75bf57/docs/plugins/getting-started.mdx), [dynamic binary guide](https://github.com/maximhq/bifrost/blob/a3cd2b5b73466ba581ea5abcba8484353e75bf57/docs/plugins/building-dynamic-binary.mdx), [repository setup](https://github.com/maximhq/bifrost/blob/a3cd2b5b73466ba581ea5abcba8484353e75bf57/docs/contributing/setting-up-repo.mdx), and [repository](https://github.com/maximhq/bifrost). The inspected `dev` head was `a3cd2b5b73466ba581ea5abcba8484353e75bf57`; those documents are guidance, not a tested gateway upgrade. Version numbers in their example commands are not this project's compatibility declaration.

The pinned [Makefile](https://github.com/maximhq/bifrost/blob/e869c3f9adc96ea53c38694a21bb04a8e1085487/Makefile) supports `make build DYNAMIC=1`: CGO stays enabled; static external-link flags and `sqlite_static` are omitted. [dev/Dockerfile](../dev/Dockerfile) uses the equivalent direct `go build` with `GOWORK=off`, `-mod=readonly`, `-trimpath`, and `-ldflags='-w -s -X main.Version=v2.4.0'`. It checks the gateway ELF interpreter. The plugin uses the same toolchain/graph/flags and `-buildmode=plugin`.

No tracked upstream source is patched. The Dockerfile fetches the exact revision, checks it, and checks that its tracked diff remains empty. A clearly identified generated text asset satisfies upstream's `go:embed all:ui` input. It is not a dashboard build or a changed Go source file. Building the upstream UI is outside this API-only qualification.

Pinned upstream contracts inspected: core schemas plugin interfaces; framework shared-object loader (`plugin.Open`, symbol lookups and exact casts); transport plugin registration, raw-body middleware and OpenAI response conversion. Actual loader execution remains necessary: matching source signatures alone cannot prove Go ABI compatibility.

## Install and load

Use Git, Python 3.12 and Docker Desktop Linux containers or Docker Engine with Compose v2/Buildx. Builds target Linux/amd64; the qualified host is Windows x86-64. Other host architectures/emulation and a separate Linux Engine installation were not qualified. No local Go, Node, virtual environment, prebuilt EpochGuard image or API key is required. Public dependency downloads are needed during build; test execution and Lab evidence are offline.

```powershell
git clone https://github.com/aditya6927/epochguard.git
cd epochguard
py -3.12 tests/lab/manage.py up --build
py -3.12 tests/lab/manage.py down
py -3.12 tests/lab/manage.py test
```

`test` starts and removes its disposable stack; `up` leaves it running at `http://127.0.0.1:8787`. The helper bypasses `.env` and builds native, verifier 004C, verifier 004E, verifier 004G and Lab in dependency order. Runtime keys are generated in a private disposable volume. Gateway, provider, verifier and management have no published ports.

Tests refuse existing project containers before building or entering cleanup. Use a distinct `--project-name` and test-only loopback `--test-port` to preserve another running Lab; see [test isolation](verification-lab.md#tests-and-demonstration-recording). Those test connections retain the fixed application Host/Origin. The interactive browser address remains port 8787.

The checked configuration is [dev/prose/gateway.json](../dev/prose/gateway.json): enabled plugin `epochguard`, local path `/app/plugins/epochguard.so`, placement `pre_builtin`, order `0`, strict policy configuration. The ingress supplies a nonce, validates the independently recomputed request digest and final response receipt, and refuses missing-plugin delivery. Copying only the plugin into an arbitrary deployment does not reproduce that protection. Treat receipt keys, loader files, setup access, private verifier and configuration as trusted operator resources.

For an operator's existing dynamic Bifrost installation, build gateway and plugin together from this exact module graph and mount the plugin/configuration privately. Reproduce the protected ingress/verifier deployment and security tests before admitting clients. The Lab is the supplied reproducible reference; production provider credentials, tenants and authentication are not qualified by it.

## Builder and ABI diagnostics

The launcher defaults to Docker's selected builder, not a builder literally named `default`. `docker context show` and `docker buildx ls` show the relationship without dumping credentials. An explicit builder must belong to the intended context:

```powershell
py -3.12 tests/lab/manage.py test --build --builder desktop-linux
```

On Linux the name may differ; omit `--builder` to use Docker's selection. `--builder default` can fail on Docker Desktop when the active context is `desktop-linux`. The [005B report](task-005b.md) records the reproduced error and clean-build scope. Never change global Docker context merely to suppress an error without checking the destination.

The helper prints only fixed stage labels and classified errors. To investigate a native build privately, run its exact public-dependency command and inspect the output locally:

```powershell
docker buildx build --load --progress plain -t epochguard-dev:002a -f dev/Dockerfile .
docker build --progress plain -t epochguard-verifier:004c -f services/verifier/Dockerfile.004c .
docker build --progress plain -t epochguard-verifier:004e -f services/verifier/Dockerfile.004e .
docker build --progress plain -t epochguard-verifier:004g -f services/verifier/Dockerfile.004g .
docker compose --env-file dev/lab.compose.env -f compose.lab.yaml build lab
```

Do not publish unrestricted logs or resolved configuration. A module mismatch fails the Dockerfile comparison. A `plugin was built with a different version of package` error requires a coordinated rebuild, not disabling checks. A missing dynamic interpreter requires correcting the gateway build/runtime libc. Go plugins cannot be safely unloaded/replaced in-process as a general upgrade strategy; use tested restart/lifecycle behavior. Local cache-access errors require excluding transient artifacts or fixing their permissions, not broadening container privileges.

## Contribution boundary

The separate [005I Explorer](../services/evidence_assessment/README.md) reuses the locked Python/FastAPI stack and adds only pinned `publicsuffix2==2.20191221` for offline publisher grouping. It has no Bifrost loader/ABI dependency or frontend build dependency. Its standalone Docker image and loopback port 8791 coexist with the original Lab. Public dependency installation needs network access; test execution is network-disabled. Publisher grouping uses a bundled 2019 PSL snapshot, never a runtime download; unknown suffixes abstain and real ownership/independence remains unproven. Live credentials must be readable by container UID 10001 while remaining private on the host; POSIX owners/mapped UIDs or explicit ACLs require operator configuration. See the [third-party audit](third-party.md).

The native policy plugin and its public-interface regression tests are candidates for a focused upstream proposal. A proposal should first agree with Bifrost maintainers on ownership and threat boundaries, and include pinned reproduction, terminal typed-error behavior and conversion-order tests. EpochGuard's Python source policies, HMAC ingress, offline fixtures and local Lab are separately maintained infrastructure; none is represented as an existing upstream feature. No upstream acceptance, release compatibility beyond this pin, or repository license grant is implied. See [contribution](../CONTRIBUTING.md), [security](security.md), and [third-party audit](third-party.md).
