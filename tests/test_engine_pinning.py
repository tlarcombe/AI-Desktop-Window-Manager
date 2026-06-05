"""Tests for drag-detection (pinning) and new-window placement."""
from __future__ import annotations

from collections.abc import Callable

from aidwm.backends.base import Backend
from aidwm.config import Config
from aidwm.engine import LayoutEngine, _geometry_delta
from aidwm.events import EventType, Geometry, WindowEvent
from aidwm.planner.zone import ZonePlanner

_SCREEN = Geometry(0, 0, 1920, 1080)
_GEO = Geometry(0, 0, 100, 100)


class FakeBackend(Backend):
    def __init__(self) -> None:
        self.applied: dict[int, Geometry] = {}
        self.workspace = 0

    def start(self, on_event: Callable, on_focus_hint: Callable) -> None:
        pass

    def stop(self) -> None:
        pass

    def apply_geometry(self, window_id: int, geometry: Geometry) -> None:
        self.applied[window_id] = geometry

    def get_screen_geometry(self) -> Geometry:
        return _SCREEN

    def get_current_workspace(self) -> int:
        return self.workspace


def _make_engine() -> tuple[LayoutEngine, FakeBackend]:
    backend = FakeBackend()
    engine = LayoutEngine(backend, ZonePlanner(), Config())
    return engine, backend


def _opened(wid: int, geo: Geometry = _GEO) -> WindowEvent:
    return WindowEvent(EventType.OPENED, wid, geometry=geo,
                       title=f"win{wid}", wm_class="test.Test", workspace=0)


def _moved(wid: int, geo: Geometry) -> WindowEvent:
    return WindowEvent(EventType.MOVED, wid, geometry=geo)


def _focused(wid: int) -> WindowEvent:
    return WindowEvent(EventType.FOCUSED, wid)


# --- geometry delta helper ---------------------------------------------------

class TestGeometryDelta:
    def test_identical(self):
        g = Geometry(10, 20, 800, 600)
        assert _geometry_delta(g, g) == 0

    def test_x_difference(self):
        a = Geometry(100, 0, 800, 600)
        b = Geometry(0, 0, 800, 600)
        assert _geometry_delta(a, b) == 100

    def test_largest_axis_wins(self):
        a = Geometry(5, 200, 810, 600)
        b = Geometry(0, 0, 800, 600)
        assert _geometry_delta(a, b) == 200


# --- new window placement ----------------------------------------------------

class TestNewWindowPlacement:
    def test_first_window_becomes_focused(self):
        engine, _ = _make_engine()
        engine.on_event(_opened(1))
        assert engine._registry.focused_id() == 1

    def test_subsequent_window_does_not_steal_focus_in_registry(self):
        engine, _ = _make_engine()
        engine.on_event(_opened(1))
        engine.on_event(_focused(1))
        engine.on_event(_opened(2))
        # Window 1 is already focused — window 2 should NOT take over in registry
        assert engine._registry.focused_id() == 1

    def test_new_window_placed_in_main_zone_after_layout(self):
        engine, backend = _make_engine()
        engine.on_event(_opened(1))
        engine._apply_layout()
        cfg = Config()
        from aidwm.zones import ZoneGrid, parse_zone
        grid = ZoneGrid(columns=cfg.zones.columns, rows=cfg.zones.rows,
                        padding=cfg.layout.padding, gap=cfg.layout.gap)
        expected = grid.geometry(parse_zone(cfg.zones.main), _SCREEN)
        assert backend.applied.get(1) == expected


# --- drag detection / pinning ------------------------------------------------

class TestPinning:
    def test_engine_move_does_not_pin(self):
        engine, backend = _make_engine()
        engine.on_event(_opened(1))
        engine._apply_layout()
        # Simulate ConfigureNotify arriving with the geometry we just set
        placed_geo = backend.applied[1]
        engine.on_event(_moved(1, placed_geo))
        assert 1 not in engine.pinned_ids()

    def test_user_drag_pins_window(self):
        engine, backend = _make_engine()
        engine.on_event(_opened(1))
        engine._apply_layout()
        # Simulate user dragging 500px to the right
        placed = backend.applied[1]
        dragged = Geometry(placed.x + 500, placed.y + 300, placed.width, placed.height)
        engine.on_event(_moved(1, dragged))
        assert 1 in engine.pinned_ids()

    def test_small_delta_does_not_pin(self):
        engine, backend = _make_engine()
        engine.on_event(_opened(1))
        engine._apply_layout()
        placed = backend.applied[1]
        # 5px difference — within rounding tolerance
        nudged = Geometry(placed.x + 5, placed.y, placed.width, placed.height)
        engine.on_event(_moved(1, nudged))
        assert 1 not in engine.pinned_ids()

    def test_pinned_window_excluded_from_layout(self):
        engine, backend = _make_engine()
        engine.on_event(_opened(1))
        engine.on_event(_opened(2))
        engine.on_event(_focused(1))
        engine._apply_layout()
        # Pin window 2 by simulating a drag
        placed = backend.applied[2]
        dragged = Geometry(placed.x + 400, placed.y + 200, placed.width, placed.height)
        engine.on_event(_moved(2, dragged))
        assert 2 in engine.pinned_ids()

        # Re-layout: window 2 should not receive a new geometry from the engine
        backend.applied.clear()
        engine._apply_layout()
        assert 2 not in backend.applied

    def test_unpin_restores_window_to_layout(self):
        engine, backend = _make_engine()
        engine.on_event(_opened(1))
        engine._apply_layout()
        placed = backend.applied[1]
        engine.on_event(_moved(1, Geometry(placed.x + 500, placed.y, placed.width, placed.height)))
        assert 1 in engine.pinned_ids()

        engine.unpin(1)
        assert 1 not in engine.pinned_ids()

        backend.applied.clear()
        engine._apply_layout()
        assert 1 in backend.applied

    def test_closed_window_removed_from_pinned(self):
        engine, backend = _make_engine()
        engine.on_event(_opened(1))
        engine._apply_layout()
        placed = backend.applied[1]
        engine.on_event(_moved(1, Geometry(placed.x + 500, placed.y, placed.width, placed.height)))
        assert 1 in engine.pinned_ids()

        engine.on_event(WindowEvent(EventType.CLOSED, 1))
        assert 1 not in engine.pinned_ids()

    def test_move_without_prior_engine_set_pins_immediately(self):
        engine, _ = _make_engine()
        engine.on_event(_opened(1))
        # Move arrives before we ever ran a layout (no expected geometry recorded)
        engine.on_event(_moved(1, Geometry(500, 300, 200, 200)))
        assert 1 in engine.pinned_ids()
