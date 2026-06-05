import pytest

from aidwm.events import Geometry
from aidwm.zones import ZoneGrid, ZoneSpec, parse_zone

SCREEN = Geometry(x=0, y=0, width=1920, height=1080)
GRID = ZoneGrid(columns=[0.25, 0.25, 0.25, 0.25], rows=[0.5, 0.5], padding=0, gap=0)


class TestParseZone:
    def test_single_cell(self):
        s = parse_zone("b2")
        assert s == ZoneSpec(col_start=1, col_end=1, row_start=1, row_end=1)

    def test_merged_horizontal(self):
        s = parse_zone("b2:c2")
        assert s == ZoneSpec(col_start=1, col_end=2, row_start=1, row_end=1)

    def test_merged_horizontal_reversed(self):
        # c1:d1 and d1:c1 should be identical
        assert parse_zone("c1:d1") == parse_zone("d1:c1")

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_zone("22")

    def test_str_roundtrip_single(self):
        assert str(parse_zone("a1")) == "a1"

    def test_str_roundtrip_merged(self):
        assert str(parse_zone("b2:c2")) == "b2:c2"


class TestZoneGrid:
    def test_full_screen_single_zone(self):
        grid = ZoneGrid(columns=[1.0], rows=[1.0], padding=0, gap=0)
        geo = grid.geometry(parse_zone("a1"), SCREEN)
        assert geo == Geometry(x=0, y=0, width=1920, height=1080)

    def test_column_widths_equal_without_padding(self):
        geo_a = GRID.geometry(parse_zone("a1"), SCREEN)
        geo_b = GRID.geometry(parse_zone("b1"), SCREEN)
        assert geo_a.width == geo_b.width == 480

    def test_merged_zone_spans_two_columns(self):
        single = GRID.geometry(parse_zone("b1"), SCREEN)
        merged = GRID.geometry(parse_zone("b1:c1"), SCREEN)
        assert merged.width == single.width * 2

    def test_main_zone_b2c2_position(self):
        geo = GRID.geometry(parse_zone("b2:c2"), SCREEN)
        assert geo.x == 480       # column b starts at 25%
        assert geo.y == 540       # row 2 starts at 50%
        assert geo.width == 960   # 50% of 1920
        assert geo.height == 540  # 50% of 1080

    def test_mpv_zone_c1d1(self):
        geo = GRID.geometry(parse_zone("c1:d1"), SCREEN)
        assert geo.x == 960
        assert geo.y == 0
        assert geo.width == 960
        assert geo.height == 540

    def test_ytv_zone_b1(self):
        geo = GRID.geometry(parse_zone("b1"), SCREEN)
        assert geo.x == 480
        assert geo.y == 0
        assert geo.width == 480
        assert geo.height == 540

    def test_padding_applied(self):
        grid = ZoneGrid(columns=[1.0], rows=[1.0], padding=10, gap=0)
        geo = grid.geometry(parse_zone("a1"), SCREEN)
        assert geo.x == 10
        assert geo.y == 10
        assert geo.width == 1900
        assert geo.height == 1060

    def test_zones_do_not_overlap(self):
        specs = [parse_zone(z) for z in ["a1", "b1", "c1", "d1", "a2", "b2", "c2", "d2"]]
        geos = [GRID.geometry(s, SCREEN) for s in specs]
        for i, g1 in enumerate(geos):
            for j, g2 in enumerate(geos):
                if i == j:
                    continue
                # No horizontal + vertical overlap simultaneously
                h_overlap = g1.x < g2.x + g2.width and g1.x + g1.width > g2.x
                v_overlap = g1.y < g2.y + g2.height and g1.y + g1.height > g2.y
                assert not (h_overlap and v_overlap), f"zones {i} and {j} overlap"
