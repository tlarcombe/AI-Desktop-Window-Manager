import textwrap
from pathlib import Path

import pytest

from aidwm.config import Config


def test_defaults():
    cfg = Config.load(Path("/nonexistent/path.toml"))
    assert cfg.general.trigger_on_focus is True
    assert cfg.layout.active_fraction == 0.6
    assert cfg.rules == []


def test_load_from_file(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text(textwrap.dedent("""\
        [general]
        layout_delay_ms = 100

        [layout]
        active_fraction = 0.7

        [[rules]]
        class = "firefox"
        fixed_position = { x = 0, y = 0, width = 1920, height = 1080 }
        fixed_across_workspaces = true
    """))
    cfg = Config.load(toml)
    assert cfg.general.layout_delay_ms == 100
    assert cfg.layout.active_fraction == 0.7
    assert len(cfg.rules) == 1
    assert cfg.rules[0].class_pattern == "firefox"
    assert cfg.rules[0].fixed_position is not None
    assert cfg.rules[0].fixed_across_workspaces is True
