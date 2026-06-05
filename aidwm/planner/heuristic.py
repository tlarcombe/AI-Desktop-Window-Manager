from __future__ import annotations

from typing import Dict, List, Optional

from aidwm.config import Config
from aidwm.events import Geometry, WindowInfo
from aidwm.planner.base import Planner


class HeuristicPlanner(Planner):
    """Main-and-stack layout.

    Active window takes the left active_fraction of the screen width at full
    height.  Remaining windows share the right column equally, stacked
    vertically.  When there is no active window, all windows share width
    equally (columns).

    Layout diagram (2 secondary windows):

        ┌──────────────┬───────┐
        │              │  B    │
        │   ACTIVE (A) ├───────┤
        │              │  C    │
        └──────────────┴───────┘
    """

    def plan(
        self,
        windows: List[WindowInfo],
        active_id: Optional[int],
        screen: Geometry,
        config: Config,
    ) -> Dict[int, Geometry]:
        if not windows:
            return {}

        p = config.layout.padding
        g = config.layout.gap
        frac = 0.6      # active window takes 60% of width

        usable_x = screen.x + p
        usable_y = screen.y + p
        usable_w = screen.width - 2 * p
        usable_h = screen.height - 2 * p

        active = _find(windows, active_id)
        others = [w for w in windows if w.id != (active.id if active else None)]

        if active is None or not others:
            return _tile_columns(windows, usable_x, usable_y, usable_w, usable_h, g)

        main_w = int(usable_w * frac) - (g // 2)
        side_x = usable_x + main_w + g
        side_w = usable_w - main_w - g

        result: Dict[int, Geometry] = {
            active.id: Geometry(x=usable_x, y=usable_y, width=main_w, height=usable_h),
        }
        result.update(_tile_stack(others, side_x, usable_y, side_w, usable_h, g))
        return result


def _find(windows: List[WindowInfo], window_id: Optional[int]) -> Optional[WindowInfo]:
    if window_id is None:
        return None
    return next((w for w in windows if w.id == window_id), None)


def _tile_columns(
    windows: List[WindowInfo],
    x: int, y: int, w: int, h: int, gap: int,
) -> Dict[int, Geometry]:
    n = len(windows)
    col_w = (w - gap * (n - 1)) // n
    result: Dict[int, Geometry] = {}
    for i, win in enumerate(windows):
        result[win.id] = Geometry(x=x + i * (col_w + gap), y=y, width=col_w, height=h)
    return result


def _tile_stack(
    windows: List[WindowInfo],
    x: int, y: int, w: int, h: int, gap: int,
) -> Dict[int, Geometry]:
    n = len(windows)
    row_h = (h - gap * (n - 1)) // n
    result: Dict[int, Geometry] = {}
    for i, win in enumerate(windows):
        result[win.id] = Geometry(x=x, y=y + i * (row_h + gap), width=w, height=row_h)
    return result
