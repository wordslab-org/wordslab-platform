#!/usr/bin/env bash
# Smoke contract for the Linux entry point (installer/linux/install.sh): numbered labels,
# successful handoff from a checkout, and loud gap exits. Run: bash test_install_smoke.sh
set -uo pipefail   # deliberately NOT -e: the failure paths under test exit non-zero on purpose
cd "$(dirname "$0")"
TMPDIR_STUB="$(mktemp -d)"

pass=0; fail=0
check() { if [ "$1" = "$2" ]; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: expected '$2', got '$1'"; fi; }
has() { if grep -q -- "$2" <<<"$1"; then echo ok; else echo no; fi; }

params="$(mktemp)"; echo '{"data_disk": "/data"}' > "$params"

# 1) dev checkout flow: numbered journey + handoff to the TUI + web address line
out=$(bash install.sh --parameters "$params" 2>&1); rc=$?
check "$rc" 0
check "$(has "$out" '^\[01\] Download the Wordslab installer payload')" ok
check "$(has "$out" '\[03\] Install uv + Python')" ok
check "$(has "$out" 'handing the journey to the Python installer TUI')" ok
check "$(has "$out" '\[06\]')" ok  # the TUI continued the numbered journey
check "$(has "$out" 'continues in the dashboard at: https://wordslab.local/')" ok

# 2) no parameters file: named gap, exit 1, nothing installed silently
out2=$(bash install.sh 2>&1); rc2=$?
check "$rc2" 1
check "$(has "$out2" 'No parameters file')" ok

# 3) runner contract: stderr lines mirror as "[NN] ! ..." (shared with the C#/Python runners).
#     Uses a stub payload so a script can emit stderr without touching the real placeholders.
stub="$TMPDIR_STUB"; mkdir -p "$stub/scripts/linux" "$stub/python"
printf '#!/usr/bin/env bash\necho out-line\necho err-line >&2\n' > "$stub/scripts/linux/01-payload-download.sh"
for n in 02-reachability 03-uv-python; do printf '#!/usr/bin/env bash\ntrue\n' > "$stub/scripts/linux/$n.sh"; done
printf 'import sys\nprint("stub tui ran: " + " ".join(sys.argv[1:]))\n' > "$stub/python/tui.py"
out3=$(WORDSLAB_INSTALL_DIR="$stub" bash install.sh --parameters "$params" 2>&1)
check "$(has "$out3" '\[01\] out-line')" ok
check "$(has "$out3" '\[01\] ! err-line')" ok
rm -rf "$stub"

rm -f "$params"
echo "smoke: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
