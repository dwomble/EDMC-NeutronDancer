import textwrap
import copy
import json
from dataclasses import field, dataclass, asdict
from functools import partial

import tkinter as tk
from tkinter import ttk, colorchooser as tkColorChooser
import myNotebook as nb # type: ignore

try:
    from EDMCOverlay import edmcoverlay # type: ignore
except ImportError:
    try:
        from edmcoverlay import edmcoverlay # type: ignore
    except ImportError:
        edmcoverlay = None

from config import config # type:ignore

from utils.debug import Debug, catch_exceptions
from utils.placeholder import Placeholder
from .context import Context
from .constants import NAME

@dataclass
class OvFrame:
    """ Overlay frame details """
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
    bgenabled:bool = False
    background:str = 'grey'
    border:str = ''
    border_colour:str = ''
    border_width:int = 0
    anchor:str = "nw"
    justification:str = "left" if centered_x == False else "center"
    text_size:str = "normal"

class Overlay():
    # Singleton pattern
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance


    def __init__(self) -> None:
        # Only initialize if it's the first time
        if hasattr(self, '_initialized'): return
        self.ovf:OvFrame = OvFrame()
        self._load_prefs()
        self.ovf.name = 'Default'
        self.messages:dict = {}
        self._initialized = True


    def _get_overlay(self):
        """ Is an overlay installed and running? """
        Debug.logger.debug(f"Get overlay")
        if not edmcoverlay:
            Debug.logger.warning(f"edmcoverlay plugin is not installed")
            return

        # Is it running?
        try:
            return edmcoverlay.Overlay()
        except Exception as e:
            Debug.logger.warning(f"EDMCOverlay is not running")
            return

    def clear_messages(self) -> None:
        """ Clear all overlay messages """
        Debug.logger.debug(f"Clearing {self.messages}")
        #messages:list = copy.copy([self.messages.keys()])
        [self.clear_message(m) for m in list(self.messages)]

    @catch_exceptions
    def clear_message(self, msgid:str = "") -> bool:
        """ Clear a message """
        if msgid not in self.messages: return False
        status:bool = self.ovf.enabled
        self.ovf.enabled = True
        msg:list = self.messages[msgid]
        for i in range(1, len(msg), 2):
            msg[i] = ""
        self.send_message(msgid, msg, ttl=1)
        del self.messages[msgid]
        self.ovf.enabled = status
        return True


    @catch_exceptions
    def send_message(self, msgid:str = "", text:str|list = "", size:str = "normal", ttl=120) -> None:
        overlay = self._get_overlay()
        if not overlay: return
        Debug.logger.debug(f"Overlay enabled: {self.ovf.enabled}")
        if self.ovf.enabled == False: return

        if isinstance(text, str): text = [size, text]
        y:int = self.ovf.y
        for i in range(0, len(text), 2):
            args:dict = {
                'msgid': f"ND-{msgid}-{i}",
                'text': text[i+1],
                'color': self.ovf.text_colour,
                'x': self.ovf.x,
                'y': y,
                'ttl': self.ovf.ttl,
                'size': text[i]
            }
            Debug.logger.debug(f"Sending overlay message {args}")
            overlay.send_message(**args)
            y += 20
        self.messages[msgid] = text

    @catch_exceptions
    def prefs_display(self, parent:nb.Frame) -> nb.Frame:
        """ EDMC settings pane hook. Displays one frame per row. """

        def bind_var(data_obj, attribute, tk_var):
            # Update dataclass whenever the UI changes
            def update_obj(*args) -> None:
                setattr(data_obj, attribute, tk_var.get())
                self.send_message("Test", "Test Message", "normal", 10)

            tk_var.trace_add("write", update_obj)
            return tk_var

        def colour_picker(parent:nb.Frame, which:str, col:tk.StringVar) -> None:
            (_, color) = tkColorChooser.askcolor(col.get(), title=which, parent=parent)

            if color:
                col.set(color)
                Debug.logger.debug(f"{len(cbtns)} {cbtns}")
                for b in cbtns:
                    b.config(**{which.lower(): color})
                self.send_message("Test", "Test Message", "normal", ttl=10)

        def validate_int(val:str) -> bool:
            return True if val.isdigit() or val == '' else False

        prefsfr:nb.Frame = nb.Frame(parent)
        prefsfr.columnconfigure(6, weight=1)
        prefsfr.rowconfigure(60, weight=1)
        prefsfr.grid()
        validate = (prefsfr.register(validate_int), '%P')

        row:int = 0; col:int = 0
        nb.Label(prefsfr, text="Overlay", justify=tk.LEFT).grid(row=row, column=0, padx=10, sticky=tk.NW); row += 1

        vars:dict = {}; cbtns:list = []; col = 0
        for k in [('enabled', 'Enable', tk.BooleanVar, tk.Checkbutton),
                  ('x', 'X', tk.IntVar, tk.Entry),
                  ('y', 'Y', tk.IntVar, tk.Entry),
                  #('w', 'W', tk.IntVar, tk.Entry),
                  #('h', 'H', tk.IntVar, tk.Entry),
                  ('text_colour', 'Foreground', tk.StringVar, 'ColorPicker'),
                  #('bgenabled', 'Use Background', tk.BooleanVar, tk.Checkbutton),
                  #('background', 'Background', tk.StringVar, 'ColorPicker')
                  ]:

            vars[k[0]] = bind_var(self.ovf, k[0], k[2](value=getattr(self.ovf, k[0])))
            match k[3]:
                case tk.Checkbutton:
                    nb.Checkbutton(prefsfr, text=k[1], variable=vars[k[0]]).grid(row=row, column=col, padx=10, pady=0, sticky=tk.W)
                case tk.Entry:
                    nb.Label(prefsfr, text=k[1]).grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)
                    col += 1
                    tk.Entry(prefsfr, textvariable=vars[k[0]], width=8, validate='all', validatecommand=validate).grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)
                case 'ColorPicker':
                    btn:tk.Button = tk.Button(prefsfr, text=k[1], foreground=self.ovf.text_colour, background=self.ovf.background, command=partial(colour_picker, prefsfr, k[1], vars[k[0]]))
                    btn.grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)
                    cbtns.append(btn)
            col += 1

        return prefsfr


    def save_prefs(self) -> bool:
        """ Serialize and save the frames dictionary to EDMC config. """
        # Store the serialized frames in the config
        self.send_message("Test", "", "normal", ttl=1)
        config.set(f"{NAME}_overlay", json.dumps(asdict(self.ovf)))
        if self.ovf.enabled == False:
            self.clear_messages()
        Debug.logger.info(f"Saved {self.ovf} frames to EDMC config")
        return True


    def _load_prefs(self):
        """ Read frame data from the EDMC config. """
        conf = config.get(f"{NAME}_overlay")
        Debug.logger.debug(f"{conf}")
        if conf == None: return
        data:dict = json.loads(conf)
        self.ovf = OvFrame(**data)
