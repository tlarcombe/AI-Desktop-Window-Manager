from __future__ import annotations

import logging
import threading

from aidwm.backends.base import Backend
from aidwm.config import Config
from aidwm.events import EventType, FocusHint, Geometry, WindowEvent, WindowInfo
from aidwm.planner.base import Planner
from aidwm.registry import WindowRegistry
from aidwm.zones import ZoneGrid, parse_zone

log = logging.getLogger(__name__)

_FOCUS_HINT_THRESHOLD = 0.75
# geometry delta below this is treated as engine rounding, not a user drag
_DRAG_TOLERANCE_PX = 30


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

    Pinning:
        When a MOVED/RESIZED event arrives with geometry that differs from what
        the engine last set by more than _DRAG_TOLERANCE_PX, the window is
        added to _pinned and excluded from all future layouts.  Pinned windows
        keep whatever position the user dragged them to.

    New-window placement:
        On OPENED, if no window currently has focus the new window is
        immediately treated as focused so the next layout places it in the main
        zone.  If a focused window already exists the new window will receive
        focus from the WM within milliseconds, which triggers a FOCUSED event
        and the normal layout cycle.
    """

    def __init__(self, backend: Backend, planner: Planner, config: Config) -> None:
        self._backend = backend
        self._planner = planner
        self._config = config
        self._registry = WindowRegistry()
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._pinned: set[int] = set()
        self._expected_geometries: dict[int, Geometry] = {}

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

    def pinned_ids(self) -> set[int]:
        with self._lock:
            return set(self._pinned)

    def unpin(self, window_id: int) -> None:
        with self._lock:
            self._pinned.discard(window_id)
        self._schedule_layout()

    # --- event handlers ------------------------------------------------------

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
        log.debug(
            "Focus hint from %s → window %d (%.2f)", hint.source, hint.window_id, hint.confidence
        )
        with self._lock:
            self._registry.set_focused(hint.window_id)
        self._schedule_layout()

    # --- internal ------------------------------------------------------------

    def _apply_event(self, event: WindowEvent) -> None:
        match event.type:
            case EventType.OPENED:
                if (
                    event.title is not None
                    and event.wm_class is not None
                    and event.geometry is not None
                ):
                    self._registry.add_or_update(WindowInfo(
                        id=event.window_id,
                        title=event.title,
                        wm_class=event.wm_class,
                        workspace=event.workspace or 0,
                        geometry=event.geometry,
                    ))
                    # If nothing is focused yet, treat this window as active so
                    # the layout places it in the main zone immediately.
                    if self._registry.focused_id() is None:
                        self._registry.set_focused(event.window_id)

            case EventType.CLOSED:
                self._registry.remove(event.window_id)
                self._pinned.discard(event.window_id)
                self._expected_geometries.pop(event.window_id, None)

            case EventType.FOCUSED:
                self._registry.set_focused(event.window_id)

            case EventType.MOVED | EventType.RESIZED:
                if event.geometry:
                    self._registry.update_geometry(event.window_id, event.geometry)
                    self._maybe_pin(event.window_id, event.geometry)

            case EventType.WORKSPACE_CHANGED:
                if event.workspace is not None:
                    self._registry.update_workspace(event.window_id, event.workspace)

    def _maybe_pin(self, window_id: int, actual: Geometry) -> None:
        expected = self._expected_geometries.get(window_id)
        if expected is None:
            # We never moved this window — any geometry change is user-initiated.
            self._pin(window_id)
            return
        if _geometry_delta(actual, expected) > _DRAG_TOLERANCE_PX:
            self._pin(window_id)

    def _pin(self, window_id: int) -> None:
        if window_id not in self._pinned:
            log.info("Pinning window %d (user-moved)", window_id)
            self._pinned.add(window_id)

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
            all_windows = self._registry.windows_on_workspace(workspace)
            active_id = self._registry.focused_id()
            config = self._config
            pinned = set(self._pinned)

        # Exclude pinned windows — they stay wherever the user put them.
        windows = [w for w in all_windows if w.id not in pinned]

        if not windows:
            return

        zc = config.zones
        grid = ZoneGrid(columns=zc.columns, rows=zc.rows,
                        padding=config.layout.padding, gap=config.layout.gap)

        geometries = self._planner.plan(windows, active_id, screen, config)

        # Rule overrides (fixed_position > zone > planner output)
        with self._lock:
            for win in windows:
                rule = self._registry.matching_rule(win, config, workspace)
                if rule is None:
                    continue
                if rule.fixed_position:
                    geometries[win.id] = rule.fixed_position
                elif rule.zone:
                    geometries[win.id] = grid.geometry(parse_zone(rule.zone), screen)

        # Apply and record expected geometries so we can detect future user drags.
        with self._lock:
            for window_id, geo in geometries.items():
                self._expected_geometries[window_id] = geo

        for window_id, geo in geometries.items():
            self._backend.apply_geometry(window_id, geo)
            log.debug("→ win %d: %dx%d+%d+%d", window_id, geo.width, geo.height, geo.x, geo.y)


def _geometry_delta(a: Geometry, b: Geometry) -> int:
    """Maximum axis-aligned difference between two geometries."""
    return max(abs(a.x - b.x), abs(a.y - b.y), abs(a.width - b.width), abs(a.height - b.height))
