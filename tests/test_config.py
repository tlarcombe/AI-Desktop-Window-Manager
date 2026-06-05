import textwrap
from pathlib import Path

from aidwm.config import Config


def test_hardcoded_defaults():
    # Test dataclass defaults directly, bypassing file loading
    cfg = Config._from_dict({})
    assert cfg.general.trigger_on_focus is True
    assert cfg.zones.main == "b2:c2"
    assert cfg.zones.columns == [0.25, 0.25, 0.25, 0.25]
    assert cfg.rules == []


def test_bundled_default_loads_ytv_and_mpv_rules():
    # The bundled default.toml should always include the ytv and mpv rules
    cfg = Config.load(Path("/nonexistent/path.toml"))
    class_patterns = [r.class_pattern for r in cfg.rules]
    title_patterns = [r.title_pattern for r in cfg.rules]
    assert "mpv" in class_patterns
    assert "ytv" in title_patterns


def test_load_from_file(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text(textwrap.dedent("""\
        [general]
        layout_delay_ms = 100

        [[rules]]
        class = "firefox"
        fixed_position = { x = 0, y = 0, width = 1920, height = 1080 }
        fixed_across_workspaces = true
    """))
    cfg = Config.load(toml)
    assert cfg.general.layout_delay_ms == 100
    assert len(cfg.rules) == 1
    assert cfg.rules[0].class_pattern == "firefox"
    assert cfg.rules[0].fixed_position is not None
    assert cfg.rules[0].fixed_across_workspaces is True


def test_zone_rule_parsed(tmp_path):
    toml = tmp_path / "config.toml"
    toml.write_text(textwrap.dedent("""\
        [[rules]]
        title = "ytv"
        zone  = "b1"
        workspace = 8
    """))
    cfg = Config.load(toml)
    rule = cfg.rules[0]
    assert rule.title_pattern == "ytv"
    assert rule.zone == "b1"
    assert rule.workspace == 8
