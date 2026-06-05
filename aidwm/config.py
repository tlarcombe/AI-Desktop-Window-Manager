from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from aidwm.events import Geometry

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "aidwm" / "config.toml"
BUNDLED_DEFAULT = Path(__file__).parent.parent / "config" / "default.toml"


@dataclass
class ZoneConfig:
    columns: list[float] = field(default_factory=lambda: [0.25, 0.25, 0.25, 0.25])
    rows: list[float] = field(default_factory=lambda: [0.5, 0.5])
    main: str = "b2:c2"
    secondary: list[str] = field(default_factory=lambda: ["a2", "d2", "a1", "d1"])


@dataclass
class LayoutConfig:
    padding: int = 8
    gap: int = 8


@dataclass
class WindowRule:
    class_pattern: str = ".*"
    title_pattern: str = ".*"
    zone: str | None = None              # e.g. "b1", "c1:d1"
    fixed_position: Geometry | None = None
    workspace: int | None = None         # None = any workspace
    fixed_across_workspaces: bool = False   # sticky: visible on all workspaces
    priority: int = 0


@dataclass
class GeneralConfig:
    trigger_on_focus: bool = True
    layout_delay_ms: int = 50
    socket_path: str = ""


@dataclass
class Config:
    general: GeneralConfig = field(default_factory=GeneralConfig)
    layout: LayoutConfig = field(default_factory=LayoutConfig)
    zones: ZoneConfig = field(default_factory=ZoneConfig)
    rules: list[WindowRule] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        source = path or DEFAULT_CONFIG_PATH
        if not source.exists():
            source = BUNDLED_DEFAULT
        raw = tomllib.loads(source.read_text()) if source.exists() else {}
        return cls._from_dict(raw)

    @classmethod
    def _from_dict(cls, raw: dict) -> Config:
        general_raw = raw.get("general", {})
        layout_raw = raw.get("layout", {})
        zones_raw = layout_raw.get("zones", {})
        rules_raw = raw.get("rules", [])

        general = GeneralConfig(
            trigger_on_focus=general_raw.get("trigger_on_focus", True),
            layout_delay_ms=general_raw.get("layout_delay_ms", 50),
            socket_path=general_raw.get("socket_path", ""),
        )
        layout = LayoutConfig(
            padding=layout_raw.get("padding", 8),
            gap=layout_raw.get("gap", 8),
        )
        zones = ZoneConfig(
            columns=zones_raw.get("columns", [0.25, 0.25, 0.25, 0.25]),
            rows=zones_raw.get("rows", [0.5, 0.5]),
            main=zones_raw.get("main", "b2:c2"),
            secondary=zones_raw.get("secondary", ["a2", "d2", "a1", "d1"]),
        )
        rules = []
        for r in rules_raw:
            fp = r.get("fixed_position")
            rules.append(WindowRule(
                class_pattern=r.get("class", ".*"),
                title_pattern=r.get("title", ".*"),
                zone=r.get("zone"),
                fixed_position=Geometry(**fp) if fp else None,
                workspace=r.get("workspace"),
                fixed_across_workspaces=r.get("fixed_across_workspaces", False),
                priority=r.get("priority", 0),
            ))
        return cls(general=general, layout=layout, zones=zones, rules=rules)

    def socket_path_resolved(self) -> Path:
        if self.general.socket_path:
            return Path(self.general.socket_path)
        import os
        uid = os.getuid()
        return Path(f"/run/user/{uid}/aidwm.sock")
