import textwrap
import json
from dataclasses import dataclass, asdict

import tkinter as tk
from tkinter import ttk, colorchooser as tkColorChooser
from ttkHyperlinkLabel import HyperlinkLabel # type: ignore
import myNotebook as nb # type: ignore

from config import config # type: ignore

from .debug import Debug

try:
    from EDMCOverlay import edmcoverlay
except ImportError:
    try:
        from edmcoverlay import edmcoverlay
    except ImportError:
        edmcoverlay = None

# Unique name for this plugin.
PLUGIN="EDMC-NeutronDancer"

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
    name:str
    x:int
    y:int
    w:int
    h:int
    centered:bool
    ttl:int
    text_size:str
    title_color:str
    text_colour:str
    background:str
    border:str
    border_width:int

class Overlay:
    """
    Class to use the EDMC game overlay.
        * Supports text, progress bars, indicators, and shapes.
        * Provides functions to display information and data in frames on screen
        * Handles loading and saving of frame preferences.
    """
    def __init__(self, **kw):
        self.edmcoverlay:Overlay|None = None
        self.is_modern_overlay:bool = False
        self.supports_modern_overlay_backgrounds:bool = False
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
        self._load_frames()
        self._setup_plugin_groups() # Setup plugin groups for EDMCModernOverlay if available
        self._declare_ready()


    def register_frame(self, **kw) -> None:
        """ Register a frame with the overlay handler. """
        try:
            self.frames[kw['name']] = Frame(**kw)
            Debug.logger.debug(f"Registered frame: {kw['name']}")
            self._load_frames()
        except TypeError as e:
            Debug.logger.warning(f"Cannot register frame: {e}")


    """
    Display functions
    """
    def display_message(self, frame:str, message:str, fit_to_text:bool = False, ttl_override:int|None = None, text_colour_override:str|None = None, title_colour_override:str|None = None, title:str|None = None):
        """ Display a message in an overlay frame """
        if self.edmcoverlay == None: return
        if message == "": return

        try:
            if frame not in self.frames: return
            fi:Frame = self.frames[frame]

            # Split text on line breaks, then limit length of each line
            lines: list = message.splitlines()
            segments: list = []
            for line in lines:
                segments += textwrap.wrap(line, width = 80, subsequent_indent = '  ')

            message_width: int = len(max(segments, key = len)) * DEF_STD_CHAR_WIDTH if fi['text_size'] == "normal" else len(max(segments, key = len)) * DEF_LRG_CHAR_WIDTH
            message_height: int = len(segments) * DEF_STD_CHAR_HEIGHT if fi['text_size'] == "normal" else len(segments) * DEF_LRG_CHAR_HEIGHT
            ttl: int = ttl_override if ttl_override else int(fi['ttl'])
            title_colour: str = title_colour_override if title_colour_override else fi['title_colour']
            text_colour: str = text_colour_override if text_colour_override else fi['text_colour']

            # Let EDMCModernOverlay handle centering and right alignment via define_plugin_group for frame_names we've fully registered.
            x_center = fi.get('x_center', False)
            x_value = int(fi['x'])
            if self.is_modern_overlay:
                if x_center:
                    x: int = int(DEF_OVERLAY_WIDTH / 2) + x_value   # Let EDMCModernOverlay plugin group handle horizontally centering
                elif x_value < 0:
                    x: int = DEF_OVERLAY_WIDTH # Let EDMCModernOverlay plugin group handle right offset
                else:
                    x: int = x_value
            else:
                if x_center:
                    x: int = int((DEF_OVERLAY_WIDTH - message_width) / 2) + x_value   # Horizontally centred, offset by 'x' where 'x' can be negative
                elif x_value < 0:
                    x: int = DEF_OVERLAY_WIDTH + x_value # Negative 'x', offset from right of overlay
                else:
                    x: int = x_value

            y_center = fi.get('y_center', False)
            y_value = int(fi['y'])
            if self.is_modern_overlay:
                if y_center:
                    y: int = int(DEF_OVERLAY_HEIGHT / 2) + y_value   # Let EDMCModernOverlay plugin group handle vertically centering
                elif y_value < 0:
                    y: int = DEF_OVERLAY_HEIGHT # Let EDMCModernOverlay plugin group handle bottom offset
                else:
                    y: int = y_value
            else:
                if fi.get('y_center', False):
                    y: int = int((DEF_OVERLAY_HEIGHT - message_height) / 2) + y_value # Vertically centred, offset by 'y' where 'y' can be negative
                elif y_value < 0:
                    y: int = DEF_OVERLAY_HEIGHT + y_value # Negative 'y', offset from bottom of overlay
                else:
                    y: int = y_value

            # Border. Only send if background shading isn't handled by EDMCModernOverlay.
            if fi['border_colour'] and fi['fill_colour'] and not self.supports_modern_overlay_backgrounds:
                self.edmcoverlay.send_shape(f"bgstally-frame-{frame}", "rect", fi['border_colour'], fi['fill_colour'], x, y, message_width + 30 if fit_to_text else fi['w'], message_height + 10 if fit_to_text else fi['h'], ttl=ttl)

            yoffset: int = 0
            index: int = 0
            message_x: int = x if self.is_modern_overlay and x_center else x + 10 # Let EDMCModernOverlay handle centering via the plugin group definition.

            while index <= DEF_PANEL_MAX_LINES:
                if index < len(segments):
                    if segments[index].find(TAG_OVERLAY_HIGHLIGHT) > -1:
                        self.edmcoverlay.send_message(f"bgstally-msg-{frame}-{index}", segments[index].replace(TAG_OVERLAY_HIGHLIGHT, ''), title_colour, message_x, y + 5 + yoffset, ttl=ttl, size="large")
                        yoffset += DEF_LRG_CHAR_HEIGHT
                    else:
                        if index < DEF_PANEL_MAX_LINES:
                            # Line has content
                            self.edmcoverlay.send_message(f"bgstally-msg-{frame}-{index}", segments[index], text_colour, message_x, y + 5 + yoffset, ttl=ttl, size=fi['text_size'])
                        else:
                            # Last line
                            self.edmcoverlay.send_message(f"bgstally-msg-{frame}-{index}", "[...]", text_colour, message_x, y + 5 + yoffset, ttl=ttl, size=fi['text_size'])

                        yoffset += DEF_STD_CHAR_HEIGHT
                else:
                    # Unused line, clear
                    self.edmcoverlay.send_message(f"bgstally-msg-{frame}-{index}", "", text_colour, message_x, y + 5 + yoffset, ttl=ttl, size=fi['text_size'])
                    yoffset += DEF_STD_CHAR_HEIGHT

                index += 1

            self.problem_displaying = False

        except Exception as e:
            if not self.problem_displaying:
                # Only log a warning about failure once
                self.problem_displaying = True
                Debug.logger.warning(f"Could not display overlay message", exc_info=e)


    def display_indicator(self, frame_name: str, ttl_override: int = None, fill_colour_override: str = None, border_colour_override: str = None):
        """
        Display a rectangular indicator
        """
        if self.edmcoverlay == None: return
        if not self.bgstally.state.enable_overlay: return

        try:
            fi: dict | None = self.bgstally.config.overlay_frame(frame_name)
            if fi is None: return

            ttl: int = ttl_override if ttl_override else int(fi['ttl'])
            fill_colour: str = fill_colour_override if fill_colour_override else fi['fill_colour']
            border_colour: str = border_colour_override if border_colour_override else fi['border_colour']
            self.edmcoverlay.send_shape(f"bgstally-frame-{frame_name}", "rect", border_colour, fill_colour, int(fi['x']), int(fi['y']), int(fi['w']), int(fi['h']), ttl=ttl)

            self.problem_displaying = False

        except Exception as e:
            if not self.problem_displaying:
                # Only log a warning about failure once
                self.problem_displaying = True
                Debug.logger.warning(f"Could not display overlay message", exc_info=e)


    def display_progress_bar(self, frame_name: str, message: str, progress: float = 0, ttl_override: int = None):
        """
        Display a progress bar with a message
        """
        if self.edmcoverlay == None: return
        if not self.bgstally.state.enable_overlay: return

        try:
            fi: dict | None = self.bgstally.config.overlay_frame(frame_name)
            if fi is None: return

            ttl: int = ttl_override if ttl_override else int(fi['ttl'])
            bar_width: int = int(int(fi['w']) * progress)
            bar_height: int = 10

            #vect:list = [{'x':int(cx+(coords['x']*hw)), 'y':int(cy-(coords['y']*hh))]

            self.edmcoverlay.send_message(f"bgstally-msg-{frame_name}", message, fi['text_colour'], int(fi['x']) + 10, int(fi['y']) + 5, ttl=ttl, size=fi['text_size'])
            self.edmcoverlay.send_shape(f"bgstally-bar-{frame_name}", "rect", "#ffffff", fi['fill_colour'], int(fi['x']) + 10, int(fi['y']) + 20, bar_width, bar_height, ttl=ttl)
            self.edmcoverlay.send_shape(f"bgstally-frame-{frame_name}", "rect", "#ffffff", fi['border_colour'], int(fi['x']) + 10 + bar_width, int(fi['y']) + 20, int(fi['w']) - bar_width, bar_height, ttl=ttl)

            self.problem_displaying = False

        except Exception as e:
            if not self.problem_displaying:
                # Only log a warning about failure once
                self.problem_displaying = True
                Debug.logger.warning(f"Could not display overlay message", exc_info=e)


    def _check_overlay(self):
        """
        Ensure overlay is running and available
        """
        if edmcoverlay:
            try:
                # Try to find out if the overlay running is EDMCModernOverlay
                try:
                    from overlay_plugin.overlay_api import define_plugin_group as _define_plugin_group
                except Exception:
                    self.is_modern_overlay = False
                    self.supports_modern_overlay_backgrounds = False
                    Debug.logger.info(f"Detected legacy EDMCOverlay")
                else:
                    self.is_modern_overlay = True
                    self.supports_modern_overlay_backgrounds = True
                    Debug.logger.info(f"Detected EDMCModernOverlay")
                self.edmcoverlay = edmcoverlay.Overlay()
            except Exception as e:
                Debug.logger.warning(f"EDMCOverlay is not running")
            else:
                Debug.logger.info(f"EDMCOverlay is running")
        else:
            # Couldn't load edmcoverlay python lib, the plugin probably isn't installed
            Debug.logger.warning(f"EDMCOverlay plugin is not installed")


    def _setup_plugin_groups(self):
        # One time setup for EDMCModernOverlay Groups
        if not self.is_modern_overlay:
            return

        overlay_frame_names = self.bgstally.config.overlay_frame_names()
        background_color = None
        background_border_color = None
        background_border_width = 3 # This is a border that extends the background beyond the boundaries of the payload group.
        use_background = True
        progress_bar_frames = {"tw"}

        for frame_name in overlay_frame_names:
            id_prefix_group = f"BGS-Tally {frame_name.capitalize()}"
            base_id_prefixes = [f"bgstally-msg-{frame_name}-"]
            if frame_name in progress_bar_frames:
                base_id_prefixes.append(f"bgstally-bar-{frame_name}")

            fi: dict | None = self.bgstally.config.overlay_frame(frame_name)
            if fi is not None:
                background_color = fi['fill_colour']
                background_border_color = fi['border_colour']
                justification = fi.get("justification", "left")
                anchor = fi.get("anchor", "nw")
                x_center = fi.get("x_center", False)
                y_center = fi.get("y_center", False)

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
                id_prefixes = list(base_id_prefixes)
                if self._define_plugin_group(
                    plugin_group=self.bgstally.plugin_name,
                    matching_prefixes=["bgstally-"],
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

            id_prefixes = list(base_id_prefixes)
            id_prefixes.append({"value": f"bgstally-frame-{frame_name}", "matchMode": "exact"}) # For older Modern Overlay versions without background support.
            if not self._define_plugin_group(
                plugin_group=self.bgstally.plugin_name,
                matching_prefixes=["bgstally-"],
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
        """
        Declare to the overlay that BGS-Tally is ready
        """
        if self.edmcoverlay == None: return
        if not self.bgstally.state.enable_overlay: return

        try:
            self.display_message("info", _("{plugin_name} Ready").format(plugin_name=self.bgstally.plugin_name), True, 30) # LANG: Overlay message
        except Exception as e:
            Debug.logger.warning(f"Could not declare overlay ready", exc_info=e)


    def _parse_int(self, value:str | None, default:int) -> int:
        if value is None:
            return default

        try:
            return int(value)
        except (TypeError, ValueError):
            return default


    def _parse_prefixes(self, value:str | None, default:list[str]) -> list[str]:
        if not value:
            return default

        prefixes = [prefix.strip() for prefix in value.split(",") if prefix.strip()]
        return prefixes or default


    def _define_plugin_group(
        self,
        *,
        plugin_group: str,
        matching_prefixes: list[str] | None = None,      # Broadly scope prefix(es) for the plugin group (different from payload group below). Should usually be ["bgstally-"]
        id_prefix_group: str | None = None,              # A human readable payload group name we are configuring. Should usually be "BGS-Tally {frame_name}"
        id_prefixes: list[str | dict[str, object]] | None = None,  # Prefixes to match for this payload group.
        id_prefix_group_anchor: str | None = None,
        id_prefix_offset_x: int | float | None = None,
        id_prefix_offset_y: int | float | None = None,
        payload_justification: str | None = None,
        marker_label_position: str | None = None,
        controller_preview_box_mode: str | None = None,
        background_color: str | None = None,
        background_border_color: str | None = None,
        background_border_width: int | None = None,
        include_background: bool = True,
        disable_on_error: bool = True,
    ) -> bool:
        """
        Register a plugin group with Modern Overlay if available.
        """
        if not self.is_modern_overlay:
            return False

        try:
            from overlay_plugin.overlay_api import define_plugin_group as _define_plugin_group
        except Exception:
            self.is_modern_overlay = False
            self.supports_modern_overlay_backgrounds = False
            return False

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
            _define_plugin_group(**kwargs)
        except Exception as e:
            Debug.logger.debug("EDMCModernOverlay define_plugin_group failed", exc_info=e)
            if disable_on_error:
                self.is_modern_overlay = False
                self.supports_modern_overlay_backgrounds = False
                Debug.logger.warning(f"Could not register EDMCModernOverlay plugin group. Reverting to legacy EDMCOverlay. Most likely due to an outdated version of EDMCModernOverlay (pre 0.7.6)")
            return False

        return True


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


    def _load_frames(self):
        """ Read frame data from the EDMC config. """
        prefs:dict = json.loads(config.get(f"{PLUGIN}_overlay_frames")):
        for name in self.frames.keys():
            if name in prefs: self.frames[name] = prefs[name]


    def prefs_display(self, parent:ttk.Notebook) -> nb.Frame:
        """ EDMC settings pane hook. Displays one frame per row. """

        def color_picker() -> None:
            (_, color) = tkColorChooser.askcolor(Context.overlay_color.get(), title='Overlay Color', parent=Context.parent)

            if color:
                Context.overlay_color.set(color)
                if colour_button is not None:
                    colour_button['foreground'] = color

        def validate_int(val:str) -> bool:
            return True if val.isdigit() or val == '' else False

        if self.edmcoverlay == None or self.frames == {}: return


        frame:nb.Frame = nb.Frame(parent)
        frame.columnconfigure(6, weight=1)
        frame.rowconfigure(60, weight=1)

        validate:tuple = (frame.register(validate_int), '%P')

        row:int = 0
        nb.Label(frame, text=Context.plugin_name, justify=tk.LEFT, font=BOLD).grid(row=row, column=0, columnspan=2, padx=10, pady=10, sticky=tk.NW)
        HyperlinkLabel(frame, text=f"{cnf['version']} {Context.plugin_version}", url=f"{GIT_RELEASES}/v{Context.plugin_version}", justify=tk.RIGHT).grid(row=row, column=2, columnspan=5, padx=10, pady=10, sticky=tk.NE)

        row += 1
        ttk.Separator(frame).grid(row=row, columnspan=7, pady=(0,5), sticky=tk.EW)

        row += 1
        nb.Label(frame, text=cnf['overlay'], justify=tk.LEFT, font=BOLD).grid(row=row, column=0, padx=10, sticky=tk.NW)

        row += 1; col:int = 0
        nb.Checkbutton(frame, text=cnf['overlay_enable'], variable=Context.overlay).grid(row=row, column=col, padx=10, pady=0, sticky=tk.W); col += 1

        nb.Label(frame, text=cnf['overlay_position']).grid(row=row, column=col, padx=10, pady=5, sticky=tk.W); col += 1

        nb.Label(frame, text=cnf['X']).grid(row=row, column=col, padx=5, pady=5, sticky=tk.W); col += 1
        nb.EntryMenu(frame, text=Context.overlay_x.get(), textvariable=Context.overlay_x, width=8, validate='all', validatecommand=(validate, '%P')).grid(row=row, column=col, padx=5, pady=5, sticky=tk.W); col += 1

        nb.Label(frame, text=cnf['Y']).grid(row=row, column=col, padx=5, pady=5, sticky=tk.W); col += 1
        nb.EntryMenu(frame, text=Context.overlay_y.get(), textvariable=Context.overlay_y, width=8, validate='all', validatecommand=(validate, '%P')).grid(row=row, column=col, padx=5, pady=5, sticky=tk.W); col += 1

        colour_button:tk.Button = tk.Button(frame, text=cnf['overlay_colour'], foreground=Context.overlay_color.get(), command=lambda: color_picker())
        colour_button.grid(row=row, column=col, padx=10, pady=5, sticky=tk.W)

        return frame


    def prefs_save() -> None:
        """ Save preferences to config """
        config.set('neutrondancer-overlay', Context.overlay.get())
        config.set('neutrondancer-overlay-color', Context.overlay_color.get())
        config.set('neutrondancer-overlay-x', Context.overlay_x.get())
        config.set('neutrondancer-overlay-y', Context.overlay_y.get())
