from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from ewmh import EWMH
from Xlib import X
from Xlib import display as xdisplay
from Xlib import error as xerror
from Xlib.protocol import rq

from aidwm.backends.base import Backend
from aidwm.events import EventType, FocusHint, Geometry, WindowEvent, WindowInfo

log = logging.getLogger(__name__)

_NET_ACTIVE_WINDOW = "_NET_ACTIVE_WINDOW"
_NET_CLIENT_LIST = "_NET_CLIENT_LIST"
_NET_CURRENT_DESKTOP = "_NET_CURRENT_DESKTOP"
_NET_WM_DESKTOP = "_NET_WM_DESKTOP"


class X11Backend(Backend):
    def __init__(self) -> None:
        self._ewmh: EWMH | None = None
        self._display: xdisplay.Display | None = None
        self._running = threading.Event()
        self._on_event: Callable[[WindowEvent], None] | None = None
        self._on_focus_hint: Callable[[FocusHint], None] | None = None

    # --- Backend interface ---------------------------------------------------

    def start(
        self,
        on_event: Callable[[WindowEvent], None],
        on_focus_hint: Callable[[FocusHint], None],
    ) -> None:
        self._on_event = on_event
        self._on_focus_hint = on_focus_hint
        self._display = xdisplay.Display()
        self._ewmh = EWMH(self._display)
        self._running.set()

        root = self._display.screen().root
        root.change_attributes(event_mask=X.PropertyChangeMask | X.SubstructureNotifyMask)
        self._display.flush()

        self._emit_initial_snapshot()
        self._event_loop()

    def stop(self) -> None:
        self._running.clear()

    def apply_geometry(self, window_id: int, geometry: Geometry) -> None:
        if not self._display:
            return
        try:
            win = self._display.create_resource_object("window", window_id)
            win.configure(
                x=geometry.x,
                y=geometry.y,
                width=geometry.width,
                height=geometry.height,
            )
            self._display.flush()
        except xerror.BadWindow:
            log.debug("apply_geometry: window %d no longer exists", window_id)

    def get_screen_geometry(self) -> Geometry:
        assert self._display
        screen = self._display.screen()
        # TODO: subtract struts (panel reservations) for accurate work area
        return Geometry(x=0, y=0, width=screen.width_in_pixels, height=screen.height_in_pixels)

    def get_current_workspace(self) -> int:
        assert self._ewmh
        result = self._ewmh.getCurrentDesktop()
        return int(result) if result is not None else 0

    # --- private helpers -----------------------------------------------------

    def _event_loop(self) -> None:
        assert self._display
        while self._running.is_set():
            try:
                event = self._display.next_event()
                self._handle_xevent(event)
            except xerror.ConnectionClosedError:
                log.warning("X11 connection closed")
                break

    def _handle_xevent(self, event: rq.Event) -> None:
        if event.type == X.PropertyNotify:
            atom_name = self._display.get_atom_name(event.atom)  # type: ignore[union-attr]
            if atom_name == _NET_ACTIVE_WINDOW:
                self._on_active_window_changed()
            elif atom_name == _NET_CLIENT_LIST:
                self._on_client_list_changed()
        elif event.type == X.DestroyNotify:
            self._dispatch(WindowEvent(type=EventType.CLOSED, window_id=event.window.id))
        elif event.type == X.ConfigureNotify:
            geo = Geometry(
                x=event.x,
                y=event.y,
                width=event.width,
                height=event.height,
            )
            self._dispatch(WindowEvent(
                type=EventType.MOVED,
                window_id=event.window.id,
                geometry=geo,
            ))

    def _on_active_window_changed(self) -> None:
        assert self._ewmh
        win = self._ewmh.getActiveWindow()
        if win:
            self._dispatch(WindowEvent(type=EventType.FOCUSED, window_id=win.id))

    def _on_client_list_changed(self) -> None:
        assert self._ewmh
        clients = self._ewmh.getClientList() or []
        for win in clients:
            info = self._window_info(win)
            if info:
                self._dispatch(WindowEvent(
                    type=EventType.OPENED,
                    window_id=win.id,
                    title=info.title,
                    wm_class=info.wm_class,
                    workspace=info.workspace,
                    geometry=info.geometry,
                ))

    def _emit_initial_snapshot(self) -> None:
        assert self._ewmh
        clients = self._ewmh.getClientList() or []
        for win in clients:
            info = self._window_info(win)
            if info:
                self._dispatch(WindowEvent(
                    type=EventType.OPENED,
                    window_id=win.id,
                    title=info.title,
                    wm_class=info.wm_class,
                    workspace=info.workspace,
                    geometry=info.geometry,
                ))
        active = self._ewmh.getActiveWindow()
        if active:
            self._dispatch(WindowEvent(type=EventType.FOCUSED, window_id=active.id))

    def _window_info(self, win: object) -> WindowInfo | None:
        assert self._ewmh
        try:
            geo = win.get_geometry()  # type: ignore[attr-defined]
            name = self._ewmh.getWmName(win) or ""
            wm_class = win.get_wm_class()  # type: ignore[attr-defined]
            class_str = ".".join(wm_class) if wm_class else "unknown"
            desktop = self._ewmh.getWmDesktop(win)
            workspace = int(desktop) if desktop is not None else 0
            return WindowInfo(
                id=win.id,  # type: ignore[attr-defined]
                title=name if isinstance(name, str) else name.decode("utf-8", errors="replace"),
                wm_class=class_str,
                workspace=workspace,
                geometry=Geometry(x=geo.x, y=geo.y, width=geo.width, height=geo.height),
            )
        except (xerror.BadWindow, xerror.BadDrawable, AttributeError):
            return None

    def _dispatch(self, event: WindowEvent) -> None:
        if self._on_event:
            try:
                self._on_event(event)
            except Exception:
                log.exception("Error in event handler")
