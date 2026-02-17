import json
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


class OverlayView(Enum):
    hidden = 0
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
        self._view: OverlayView = OverlayView.hidden
        self._title_text: str = ""
        self._body_text: str = ""
        self._load_prefs()
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
            self._draw_overlay()

    @property
    def _overlay(self):
        """Is an overlay installed and running?"""
        if not edmcoverlay:
            Debug.logger.warning(f"edmcoverlay plugin is not installed")
            return None

        # Is it running?
        try:
            return edmcoverlay.Overlay()
        except Exception as e:
            Debug.logger.warning(f"EDMCOverlay is not running")
            return None

    @property
    def view(self) -> OverlayView:
        return self._view

    @view.setter
    def view(self, value: OverlayView) -> None:
        self._view = value
        self._draw_overlay()

    @property
    def title_text(self) -> str:
        return self._title_text

    @title_text.setter
    def title_text(self, value: str) -> None:
        self._title_text = value
        self._draw_overlay()

    @property
    def body_text(self) -> str:
        return self._body_text

    @body_text.setter
    def body_text(self, value: str) -> None:
        self._body_text = value
        self._draw_overlay()

    @catch_exceptions
    def _draw_overlay(self) -> None:
        if not self._overlay:
            # no overlay, just no-op.
            return
        x, y = {
            OverlayView.hidden: (0, 0),
            OverlayView.cockpit: (self.ovf.cockpit_x, self.ovf.cockpit_y),
            OverlayView.galaxy_map: (self.ovf.galaxy_map_x, self.ovf.galaxy_map_y),
        }[self.view]
        if not self.ovf.enabled or self.view == OverlayView.hidden:
            Debug.logger.info("Clearing overlay")
            title_text = ""
            body_text = ""
        else:
            title_text = self.title_text
            body_text = self.body_text
        # Draw title
        self._overlay.send_message(
            msgid=f"{OVERLAY_NAME}-{self.ovf.name}-title",
            text=title_text,
            color=self.ovf.text_colour,
            x=x,
            y=y,
            ttl=0,
            size="large",
        )
        # Draw body
        self._overlay.send_message(
            msgid=f"{OVERLAY_NAME}-{self.ovf.name}-body",
            text=body_text,
            color=self.ovf.text_colour,
            x=x,
            y=y + 20,
            ttl=0,
            size="normal",
        )

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
        Debug.logger.info(f"Saved {self.ovf} frames to EDMC config")
        self._draw_overlay()
        return True

    def _load_prefs(self) -> None:
        """Read frame data from the EDMC config."""

        conf = config.get(f"{OVERLAY_NAME}_overlay", {})
        Debug.logger.debug(f"Loading config: {conf}")
        try:
            data: dict = json.loads(conf)
            self.ovf = OvFrame(**data)
        except Exception:
            self.ovf = OvFrame()
