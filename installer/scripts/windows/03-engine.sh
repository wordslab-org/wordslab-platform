#!/usr/bin/env bash
# 03 — install the Wordslab engine (uv + a managed CPython) INSIDE the app VM.
# Windows-only journey step (Linux step 03 installs uv natively in scripts/linux/).
#
# Contract: 03-engine.sh --parameters <file>
#   in : the JSON the wizard wrote (install_dir + volume_<DRIVE> keys; only echoed here).
#   out: uv/python version lines + a final human sentence (the step card shows it).
#   exit: 0 ok · 2 bad usage · non-zero = the engine is missing, the journey stops.
#   re-run: the uv installer runs EVERY time on purpose — re-running updates uv in place
#           (the engine layer of the update lane, ADR-0016 §8); uv python install is a no-op
#           when 3.12 is already present.
#
# Why a file and not an inline `bash -c` body (#88 live bug, 2026-10-31): a multi-line body
# containing embedded quotes gets re-split on the Linux side of wsl.exe, bash sees an
# unterminated quote and dies with exit 2. Script files cross the boundary as ONE translated
# path — the same mechanism steps 4–6 already used.
set -euo pipefail

# shellcheck source=../distro/_parameters.sh
. "$(dirname "$0")/../distro/_parameters.sh"   # shared --parameters contract (#88)
echo "03: install parameters read from $PARAMS"

if ! command -v curl >/dev/null 2>&1; then
  apt-get update -qq && apt-get install -y -qq curl ca-certificates
fi

# Engine landing place (#88 ruling): uv in /usr/local/bin, CPython + cache under /opt/wordslab.
# uv's installer takes ENV, not flags (a --install-dir flag made it exit "unknown option",
# live 2026-10-31): UV_INSTALL_DIR sets the destination, UV_NO_MODIFY_PATH keeps it out of
# shell rc files (/usr/local/bin is already on the default PATH).
curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh
# Verification (not a skip-guard): the installer re-runs every time, but uv must be THERE after.
test -x /usr/local/bin/uv || { echo "03 ! uv did not land in /usr/local/bin" >&2; exit 1; }
grep -q UV_PYTHON_INSTALL_DIR /etc/environment 2>/dev/null ||
  printf 'UV_PYTHON_INSTALL_DIR=/opt/wordslab/python\nUV_CACHE_DIR=/opt/wordslab/uv-cache\n' >> /etc/environment
export UV_PYTHON_INSTALL_DIR=/opt/wordslab/python
export UV_CACHE_DIR=/opt/wordslab/uv-cache

uv python install 3.12
UVV=$(uv --version | cut -d' ' -f2)
PYV=$(uv run --no-project --python 3.12 python -c 'import sys; print(sys.version.split()[0])')
echo "Wordslab engine ready - uv $UVV and Python $PYV in the Wordslab virtual machine."
