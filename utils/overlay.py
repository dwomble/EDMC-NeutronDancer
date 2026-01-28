import textwrap
import json
import re
from dataclasses import dataclass, asdict
from functools import partial

import tkinter as tk
from tkinter import ttk, colorchooser as tkColorChooser
import myNotebook as nb # type: ignore

from config import config # type:ignore

from .debug import Debug

# Unique name for this plugin.
PLUGIN="EDMC-NeutronDancer"

TAG_OVERLAY_HIGHLIGHT: str = "<H>"

DEF_OVERLAY_WIDTH = 1280  # Virtual screen width of overlay
DEF_OVERLAY_HEIGHT = 960  # Virtual screen height of overlay

DEF_STD_CHAR_WIDTH = 4
DEF_STD_CHAR_HEIGHT = 14
DEF_LRG_CHAR_WIDTH = 7
DEF_LRG_CHAR_HEIGHT = 20
DEF_PANEL_MAX_LINES = 30

@dataclass
class Frame:
    """ Details of a single overlay frame """
    name:str = ''
    enabled:bool = True
    x:int = 0
    y:int = 0
    w:int = 0
    h:int = 0
    centered_x:bool = False
    centered_y:bool = False
    ttl:int = 0
    title_colour:str = 'white'
    text_colour:str = 'white'
    background:str = 'grey'
    border:str = ''
    border_colour:str = ''
    border_width:int = 0
    anchor:str = "nw"
    justification:str = "left" if centered_x == False else "center"
    text_size:str = "normal"

class OverlayManager:
    """
    Class to use the EDMC game overlay.
        * Supports text, progress bars, indicators, and shapes.
        * Provides functions to display information and data in frames on screen
        * Handles loading and saving of frame preferences.
    """
    # Singleton pattern
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, **kw):
        self.edmcoverlay:Overlay|None = None # type: ignore
        self.is_legacy:bool = False
        self.problem_displaying:bool = False

        self.overlay_width:int = kw.get('width', DEF_OVERLAY_WIDTH)
        self.overlay_height:int = kw.get('height', DEF_OVERLAY_HEIGHT)
        self.std_char_width:int = kw.get('std_char_width', DEF_STD_CHAR_WIDTH)
        self.std_char_height:int = kw.get('std_char_height', DEF_STD_CHAR_HEIGHT)
        self.lrg_char_width:int = kw.get('lrg_char_width', DEF_LRG_CHAR_WIDTH)
        self.lrg_char_height:int = kw.get('lrg_char_height', DEF_LRG_CHAR_HEIGHT)
        self.panel_max_lines:int = kw.get('panel_max_lines', DEF_PANEL_MAX_LINES)

        self.frames:dict[str, Frame] = {}

        self._check_overlay()

        #self._setup_plugin_groups() # Setup plugin groups for EDMCModernOverlay if available
        self._declare_ready()

        self._initialized = True


    def register_frame(self, name:str, **kw) -> None:
        """ Register a frame with the overlay handler. """
        Debug.logger.debug(f"Registering frame {name}")
        try:
            self.frames[name] = Frame(name, **kw)
            Debug.logger.debug(f"Registered frame: {name}")
            self._load_frame(name)
        except TypeError as e:
            Debug.logger.warning(f"Cannot register frame: {e}")

        Debug.logger.debug(f"{self.frames}")


    """
    Display functions
    """
    def display_message(self, frame:str, message:str, fit_to_text:bool = False, ttl_override:int|None = None, text_colour_override:str|None = None, title_colour_override:str|None = None, title:str|None = None):
        """ Display a message in an overlay frame """
        if self.edmcoverlay == None: return
        if message == "": return

        if frame not in self.frames: return
        fi:Frame = self.frames[frame]

        # Split text on line breaks, then limit length of each line
        lines: list = message.splitlines()
        segments: list = []
        for line in lines:
            segments += textwrap.wrap(line, width = 80, subsequent_indent = '  ')

        message_width: int = len(max(segments, key = len)) * DEF_STD_CHAR_WIDTH if fi.text_size == "normal" else len(max(segments, key = len)) * DEF_LRG_CHAR_WIDTH
        message_height: int = len(segments) * DEF_STD_CHAR_HEIGHT if fi.text_size == "normal" else len(segments) * DEF_LRG_CHAR_HEIGHT
        ttl: int = ttl_override if ttl_override else int(fi.ttl)
        title_colour: str = title_colour_override if title_colour_override else fi.title_colour
        text_colour: str = text_colour_override if text_colour_override else fi.text_colour
        # Let EDMCModernOverlay handle centering and right alignment via define_plugin_group for frame_names we've fully registered.

        x:int = int(fi.x)
        if fi.centered_x:
            x: int = int(DEF_OVERLAY_WIDTH / 2) + fi.x   # Let EDMCModernOverlay plugin group handle horizontally centering
        elif fi.x < 0:
            x: int = DEF_OVERLAY_WIDTH # Let EDMCModernOverlay plugin group handle right offset

        if self.is_legacy:
            if fi.centered_x:
                x: int = int((DEF_OVERLAY_WIDTH - message_width) / 2) + fi.x   # Horizontally centred, offset by 'x' where 'x' can be negative
            elif fi.x < 0:
                x: int = DEF_OVERLAY_WIDTH + fi.x # Negative 'x', offset from right of overlay

        y:int = int(fi.y)
        if fi.centered_y:
            y = int(DEF_OVERLAY_HEIGHT / 2) + fi.y   # Let EDMCModernOverlay plugin group handle vertically centering
        elif fi.y < 0:
            y = DEF_OVERLAY_HEIGHT # Let EDMCModernOverlay plugin group handle bottom offset

        if self.is_legacy:
            if fi.centered_y:
                y = int((DEF_OVERLAY_HEIGHT - message_height) / 2) + fi.y # Vertically centred, offset by 'y' where 'y' can be negative
            elif fi.y < 0:
                y = DEF_OVERLAY_HEIGHT + fi.y # Negative 'y', offset from bottom of overlay

        try:
            # Border. Only send if background shading isn't handled by EDMCModernOverlay.
            if fi.border and fi.background and self.is_legacy:
                self.edmcoverlay.send_shape(f"{PLUGIN}-frame-{frame}", "rect", fi.border, fi.background, x, y, message_width + 30 if fit_to_text else fi.w, message_height + 10 if fit_to_text else fi.h, ttl=ttl)

            yoffset:int = 0
            indexint = 0
            message_x:int = x + 10 if self.is_legacy or fi.centered_x == False else  x # Let EDMCModernOverlay handle centering via the plugin group definition.

            while index <= DEF_PANEL_MAX_LINES:
                if index < len(segments):
                    if segments[index].find(TAG_OVERLAY_HIGHLIGHT) > -1:
                        self.edmcoverlay.send_message(f"{PLUGIN}-msg-{frame}-{index}", segments[index].replace(TAG_OVERLAY_HIGHLIGHT, ''), title_colour, message_x, y + 5 + yoffset, ttl=ttl, size="large")
                        yoffset += DEF_LRG_CHAR_HEIGHT
                    else:
                        if index < DEF_PANEL_MAX_LINES:
                            # Line has content
                            self.edmcoverlay.send_message(f"{PLUGIN}-msg-{frame}-{index}", segments[index], text_colour, message_x, y + 5 + yoffset, ttl=ttl, size=fi.text_size)
                        else:
                            # Last line
                            self.edmcoverlay.send_message(f"{PLUGIN}-msg-{frame}-{index}", "[...]", text_colour, message_x, y + 5 + yoffset, ttl=ttl, size=fi.text_size)

                        yoffset += DEF_STD_CHAR_HEIGHT
                else:
                    # Unused line, clear
                    self.edmcoverlay.send_message(f"{PLUGIN}-msg-{frame}-{index}", "", text_colour, message_x, y + 5 + yoffset, ttl=ttl, size=fi.text_size)
                    yoffset += DEF_STD_CHAR_HEIGHT

                index += 1

            self.problem_displaying = False

        except Exception as e:
            if self.problem_displaying == True: return
            # Only log a warning about failure once
            Debug.logger.warning(f"Could not display overlay message", exc_info=e)
            self.problem_displaying = True


    def display_indicator(self, frame:str, ttl_override:int|None = None, fill_colour_override:str|None = None, border_colour_override:str|None = None):
        """ Display a rectangular indicator """
        if self.edmcoverlay == None or frame not in self.frames: return
        fi:Frame = self.frames[frame]

        ttl:int = ttl_override if ttl_override else int(fi.ttl)
        fill_colour:str = fill_colour_override if fill_colour_override else fi.background
        border_colour:str = border_colour_override if border_colour_override else fi.border

        try:
            self.edmcoverlay.send_shape(f"{PLUGIN}-frame-{frame}", "rect", border_colour, fill_colour, int(fi.x), int(fi.y), int(fi.w), int(fi.h), ttl=ttl)
            self.problem_displaying = False
        except Exception as e:
            if self.problem_displaying == True: return
            # Only log a warning about failure once
            Debug.logger.warning(f"Could not display overlay message", exc_info=e)
            self.problem_displaying = True


    def display_progress_bar(self, frame:str, message:str, progress:float = 0, ttl_override:int|None = None):
        """
        Display a progress bar with a message
        """
        if self.edmcoverlay == None or frame not in self.frames: return
        fi:Frame = self.frames[frame]


        ttl: int = ttl_override if ttl_override else int(fi.ttl)
        bar_width: int = int(int(fi.w) * progress)
        bar_height: int = 10

        try:
            self.edmcoverlay.send_message(f"{PLUGIN}-msg-{frame}", message, fi.text_colour, int(fi.x) + 10, int(fi.y) + 5, ttl=ttl, size=fi.text_size)
            self.edmcoverlay.send_shape(f"{PLUGIN}-bar-{frame}", "rect", "#ffffff", fi.background, int(fi.x) + 10, int(fi.y) + 20, bar_width, bar_height, ttl=ttl)
            self.edmcoverlay.send_shape(f"{PLUGIN}-frame-{frame}", "rect", "#ffffff", fi.border, int(fi.x) + 10 + bar_width, int(fi.y) + 20, int(fi.w) - bar_width, bar_height, ttl=ttl)
            self.problem_displaying = False

        except Exception as e:
            if self.problem_displaying == True: return
            # Only log a warning about failure once
            Debug.logger.warning(f"Could not display overlay message", exc_info=e)
            self.problem_displaying = True


    def _check_overlay(self):
        """ Ensure overlay is running and available """
        if self.edmcoverlay != None: return

        # Do we have an overlay at all?
        try:
            from EDMCOverlay import edmcoverlay # type: ignore
        except ImportError:
            try:
                from edmcoverlay import edmcoverlay # type: ignore
            except ImportError:
                Debug.logger.warning(f"EDMCOverlay plugin is not installed")
                return

        # Is it running?
        try:
            self.edmcoverlay = edmcoverlay.Overlay()
        except Exception as e:
            Debug.logger.warning(f"EDMCOverlay is not running")
            return

        Debug.logger.info(f"EDMCOverlay is running")
        # Try to find out if the overlay running is EDMCModernOverlay
        try:
            from overlay_plugin.overlay_api import define_plugin_group as define_plugin_group # type: ignore
            self.is_legacy = False
        except Exception as e:
            self.is_legacy = True
            Debug.logger.info(f"Detected legacy EDMCOverlay")


    def _setup_plugin_groups(self):
        """ One time setup for EDMCModernOverlay Groups """
        if self.is_legacy: return

        background_color = None
        background_border_color = None
        background_border_width = 3 # This is a border that extends the background beyond the boundaries of the payload group.
        use_background = True
        progress_bar_frames = {"tw"}

        for frame_name, fi in self.frames.items():
            id_prefix_group = f"{PLUGIN} {frame_name.capitalize()}"
            id_prefixes:list[str | dict[str, object]] = [f"{PLUGIN}-msg-{frame_name}-"]
            if frame_name in progress_bar_frames:
                id_prefixes.append(f"{PLUGIN}-bar-{frame_name}")

            if fi is not None:
                background_color = fi.background
                background_border_color = fi.border_colour
                justification = fi.justification
                anchor = fi.anchor
                x_center = fi.centered_x
                y_center = fi.centered_y

                # Make anchor assumptions based on x_center and y_center configs
                if x_center and y_center:
                    anchor = "center"
                elif x_center:
                    anchor = "top"
                elif y_center:
                    anchor = "left"

                if x_center:
                    justification = "center"

            if anchor in ["ne", "right", "se"]:
                # Assume a right side anchor means we're on the right side of the screen and force a small offset to avoid clipping.
                id_prefix_offset_x = -5
                justification = "right" # this does not work well with vector images.
            else:
                id_prefix_offset_x = None

            if use_background:
                if self._define_plugin_group(
                    plugin_group=PLUGIN,
                    matching_prefixes=["{PLUGIN}-"],
                    id_prefix_group=id_prefix_group,
                    id_prefixes=id_prefixes,
                    id_prefix_offset_x=id_prefix_offset_x,
                    background_color=background_color,
                    background_border_color=background_border_color,
                    background_border_width=background_border_width,
                    payload_justification=justification,
                    id_prefix_group_anchor=anchor,
                    include_background=True,
                    disable_on_error=False
                ):
                    Debug.logger.info(f"EDMCModernOverlay plugin group '{id_prefix_group}' configured.")
                    continue

                Debug.logger.info(f"EDMCModernOverlay background args unavailable; falling back to previous define_plugin_group specification without background")
                use_background = False
                self.supports_modern_overlay_backgrounds = False

            id_prefixes.append({"value": f"{PLUGIN}-frame-{frame_name}", "matchMode": "exact"}) # For older Modern Overlay versions without background support.
            if not self._define_plugin_group(
                plugin_group=PLUGIN,
                matching_prefixes=["{PLUGIN}-"],
                id_prefix_group=id_prefix_group,
                id_prefixes=id_prefixes,
                id_prefix_offset_x=id_prefix_offset_x,
                background_color=background_color,
                background_border_color=background_border_color,
                background_border_width=background_border_width,
                payload_justification=justification,
                id_prefix_group_anchor=anchor,
                include_background=False,
                disable_on_error=True
            ):
                Debug.logger.info(f"EDMCModernOverlay plugin group '{id_prefix_group}' configured using previous define_plugin_group specification")
                break


    def _declare_ready(self):
        """ Declare to the overlay that we're ready by displaying a message """
        if self.edmcoverlay == None: return

        try:
            self.display_message("info", f"{PLUGIN} Ready", True, 30) # LANG: Overlay message
        except Exception as e:
            Debug.logger.warning(f"Could not declare overlay ready", exc_info=e)


    def _parse_int(self, value:str|None, default:int) -> int:
        if value is None: return default
        return int(value) if re.match(r"^[0-9\.]+$", value) else default


    def _parse_prefixes(self, value:str | None, default:list[str]) -> list[str]:
        if not value: return default

        prefixes = [prefix.strip() for prefix in value.split(",") if prefix.strip()]
        return prefixes or default


    def _define_plugin_group(
        self,
        *,
        plugin_group:str,
        matching_prefixes:list[str]|None = None,      # Broadly scope prefix(es) for the plugin group (different from payload group below). Should usually be ["{PLUGIN}-"]
        id_prefix_group:str|None = None,              # A human readable payload group name we are configuring. Should usually be "BGS-Tally {frame_name}"
        id_prefixes:list[str|dict[str, object]]|None = None,  # Prefixes to match for this payload group.
        id_prefix_group_anchor:str|None = None,
        id_prefix_offset_x:int|float|None = None,
        id_prefix_offset_y:int|float|None = None,
        payload_justification:str|None = None,
        marker_label_position:str|None = None,
        controller_preview_box_mode:str|None = None,
        background_color:str|None = None,
        background_border_color:str|None = None,
        background_border_width:int|None = None,
        include_background:bool = True,
        disable_on_error:bool = True,
    ) -> bool:
        """
        Register a plugin group with Modern Overlay if available.
        """
        if self.is_legacy or self.edmcoverlay == None: return False

        try:
            kwargs = dict(
                plugin_group=plugin_group,
                matching_prefixes=matching_prefixes,
                id_prefix_group=id_prefix_group,
                id_prefixes=id_prefixes,
                id_prefix_group_anchor=id_prefix_group_anchor,
                id_prefix_offset_x=id_prefix_offset_x,
                id_prefix_offset_y=id_prefix_offset_y,
                payload_justification=payload_justification,
            )

            if include_background: # If the overlay supports background then we're not on a pre-0.7.6 version of EDMCModernOverlay.
                kwargs.update(
                    marker_label_position=marker_label_position,
                    controller_preview_box_mode=controller_preview_box_mode,
                    background_color=background_color,
                    background_border_color=background_border_color,
                    background_border_width=background_border_width,
                )
            define_plugin_group(**kwargs) # type: ignore
            return True
        except Exception as e:
            Debug.logger.debug("EDMCModernOverlay define_plugin_group failed", exc_info=e)
            if disable_on_error:
                self.is_legacy = True
                Debug.logger.warning(f"Could not register EDMCModernOverlay plugin group. Reverting to legacy EDMCOverlay. Most likely due to an outdated version of EDMCModernOverlay (pre 0.7.6)")

        return False


    def _save_frames(self) -> bool:
        """ Serialize and save the frames dictionary to EDMC config. """
        # Convert frames dictionary to a serializable format
        frames_data = {}
        for frame_name, frame in self.frames.items():
            frames_data[frame_name] = asdict(frame)

        # Store the serialized frames in the config
        config.set(f"{PLUGIN}_overlay_frames", json.dumps(frames_data))
        Debug.logger.info(f"Saved {len(self.frames)} frames to EDMC config")
        return True


    def _load_frame(self, name:str):
        """ Read frame data from the EDMC config. """

        conf = config.get(f"{PLUGIN}_overlay_frames")
        if conf == None:
            return
        Debug.logger.debug(f"{conf}")
        prefs:dict = json.loads(conf)
        if name in prefs:
            self.frames[name] = prefs[name]


    def prefs_display(self, parent:ttk.Notebook) -> nb.Frame:
        """ EDMC settings pane hook. Displays one frame per row. """

        Debug.logger.debug(f"{self.edmcoverlay} {self.frames}")
        if self.edmcoverlay == None or self.frames == {}: return

        def color_picker(parent:nb.Frame, col:str) -> None:
            (_, color) = tkColorChooser.askcolor(col, title='Overlay Color', parent=parent)

            if color:
                col = color
                if colour_button is not None:
                    colour_button['foreground'] = color

        def validate_int(val:str) -> bool:
            return True if val.isdigit() or val == '' else False

        fr:nb.Frame = nb.Frame(parent)
        for frame, fi in self.frames.items():
            Debug.logger.debug(f"Overlay Frame: {frame} - {fi}")

            prefsfr:nb.Frame = nb.Frame(fr)
            prefsfr.columnconfigure(6, weight=1)
            prefsfr.rowconfigure(60, weight=1)

            validate:tuple = (prefsfr.register(validate_int), '%P')

            row:int = 0
            row += 1
            ttk.Separator(prefsfr).grid(row=row, columnspan=7, pady=(0,5), sticky=tk.EW)

            row += 1
            nb.Label(prefsfr, text=frame, justify=tk.LEFT).grid(row=row, column=0, padx=10, sticky=tk.NW)

            row += 1; col:int = 0
            nb.Checkbutton(prefsfr, text="Enable", variable=fi.enabled).grid(row=row, column=col, padx=10, pady=0, sticky=tk.W); col += 1

            nb.Label(prefsfr, text="Location").grid(row=row, column=col, padx=10, pady=5, sticky=tk.W); col += 1

            nb.Label(prefsfr, text='X').grid(row=row, column=col, padx=5, pady=5, sticky=tk.W); col += 1
            nb.EntryMenu(prefsfr, text=fi.x, textvariable=fi.x, width=8, validate='all', validatecommand=(validate, '%P')).grid(row=row, column=col, padx=5, pady=5, sticky=tk.W); col += 1

            nb.Label(prefsfr, text='Y').grid(row=row, column=col, padx=5, pady=5, sticky=tk.W); col += 1
            nb.EntryMenu(prefsfr, text=fi.y, textvariable=fi.y, width=8, validate='all', validatecommand=(validate, '%P')).grid(row=row, column=col, padx=5, pady=5, sticky=tk.W); col += 1

            nb.Label(prefsfr, text='W').grid(row=row, column=col, padx=5, pady=5, sticky=tk.W); col += 1
            nb.EntryMenu(prefsfr, text=fi.w, textvariable=fi.w, width=8, validate='all', validatecommand=(validate, '%P')).grid(row=row, column=col, padx=5, pady=5, sticky=tk.W); col += 1

            nb.Label(prefsfr, text='H').grid(row=row, column=col, padx=5, pady=5, sticky=tk.W); col += 1
            nb.EntryMenu(prefsfr, text=fi.h, textvariable=fi.h, width=8, validate='all', validatecommand=(validate, '%P')).grid(row=row, column=col, padx=5, pady=5, sticky=tk.W); col += 1

            colour_button:tk.Button = tk.Button(prefsfr, text="Color", foreground=fi.text_colour, background=fi.background, command=partial(color_picker, prefsfr, fi.text_colour))
            colour_button.grid(row=row, column=col, padx=10, pady=5, sticky=tk.W)

        return prefsfr

    def prefs_save(self) -> None:
        return
