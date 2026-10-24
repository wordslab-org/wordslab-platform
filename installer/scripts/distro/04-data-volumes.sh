#!/usr/bin/env bash
# 04 — mount Wordslab's Linux disks inside its own Linux machine (#88 machinery).
#
# Contract: 04-data-volumes.sh --parameters <file>
#   in : the JSON the wizard/TUI wrote (install_dir + one volume_<DRIVE> per enabled drive).
#   out: one status line per disk + a final summary line (the wizard shows it on the step card).
#   exit: 0 ok · 2 bad usage · any other non-zero = a mount failed, loudly, journey stops.
#   re-run: idempotent — an existing bind mount is kept, never remounted over.
#
# The Windows host step (Script04) imported one minimal WSL instance per drive — its WSL-managed
# ext4.vhdx lives in <drive>:\wordslab\wordslab-<letter>\ — and published each instance's
# /volume folder into /mnt/wsl, which WSL shares across distros (the proven wordslab-notebooks
# mechanism; no wsl --mount, no admin). Here the app machine bind-mounts those folders under
# /mnt/wordslab/<letter> — one stable in-distro place for the core to keep data (ADR-0004 §8).
set -euo pipefail

# shellcheck source=_parameters.sh
. "$(dirname "$0")/_parameters.sh"   # shared --parameters contract (#88)
echo "04: install parameters read from $PARAMS"

found=0
for published in /mnt/wsl/wordslab-*; do
  [ -d "$published" ] || continue          # glob unmatched: no Wordslab Linux disks published
  letter="${published##*/wordslab-}"
  target="/mnt/wordslab/$letter"
  mkdir -p "$target"
  mountpoint -q "$target" || mount --bind "$published" "$target"
  if ! mountpoint -q "$target"; then
    echo "04 ! the Linux disk $letter did not mount at $target" >&2; exit 1
  fi
  echo "Wordslab Linux disk $letter mounted at $target"
  found=$((found + 1))
done

if [ "$found" -eq 0 ]; then
  # Legitimate on a native Linux host: there data disks are mounted by the host itself, and that
  # wiring is ticket #89's job. Saying so beats pretending a mount happened.
  echo "no Wordslab Linux disks published through /mnt/wsl — native-Linux data-disk wiring arrives with ticket #89"
fi
echo "Data volumes ready — $found Wordslab Linux disk(s) mounted."
