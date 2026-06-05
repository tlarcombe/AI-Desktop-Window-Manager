from __future__ import annotations

import re
from typing import Dict, Optional

from aidwm.config import Config, WindowRule
from aidwm.events import Geometry, WindowInfo


class WindowRegistry:
    def __init__(self) -> None:
        self._windows: Dict[int, WindowInfo] = {}
        self._focused_id: Optional[int] = None

    # --- mutations -----------------------------------------------------------

    def add_or_update(self, info: WindowInfo) -> None:
        self._windows[info.id] = info

    def remove(self, window_id: int) -> None:
        self._windows.pop(window_id, None)
        if self._focused_id == window_id:
            self._focused_id = None

    def set_focused(self, window_id: int) -> None:
        if prev := self._focused_id:
            if prev in self._windows:
                self._windows[prev].is_focused = False
        self._focused_id = window_id
        if window_id in self._windows:
            self._windows[window_id].is_focused = True

    def update_geometry(self, window_id: int, geometry: Geometry) -> None:
        if window_id in self._windows:
            self._windows[window_id].geometry = geometry

    def update_workspace(self, window_id: int, workspace: int) -> None:
        if window_id in self._windows:
            self._windows[window_id].workspace = workspace

    # --- queries -------------------------------------------------------------

    def get(self, window_id: int) -> Optional[WindowInfo]:
        return self._windows.get(window_id)

    def focused_id(self) -> Optional[int]:
        return self._focused_id

    def windows_on_workspace(self, workspace: int) -> list[WindowInfo]:
        return [w for w in self._windows.values() if w.workspace == workspace]

    def all_windows(self) -> list[WindowInfo]:
        return list(self._windows.values())

    # --- rule matching -------------------------------------------------------

    def fixed_position_for(self, info: WindowInfo, config: Config) -> Optional[Geometry]:
        """Return the fixed geometry for a window if a rule applies, else None."""
        for rule in config.rules:
            if _matches(info, rule):
                return rule.fixed_position
        return None

    def __len__(self) -> int:
        return len(self._windows)


def _matches(info: WindowInfo, rule: WindowRule) -> bool:
    return (
        re.search(rule.class_pattern, info.wm_class, re.IGNORECASE) is not None
        and re.search(rule.title_pattern, info.title, re.IGNORECASE) is not None
    )
