#!/bin/sh
set -eu
# Native SecretVar resolves this process-only environment reference. The key is
# never a command argument, Compose environment value or generated config value.
if [ "${EPOCHGUARD_005C_MODE:-offline}" = live ]; then
    [ "${EPOCHGUARD_RUN_MODEL_005C:-}" = 1 ] || exit 1
    IFS= read -r EPOCHGUARD_005C_KEY < /run/secrets/provider || test -n "${EPOCHGUARD_005C_KEY:-}"
else
    EPOCHGUARD_005C_KEY=offline-fixture-only
fi
export EPOCHGUARD_005C_KEY
# Upstream diagnostics are not qualified for secret/content safety. Suppress
# them in this isolated profile, including startup and provider HTTP errors.
exec /app/bifrost-http -app-dir /app/verify -host 0.0.0.0 -port 8080 >/dev/null 2>&1
