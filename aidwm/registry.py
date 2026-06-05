from __future__ import annotations

import re

from aidwm.config import Config, WindowRule
from aidwm.events import Geometry, WindowInfo


class WindowRegistry:
    def __init__(self) -> None:
        self._windows: dict[int, WindowInfo] = {}
        self._focused_id: int | None = None

    # --- mutations -----------------------------------------------------------

    def add_or_update(self, info: WindowInfo) -> None:
        self._windows[info.id] = info

    def remove(self, window_id: int) -> None:
        self._windows.pop(window_id, None)
        if self._focused_id == window_id:
            self._focused_id = None

    def set_focused(self, window_id: int) -> None:
        if (prev := self._focused_id) and prev in self._windows:
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

    def get(self, window_id: int) -> WindowInfo | None:
        return self._windows.get(window_id)

    def focused_id(self) -> int | None:
        return self._focused_id

    def windows_on_workspace(self, workspace: int) -> list[WindowInfo]:
        return [w for w in self._windows.values() if w.workspace == workspace]

    def all_windows(self) -> list[WindowInfo]:
        return list(self._windows.values())

    # --- rule matching -------------------------------------------------------

    def matching_rule(
        self, info: WindowInfo, config: Config, current_workspace: int
    ) -> WindowRule | None:
        """Return the first rule that matches this window on the current workspace."""
        for rule in config.rules:
            if not _matches_pattern(info, rule):
                continue
            # workspace-restricted rules only apply on that workspace
            if rule.workspace is not None and rule.workspace != current_workspace:
                continue
            if rule.zone or rule.fixed_position:
                return rule
        return None

    # kept for backward-compat with existing tests
    def fixed_position_for(self, info: WindowInfo, config: Config) -> Geometry | None:
        for rule in config.rules:
            if _matches_pattern(info, rule):
                return rule.fixed_position
        return None

    def __len__(self) -> int:
        return len(self._windows)


def _matches_pattern(info: WindowInfo, rule: WindowRule) -> bool:
    return (
        re.search(rule.class_pattern, info.wm_class, re.IGNORECASE) is not None
        and re.search(rule.title_pattern, info.title, re.IGNORECASE) is not None
    )
