# ChartThrob for GIMP (unofficial port)

[![tests](https://github.com/akendrick/chartthrob-gimp/actions/workflows/tests.yml/badge.svg)](https://github.com/akendrick/chartthrob-gimp/actions/workflows/tests.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A GIMP 3 plugin for calibrating **digital-negative contact printing** —
platinum/palladium, cyanotype, silver, bromoil and other alternative
processes. It is a port of [ChartThrob](https://github.com/joker-b/ChartThrob),
Kevin Bjorke's Photoshop script (original chart design by Thomas Howard).

> **Unofficial.** This is an independent reimplementation, not affiliated
> with or endorsed by the original author. See the
> [licensing note](#licensing-note).

## What it does

1. **Build Chart** — generates a printable grayscale calibration chart
   (a 10×10 patch grid, an extra black patch, a 21-step strip and a
   gradient bar).
2. You print that chart as a digital negative, contact-print it with *your*
   process, scan or photograph the resulting positive, and crop it to the
   chart.
3. **Analyze Scan** — measures every patch on your print and produces a
   **tone-correction curve** for your process. Apply that curve to your
   black-and-white images before printing negatives from them, and their
   tones are remapped to the range your process can actually reproduce.

## Requirements

- **GIMP 3.0 or newer.** Developed and tested on **GIMP 3.2.4 on macOS**.
  Nothing else is needed — the plugin uses GIMP's own bundled Python.
- Linux and Windows should work (nothing in the code is OS-specific) but
  have **not been tested**; see the notes in [Installation](#installation).

## Installation

GIMP 3 finds a Python plugin only if it lives in **its own folder**, the
folder is named **exactly like the `.py` file inside it**
(`chartthrob-plugin/chartthrob-plugin.py`), and the file is **executable**.
The release download already has this layout.

### Option A — install script (macOS and Linux)

1. Download `chartthrob-gimp-<version>.zip` from the
   [latest release](https://github.com/akendrick/chartthrob-gimp/releases/latest)
   and unzip it.
2. In a terminal, from the unzipped folder:

   ```sh
   ./scripts/install.sh
   ```

   The script assumes GIMP profile version `3.0`. If you run GIMP 3.2, say so:

   ```sh
   ./scripts/install.sh --gimp-version 3.2
   ```

3. **Restart GIMP.**

To remove it later: `./scripts/install.sh --uninstall` (same
`--gimp-version` if you used one).

### Option B — by hand

1. Find your GIMP plug-ins folder. In GIMP: **Edit → Preferences → Folders
   → Plug-Ins** lists the exact paths; use the one inside your user profile.
   Typical locations (replace `3.x` with your version, e.g. `3.2`):

   | OS | Plug-ins folder |
   |---|---|
   | macOS | `~/Library/Application Support/GIMP/3.x/plug-ins/` |
   | Linux | `~/.config/GIMP/3.x/plug-ins/` |
   | Linux (Flatpak) | `~/.var/app/org.gimp.GIMP/config/GIMP/3.x/plug-ins/` |
   | Windows | `%APPDATA%\GIMP\3.x\plug-ins\` |

   (Flatpak and Windows paths are the standard GIMP locations but haven't
   been verified with this plugin — trust the Preferences dialog over this
   table.)

2. Copy the whole **`chartthrob-plugin`** folder from the download into it.
   The folder must contain `chartthrob-plugin.py` and a `chartthrob/`
   subfolder — don't copy the `.py` file on its own.
3. On macOS/Linux, make sure the script is executable:

   ```sh
   chmod +x ".../plug-ins/chartthrob-plugin/chartthrob-plugin.py"
   ```

4. **Restart GIMP.**

### Check that it worked

You should now have two new menu entries:

- **File → Create → ChartThrob → ChartThrob: Build Chart...**
  (always available)
- **Colors → ChartThrob → ChartThrob: Analyze Scan...**
  (greyed out until an image is open)

If they don't appear, see [Troubleshooting](#troubleshooting).

## Using it

### 1. Build a chart

**File → Create → ChartThrob → Build Chart...**

| Option | Meaning |
|---|---|
| **DPI** | Resolution of the new chart (72–2400, default 300). The printed size is the same at any DPI; higher DPI just means more pixels. |
| **Numbers** | Label each patch with its value. Slower to generate. |
| **Outlines** | Draw the patch grid lines (on by default). |
| **Add Padding** / **Padding Size (px)** | Adds a solid white border of the given pixel width (default 40) around the whole chart. When you invert the chart to make a negative, that border stays fully unexposed, giving you a firm margin to isolate the print from its support. Off by default; the size field is only active when the checkbox is on. |
| **Label** | Title printed above the grid. |

The chart is a **positive** (dark patches on white). Invert it, or let your
print driver do it, depending on how you make your negatives.

### 2. Print, expose, scan

Print the negative, contact-print it with your process, and let it dry.
Then scan it — ideally a flatbed scan with **gamma 1.0**, full range
(don't let the scanner auto-level) — or take a flat, evenly-lit,
glare-free photo of it. **Crop tightly to the chart's patch grid** (no
table or background around the edges) and keep it at least ~600 px wide.

Use one consistent process every time: same paper, exposure and
development, and an evenly exposed print. Nothing can correct for an
uneven exposure across the chart.

### 3. Analyze the scan

Open the cropped scan, then **Colors → ChartThrob → Analyze Scan...**

| Option | Meaning |
|---|---|
| **Outline Sample Areas** | Opens a copy of the scan with the sampled areas outlined in red, so you can check they landed on the patches. |
| **Negate Output Curve** | Invert the resulting curve (e.g. for use with QuadToneRIP). |
| **Export Curve File** | Optional. Also saves the curve as a `.curves` file (see below). Leave empty to skip. |

When it finishes you get a report (where the lightest/darkest patches
were found, plus a suggestion if your exposure looks off). The correction
curve is attached to the scan's layer as a **hidden filter named
"Print Curve"** (or "Negative Curve"). It's hidden on purpose: it's
meant to be reused on *other* images, not to change the scan itself.
You'll find it in that layer's filter list in the Layers dialog (the
*fx* icon); toggle its eye to preview it, or double-click it to open it in
the Curves editor.

### 4. Reuse the curve on other images

A hidden filter belongs to the one layer it was created on. To use the
curve elsewhere — including after you've closed GIMP — use **Export Curve
File**: it writes a standard GIMP curves file that you load on any image
via **Colors → Curves**, using the import/export button next to the
**Presets** field.

Check your result: apply the curve to the original chart, print again, and
you should get a full, even range of grays.

## Troubleshooting

**The menu entries don't appear.**
- Restart GIMP after installing.
- Make sure the folder is named `chartthrob-plugin`, contains
  `chartthrob-plugin.py` *and* the `chartthrob/` folder, and that the
  script is executable (`chmod +x`).
- Confirm you used the plug-ins folder of the GIMP *version* you're
  running (Edit → Preferences → Folders → Plug-Ins shows it).
- You need GIMP **3.x**; this will not load in GIMP 2.10.

**"Not enough samples had valid values to estimate a curve."**
The message now says which cause applies:
- *Tonal range read back nearly flat* — the crop probably includes
  background outside the chart, the print has very little contrast, or the
  scan went through an auto-levels step.
- *Paper-tone patch read unusually dark* — the scan may be inverted (a
  negative), or the crop's top-left corner isn't the chart's lightest
  patch.
- Otherwise, check the crop matches the chart's proportions and
  orientation (10 columns × 11 rows of patches).

Analyze Scan measures ChartThrob's **own** chart layout. Pointing it at any
other image (a photo, a different step wedge) gives meaningless results.

**A patch or two looks slightly off after applying the curve.** The curve
is fit through 14 points (the original tool's own limit), so the smooth
curve can wobble a little between them; your eye also exaggerates edges
between adjacent flat patches. A subtle 1–2 level difference is expected.

**One bad patch skewed the whole curve.** A dust speck or clipped patch can
distort a large part of the curve *without* any error — that is inherent
to the original algorithm. Rescan or clean the print and analyze again.

## Development

The math (`chartthrob/geometry.py`, `chartthrob/curve_math.py`) has no GIMP
dependency and is tested with plain `pytest`:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

Everything that talks to GIMP is verified by running scripts inside a real
headless GIMP:

```sh
scripts/run_gimp_batch.sh tests/integration/manual_full_roundtrip.py
# or all of them:
scripts/run_integration.sh
```

The scripts use `gimp-console` when available; on recent macOS the regular
`GIMP` binary crashes in `-i` mode ("Can't create a GtkStyleContext without a
display connection").

For working on the plugin itself, install it as a symlink so edits apply
immediately: `scripts/install.sh --link` (then restart GIMP).

To build a release zip: `scripts/build_release.sh` → `dist/`.

`docs/PLAN.md` has the project plan, what was found along the way and the
workarounds; `docs/API_MAPPING.md` maps every function in the original
`ChartThrob.jsx` to this port and calls out every deliberate difference.
`CHANGELOG.md` lists what changed between versions.

## Differences from the original

Same math and the same two workflows. Native GIMP calls replace
Photoshop's scripting workarounds, there is **no telemetry** (the plugin
makes no network requests), and there are two additions: chart padding and
curve-file export. See `CHANGELOG.md`.

## Credits

ChartThrob © 2006–2019 Kevin Bjorke —
<https://github.com/joker-b/ChartThrob>. Original grayscale chart design by
Thomas Howard — <http://LuminaryArts.com/>. The chart this plugin
generates carries those credits, as the original does.

## Licensing note

The code in this repository is a new implementation written for GIMP and
is released under the [MIT License](LICENSE). It contains none of the
original script's source code.

ChartThrob itself, its name, its method and the chart design belong to
their authors (see [Credits](#credits)). The original `ChartThrob.jsx`
says *"Script (C)2006-2010 Kevin Bjorke. Free for use and re-use"* and
also *"PLEASE DON'T DISTRIBUTE ALTERED COPIES."* This project is an
independent reimplementation for another platform, not an altered copy of
that script, and it is not endorsed by Kevin Bjorke. If you are the
original author and would like anything changed or credited differently,
please open an issue.

## License

The GIMP port is [MIT](LICENSE) © 2026 akendrick; see the
[licensing note](#licensing-note) for the original's terms. Issues and pull
requests are welcome at <https://github.com/akendrick/chartthrob-gimp>.
