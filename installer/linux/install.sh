#!/usr/bin/env bash
# Wordslab Platform — Linux entry point (ADR-0014 §7: curl https://wordslab.org/install.sh | bash).
# Thin by design: it downloads the installer payload, then runs the same guided journey as the
# Windows .exe. The numbered bootstrap scripts are ticket #88's home; here they are the visible
# numbered slots the journey drives. Nothing is installed silently.
set -euo pipefail

WORDSLAB_INSTALL_DIR="${WORDSLAB_INSTALL_DIR:-$HOME/.wordslab/installer}"
WORDSLAB_PAYLOAD_URL="${WORDSLAB_PAYLOAD_URL:-https://wordslab.org/downloads/installer-latest.tar.gz}"

echo "Wordslab Platform installer (Linux)."
echo "Every step is shown as a numbered script; you can re-run any of them yourself."
echo

step() {
  local n="$1" title="$2"; shift 2
  printf '[%02d] %s\n' "$n" "$title"
  "$@" | sed "s/^/[$(printf '%02d' "$n")] /"
  local rc=${PIPESTATUS[0]}
  if [ "$rc" -ne 0 ]; then
    printf '[%02d] FAILED (exit %s) — the journey stops here; nothing further is installed.\n' "$n" "$rc"
    exit "$rc"
  fi
}

# 01 — fetch the installer payload (the Python TUI + the numbered scripts live inside it)
step 1 "Download the Wordslab installer payload" bash -c "echo 'payload download: placeholder until #88 (\$WORDSLAB_PAYLOAD_URL -> \$WORDSLAB_INSTALL_DIR)'"

# 02 — network reachability (github, pypi)
step 2 "Check network reachability (github, pypi)" bash -c "echo 'reachability check: placeholder until #88'"

# 03 — uv + Python
step 3 "Install uv + Python" bash -c "echo 'uv bootstrap: placeholder until #88'"

# Handoff: once Python exists, the Python TUI takes the journey over (ADR-0014 §3 phase 2).
if command -v python3 >/dev/null 2>&1; then
  echo "[--] Python is available — handing the journey to the Python installer TUI."
  exec python3 "$(dirname "$0")/../python/tui.py" "$@"
fi

echo "[--] Python is not available yet — the bootstrap scripts above must complete first."
exit 1
