from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from aidwm.config import Config
from aidwm.events import Geometry, WindowInfo


class Planner(ABC):
    """Decides target geometries for a set of windows.

    The engine calls plan() whenever a re-layout is needed. Implementations
    must be fast (target < 150 ms) — fixed-position overrides are applied by
    the engine *after* plan() returns, so planners need not know about them.
    """

    @abstractmethod
    def plan(
        self,
        windows: List[WindowInfo],
        active_id: Optional[int],
        screen: Geometry,
        config: Config,
    ) -> Dict[int, Geometry]:
        """Return a mapping of window_id → target Geometry for all windows."""
