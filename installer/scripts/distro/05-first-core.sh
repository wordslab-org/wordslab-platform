#!/usr/bin/env bash
# 05 — install the first Wordslab core programs (#88 machinery; the core's first build is #62).
#
# Contract: 05-first-core.sh --parameters <file>
#   in : the JSON the wizard/TUI wrote (install_dir + volume_<DRIVE> keys).
#   out: what the core slot is and where its engine lives, as visible lines.
#   exit: 0 ok · 2 bad usage · non-zero = failed install, loudly, journey stops.
#   re-run: installing the same core version again is a no-op (Update path, ADR-0014 §7).
#
# The engine slot is #88's landing place: uv in /usr/local/bin, uv-managed Python under
# /opt/wordslab (step 03 placed them). When #62 ships the first core package, THIS step is the
# line that installs it — the slot, the parameters and the numbering already exist.
set -euo pipefail

# shellcheck source=_parameters.sh
. "$(dirname "$0")/_parameters.sh"   # shared --parameters contract (#88)
echo "05: install parameters read from $PARAMS"

command -v uv >/dev/null 2>&1 || { echo "05 ! uv is missing — step 03 must complete first" >&2; exit 1; }
echo "engine slot present: $(uv --version 2>/dev/null) in $(command -v uv), Python under /opt/wordslab/python"
echo "core install slot ready — the first core package installs here when ticket #62 ships it"
