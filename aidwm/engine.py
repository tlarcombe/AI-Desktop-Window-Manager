from __future__ import annotations

import logging
import threading
from typing import Optional

from aidwm.backends.base import Backend
from aidwm.config import Config, WindowRule
from aidwm.events import EventType, FocusHint, Geometry, WindowEvent, WindowInfo
from aidwm.planner.base import Planner
from aidwm.registry import WindowRegistry
from aidwm.zones import ZoneGrid, parse_zone

log = logging.getLogger(__name__)

_FOCUS_HINT_THRESHOLD = 0.75    # confidence required to act on a gaze hint


class LayoutEngine:
    """Ties backend, registry, and planner together.

    Event flow:
        Backend → on_event() → registry mutation → _schedule_layout()
        _schedule_layout() → debounce timer → _apply_layout()
        _apply_layout() → planner.plan() → rule overrides → backend.apply_geometry()

    Rule override priority (highest wins):
        1. fixed_position  (absolute pixel geometry)
        2. zone            (grid-relative geometry, converted at layout time)
        3. planner output

    FocusHint flow (gaze / mouse proximity):
        Source → on_focus_hint() → registry.set_focused() → _schedule_layout()
    """

    def __init__(self, backend: Backend, planner: Planner, config: Config) -> None:
        self._backend = backend
        self._planner = planner
        self._config = config
        self._registry = WindowRegistry()
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

    # --- public API ----------------------------------------------------------

    def run(self) -> None:
        self._backend.start(
            on_event=self.on_event,
            on_focus_hint=self.on_focus_hint,
        )

    def reload_config(self, config: Config) -> None:
        with self._lock:
            self._config = config
        self._schedule_layout()

    # --- event handlers (called from backend thread) -------------------------

    def on_event(self, event: WindowEvent) -> None:
        with self._lock:
            self._apply_event(event)
        if event.type in (
            EventType.OPENED,
            EventType.CLOSED,
            EventType.FOCUSED,
            EventType.WORKSPACE_CHANGED,
        ):
            self._schedule_layout()

    def on_focus_hint(self, hint: FocusHint) -> None:
        if hint.confidence < _FOCUS_HINT_THRESHOLD:
            return
        log.debug("Focus hint from %s → window %d (%.2f)", hint.source, hint.window_id, hint.confidence)
        with self._lock:
            self._registry.set_focused(hint.window_id)
        self._schedule_layout()

    # --- internal ------------------------------------------------------------

    def _apply_event(self, event: WindowEvent) -> None:
        match event.type:
            case EventType.OPENED:
                if event.title is not None and event.wm_class is not None and event.geometry is not None:
                    self._registry.add_or_update(WindowInfo(
                        id=event.window_id,
                        title=event.title,
                        wm_class=event.wm_class,
                        workspace=event.workspace or 0,
                        geometry=event.geometry,
                    ))
            case EventType.CLOSED:
                self._registry.remove(event.window_id)
            case EventType.FOCUSED:
                self._registry.set_focused(event.window_id)
            case EventType.MOVED | EventType.RESIZED:
                if event.geometry:
                    self._registry.update_geometry(event.window_id, event.geometry)
            case EventType.WORKSPACE_CHANGED:
                if event.workspace is not None:
                    self._registry.update_workspace(event.window_id, event.workspace)

    def _schedule_layout(self) -> None:
        delay = self._config.general.layout_delay_ms / 1000.0
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(delay, self._apply_layout)
            self._timer.daemon = True
            self._timer.start()

    def _apply_layout(self) -> None:
        with self._lock:
            workspace = self._backend.get_current_workspace()
            screen = self._backend.get_screen_geometry()
            windows = self._registry.windows_on_workspace(workspace)
            active_id = self._registry.focused_id()
            config = self._config

        if not windows:
            return

        # Build zone grid once per layout pass
        zc = config.zones
        grid = ZoneGrid(columns=zc.columns, rows=zc.rows,
                        padding=config.layout.padding, gap=config.layout.gap)

        geometries = self._planner.plan(windows, active_id, screen, config)

        # Apply rule overrides (fixed_position > zone > planner)
        with self._lock:
            for win in windows:
                rule = self._registry.matching_rule(win, config, workspace)
                if rule is None:
                    continue
                if rule.fixed_position:
                    geometries[win.id] = rule.fixed_position
                elif rule.zone:
                    geometries[win.id] = grid.geometry(parse_zone(rule.zone), screen)

        for window_id, geo in geometries.items():
            self._backend.apply_geometry(window_id, geo)
            log.debug("→ win %d: %dx%d+%d+%d", window_id, geo.width, geo.height, geo.x, geo.y)
