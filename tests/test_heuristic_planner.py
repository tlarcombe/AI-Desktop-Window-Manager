import pytest

from aidwm.config import Config
from aidwm.events import Geometry, WindowInfo
from aidwm.planner.heuristic import HeuristicPlanner

SCREEN = Geometry(x=0, y=0, width=1920, height=1080)


def _win(id: int, workspace: int = 0) -> WindowInfo:
    return WindowInfo(id=id, title=f"win{id}", wm_class="test.Test",
                      workspace=workspace, geometry=Geometry(0, 0, 100, 100))


def _plan(windows, active_id=None):
    return HeuristicPlanner().plan(windows, active_id, SCREEN, Config())


class TestHeuristicPlanner:
    def test_empty(self):
        assert _plan([]) == {}

    def test_single_window_fills_screen(self):
        result = _plan([_win(1)], active_id=1)
        geo = result[1]
        cfg = Config()
        p = cfg.layout.padding
        assert geo.x == p
        assert geo.y == p
        assert geo.width == SCREEN.width - 2 * p
        assert geo.height == SCREEN.height - 2 * p

    def test_active_window_gets_left_fraction(self):
        cfg = Config()
        windows = [_win(1), _win(2)]
        result = _plan(windows, active_id=1)
        expected_w = int((SCREEN.width - 2 * cfg.layout.padding) * cfg.layout.active_fraction) - cfg.layout.gap // 2
        assert result[1].width == expected_w
        assert result[1].x == cfg.layout.padding

    def test_secondary_window_placed_right(self):
        result = _plan([_win(1), _win(2)], active_id=1)
        assert result[2].x > result[1].x

    def test_multiple_secondary_windows_stacked(self):
        result = _plan([_win(1), _win(2), _win(3)], active_id=1)
        assert result[2].y < result[3].y
        assert result[2].x == result[3].x

    def test_no_active_columns(self):
        result = _plan([_win(1), _win(2)], active_id=None)
        assert result[1].x < result[2].x
        assert result[1].y == result[2].y

    def test_all_windows_within_screen(self):
        windows = [_win(i) for i in range(5)]
        result = _plan(windows, active_id=1)
        for geo in result.values():
            assert geo.x >= 0
            assert geo.y >= 0
            assert geo.x + geo.width <= SCREEN.width
            assert geo.y + geo.height <= SCREEN.height
