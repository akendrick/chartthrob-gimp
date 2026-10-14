#!/usr/bin/env bash
# Install the ChartThrob plugin into a GIMP 3 user plug-ins folder.
#
#   scripts/install.sh [--gimp-version 3.2] [--plugins-dir DIR] [--link] [--uninstall]
#
# Works from either a release download (plugin folder sits next to this
# script's parent) or a development checkout (plugin/chartthrob-plugin/).
#   --link       symlink instead of copy (development: edits apply live)
#   --uninstall  remove a previously installed copy/link
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
NAME="chartthrob-plugin"

if   [ -d "$ROOT/$NAME" ];         then SRC="$ROOT/$NAME"          # release layout
elif [ -d "$ROOT/plugin/$NAME" ];  then SRC="$ROOT/plugin/$NAME"   # dev checkout
else echo "Can't find the $NAME folder next to this script." >&2; exit 1; fi

GIMP_VERSION="3.0"; PLUGINS_DIR=""; LINK=0; UNINSTALL=0
while [ $# -gt 0 ]; do
  case "$1" in
    --gimp-version) GIMP_VERSION="$2"; shift 2 ;;
    --plugins-dir)  PLUGINS_DIR="$2";  shift 2 ;;
    --link) LINK=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [ -z "$PLUGINS_DIR" ]; then
  case "$(uname -s)" in
    Darwin) PLUGINS_DIR="$HOME/Library/Application Support/GIMP/$GIMP_VERSION/plug-ins" ;;
    Linux)  PLUGINS_DIR="$HOME/.config/GIMP/$GIMP_VERSION/plug-ins" ;;
    *) echo "Unsupported OS for auto-detection; pass --plugins-dir (see README)." >&2; exit 1 ;;
  esac
fi
DEST="$PLUGINS_DIR/$NAME"

if [ "$UNINSTALL" = 1 ]; then
  rm -rf "$DEST"; echo "Removed $DEST"; exit 0
fi

mkdir -p "$PLUGINS_DIR"
rm -rf "$DEST"
if [ "$LINK" = 1 ]; then
  ln -s "$SRC" "$DEST"; echo "Linked $DEST -> $SRC"
else
  cp -R "$SRC" "$DEST"
  find "$DEST" \( -name '__pycache__' -o -name '.DS_Store' \) -prune -exec rm -rf {} +
  echo "Copied to $DEST"
fi
chmod +x "$DEST/$NAME.py"
echo "Done. Restart GIMP, then look for:"
echo "  File > Create > ChartThrob   and   Colors > ChartThrob"
echo "(GIMP profile version used: $GIMP_VERSION -- pass --gimp-version if yours differs.)"
