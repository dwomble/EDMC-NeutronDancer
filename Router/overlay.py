import json
from dataclasses import dataclass, asdict
from functools import partial
from datetime import datetime, timedelta
from threading import Thread, Event
from math import floor
from datetime import UTC, datetime, timedelta

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
    x:int = 0
    y:int = 0
    w:int = 0
    h:int = 0
    ttl:int = 0
    title_colour:str = 'white'
    text_colour:str = 'white'
    bgenabled:bool = False
    background:str = 'grey'
    border:str = ''
    border_width:int = 0
    anchor:str = "nw"
    justification:str = "left"
    text_size:str = "normal"
    stopper:Event = Event()

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

        self.ovfrs:dict[str, OvFrame] = {'Default': OvFrame(), 'Carrier': OvFrame()}
        self._load_prefs()
        self.create_frame(Context.appname, self.ovfrs['Default'])
        self.create_frame(Context.appname, self.ovfrs['Carrier'])
        self.src_msgs:dict = {}
        self.msgs:dict = {}

        self.state:dict = {}
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
            Debug.logger.warning(f"EDMCOverlay is not running")
            return


    def redraw_frames(self) -> None:
        """ Redraw all overlay frames """
        Debug.logger.debug(f"Redrawing mesages")
        [self.display_frame(m, text) for m, text in self.src_msgs.items()]


    def clear_frames(self) -> None:
        """ Clear all overlay frames """
        [self.clear_frame(fr) for fr in self.ovfrs]


    @catch_exceptions
    def clear_frame(self, frame:str = "") -> None:
        """ Clear a message frame """
        overlay = self._get_overlay()
        if not overlay or frame not in self.msgs: return

        # temporarily enable the frame if necessary
        status:bool = self.ovfrs[frame].enabled
        self.ovfrs[frame].enabled = True
        msg:dict = self.msgs[frame]
        msg['ttl'] = 1
        overlay.send_message(**msg)
        #del self.msgs[msgid]

        self.ovfrs[frame].enabled = status


    @catch_exceptions
    def create_frame(self, group:str, ovf:OvFrame) -> None:
        """ Initialize a frame """
        if not self._get_overlay(): return

        kw:dict = {
            'plugin_group': group,
            'matching_prefixes': f"{group}-",
            'id_prefix_group': ovf.name,
            'id_prefixes': [f"{group}-{ovf.name}-"],
            'id_prefix_group_anchor': ovf.anchor,
            'payloadJustification': ovf.justification,
            'marker_label_position': "below",
            'controller_preview_box_mode': "last",
        }

        if ovf.bgenabled:
            kw['background_color'] = ovf.background
            kw['background_border_width'] = ovf.border_width


    @catch_exceptions
    def display_frame(self, frame:str = "", content:str|list[dict] = "", size:str = "normal", ttl:int = 120) -> None:
        """ Display/update a frame with a set of messages """

        overlay = self._get_overlay()
        if not overlay or frame not in self.ovfrs: return
        fr:OvFrame = self.ovfrs[frame]

        if isinstance(content, str): content = [{'size': size, 'text': content}]

        y:int = fr.y
        for i, c in enumerate(content):
            id:str = f"{Context.appname}-{frame}-{i}"
            args:dict = {
                'msgid': id,
                'text': c.get('text', ''),
                'color': c.get('colour', fr.text_colour),
                'x': fr.x,
                'y': y,
                'ttl': ttl,
                'size': c.get('size', 'normal')
            }
            Debug.logger.debug(f"Sending overlay message {args}")
            overlay.send_message(**args)
            self.msgs[id] = args
            y += 20 # @TODO This needs to adapt to text size
        self.src_msgs[frame] = content


    def _timedelta_str(self, delta:timedelta) -> str:
        """ Display remaining time showing hh:mm:ss """
        days , rem = divmod(int(delta.seconds), 60*60*24)
        hours, rem = divmod(rem, 60*60)
        mins, secs = divmod(rem, 60)
        tmp:list = []
        if floor(days) > 1: tmp.append(f"{floor(days)} days")
        elif int(days) > 0: tmp.append(f"1 day")
        if floor(hours) > 1: tmp.append(f"{floor(hours)} hours")
        elif int(hours) > 0: tmp.append(f" 1 hour")
        if floor(mins) > 1 and len(tmp) < 2:
            if floor(mins) > 1: tmp.append(f" {int(mins)} minutes")
        elif floor(mins) > 0: tmp.append(f" 1 minute")
        if floor(secs) > 1 and len(tmp) < 2:
            if floor(secs) > 1: tmp.append(f" {int(secs)} seconds")
            elif secs > 0: tmp.append(f" 1 second")
        return ' '.join(tmp)

    #    s:int = delta.seconds
    #    unit:int = 3600
    #    res:str = ""
    #    while unit > 1:
    #        t, s = divmod(s, unit)
    #        unit = int(unit / 60)
    #        if t > 0:
    #            res += f"{t:02d}"
    #    return res


    def _countdown(self, frame:str, content:str|list[dict], end:datetime, stop:Event) -> None:
        """ Update the countdown display frame until zero or stopped """
        rem = end - datetime.now(tz=end.tzinfo)
        while rem.seconds > 0 and not stop.wait(1):
            rem = end - datetime.now(tz=end.tzinfo)
            display = [{k:v.format(t=self._timedelta_str(rem)) for k, v in c} for c in content] \
                if isinstance(content, list) else content.format(t=self._timedelta_str(rem))            
            Context.overlay.display_frame(frame, display, ttl=1)
        
        stop.clear()
        Debug.logger.debug("Countdown thread is ending.")


    def stop_countdown(self, frame:str) -> None:
        """ Stop a countdown display for a frame """
        if frame not in self.ovfrs: return
        self.ovfrs[frame].stopper.set()


    def display_countdown(self, frame:str, content:str|list[dict], end:datetime|int|None) -> None:  
        """ 
        Like display message but with a countdown either until a specific time or for some number of seconds 
        The countdown should be in a variable t in the content string
        """
        if end == None or frame not in self.ovfrs: return
        if isinstance(end, int): end = datetime.now() + timedelta(seconds=end)
        
        Thread(target=self._countdown, args=(frame, content, end, self.ovfrs[frame].stopper), 
                                             name=f"{Context.appname}_{frame} overlay countdown worker").start()


    @catch_exceptions
    def dashboard_entry(self, cmdr:str, is_beta:bool, entry:dict) -> None:
        """ ED UI state change, store the current state """

        # @TODO: Add alternate location when in galaxy map
        # Default frame, visible in ship main view only
        if not (Context.route and bool(entry["Flags"] & edmc_data.FlagsInMainShip)) or \
            entry.get("GuiFocus") not in [edmc_data.GuiFocusNoFocus]:
            self.clear_frame('Default')
            self.ovfrs['Default'].visible = False
        else:
            self.ovfrs['Default'].visible = True

        # Carrier frame, visible in ship main view only
        if not (Context.route and bool(entry["Flags"] & edmc_data.FlagsInMainShip)) or \
            entry.get("GuiFocus") not in [edmc_data.GuiFocusNoFocus]:
            self.clear_frame('Carrier')
            self.ovfrs['Carrier'].visible = False
        else:
            self.ovfrs['Carrier'].visible = True

        self.redraw_frames()


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
            ('x', 'X', tk.IntVar, tk.Entry),
            ('y', 'Y', tk.IntVar, tk.Entry),
            #('w', 'W', tk.IntVar, tk.Entry),
            #('h', 'H', tk.IntVar, tk.Entry),
            ('text_colour', 'Foreground', tk.StringVar, 'ColorPicker'),
            #('bgenabled', 'Use Background', tk.BooleanVar, tk.Checkbutton),
            #('background', 'Background', tk.StringVar, 'ColorPicker')
            ]

        # Hide existing messages. Redraw them in the new location when the user clicks save
        self.clear_frames()

        ovrprefs:nb.Frame = nb.Frame(parent)
        ovrprefs.columnconfigure(6, weight=1)
        ovrprefs.rowconfigure(60, weight=1)
        ovrprefs.grid()
        validate:tuple = (ovrprefs.register(validate_int), '%P')

        row:int = 0; col:int = 0
        nb.Label(ovrprefs, text="Overlays", justify=tk.LEFT).grid(row=row, column=0, padx=10, sticky=tk.NW); row += 1

        # Loop through the frames and create a preferences line for each
        vars:dict = {}; cbtns:dict = {}
        for name, fr in self.ovfrs.items():
            nb.Label(ovrprefs, text=name, justify=tk.LEFT).grid(row=row, column=0, padx=10, sticky=tk.NW)
            row += 1; col = 0
            for k in pref_opts:
                var = bind_var(fr, k[0], k[2](value=getattr(fr, k[0])))
                vars[f"{name}-{k[0]}"] = var
                match k[3]:
                    case tk.Checkbutton:
                        nb.Checkbutton(ovrprefs, text=k[1], variable=var).grid(row=row, column=col, padx=10, pady=0, sticky=tk.W)
                    case tk.Entry:
                        nb.Label(ovrprefs, text=k[1]).grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)
                        col += 1
                        ent:tk.Entry = tk.Entry(ovrprefs, textvariable=var, width=8, validate='all', validatecommand=validate)
                        ent.grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)
                    case 'ColorPicker':
                        btn:tk.Button = tk.Button(ovrprefs, text=k[1], foreground=fr.text_colour, background=fr.background,
                                                  command=partial(colour_picker, ovrprefs, name, k[1], var))
                        btn.grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)
                        cbtns[name] = btn
                col += 1
            row += 1
        return ovrprefs


    def save_prefs(self) -> bool:
        """ Serialize and save the frames dictionary to EDMC config. """
        # Store the serialized frames in the config

        for name, fr in self.ovfrs.items():
            config.set(f"{Context.appname}_{name}_overlay", json.dumps(asdict(fr)))

        self.redraw_frames()
        Debug.logger.info(f"Saved frames to EDMC config")
        return True


    def _load_prefs(self) -> None:
        """ Read frame data from the EDMC config. """

        for name in self.ovfrs:
            conf:str|None = config.get(f"{Context.appname}_{name}_overlay")
            Debug.logger.debug(f"Loading config: {conf}")
            if conf == None: continue
            data:dict = json.loads(conf)
            self.ovfrs[name] = OvFrame(**data)
