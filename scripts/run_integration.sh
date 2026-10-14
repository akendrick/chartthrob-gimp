#!/usr/bin/env bash
# Run every tests/integration/manual_*.py inside a real headless GIMP and
# print one PASS/FAIL line each. Requires GIMP 3 (see run_gimp_batch.sh).
cd "$(dirname "$0")/.."
fail=0
for t in tests/integration/manual_*.py; do
  out="$(./scripts/run_gimp_batch.sh "$t" 2>&1)"
  # Match a whole output line and reject tracebacks: a failure traceback echoes
  # the script's source, which itself contains the print("..._PASSED") text.
  if echo "$out" | grep -qE '^([A-Z0-9_]+_PASSED|CURVE_REUSE_OK)$' && ! echo "$out" | grep -q 'Traceback'; then echo "PASS  $t"
  else echo "FAIL  $t"; echo "$out" | tail -15; fail=1; fi
done
exit $fail
