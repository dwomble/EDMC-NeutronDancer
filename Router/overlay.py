import json
from dataclasses import dataclass, asdict
from functools import partial
from datetime import datetime, timedelta
from threading import Thread, Event
from math import floor
from datetime import UTC, datetime, timedelta
from copy import deepcopy

import tkinter as tk
from tkinter import ttk, colorchooser as tkColorChooser
import myNotebook as nb # type: ignore

try:
    from EDMCOverlay import edmcoverlay # type: ignore
    from overlay_plugin.overlay_api import define_plugin_group # type: ignore
except ImportError:
    edmcoverlay = None

from config import config # type: ignore
#from edmc_data import GuiFocusNoFocus, FlagsInMainShip, GuiFocusGalaxyMap # type: ignore
import edmc_data # type: ignore

from utils.debug import Debug, catch_exceptions
from .context import Context

#FLAGS = [edmc_data.FlagsDocked, edmc_data.FlagsLanded, edmc_data.FlagsLandingGearDown, edmc_data.FlagsShieldsUp, edmc_data.FlagsSupercruise,
#         edmc_data.FlagsFlightAssistOff, edmc_data.FlagsHardpointsDeployed, edmc_data.FlagsInWing]
@dataclass
class OvFrame:
    """ Overlay frame details """
    name:str = 'Default'
    enabled:bool = True # Preference state
    visible:bool = True # Current visibility state
    text_colour:str = "#ffffff"
    ttl:int = 0

class Overlay():
    """
    Overlay frame manager.
     - Currently it just supports a single frame and simple messages but will be extended in future.
     - Each frame can display multiple messages with different text sizes.
    """

    # Singleton pattern
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance


    def __init__(self) -> None:
        # Only initialize if it's the first time
        if hasattr(self, '_initialized'): return

        self.ovfrs:dict[str, OvFrame] = {'Default': OvFrame(), 'Galaxy Map': OvFrame(), 'Carrier': OvFrame()}
        self.stoppers:dict[str, Event] = {}
        self._load_prefs()
        for k, fr in self.ovfrs.items():
            fr.name = k
            self.create_frame(Context.plugin_name, fr)

        self.msgs:dict = {}
        self._initialized = True


    def _get_overlay(self):
        """ Is an overlay installed and running? """
        if not edmcoverlay:
            Debug.logger.warning(f"edmcoverlay plugin is not installed")
            return

        # Is it running?
        try:
            return edmcoverlay.Overlay()
        except Exception as e:
            Debug.logger.warning(f"EDMCOverlay is not running {e}")
            return


    def redraw_frames(self) -> None:
        """ Redraw all overlay frames """
        Debug.logger.debug(f"Redrawing frames")
        [self.redraw_frame(fr) for fr in self.msgs]

    def redraw_frame(self, frame:str = "") -> None:
        overlay = self._get_overlay()
        if not overlay or frame not in self.msgs: return
        self.ovfrs[frame].visible = True
        [overlay.send_message(**m) for m in self.msgs[frame].values()]


    def hide_frames(self) -> None:
        """ Clear all overlay frames """
        [self.hide_frame(fr) for fr in self.ovfrs]


    @catch_exceptions
    def hide_frame(self, frame:str = "") -> None:
        """ Clear a message frame """
        overlay = self._get_overlay()
        if not overlay or frame not in self.msgs: return

        self.ovfrs[frame].visible = False
        for m in self.msgs[frame].values():
            tmp:dict = deepcopy(m)
            tmp['ttl'] = 1
            tmp['text'] = ''
            Debug.logger.debug(f"Hiding frame {tmp}")
            overlay.send_message(**tmp)


    @catch_exceptions
    def create_frame(self, group:str, ovf:OvFrame) -> None:
        """ Initialize a frame """
        if not self._get_overlay(): return

        kw:dict = {
            'plugin_group': group,
            'matching_prefixes': f"{group}-",
            'id_prefix_group': f"{group} {ovf.name}",
            'id_prefixes': [f"{group}-{ovf.name}-"],
            'id_prefix_group_anchor': "nw",
            'payload_justification': "left",
            'marker_label_position': "below",
            'controller_preview_box_mode': "last",
        }
        define_plugin_group(**kw)

    @catch_exceptions
    def display_frame(self, frame:str = "", content:str|list[dict] = "", size:str = "normal", ttl:int = 120) -> None:
        """ Display/update a frame with a set of messages """

        overlay = self._get_overlay()
        Debug.logger.debug(f"Display called for {frame} {overlay}")
        if not overlay or frame not in self.ovfrs: return
        fr:OvFrame = self.ovfrs[frame]

        if fr.enabled == False: return

        if isinstance(content, str): content = [{'size': size, 'text': content}]

        self.ovfrs[frame].visible = True
        self.msgs[frame] = {}
        y:int = 0
        for i, c in enumerate(content):
            id:str = f"{Context.plugin_name}-{frame}-{i}"
            args:dict = {
                'msgid': id,
                'text': c.get('text', ''),
                'color': c.get('colour', fr.text_colour),
                'x': 0,
                'y': y,
                'ttl': c.get('ttl', ttl), # @TODO: ttl needs to be a datetime
                'size': c.get('size', 'normal')
            }
            if fr.visible == True:
                overlay.send_message(**args)
            if frame not in self.msgs: self.msgs[frame] = {}
            self.msgs[frame][id] = args
            y += 20 # @TODO This needs to adapt to text size


    def _timedelta_str(self, delta:timedelta) -> str:
        """ Display remaining time showing hh:mm:ss """
        s:int = delta.seconds
        unit:int = 60
        res:list = []
        while unit > 0:
            t, s = divmod(s, unit)
            unit = int(unit / 60)
            if t > 0 or unit < 3600:
                res.append(f"{t:02d}")
        return ':'.join(res)


    @catch_exceptions
    def _countdown(self, frame:str, content:str|list[dict], end:datetime, stop:Event) -> None:
        """ Update the countdown display frame until zero or stopped """
        rem:timedelta = end - datetime.now(tz=end.tzinfo)
        while rem.seconds > 0 and not stop.wait(1):
            rem = end - datetime.now(tz=end.tzinfo)
            display:list|str = [{k:v.format(t=self._timedelta_str(rem)) for k, v in c} for c in content] \
                if isinstance(content, list) else content.format(t=self._timedelta_str(rem))
            Context.overlay.display_frame(frame, display, ttl=1)

        stop.clear()
        Context.overlay.display_frame(frame, '', ttl=1)
        Debug.logger.debug("Countdown thread is ending.")


    def stop_countdown(self, frame:str) -> None:
        """ Stop a countdown display for a frame """
        if frame not in self.stoppers: return
        self.stoppers[frame].set()


    @catch_exceptions
    def display_countdown(self, frame:str, content:str|list[dict], end:datetime|int|None) -> None:
        """
        Like display message but with a countdown either until a specific time or for some number of seconds
        The countdown should be in a variable t in the content string
        """
        Debug.logger.debug(f"Countdown starting {content} {end}")
        if end == None or frame not in self.ovfrs: return
        if isinstance(end, int): end = datetime.now() + timedelta(seconds=end)
        self.stoppers[frame] = Event()
        Thread(target=self._countdown, args=(frame, content, end, self.stoppers[frame]),
                                             name=f"{Context.plugin_name}_{frame} overlay countdown worker").start()


    @catch_exceptions
    def dashboard_entry(self, cmdr:str, is_beta:bool, entry:dict) -> None:
        """ ED UI state change, store the current state """

        # Default frame, visible in ship main view only
        # Galaxy Map frame, visible in galaxy map only
        if not Context.route or not (bool(entry["Flags"] & edmc_data.FlagsInMainShip)):
            self.hide_frame('Default')
            self.hide_frame('Galaxy Map')
        elif entry.get("GuiFocus") == edmc_data.GuiFocusNoFocus:
            self.redraw_frame('Default')
            self.hide_frame('Galaxy Map')
        elif entry.get("GuiFocus") == edmc_data.GuiFocusGalaxyMap:
            self.ovfrs['Galaxy Map'].visible = True
            self.redraw_frame('Galaxy Map')
            self.hide_frame('Default')
        else:
            self.hide_frame('Default')
            self.hide_frame('Galaxy Map')

        # Carrier frame, visible in ship main view only
        if not bool(entry["Flags"] & edmc_data.FlagsInMainShip) or \
            entry.get("GuiFocus") not in [edmc_data.GuiFocusNoFocus]:
            self.hide_frame('Carrier')
        else:
            self.redraw_frame('Carrier')


    @catch_exceptions
    def prefs_display(self, parent:nb.Frame) -> nb.Frame:
        """ EDMC settings pane hook. Displays one frame per row. """

        def bind_var(data_obj, attribute, tk_var):
            # Update dataclass whenever the UI changes
            def update_obj(*args) -> None:
                setattr(data_obj, attribute, tk_var.get())

            tk_var.trace_add("write", update_obj)
            return tk_var

        def colour_picker(parent:nb.Frame, frame:str, which:str, col:tk.StringVar) -> None:
            (_, color) = tkColorChooser.askcolor(col.get(), title=which, parent=parent)

            if color:
                col.set(color)
                cbtns[frame].config(**{which.lower(): color})

        def validate_int(val:str) -> bool:
            return True if val.isdigit() or val == '' else False

        pref_opts:list = [
            ('enabled', 'Enable', tk.BooleanVar, tk.Checkbutton),
            ('text_colour', 'Foreground', tk.StringVar, 'ColorPicker'),
            ]

        # Hide existing messages. Redraw them in the new location when the user clicks save
        self.hide_frames()

        ovrprefs:nb.Frame = nb.Frame(parent)
        ovrprefs.columnconfigure(6, weight=1)
        ovrprefs.rowconfigure(60, weight=1)
        ovrprefs.grid()

        row:int = 0; col:int = 0
        nb.Label(ovrprefs, text="Overlays", justify=tk.LEFT).grid(row=row, column=0, padx=10, sticky=tk.NW); row += 1

        # Loop through the frames and create a preferences line for each
        vars:dict = {}; cbtns:dict = {}
        row += 1; col = 0
        for name, fr in self.ovfrs.items():
            nb.Label(ovrprefs, text=name, justify=tk.LEFT).grid(row=row, column=col, padx=10, pady=5, sticky=tk.W)
            col += 1
            for k in pref_opts:
                var = bind_var(fr, k[0], k[2](value=getattr(fr, k[0])))
                vars[f"{name}-{k[0]}"] = var
                match k[3]:
                    case tk.Checkbutton:
                        nb.Checkbutton(ovrprefs, text=k[1], variable=var).grid(row=row, column=col, padx=10, pady=0, sticky=tk.W)
                    case 'ColorPicker':
                        btn:tk.Button = tk.Button(ovrprefs, text=k[1], foreground=fr.text_colour, background="#555555",
                                                  command=partial(colour_picker, ovrprefs, name, k[1], var))
                        btn.grid(row=row, column=col, padx=5, pady=0, sticky=tk.W)
                        cbtns[name] = btn
                col += 1
            #row += 1
        return ovrprefs


    def save_prefs(self) -> bool:
        """ Serialize and save the frames dictionary to EDMC config. """
        # Store the serialized frames in the config

        for name, fr in self.ovfrs.items():
            config.set(f"{Context.plugin_name}_{name}_overlay", json.dumps(asdict(fr)))

        self.redraw_frames()
        Debug.logger.info(f"Saved frames to EDMC config")
        return True

    def _from_dict(self, name, data:dict) -> None:
        self.ovfrs[name] = OvFrame(**data)

    def _load_prefs(self) -> None:
        """ Read frame data from the EDMC config. """

        for name in self.ovfrs:
            conf:str|None = config.get(f"{Context.plugin_name}_{name}_overlay")
            if conf == None: continue
            data:dict = json.loads(conf)
            try:
                self.ovfrs[name] = OvFrame(**data)
            except:
                pass
