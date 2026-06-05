from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from aidwm.events import FocusHint, Geometry, WindowEvent


class Backend(ABC):
    """Protocol-agnostic display backend interface.

    Implementations emit WindowEvents and FocusHints to the engine via
    callbacks, and accept geometry commands from the engine via apply_geometry.
    """

    @abstractmethod
    def start(
        self,
        on_event: Callable[[WindowEvent], None],
        on_focus_hint: Callable[[FocusHint], None],
    ) -> None:
        """Begin listening for window events. Blocks until stop() is called."""

    @abstractmethod
    def stop(self) -> None:
        """Signal the backend to stop its event loop."""

    @abstractmethod
    def apply_geometry(self, window_id: int, geometry: Geometry) -> None:
        """Move and resize a window."""

    @abstractmethod
    def get_screen_geometry(self) -> Geometry:
        """Return the usable screen area (respects struts/panels)."""

    @abstractmethod
    def get_current_workspace(self) -> int:
        """Return the index of the currently active workspace."""
