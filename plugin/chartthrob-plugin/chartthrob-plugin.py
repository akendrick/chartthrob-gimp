#!/usr/bin/env python3
"""ChartThrob GIMP plugin entry point.

Ported from `userDialog()`, `helpDialog()`, `scanResultsReport()`, and
`main()` in the original ChartThrob.jsx. Registers two GIMP menu commands
instead of the original's single adaptive dialog (see docs/API_MAPPING.md
Phase 4 for why that split is more GIMP-idiomatic, not a shortcut):

  - "Build Chart...": a plain `Gimp.Procedure` (no image required), always
    available -- ports the `buildChart()` half of `userDialog()`.
  - "Analyze Scan...": a `Gimp.ImageProcedure` (requires an active image/
    drawable, greyed out otherwise by GIMP's own menu sensitivity --
    replacing the original's manual `app.documents.length<1` check) --
    ports the `scanChart()` half.

Install: symlink (not copy) this *directory* into GIMP's plug-ins folder,
e.g. on macOS:
    ln -s /path/to/ChartThrob-GIMP/plugin/chartthrob-plugin \
          ~/Library/Application\\ Support/GIMP/3.0/plug-ins/chartthrob-plugin
This file must stay executable (`chmod +x`) and its containing directory
name must match its own basename -- both are GIMP 3 plugin-discovery
requirements, not stylistic choices.
"""
import os
import sys

_PLUGIN_DIR = os.path.dirname(os.path.realpath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_PLUGIN_DIR, "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import gi

gi.require_version("Gimp", "3.0")
from gi.repository import Gimp, GLib, GObject  # noqa: E402

from chartthrob import chart_analyzer as ca  # noqa: E402
from chartthrob import chart_builder as cb  # noqa: E402
from chartthrob import geometry as geo  # noqa: E402


def N_(message):
    return message


def _(message):
    return GLib.dgettext(None, message)


BUILD_PROC_NAME = "python-fu-chartthrob-build"
ANALYZE_PROC_NAME = "python-fu-chartthrob-analyze"

# Mirrors helpDialog()'s step list -- used as the long-form documentation
# ("blurb") for both procedures rather than a separate custom Help dialog
# window, relying on GIMP's own procedure-documentation UI instead
# (Procedure Browser / dialog description) since that gap only existed in
# the original because Photoshop's ScriptUI dialogs have no such built-in
# display.
HELP_TEXT = _(
    "ChartThrob is a tool for digital-negative contact printing "
    "(platinum/palladium, cyanotype, silver, bromoil, etc).\n\n"
    "Normally you run it TWICE:\n"
    "1. Build Chart: create a new, positive calibration chart.\n"
    "2. Print the chart to a digital negative, contact-print it with your "
    "process, scan the resulting positive, and crop the scan to the "
    "chart's original bounds.\n"
    "3. Analyze Scan: open the cropped scan and run this on it. It adds a "
    "hidden 'Print Curve' filter to the image.\n"
    "4. Apply that same curve to any B&W image before printing digital "
    "negatives from it -- their tones will be remapped to the range your "
    "process can actually reproduce.\n\n"
    "For repeatable results, your printing process itself must be "
    "repeatable: same paper, same exposure/processing steps, uniform "
    "across the whole print."
)


def _report_message(result: ca.ScanResult) -> str:
    """Ports the analysis summary from `scanResultsReport()`, including its
    shoulder/toe exposure suggestion, as plain text for `Gimp.message()`
    rather than a custom dialog window."""
    lines = [
        "ChartThrob scan analysis complete.",
        f"See the hidden \"{result.curve_name}\" filter in the layer's effects "
        "-- reuse it on other B&W images before printing digital negatives.",
        f"Lightest scan value was at sample {result.dynamic_range.max_index}",
        f"Darkest scan value was at sample {result.dynamic_range.min_index}",
    ]
    if result.dark_paper_warning:
        lines.append(
            "Warning: the paper-tone patch read unusually dark -- did you "
            "accidentally scan a negative image of the chart?"
        )
    if result.negated:
        lines.append("The curve was negated (inverted), as requested.")

    shoulder = result.dynamic_range.max_index
    toe = 101 - result.dynamic_range.min_index
    if toe > shoulder * 1.5 and toe > 5:
        lines.append(
            "Suggestion: while this curve is valid, you may want to reprint "
            "this chart with a decreased exposure time, then re-scan and "
            "re-analyze."
        )
    elif shoulder > toe * 1.5 and shoulder > 5:
        lines.append(
            "Suggestion: while this curve is valid, you may want to reprint "
            "this chart with an increased exposure time, then re-scan and "
            "re-analyze."
        )
    return "\n".join(lines)


def build_chart_run(procedure, config, data):
    run_mode = config.get_property("run-mode")

    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version("GimpUi", "3.0")
        from gi.repository import GimpUi

        GimpUi.init(BUILD_PROC_NAME)
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(["dpi", "numbers", "outlines", "label"])
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    dpi = config.get_property("dpi")
    numbers = config.get_property("numbers")
    outlines = config.get_property("outlines")
    label = config.get_property("label")

    layout = geo.ChartLayout.from_dpi(dpi)
    options = cb.ChartOptions(numbers=numbers, outlines=outlines)
    image = cb.build_chart(label, layout, options)

    # Best-effort: there's no display server to attach a window to when
    # this runs headlessly (e.g. driven straight through the PDB in a
    # batch/automation context, as opposed to GIMP's normal interactive
    # GUI) -- confirmed against real GIMP that Gimp.Display.new() raises
    # there rather than silently no-oping. The image itself is still
    # created and valid either way, so this shouldn't fail the whole
    # procedure over a display that was never going to exist.
    try:
        Gimp.Display.new(image)
        Gimp.displays_flush()
    except TypeError:
        pass

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


def analyze_scan_run(procedure, run_mode, image, drawables, config, data):
    if not drawables:
        return procedure.new_return_values(
            Gimp.PDBStatusType.CALLING_ERROR,
            GLib.Error("No active drawable to analyze."),
        )

    if run_mode == Gimp.RunMode.INTERACTIVE:
        gi.require_version("GimpUi", "3.0")
        from gi.repository import GimpUi

        GimpUi.init(ANALYZE_PROC_NAME)
        dialog = GimpUi.ProcedureDialog(procedure=procedure, config=config)
        dialog.fill(["show-samples", "negate"])
        if not dialog.run():
            dialog.destroy()
            return procedure.new_return_values(Gimp.PDBStatusType.CANCEL, GLib.Error())
        dialog.destroy()

    show_samples = config.get_property("show-samples")
    negate = config.get_property("negate")
    options = ca.ScanOptions(show_samples=show_samples, negate=negate)

    try:
        result = ca.analyze_chart(image, options)
    except ca.ChartAnalysisError as exc:
        Gimp.message(str(exc))
        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR, GLib.Error(str(exc)))

    Gimp.displays_flush()
    Gimp.message(_report_message(result))

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


class ChartThrobPlugIn(Gimp.PlugIn):
    def do_set_i18n(self, procname):
        return True, "gimp30-python", None

    def do_query_procedures(self):
        return [BUILD_PROC_NAME, ANALYZE_PROC_NAME]

    def do_create_procedure(self, name):
        if name == BUILD_PROC_NAME:
            procedure = Gimp.Procedure.new(
                self, name, Gimp.PDBProcType.PLUGIN, build_chart_run, None
            )
            procedure.set_documentation(
                _("Build a ChartThrob calibration chart"), HELP_TEXT, name
            )
            procedure.set_menu_label(_("ChartThrob: Build Chart..."))
            procedure.set_attribution(
                "Kevin Bjorke (original); GIMP port", "Free for use and re-use", "2026"
            )
            procedure.add_menu_path("<Image>/File/Create/ChartThrob")

            procedure.add_enum_argument(
                "run-mode", _("Run mode"), _("The run mode"),
                Gimp.RunMode, Gimp.RunMode.NONINTERACTIVE, GObject.ParamFlags.READWRITE,
            )
            procedure.add_double_argument(
                "dpi", _("_DPI"), _("Resolution for the new chart (72-2400)"),
                72.0, 2400.0, 300.0, GObject.ParamFlags.READWRITE,
            )
            procedure.add_boolean_argument(
                "numbers", _("_Numbers"),
                _("Label patch values (slows generation considerably)"),
                False, GObject.ParamFlags.READWRITE,
            )
            procedure.add_boolean_argument(
                "outlines", _("_Outlines"), _("Draw patch border/grid lines"),
                True, GObject.ParamFlags.READWRITE,
            )
            procedure.add_string_argument(
                "label", _("_Label"), _("Label printed on the chart"),
                cb.CHART_TITLE, GObject.ParamFlags.READWRITE,
            )
            return procedure

        if name == ANALYZE_PROC_NAME:
            procedure = Gimp.ImageProcedure.new(
                self, name, Gimp.PDBProcType.PLUGIN, analyze_scan_run, None
            )
            procedure.set_image_types("RGB*, GRAY*, INDEXED*")
            procedure.set_sensitivity_mask(
                Gimp.ProcedureSensitivityMask.DRAWABLE
                | Gimp.ProcedureSensitivityMask.DRAWABLES
            )
            procedure.set_documentation(
                _("Analyze a scanned ChartThrob chart"), HELP_TEXT, name
            )
            procedure.set_menu_label(_("ChartThrob: Analyze Scan..."))
            procedure.set_attribution(
                "Kevin Bjorke (original); GIMP port", "Free for use and re-use", "2026"
            )
            procedure.add_menu_path("<Image>/Colors/ChartThrob")

            procedure.add_boolean_argument(
                "show-samples", _("_Outline Sample Areas"),
                _("Keep the averaged sample regions outlined for inspection"),
                False, GObject.ParamFlags.READWRITE,
            )
            procedure.add_boolean_argument(
                "negate", _("_Negate Output Curve"),
                _("Invert the final curve (e.g. for use with QuadToneRIP)"),
                False, GObject.ParamFlags.READWRITE,
            )
            return procedure

        return None


if __name__ == "__main__":
    # Guarded rather than a bare module-level call: GIMP always invokes this
    # file directly (`python3 chartthrob-plugin.py <wire-protocol args>`), so
    # __name__ == "__main__" there and this runs exactly as before for real
    # usage. The guard only matters for *importing* this module -- e.g. from
    # a test harness -- without also kicking off Gimp.main()'s blocking
    # wire-protocol handshake, which hangs forever given argv that isn't a
    # real GIMP-supplied plugin invocation.
    Gimp.main(ChartThrobPlugIn.__gtype__, sys.argv)
