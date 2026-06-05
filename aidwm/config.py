from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-reuse-def]

from aidwm.events import Geometry

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "aidwm" / "config.toml"
BUNDLED_DEFAULT = Path(__file__).parent.parent / "config" / "default.toml"


@dataclass
class LayoutConfig:
    padding: int = 8
    gap: int = 8
    active_fraction: float = 0.6    # fraction of screen width for the active window


@dataclass
class WindowRule:
    class_pattern: str = ".*"
    title_pattern: str = ".*"
    fixed_position: Optional[Geometry] = None
    fixed_across_workspaces: bool = False
    priority: int = 0               # higher = more important to the planner


@dataclass
class GeneralConfig:
    trigger_on_focus: bool = True
    layout_delay_ms: int = 50       # debounce before re-layout
    socket_path: str = ""           # empty = auto (/run/user/{uid}/aidwm.sock)


@dataclass
class Config:
    general: GeneralConfig = field(default_factory=GeneralConfig)
    layout: LayoutConfig = field(default_factory=LayoutConfig)
    rules: list[WindowRule] = field(default_factory=list)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        source = path or DEFAULT_CONFIG_PATH
        if not source.exists():
            source = BUNDLED_DEFAULT
        raw = tomllib.loads(source.read_text()) if source.exists() else {}
        return cls._from_dict(raw)

    @classmethod
    def _from_dict(cls, raw: dict) -> "Config":
        general_raw = raw.get("general", {})
        layout_raw = raw.get("layout", {})
        rules_raw = raw.get("rules", [])

        general = GeneralConfig(
            trigger_on_focus=general_raw.get("trigger_on_focus", True),
            layout_delay_ms=general_raw.get("layout_delay_ms", 50),
            socket_path=general_raw.get("socket_path", ""),
        )
        layout = LayoutConfig(
            padding=layout_raw.get("padding", 8),
            gap=layout_raw.get("gap", 8),
            active_fraction=layout_raw.get("active_fraction", 0.6),
        )
        rules = []
        for r in rules_raw:
            fp = r.get("fixed_position")
            rules.append(WindowRule(
                class_pattern=r.get("class", ".*"),
                title_pattern=r.get("title", ".*"),
                fixed_position=Geometry(**fp) if fp else None,
                fixed_across_workspaces=r.get("fixed_across_workspaces", False),
                priority=r.get("priority", 0),
            ))
        return cls(general=general, layout=layout, rules=rules)

    def socket_path_resolved(self) -> Path:
        if self.general.socket_path:
            return Path(self.general.socket_path)
        import os
        uid = os.getuid()
        return Path(f"/run/user/{uid}/aidwm.sock")
