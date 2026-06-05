from aidwm.config import Config
from aidwm.events import Geometry, WindowInfo
from aidwm.planner.zone import ZonePlanner
from aidwm.zones import ZoneGrid, parse_zone

SCREEN = Geometry(x=0, y=0, width=1920, height=1080)


def _win(id: int) -> WindowInfo:
    return WindowInfo(id=id, title=f"win{id}", wm_class="test.Test",
                      workspace=0, geometry=Geometry(0, 0, 100, 100))


def _plan(windows, active_id=None, config=None):
    return ZonePlanner().plan(windows, active_id, SCREEN, config or Config())


def _main_geo(config=None) -> Geometry:
    cfg = config or Config()
    grid = ZoneGrid(columns=cfg.zones.columns, rows=cfg.zones.rows,
                    padding=cfg.layout.padding, gap=cfg.layout.gap)
    return grid.geometry(parse_zone(cfg.zones.main), SCREEN)


class TestZonePlanner:
    def test_empty(self):
        assert _plan([]) == {}

    def test_active_goes_to_main_zone(self):
        result = _plan([_win(1)], active_id=1)
        assert result[1] == _main_geo()

    def test_secondary_window_not_in_main_zone(self):
        result = _plan([_win(1), _win(2)], active_id=1)
        assert result[2] != _main_geo()

    def test_secondary_windows_placed_in_order(self):
        cfg = Config()
        result = _plan([_win(1), _win(2), _win(3)], active_id=1, config=cfg)
        grid = ZoneGrid(columns=cfg.zones.columns, rows=cfg.zones.rows,
                        padding=cfg.layout.padding, gap=cfg.layout.gap)
        secondary_0 = grid.geometry(parse_zone(cfg.zones.secondary[0]), SCREEN)
        secondary_1 = grid.geometry(parse_zone(cfg.zones.secondary[1]), SCREEN)
        assert result[2] == secondary_0
        assert result[3] == secondary_1

    def test_no_active_all_in_secondary_zones(self):
        result = _plan([_win(1), _win(2)], active_id=None)
        cfg = Config()
        grid = ZoneGrid(columns=cfg.zones.columns, rows=cfg.zones.rows,
                        padding=cfg.layout.padding, gap=cfg.layout.gap)
        sec0 = grid.geometry(parse_zone(cfg.zones.secondary[0]), SCREEN)
        assert result[1] == sec0

    def test_all_windows_within_screen(self):
        windows = [_win(i) for i in range(6)]
        result = _plan(windows, active_id=1)
        for geo in result.values():
            assert geo.x >= 0
            assert geo.y >= 0
            assert geo.x + geo.width <= SCREEN.width + 1   # allow 1px rounding
            assert geo.y + geo.height <= SCREEN.height + 1
