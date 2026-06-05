from __future__ import annotations

from typing import Dict, List, Optional

from aidwm.config import Config, ZoneConfig
from aidwm.events import Geometry, WindowInfo
from aidwm.planner.base import Planner
from aidwm.zones import ZoneGrid, ZoneSpec, parse_zone


class ZonePlanner(Planner):
    """Zone-grid layout planner.

    Active window → main zone (e.g. b2:c2).
    Remaining non-fixed windows → secondary zones in config order.
    Windows with explicit zone rules are skipped here; the engine applies
    those overrides after plan() returns.

    Layout (default config, 4×2 grid):
        a1  │  b1  │  c1+d1
        ────┼──────┼────────
        a2  │ b2+c2│  d2
                ↑ active
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

        zc = config.zones
        grid = ZoneGrid(
            columns=zc.columns,
            rows=zc.rows,
            padding=config.layout.padding,
            gap=config.layout.gap,
        )
        main_spec = parse_zone(zc.main)
        secondary_specs = [parse_zone(s) for s in zc.secondary]

        # Partition windows: active first, then the rest
        active = next((w for w in windows if w.id == active_id), None)
        others = [w for w in windows if w.id != (active.id if active else None)]

        result: Dict[int, Geometry] = {}

        if active:
            result[active.id] = grid.geometry(main_spec, screen)

        # Distribute remaining windows across secondary zones in order.
        # If there are more windows than secondary zones, extras stack into
        # the last zone (they will overlap — a signal to the user that the
        # screen is over-full).
        for i, win in enumerate(others):
            spec = secondary_specs[min(i, len(secondary_specs) - 1)]
            result[win.id] = grid.geometry(spec, screen)

        return result
