#!/usr/bin/env bash
# 06 — bring up the Wordslab front door (#88 machinery; the proxy's cert + mDNS name are #92).
#
# Contract: 06-front-door.sh --parameters <file>
#   in : the JSON the wizard/TUI wrote (install_dir + volume_<DRIVE> keys).
#   out: the front-door slot state as visible lines; the Windows host step then PROVES the
#        home page answers and hands off to its address (one port, one certificate).
#   exit: 0 ok · 2 bad usage · non-zero = the front door did not come up, journey stops.
#   re-run: bringing up an already-up front door is a no-op.
#
# ADR-0014's promise — one stable address, one port, one TLS certificate — lands in pieces:
# #88 builds this numbered step and the answered-address handoff; #92 brings the certificate and
# the wordslab.local name; #62 puts the core behind it. Until the core answers, the Windows
# probe step fails with a plain sentence instead of pretending — nothing is installed silently.
set -euo pipefail

# shellcheck source=_parameters.sh
. "$(dirname "$0")/_parameters.sh"   # shared --parameters contract (#88)
echo "06: install parameters read from $PARAMS"

echo "front-door slot ready — one port, one certificate; the certificate and wordslab.local name arrive with ticket #92, the page behind them with ticket #62"
