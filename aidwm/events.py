from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class EventType(Enum):
    OPENED = auto()
    CLOSED = auto()
    FOCUSED = auto()
    MOVED = auto()
    RESIZED = auto()
    WORKSPACE_CHANGED = auto()
    FOCUS_HINT = auto()   # slot for gaze / mouse-proximity signals


@dataclass(frozen=True)
class Geometry:
    x: int
    y: int
    width: int
    height: int

    def area(self) -> int:
        return self.width * self.height


@dataclass
class WindowInfo:
    id: int
    title: str
    wm_class: str          # e.g. "firefox.Firefox"
    workspace: int
    geometry: Geometry
    is_focused: bool = False


@dataclass
class WindowEvent:
    type: EventType
    window_id: int
    geometry: Geometry | None = None
    title: str | None = None
    wm_class: str | None = None
    workspace: int | None = None


@dataclass
class FocusHint:
    """Soft focus signal from gaze tracking or other heuristics.

    The engine accumulates confidence over time before treating this as a
    focus change — prevents jitter from brief glances.
    """
    window_id: int
    confidence: float       # 0.0–1.0
    source: str             # "gaze", "mouse_proximity", "keyboard_shortcut"
    timestamp: float = field(default_factory=lambda: __import__("time").monotonic())
