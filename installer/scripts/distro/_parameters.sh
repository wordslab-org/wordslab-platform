#!/usr/bin/env bash
# Shared --parameters parsing for the numbered distro scripts (#88 shared contract):
# every distro script receives the very JSON the wizard/TUI wrote, and scripts re-run by
# hand read the same file. Source this from a numbered script; afterwards $PARAMS holds the
# validated path. Usage errors exit 2 loudly — the runner mirrors the line, never silent.

PARAMS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --parameters) PARAMS="$2"; shift 2 ;;
    *) echo "$(basename "$0"): unknown argument '$1' — usage: $(basename "$0") --parameters <file>" >&2; exit 2 ;;
  esac
done
[ -n "$PARAMS" ] || { echo "$(basename "$0"): no --parameters file given — usage: $(basename "$0") --parameters <file>" >&2; exit 2; }
[ -f "$PARAMS" ] || { echo "$(basename "$0"): parameters file '$PARAMS' does not exist" >&2; exit 2; }
