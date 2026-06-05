import pytest

from aidwm.config import Config, WindowRule
from aidwm.events import Geometry, WindowInfo
from aidwm.registry import WindowRegistry

_GEO = Geometry(0, 0, 800, 600)


def _info(id: int, wm_class: str = "test.Test", title: str = "Test") -> WindowInfo:
    return WindowInfo(id=id, title=title, wm_class=wm_class, workspace=0, geometry=_GEO)


class TestWindowRegistry:
    def test_add_and_retrieve(self):
        reg = WindowRegistry()
        reg.add_or_update(_info(1))
        assert reg.get(1) is not None
        assert len(reg) == 1

    def test_remove(self):
        reg = WindowRegistry()
        reg.add_or_update(_info(1))
        reg.remove(1)
        assert reg.get(1) is None

    def test_set_focused_clears_previous(self):
        reg = WindowRegistry()
        reg.add_or_update(_info(1))
        reg.add_or_update(_info(2))
        reg.set_focused(1)
        reg.set_focused(2)
        assert not reg.get(1).is_focused
        assert reg.get(2).is_focused
        assert reg.focused_id() == 2

    def test_windows_on_workspace(self):
        reg = WindowRegistry()
        w1 = WindowInfo(id=1, title="a", wm_class="x", workspace=0, geometry=_GEO)
        w2 = WindowInfo(id=2, title="b", wm_class="x", workspace=1, geometry=_GEO)
        reg.add_or_update(w1)
        reg.add_or_update(w2)
        assert len(reg.windows_on_workspace(0)) == 1
        assert len(reg.windows_on_workspace(1)) == 1

    def test_fixed_position_rule_match(self):
        reg = WindowRegistry()
        fixed = Geometry(100, 100, 500, 400)
        cfg = Config(rules=[WindowRule(class_pattern="firefox", fixed_position=fixed)])
        info = _info(1, wm_class="firefox.Firefox")
        reg.add_or_update(info)
        assert reg.fixed_position_for(info, cfg) == fixed

    def test_fixed_position_rule_no_match(self):
        reg = WindowRegistry()
        fixed = Geometry(100, 100, 500, 400)
        cfg = Config(rules=[WindowRule(class_pattern="firefox", fixed_position=fixed)])
        info = _info(1, wm_class="alacritty.Alacritty")
        reg.add_or_update(info)
        assert reg.fixed_position_for(info, cfg) is None
