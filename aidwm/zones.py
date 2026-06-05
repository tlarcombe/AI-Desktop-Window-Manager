from __future__ import annotations

import re
from dataclasses import dataclass

from aidwm.events import Geometry

_COL_NAMES = "abcdefghijklmnopqrstuvwxyz"


@dataclass(frozen=True)
class ZoneSpec:
    col_start: int
    col_end: int    # inclusive
    row_start: int
    row_end: int    # inclusive

    def __str__(self) -> str:
        cs = _COL_NAMES[self.col_start]
        ce = _COL_NAMES[self.col_end]
        rs = self.row_start + 1
        re_ = self.row_end + 1
        if cs == ce and rs == re_:
            return f"{cs}{rs}"
        return f"{cs}{rs}:{ce}{re_}"


def parse_zone(spec: str) -> ZoneSpec:
    """Parse "b2" or "b2:c2" into a ZoneSpec (columns a-z, rows 1-n)."""
    parts = spec.strip().split(":")
    if len(parts) == 1:
        c, r = _parse_cell(parts[0])
        return ZoneSpec(c, c, r, r)
    c1, r1 = _parse_cell(parts[0])
    c2, r2 = _parse_cell(parts[1])
    return ZoneSpec(min(c1, c2), max(c1, c2), min(r1, r2), max(r1, r2))


def _parse_cell(s: str) -> tuple[int, int]:
    m = re.match(r"^([a-z]+)(\d+)$", s.strip(), re.IGNORECASE)
    if not m:
        raise ValueError(f"Invalid zone cell: {s!r}  (expected e.g. 'b2')")
    col_idx = _COL_NAMES.index(m.group(1).lower())
    row_idx = int(m.group(2)) - 1      # user uses 1-based rows
    return col_idx, row_idx


class ZoneGrid:
    """Converts a fraction-based column/row grid into pixel geometries.

    columns and rows are lists of fractions that must sum to 1.0.
    Example: columns=[0.25,0.25,0.25,0.25], rows=[0.5,0.5]
    """

    def __init__(
        self,
        columns: list[float],
        rows: list[float],
        padding: int = 8,
        gap: int = 8,
    ) -> None:
        self.columns = columns
        self.rows = rows
        self.padding = padding
        self.gap = gap

    def geometry(self, spec: ZoneSpec, screen: Geometry) -> Geometry:
        """Return the pixel Geometry for a ZoneSpec relative to screen."""
        p = self.padding
        g = self.gap
        nc = len(self.columns)
        nr = len(self.rows)

        # Net usable area after outer padding and all inter-zone gaps
        net_w = screen.width - 2 * p - (nc - 1) * g
        net_h = screen.height - 2 * p - (nr - 1) * g

        # Pixel boundaries for each column/row (left/top edge, then right/bottom edge)
        col_px = _boundaries(self.columns, net_w, p + screen.x, g)
        row_px = _boundaries(self.rows, net_h, p + screen.y, g)

        x0 = col_px[spec.col_start]
        x1 = col_px[spec.col_end + 1]
        y0 = row_px[spec.row_start]
        y1 = row_px[spec.row_end + 1]

        return Geometry(x=x0, y=y0, width=x1 - x0, height=y1 - y0)

    def all_zone_specs(self) -> list[ZoneSpec]:
        """Return every single-cell ZoneSpec in the grid."""
        return [
            ZoneSpec(c, c, r, r)
            for r in range(len(self.rows))
            for c in range(len(self.columns))
        ]


def _boundaries(fractions: list[float], net_px: int, origin: int, gap: int) -> list[int]:
    """Return the pixel start of each slot, plus a final sentinel (right/bottom edge)."""
    result = [origin]
    acc = 0.0
    for i, f in enumerate(fractions):
        acc += f
        edge = origin + round(acc * net_px) + i * gap
        result.append(edge)
    return result
