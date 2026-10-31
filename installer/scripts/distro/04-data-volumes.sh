#!/usr/bin/env bash
# 04 — mount Wordslab's Linux disks inside its own Linux machine (#88 machinery).
#
# Contract: 04-data-volumes.sh --parameters <file>
#   in : the JSON the wizard/TUI wrote (install_dir + one volume_<DRIVE> per enabled drive).
#   out: one status line per disk + a final summary line (the wizard shows it on the step card).
#   exit: 0 ok (every ENABLED drive is mounted) · 2 bad usage · non-zero = a disk did not
#         appear, printed with what /mnt/wsl actually holds — the journey stops.
#   re-run: idempotent — an existing bind mount is kept, never remounted over.
#   test: WORDSLAB_MOUNT_ROOT overrides the in-VM mount root (smoke tests only; the journey
#         always uses the real /mnt/wordslab-platform).
#
# The Windows host step (Script04) imported one minimal WSL instance per drive — its WSL-managed
# ext4.vhdx lives in <drive>:\wordslab-platform\wordslab-platform-disk<letter>\ — and published
# that instance's /volume folder into /mnt/wsl, which WSL shares across distros (the proven
# wordslab-notebooks mechanism; no wsl --mount, no admin). Here the app machine bind-mounts those
# folders under /mnt/wordslab-platform/disk<letter> — one stable in-distro place for the core to
# keep data (ADR-0004 §8).
#
# Verification is by OUTCOME, not by attempt: an enabled drive whose disk is not mounted fails
# this step. (Live bug 2026-10-31: step 4 went green while nothing was mounted, because "zero
# disks found" was accepted as the native-Linux case.)
set -euo pipefail

# shellcheck source=_parameters.sh
. "$(dirname "$0")/_parameters.sh"   # shared --parameters contract (#88)
echo "04: install parameters read from $PARAMS"

# Which drives did the wizard enable? One volume_<DRIVE> key per enabled drive.
drives=$(grep -o '"volume_[A-Z]"' "$PARAMS" | sed 's/.*volume_//; s/"//' || true)

if [ -z "$drives" ]; then
  # Native Linux host: no data volumes were configured, and mounting host disks is #89's job.
  echo "no data volumes were configured in the parameters — nothing to mount here (native-Linux disk wiring is ticket #89)"
  echo "Data volumes ready - 0 Wordslab Linux disk(s) mounted."
  exit 0
fi

mount_root="${WORDSLAB_MOUNT_ROOT:-/mnt/wordslab-platform}"
mounted=0
missing=""
for drive in $drives; do
  letter=$(printf '%s' "$drive" | tr 'A-Z' 'a-z')
  source_dir="/mnt/wsl/wordslab-platform-disk$letter"
  target="$mount_root/disk$letter"
  mkdir -p "$target"
  if [ -d "$source_dir" ]; then
    mountpoint -q "$target" || mount --bind "$source_dir" "$target"
  fi
  if mountpoint -q "$target"; then
    echo "Wordslab Linux disk $letter mounted at $target"
    mounted=$((mounted + 1))
  else
    echo "04 ! disk $letter: '$source_dir' is not there, so $target has no data behind it" >&2
    missing="$missing $letter"
  fi
done

if [ -n "$missing" ]; then
  echo "04 ! /mnt/wsl inside the app VM holds: $(ls -A /mnt/wsl 2>/dev/null | tr '\n' ' ')" >&2
  echo "04 ! the disk(s)$missing could not be attached — press Start install again; nothing further was installed." >&2
  exit 1
fi

echo "Data volumes ready - $mounted Wordslab Linux disk(s) mounted."
