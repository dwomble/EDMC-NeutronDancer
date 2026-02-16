import json
import threading
from dataclasses import dataclass, asdict
from enum import Enum
from functools import partial

import tkinter as tk
from tkinter import ttk, colorchooser as tkColorChooser
import myNotebook as nb  # type: ignore

try:
    from EDMCOverlay import edmcoverlay  # type: ignore
    from overlay_plugin.overlay_api import define_plugin_group as _define_plugin_group  # type: ignore
except ImportError:
    try:
        from edmcoverlay import edmcoverlay  # type: ignore

    except ImportError:
        edmcoverlay = None

from config import config  # type:ignore

from utils.debug import Debug, catch_exceptions
from utils.placeholder import Placeholder
from .context import Context
from .constants import OVERLAY_NAME


class OverlayMode(Enum):
    cockpit = 1
    galaxy_map = 2


@dataclass
class OvFrame:
    """Overlay frame details"""

    name: str = "Default"
    enabled: bool = True
    cockpit_x: int = 525
    cockpit_y: int = 625
    galaxy_map_x: int = 460
    galaxy_map_y: int = 70
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    centered_x: bool = False
    centered_y: bool = False
    ttl: int = 0
    title_colour: str = "white"
    text_colour: str = "white"
    bgenabled: bool = False
    background: str = "grey"
    border: str = ""
    border_colour: str = ""
    border_width: int = 0
    anchor: str = "nw"
    justification: str = "left" if centered_x == False else "center"
    text_size: str = "normal"


class Overlay:

    def __init__(self) -> None:
        self._enabled: bool = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.mode: OverlayMode | None = None
        self.title_text: str = ""
        self.body_text: str = ""
        self.ovf: OvFrame = OvFrame()
        if self._overlay:
            _define_plugin_group(
                plugin_group=OVERLAY_NAME,
                matching_prefixes=[f"{OVERLAY_NAME}-"],
                id_prefix_group=f"{self.ovf.name}",
                id_prefixes=[f"{OVERLAY_NAME}-{self.ovf.name}-"],
                id_prefix_group_anchor="nw",
                marker_label_position="below",
                controller_preview_box_mode="last",
                background_color="#00000000",
                background_border_width=2,
            )
        self._load_prefs()
        self.enabled = self.ovf.enabled

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, value):
        if value is False and self._thread is not None:
            # Stop the thread before we disable.
            self.hide()
        self._enabled = value

    @property
    def _overlay(self):
        """Is an overlay installed and running?"""
        if not edmcoverlay:
            Debug.logger.warning(f"edmcoverlay plugin is not installed")
            return

        # Is it running?
        try:
            return edmcoverlay.Overlay()
        except Exception as e:
            Debug.logger.warning(f"EDMCOverlay is not running")
            return

    @catch_exceptions
    def _draw_overlay(self) -> None:
        x, y = {
            OverlayMode.cockpit: (self.ovf.cockpit_x, self.ovf.cockpit_y),
            OverlayMode.galaxy_map: (self.ovf.galaxy_map_x, self.ovf.galaxy_map_y),
        }[self.mode]
        # Draw title
        self._overlay.send_message(
            msgid=f"{OVERLAY_NAME}-{self.ovf.name}-title",
            text=self.title_text,
            color=self.ovf.text_colour,
            x=x,
            y=y,
            ttl=1,
            size="large",
        )
        # Draw body
        self._overlay.send_message(
            msgid=f"{OVERLAY_NAME}-{self.ovf.name}-body",
            text=self.body_text,
            color=self.ovf.text_colour,
            x=x,
            y=y + 20,
            ttl=1,
            size="normal",
        )

    @catch_exceptions
    def show(self, mode: OverlayMode) -> None:
        self.mode = mode
        if not self._overlay or not self.enabled:
            # No overlay, just no-op
            return
        if self._thread is not None:
            # We're already started.
            return

        def _loop():
            while not self._stop.wait(1):
                self._draw_overlay()

        self._thread = threading.Thread(target=_loop, daemon=True)
        # Draw the overlay immediately, then start the thread
        self._draw_overlay()
        self._thread.start()

    @catch_exceptions
    def hide(self) -> None:
        if not self._overlay or not self.enabled:
            # No overlay, just no-op
            return
        if self._thread is None:
            # We're already stopped.
            return
        self._stop.set()
        # Clear the message
        self._overlay.send_raw({"id": f"{OVERLAY_NAME}-title", "text": "", "ttl": 0})
        self._overlay.send_raw({"id": f"{OVERLAY_NAME}-body", "text": "", "ttl": 0})
        # Wait for the thread to stop
        self._thread.join()
        # Clean up
        self._thread = None
        self._stop.clear()

    @catch_exceptions
    def prefs_display(self, parent: nb.Frame) -> nb.Frame:
        """EDMC settings pane hook. Displays one frame per row."""

        def bind_var(data_obj, attribute, tk_var):
            # Update dataclass whenever the UI changes
            def update_obj(*args) -> None:
                setattr(data_obj, attribute, tk_var.get())

            tk_var.trace_add("write", update_obj)
            return tk_var

        def colour_picker(parent: nb.Frame, which: str, col: tk.StringVar) -> None:
            (_, color) = tkColorChooser.askcolor(col.get(), title=which, parent=parent)

            if color:
                col.set(color)
                Debug.logger.debug(f"{len(cbtns)} {cbtns}")
                for b in cbtns:
                    b.config(**{which.lower(): color})

        def validate_int(val: str) -> bool:
            return True if val.isdigit() or val == "" else False

        prefsfr: nb.Frame = nb.Frame(parent)
        prefsfr.columnconfigure(6, weight=1)
        prefsfr.rowconfigure(60, weight=1)
        prefsfr.grid()
        validate = (prefsfr.register(validate_int), "%P")

        row: int = 0
        col: int = 0
        nb.Label(prefsfr, text="Overlay", justify=tk.LEFT).grid(
            row=row, column=0, padx=10, sticky=tk.NW
        )
        row += 1

        vars: dict = {}
        cbtns: list = []
        col = 0
        for k in [
            ("enabled", "Enable", tk.BooleanVar, tk.Checkbutton),
            ("cockpit_x", "Cockpit X", tk.IntVar, tk.Entry),
            ("cockpit_y", "Cockpit Y", tk.IntVar, tk.Entry),
            ("galaxy_map_x", "Galaxy Map X", tk.IntVar, tk.Entry),
            ("galaxy_map_y", "Galaxy Map Y", tk.IntVar, tk.Entry),
            # ('w', 'W', tk.IntVar, tk.Entry),
            # ('h', 'H', tk.IntVar, tk.Entry),
            ("text_colour", "Foreground", tk.StringVar, "ColorPicker"),
            # ('bgenabled', 'Use Background', tk.BooleanVar, tk.Checkbutton),
            # ('background', 'Background', tk.StringVar, 'ColorPicker')
        ]:

            vars[k[0]] = bind_var(self.ovf, k[0], k[2](value=getattr(self.ovf, k[0])))
            match k[3]:
                case tk.Checkbutton:
                    nb.Checkbutton(prefsfr, text=k[1], variable=vars[k[0]]).grid(
                        row=row, column=col, padx=10, pady=0, sticky=tk.W
                    )
                case tk.Entry:
                    nb.Label(prefsfr, text=k[1]).grid(
                        row=row, column=col, padx=5, pady=5, sticky=tk.W
                    )
                    col += 1
                    tk.Entry(
                        prefsfr,
                        textvariable=vars[k[0]],
                        width=8,
                        validate="all",
                        validatecommand=validate,
                    ).grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)
                case "ColorPicker":
                    btn: tk.Button = tk.Button(
                        prefsfr,
                        text=k[1],
                        foreground=self.ovf.text_colour,
                        background=self.ovf.background,
                        command=partial(colour_picker, prefsfr, k[1], vars[k[0]]),
                    )
                    btn.grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)
                    cbtns.append(btn)
            col += 1

        return prefsfr

    def save_prefs(self) -> bool:
        """Serialize and save the frames dictionary to EDMC config."""
        # Store the serialized frames in the config

        config.set(f"{OVERLAY_NAME}_overlay", json.dumps(asdict(self.ovf)))
        self.enabled = self.ovf.enabled

        Debug.logger.info(f"Saved {self.ovf} frames to EDMC config")
        return True

    def _load_prefs(self) -> None:
        """Read frame data from the EDMC config."""

        conf = config.get(f"{OVERLAY_NAME}_overlay")
        Debug.logger.debug(f"Loading config: {conf}")
        if conf == None:
            return
        data: dict = json.loads(conf)
        self.ovf = OvFrame(**data)
