#!/bin/sh
set -eu
if [ "${EPOCHGUARD_005C_MODE:-offline}" = live ]; then
    [ "${EPOCHGUARD_005E_ALLOW_MODEL:-}" = 1 ] || exit 1
    [ "${EPOCHGUARD_005E_ALLOW_EVIDENCE:-}" = 1 ] || exit 1
fi
exec sh /run/start-model-gateway.sh
