"""Small numeric helpers shared by the pure-logic modules.

ChartThrob.jsx consistently rounds with ``Math.floor(0.5 + x)`` (round-half-up).
Python's builtin ``round()`` uses round-half-to-even, so swapping it in would
silently diverge from the original on exact .5 boundaries.
"""
from __future__ import annotations

import math


def round_half_up(value: float) -> int:
    return math.floor(0.5 + value)
