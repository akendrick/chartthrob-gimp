#!/usr/bin/env bash
# Run a Python script inside a real, headless GIMP 3 process.
#
# Usage: scripts/run_gimp_batch.sh path/to/script.py
#
# The script runs with `Gimp`, `Gegl`, `Babl`, `GObject`, `GLib`, and `Gio`
# already imported into its globals (GIMP's python-eval plugin does this),
# and with CHARTTHROB_ROOT set to this repo's root (the integration scripts
# use it to import the package -- no machine-specific paths).
#
# Flags that matter and are easy to get wrong (found against GIMP 3.2.4):
#   -i, --no-interface   required for headless use.
#   -s, --no-splash      faster startup.
#   Do NOT pass -d (--no-data) or -f (--no-fonts): -d disables gradients
#   (gradient fills need the built-in "FG to BG (RGB)") and -f disables
#   fonts (text layers) -- both fail in confusing, non-obvious ways.
#   --quit               ends the process after the batch commands; without
#   it GIMP stays resident. `pdb.gimp_quit()` is NOT available here.
#
# gimp-console is preferred: the GUI binary with -i crashes on newer macOS
# ("Can't create a GtkStyleContext without a display connection").
#
# Override the binary with GIMP_BIN=/path/to/gimp.

set -euo pipefail

export CHARTTHROB_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT_PATH="$1"

if [ -z "${GIMP_BIN:-}" ]; then
  for candidate in \
      "/Applications/GIMP.app/Contents/MacOS/gimp-console" \
      "$(command -v gimp-console 2>/dev/null || true)" \
      "$(command -v gimp-3 2>/dev/null || true)" \
      "$(command -v gimp 2>/dev/null || true)" \
      "/Applications/GIMP.app/Contents/MacOS/GIMP"; do
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then GIMP_BIN="$candidate"; break; fi
  done
fi
if [ -z "${GIMP_BIN:-}" ] || [ ! -x "$GIMP_BIN" ]; then
    echo "GIMP 3 binary not found. Set GIMP_BIN=/path/to/gimp and retry." >&2
    exit 1
fi

"$GIMP_BIN" -i -s --batch-interpreter=python-fu-eval -b "$(cat "$SCRIPT_PATH")" --quit
