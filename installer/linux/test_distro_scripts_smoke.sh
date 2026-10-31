#!/usr/bin/env bash
# Smoke test for the shared distro scripts (#88 exit criterion: each bootstrap script has a thin
# smoke test asserting its documented contract — inputs, output lines, exit codes — against a
# stubbed OS). Run: bash installer/linux/test_distro_scripts_smoke.sh
set -euo pipefail

SCRIPTS="$(cd "$(dirname "$0")/../scripts" && pwd)"
DISTRO="$SCRIPTS/distro"
ENGINE="$SCRIPTS/windows/03-engine.sh"
PARAMS="$(mktemp)"; echo '{"install_dir": "/tmp/ws"}' > "$PARAMS"
STUB="$(mktemp -d)"; printf '#!/bin/sh\necho "uv 9.9.9 (stub)"\n' > "$STUB/uv"; chmod +x "$STUB/uv"
export PATH="$STUB:$PATH"
if [ -d /mnt/wsl ] && ls /mnt/wsl/wordslab-platform-* >/dev/null 2>&1; then
  echo "SKIP: /mnt/wsl/wordslab-platform-* exists on this host — the 04 mounts path needs real WSL, not CI." >&2
  exit 0
fi

fail() { echo "SMOKE FAIL: $*" >&2; exit 1; }

# Every numbered script must at least BE valid shell — a syntax error only shows up at run time
# on the Windows host otherwise (live bug: an inline bash -c body, 2026-10-31).
for script in "$DISTRO"/*.sh "$SCRIPTS"/windows/*.sh; do
  [ -f "$script" ] || continue
  bash -n "$script" || fail "$(basename "$script") has a bash syntax error"
done

# Step 03's engine script keeps its ruled content (it runs uv for real on Windows only).
grep -q "astral.sh/uv/install.sh" "$ENGINE" || fail "03-engine.sh must install uv"
grep -q "/opt/wordslab/python" "$ENGINE" || fail "03-engine.sh must name the engine slot"
grep -q "Wordslab engine ready" "$ENGINE" || fail "03-engine.sh must end on its human sentence"
if grep -q "command -v uv" "$ENGINE"; then fail "03-engine.sh must re-run the uv installer (update lane)"; fi

# Shared usage contract: missing --parameters, a nonexistent file, and unknown arguments all
# exit 2 loudly (the runner mirrors the stderr line — never silent).
for script in 04-data-volumes.sh 05-first-core.sh 06-front-door.sh; do
  rc=0; out="$(bash "$DISTRO/$script" 2>&1)" || rc=$?
  [ "$rc" -eq 2 ] || fail "$script without --parameters must exit 2 (got $rc)"
  echo "$out" | grep -q "usage:" || fail "$script must name its usage on bad arguments"
  rc=0; out="$(bash "$DISTRO/$script" --wat 2>&1)" || rc=$?
  [ "$rc" -eq 2 ] || fail "$script with unknown argument must exit 2 (got $rc)"
  bash "$DISTRO/$script" --parameters /nope/missing.json >/dev/null 2>&1 && fail "$script with a missing parameters file must fail"
done

# 04 with no published disks (native host): visible no-op + summary, exit 0 — not a fake mount.
out="$(bash "$DISTRO/04-data-volumes.sh" --parameters "$PARAMS")"
echo "$out" | grep -q "Data volumes ready — 0 Wordslab Linux disk(s) mounted." || fail "04 must summarize honestly: $out"

# 05 with a stubbed uv: the engine slot is reported, exit 0.
out="$(bash "$DISTRO/05-first-core.sh" --parameters "$PARAMS")"
echo "$out" | grep -q "engine slot present: uv 9.9.9" || fail "05 must show the stubbed engine: $out"
echo "$out" | grep -q "core install slot ready" || fail "05 must end on its promise line: $out"

# 06 with valid parameters: slot line naming what #92/#62 still bring, exit 0.
out="$(bash "$DISTRO/06-front-door.sh" --parameters "$PARAMS")"
echo "$out" | grep -q "front-door slot ready" || fail "06 must state the slot state: $out"

rm -f "$PARAMS"; rm -rf "$STUB"
echo "distro scripts smoke: OK (usage, missing file, no-op mounts, stubbed engine, slot lines)"
