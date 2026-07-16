# ChartThrob for GIMP (unofficial port)

An independent GIMP 3 port of [ChartThrob](https://github.com/joker-b/ChartThrob),
Kevin Bjorke's Photoshop tool for calibrating digital-negative contact
printing (platinum/palladium, cyanotype, silver, bromoil, and similar
alt-process printing). Original chart design by Thomas Howard.

**This is not the original project and is not affiliated with or endorsed
by its author.** See [Licensing note](#licensing-note) below before you
redistribute this.

## What it does

Two workflows, same as the original:

1. **Build a calibration chart** — a printable grayscale test chart.
2. **Analyze a scan** of a printed-and-scanned copy of that chart, producing
   a tone-correction curve you can apply to other black-and-white images
   before printing digital negatives from them.

Full step-by-step usage is in each menu command's own description inside
GIMP (Procedure Browser), carried over from the original's help text.

## Requirements

- GIMP 3.0 or later (developed and verified against 3.2.4 specifically —
  see `docs/PLAN.md` section 3 for what was actually tested).
- No separate Python install needed — this uses GIMP's own bundled Python 3.

## Installation

GIMP 3 discovers a Python plugin by folder-name-matches-file-basename
convention: the plugin must live in its own directory, named exactly the
same as the `.py` file inside it, somewhere GIMP looks for plugins.

1. Clone or download this repository.
2. Symlink (recommended, so `git pull` keeps it current) or copy
   `plugin/chartthrob-plugin/` into your GIMP plug-ins directory, keeping
   the folder name unchanged:

   | OS | Plug-ins directory |
   |---|---|
   | macOS | `~/Library/Application Support/GIMP/<version>/plug-ins/` |
   | Linux | `~/.config/GIMP/<version>/plug-ins/` |
   | Windows | `%APPDATA%\GIMP\<version>\plug-ins\` |

   Replace `<version>` with whatever your installed GIMP actually uses
   (e.g. `3.0`, `3.2`) — check by opening GIMP and looking at
   Edit → Preferences → Folders → Plug-Ins, which lists the exact path.

   macOS example, from this repo's root:
   ```sh
   ln -s "$(pwd)/plugin/chartthrob-plugin" \
         ~/Library/Application\ Support/GIMP/3.2/plug-ins/chartthrob-plugin
   ```

3. Make sure the script is executable: `chmod +x plugin/chartthrob-plugin/chartthrob-plugin.py`
4. Restart GIMP.
5. You should now see:
   - **File → Create → ChartThrob → ChartThrob: Build Chart...** (always
     available, no image needs to be open)
   - **Colors → ChartThrob → ChartThrob: Analyze Scan...** (enabled once
     you have a scanned chart open)

## Development

Pure-logic layer (`chartthrob/geometry.py`, `chartthrob/curve_math.py`) has
no GIMP dependency and is tested with plain `pytest`:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

GIMP-dependent code (`chart_builder.py`, `chart_analyzer.py`, the plugin
itself) is verified by running scripts inside a real headless GIMP process:

```sh
scripts/run_gimp_batch.sh tests/integration/manual_full_roundtrip.py
```

See `docs/PLAN.md` for the full project outline, phase-by-phase status,
and every discovery/workaround found along the way, and
`docs/API_MAPPING.md` for a function-by-function audit of the original
`ChartThrob.jsx` against this port — every original function is accounted
for, and every intentional behavior deviation is called out explicitly.

## Differences from the original

The short version: same math, same two workflows, native GIMP calls
instead of Photoshop's scripting workarounds, no telemetry. See
`CHANGELOG.md` for the full list and `docs/API_MAPPING.md` for exactly
which original function maps to which port function and why.

## Licensing note

The original `ChartThrob.jsx` states: *"Script (C)2006-2010 Kevin Bjorke.
Free for use and re-use"* but also *"PLEASE DON'T DISTRIBUTE ALTERED
COPIES. I WILL ONLY PROVIDE SUPPORT FOR COPIES THAT WERE DISTRIBUTED BY MY
OWN WEB SITE."* That's informal permission language, not a standard
open-source license, and a full rewrite for a different platform sits in
real tension with "don't distribute altered copies" even though none of
this port's files are literally the original's altered source. This
project has not assigned itself a license, and doesn't include one. If you
plan to publish or redistribute this beyond personal/local use, that's
worth resolving deliberately — e.g. by reaching out to the original author
— rather than assuming either "free for use and re-use" or an implied
open-source license covers a full independent reimplementation.
