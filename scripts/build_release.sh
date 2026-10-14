#!/usr/bin/env bash
# Build dist/chartthrob-gimp-<version>.zip: a self-contained plugin folder
# (the chartthrob package bundled inside it), install script, README, CHANGELOG.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="$(python3 -c 'import re;print(re.search(r"__version__ = \"(.+?)\"",open("chartthrob/__init__.py").read()).group(1))')"
OUT="dist/chartthrob-gimp-$VERSION"
rm -rf "$OUT" "$OUT.zip"; mkdir -p "$OUT/chartthrob-plugin" "$OUT/scripts"

cp plugin/chartthrob-plugin/chartthrob-plugin.py "$OUT/chartthrob-plugin/"
cp -R chartthrob "$OUT/chartthrob-plugin/chartthrob"
cp scripts/install.sh "$OUT/scripts/"
cp README.md CHANGELOG.md LICENSE "$OUT/"
find "$OUT" \( -name '__pycache__' -o -name '.DS_Store' -o -name '*.pyc' \) -prune -exec rm -rf {} +
chmod +x "$OUT/chartthrob-plugin/chartthrob-plugin.py" "$OUT/scripts/install.sh"

if grep -rIl "/Users/" "$OUT" >/dev/null 2>&1; then
  echo "ERROR: a personal absolute path leaked into the release:" >&2
  grep -rIn "/Users/" "$OUT" >&2; exit 1
fi
(cd dist && zip -qr "chartthrob-gimp-$VERSION.zip" "chartthrob-gimp-$VERSION")
echo "Built dist/chartthrob-gimp-$VERSION.zip"
shasum -a 256 "dist/chartthrob-gimp-$VERSION.zip"
