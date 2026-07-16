#!/usr/bin/env bash
# Run a Python script inside a real, headless GIMP 3 process.
#
# Usage: scripts/run_gimp_batch.sh path/to/script.py
#
# The script runs with `Gimp`, `Gegl`, `Babl`, `GObject`, `GLib`, and `Gio`
# already imported into its globals (that's how GIMP's own python-eval
# plugin sets up `exec()` -- see
# <gimp>/lib/gimp/3.0/plug-ins/python-eval/python-eval.py).
#
# Flags that matter and are easy to get wrong (found by trial and error
# against a real GIMP 3.2.4 install, see docs/API_MAPPING.md Phase 2 notes):
#   -i, --no-interface   required for headless use.
#   -s, --no-splash       just faster startup, not required for correctness.
#   Do NOT pass -d (--no-data) or -f (--no-fonts): -d disables gradients
#   (chart_builder.py needs the built-in "FG to BG (RGB)" gradient for
#   gradient fills) and -f disables fonts (needed for text layers). Passing
#   either produces confusing downstream failures rather than an obvious
#   "fonts disabled" error.
#   --quit                terminates the process after the batch commands
#   run. Without it, GIMP stays resident as a background service --
#   `pdb.gimp_quit(1)` does NOT work here (`pdb` isn't a predefined global
#   in the python-fu-eval batch interpreter), so the process just hangs.

set -euo pipefail

GIMP_BIN="${GIMP_BIN:-/Applications/GIMP.app/Contents/MacOS/GIMP}"
SCRIPT_PATH="$1"

if [ ! -x "$GIMP_BIN" ]; then
    echo "GIMP binary not found or not executable at: $GIMP_BIN" >&2
    echo "Override with GIMP_BIN=/path/to/gimp $0 <script.py>" >&2
    exit 1
fi

"$GIMP_BIN" -i -s --batch-interpreter=python-fu-eval -b "$(cat "$SCRIPT_PATH")" --quit
