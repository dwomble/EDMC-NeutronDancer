"""
A themed frame with a vertically scrollable interior.

The scrollbar only appears once packed/gridded content in `.interior` exceeds `max_height`
pixels; while content fits, the widget looks and behaves like a plain frame.
"""
import tkinter as tk
from tkinter import ttk

from theme import theme # type: ignore

class ScrollableFrame(tk.Frame):
    """
    A themed frame whose content -- packed or gridded into `.interior` -- scrolls vertically
    once it exceeds `max_height` pixels. The scrollbar is hidden entirely while content fits,
    and mouse-wheel scrolling is only bound while the pointer is over this widget so it doesn't
    steal scroll events from the rest of the EDMC window.
    """
    def __init__(self, master:tk.Widget, max_height:int|None = None, **kw) -> None:
        tk.Frame.__init__(self, master, **kw)
        theme.update(self)

        self._max_height = max_height
        self._scrollbar_visible = False
        self._resize_pending = False
        self._last_height:int|None = None
        self._last_scrollregion:tuple|None = None
        self._last_item_width:int|None = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        theme.register(self._canvas)
        self._canvas.grid(row=0, column=0, sticky="nsew")

        self._scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        # Not gridded yet -- shown/hidden by _update_scrollbar_visibility() as content changes.

        from . import Frame # local import: avoids a hard circular import at module load time
        self.interior:tk.Frame = Frame(self._canvas)
        self._interior_id = self._canvas.create_window((0, 0), window=self.interior, anchor="nw")

        self.interior.bind("<Configure>", self._on_interior_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<Enter>", self._bind_mousewheel)
        self._canvas.bind("<Leave>", self._unbind_mousewheel)

    def _on_interior_configure(self, event:tk.Event|None = None) -> None:
        """
        Content changed -- schedule (don't do inline) a scroll-region/scrollbar recompute.

        Deferring via after_idle and coalescing repeat calls into one is deliberate: recomputing
        synchronously inside the event handler can end up applying configure() changes that
        themselves generate more <Configure> events (e.g. while several children are being
        destroyed in the same pass), and a burst like that can turn into a storm that a real
        update() -- not just update_idletasks() -- keeps feeding into itself indefinitely.
        """
        if self._resize_pending:
            return
        self._resize_pending = True
        self.after_idle(self._apply_resize)

    def _apply_resize(self) -> None:
        self._resize_pending = False
        if not self._canvas.winfo_exists():
            return

        bbox = self._canvas.bbox("all")
        # Compare against the value *we* last applied, not the widget's own read-back: under
        # non-100% Tk UI scaling, configure(x) and cget() don't always round-trip to the same
        # value, so comparing against a read-back can look "different" every single pass even
        # when nothing meaningful changed -- which is exactly the kind of oscillation that
        # feeds an unbounded <Configure> storm once a real update() (not just
        # update_idletasks()) is draining events, rather than the harmless one-time settle a
        # genuine content change should produce.
        if bbox is not None and bbox != self._last_scrollregion:
            self._last_scrollregion = bbox
            self._canvas.configure(scrollregion=bbox)
        content_height:int = self._content_height()
        self._update_scrollbar_visibility(content_height)

    def _content_height(self) -> int:
        """
        Sum the children's own requested heights rather than trust `.interior.winfo_reqheight()`.

        Tk caches a pack-managed frame's own requested size and does not recompute it just
        because its children were destroyed -- winfo_reqheight() on an emptied frame keeps
        reporting its last (larger) size even after update()/update_idletasks(). Summing the
        current children directly sidesteps that stale cache entirely.
        """
        return sum(child.winfo_reqheight() for child in self.interior.winfo_children())

    def _on_canvas_configure(self, event:tk.Event) -> None:
        """ Keep the interior frame's width matched to the canvas's visible width. """
        if self._last_item_width != event.width:
            self._last_item_width = event.width
            self._canvas.itemconfigure(self._interior_id, width=event.width)

    def clear(self) -> None:
        """
        Remove all content from `.interior` in one shot.

        Prefer this over destroying children individually: destroying widgets one at a time
        while the resize machinery is live re-triggers a recompute after each destroy, and a
        rapid burst of those has been observed to make Tk spin on this platform. Unbinding for
        the duration of the wipe and recomputing exactly once afterwards avoids that entirely,
        and matches how a status panel actually replaces its content each refresh anyway.
        """
        self.interior.unbind("<Configure>")
        for child in self.interior.winfo_children():
            child.destroy()
        self.interior.bind("<Configure>", self._on_interior_configure)
        self._on_interior_configure()

    def _update_scrollbar_visibility(self, content_height:int) -> None:
        needs_scroll:bool = self._max_height is not None and content_height > self._max_height

        if needs_scroll and not self._scrollbar_visible:
            self._scrollbar.grid(row=0, column=1, sticky="ns")
            self._scrollbar_visible = True
        elif not needs_scroll and self._scrollbar_visible:
            self._scrollbar.grid_forget()
            self._scrollbar_visible = False

        display_height:int = min(content_height, self._max_height) if self._max_height else content_height
        if self._last_height != display_height:
            self._last_height = display_height
            self._canvas.configure(height=display_height)

    def _bind_mousewheel(self, event:tk.Event|None = None) -> None:
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind_all("<Button-4>", self._on_mousewheel)
        self._canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self, event:tk.Event|None = None) -> None:
        self._canvas.unbind_all("<MouseWheel>")
        self._canvas.unbind_all("<Button-4>")
        self._canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event:tk.Event) -> None:
        if not self._scrollbar_visible:
            return
        if event.num == 4:
            delta = -1
        elif event.num == 5:
            delta = 1
        else:
            delta = -1 if event.delta > 0 else 1
        self._canvas.yview_scroll(delta, "units")
