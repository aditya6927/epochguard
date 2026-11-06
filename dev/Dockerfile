# Gateway, plugin, fixture and smoke runner share this exact Linux toolchain.
FROM golang:1.27.3-alpine3.24@sha256:f2c872bcee949b7be9c490efd02b48a8a2fbf947cdf533f1c58525ec9d8170fd AS build
RUN apk add --no-cache git gcc musl-dev binutils
ENV CGO_ENABLED=1 GOWORK=off GOTOOLCHAIN=local GOOS=linux GOARCH=amd64
WORKDIR /src/bifrost
RUN git init && git remote add origin https://github.com/maximhq/bifrost.git \
    && git sparse-checkout init --cone && git sparse-checkout set transports \
    && git -c http.lowSpeedLimit=1024 -c http.lowSpeedTime=120 fetch --depth 1 --filter=blob:none origin e869c3f9adc96ea53c38694a21bb04a8e1085487 \
    && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = e869c3f9adc96ea53c38694a21bb04a8e1085487
WORKDIR /src/bifrost/transports
RUN --mount=type=cache,target=/go/pkg/mod go mod download && go mod verify

# The plugin's manifest intentionally mirrors the host's full pinned module graph.
COPY plugins/epochguard/go.mod plugins/epochguard/go.sum /src/epochguard/plugins/epochguard/
RUN tail -n +2 go.mod > /tmp/host.mod \
    && tail -n +2 /src/epochguard/plugins/epochguard/go.mod > /tmp/plugin.mod \
    && cmp /tmp/host.mod /tmp/plugin.mod \
    && cmp go.sum /src/epochguard/plugins/epochguard/go.sum

# API-only build: provide an embed input, without compiling or modifying a dashboard.
COPY dev/bifrost/ui-placeholder.txt /src/bifrost/transports/bifrost-http/ui/task-002a.txt
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build \
    go build -p=2 -mod=readonly -trimpath -ldflags='-w -s -X main.Version=v2.4.0' -o /out/bifrost-http ./bifrost-http
COPY plugins/epochguard/ /src/epochguard/plugins/epochguard/
WORKDIR /src/epochguard/plugins/epochguard
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build \
    test -z "$(gofmt -l .)" && go test -mod=readonly -trimpath -v ./... \
    && go test -race -p=2 -mod=readonly -trimpath ./... \
    && go build -mod=readonly -trimpath -buildmode=plugin -o /out/epochguard.so .

COPY go.mod /src/epochguard/go.mod
COPY cmd/ /src/epochguard/cmd/
COPY tests/ /src/epochguard/tests/
WORKDIR /src/epochguard
RUN --mount=type=cache,target=/root/.cache/go-build \
    test -z "$(gofmt -l cmd tests)" \
    && go build -mod=readonly -trimpath -o /out/provider-fixture ./cmd/provider-fixture \
    && go test -mod=readonly -trimpath -c -o /out/smoke.test ./tests/smoke
RUN --mount=type=cache,target=/go/pkg/mod mkdir -p /out/build-info \
    && go version > /out/build-info/toolchain.txt \
    && go version -m /out/bifrost-http > /out/build-info/gateway.txt \
    && go version -m /out/epochguard.so > /out/build-info/plugin.txt \
    && readelf -l /out/bifrost-http > /out/build-info/gateway-elf.txt \
    && grep -q 'Requesting program interpreter' /out/build-info/gateway-elf.txt \
    && cd /src/bifrost/transports && go list -mod=readonly -m all > /out/build-info/modules.txt

# Development runtime retains the pinned Go tooling for artifact inspection.
FROM golang:1.27.3-alpine3.24@sha256:f2c872bcee949b7be9c490efd02b48a8a2fbf947cdf533f1c58525ec9d8170fd AS runtime
RUN apk add --no-cache libgcc ca-certificates \
    && addgroup -g 10001 epochguard && adduser -D -u 10001 -G epochguard epochguard \
    && mkdir -p /app/data /app/control /app/reject /app/unavailable \
    && chown epochguard:epochguard /app/data /app/control /app/reject /app/unavailable
COPY --from=build /out/bifrost-http /app/bifrost-http
COPY --from=build /out/epochguard.so /app/plugins/epochguard.so
COPY --from=build /out/provider-fixture /app/provider-fixture
COPY --from=build /out/smoke.test /app/smoke.test
COPY --from=build /out/build-info /app/build-info
COPY dev/bifrost/config.json /app/data/config.json
COPY dev/bifrost/config.no-plugin.json /app/control/config.json
COPY dev/bifrost/config.reject.json /app/reject/config.json
COPY dev/bifrost/config.unavailable.json /app/unavailable/config.json
USER 10001:10001
WORKDIR /app
CMD ["/app/bifrost-http", "-app-dir", "/app/data", "-host", "0.0.0.0", "-port", "8080"]
