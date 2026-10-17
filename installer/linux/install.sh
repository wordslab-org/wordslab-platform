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
  local label="[$(printf '%02d' "$n")]"
  printf '%s %s\n' "$label" "$title"
  # Same runner contract as the C# and Python sides: stdout mirrored with [NN], stderr with "[NN] !".
  "$@" 2> >(sed "s|^|$label ! |" >&2) | sed "s|^|$label |"
  local rc=${PIPESTATUS[0]}
  if [ "$rc" -ne 0 ]; then
    printf '%s FAILED (exit %s) — the journey stops here; nothing further is installed.\n' "$label" "$rc"
    exit "$rc"
  fi
}

# The numbered scripts are real files (installer/scripts/linux/) so the re-run promise is
# literal. Chicken-and-egg until #88 ships the payload: under `curl | bash` those very files are
# what step 1 downloads, so when they are not on disk yet each step runs its visible inline
# placeholder instead — named out loud, never silently.
SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo .)"   # $0 is `bash` under curl|bash
SCRIPTS=""
for d in "$WORDSLAB_INSTALL_DIR/scripts/linux" "$SCRIPT_DIR/../scripts/linux"; do
  if [ -d "$d" ]; then SCRIPTS="$d"; break; fi
done

if [ -n "$SCRIPTS" ]; then
  step 1 "Download the Wordslab installer payload" bash "$SCRIPTS/01-payload-download.sh"
  step 2 "Check network reachability (github, pypi)" bash "$SCRIPTS/02-reachability.sh"
  step 3 "Install uv + Python" bash "$SCRIPTS/03-uv-python.sh"
else
  # Payload not extracted yet (#88's job): the same numbered steps, visible inline placeholders.
  step 1 "Download the Wordslab installer payload" bash -c "echo 'payload download: placeholder until #88 ($WORDSLAB_PAYLOAD_URL -> $WORDSLAB_INSTALL_DIR); the numbered scripts live inside the payload'"
  step 2 "Check network reachability (github, pypi)" bash -c "echo 'reachability check: placeholder until #88'"
  step 3 "Install uv + Python" bash -c "echo 'uv bootstrap: placeholder until #88'"
fi

# Handoff (ADR-0014 §3 phase 2): gated on ARTIFACTS (interpreter + extracted payload), never on
# the user's command line — `curl … | bash` must be able to hand off once #88's payload exists.
TUI=""
for candidate in "$WORDSLAB_INSTALL_DIR/python/tui.py" "$SCRIPT_DIR/../python/tui.py"; do
  if [ -f "$candidate" ]; then TUI="$candidate"; break; fi
done

if ! command -v python3 >/dev/null 2>&1; then
  echo "[--] Python is not available — step 3 above must complete first. The journey stops here; nothing further is installed."
  exit 1
fi
if [ -z "$TUI" ]; then
  echo "[--] The installer payload is not extracted at $WORDSLAB_INSTALL_DIR — payload extraction ships with ticket #88."
  echo "[--] The journey stops here; nothing further is installed."
  exit 1
fi
if [[ " $* " != *" --parameters "* ]]; then
  # Linux parameter prompts arrive with #88's payload; until then a file can be passed through
  # the pipe: curl … | bash -s -- --parameters <file>
  echo "[--] No parameters file: Linux parameter prompts ship with ticket #88."
  echo "[--] Until then pass one through: … | bash -s -- --parameters <file>. The journey stops here."
  exit 1
fi

echo "[--] Python is available — handing the journey to the Python installer TUI."
exec python3 "$TUI" --journey linux "$@"
