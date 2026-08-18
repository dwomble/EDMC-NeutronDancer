import tkinter as tk
from tkinter import ttk, font
from tkinter import filedialog
from pathlib import Path
from dataclasses import dataclass
import myNotebook as nb # type: ignore

from config import config # type: ignore

from .utils.misc import singleton
from .utils.debug import Debug, catch_exceptions

from .constants import ROUTE_DIR, cnf
from .context import Context

@dataclass
class Pref:
    pref_type:str
    name:str
    desc:str
    var_type:type[tk.StringVar]|type[tk.BooleanVar]
    entry_type:type[tk.Entry]|type[tk.Checkbutton]

PREFS = [
    Pref('dir', 'routes_directory', cnf['routes_directory'], tk.StringVar, tk.Entry),
    Pref('bool', 'cooldown_popup', cnf['show_carrier_cooldown'], tk.BooleanVar, tk.Checkbutton),
    ]

@singleton
class Prefs:
    def __init__(self) -> None:
        self.pref_vars:dict = {}
        self._load_prefs()

    @catch_exceptions
    def prefs_frame(self, parent:tk.Frame) -> nb.Frame:
        """ Return a TK Frame for adding to the EDMC settings dialog """

        def select_folder(entry:tk.Entry, var:tk.StringVar):
            # Open the folder selection dialog
            fpath = filedialog.askdirectory(title="Select a Directory", initialdir=var.get())
            # Check if the user selected a folder or cancelled
            if not fpath:
                return
            var.set(fpath)
            entry.delete(0, tk.END)
            entry.insert(0, fpath)

        self.plugin_frame:tk.Frame = parent
        frame:nb.Frame = nb.Frame(parent)
        # Make the second column fill available space
        frame.columnconfigure(1, weight=1)

        prefsfr:nb.Frame = nb.Frame(frame)
        prefsfr.columnconfigure(3, weight=1)
        prefsfr.rowconfigure(60, weight=1)
        prefsfr.grid(sticky=tk.NW)

        props = font.Font(name="TkDefaultFont", exists=True).actual()
        props["weight"] = "bold"
        bold:font.Font = font.Font(**props)

        row:int = 0; col:int = 0
        nb.Label(prefsfr, text=cnf["options"], justify=tk.LEFT, font=bold).grid(row=row, column=col, padx=10, pady=5, sticky=tk.NW)

        vars:dict = {}; cbtns:list = []; row += 1; col = 0
        # variable, label, variable type, object type
        for k in PREFS:
            match k.pref_type:
                case 'bool':
                    self.pref_vars[k.name] = tk.BooleanVar(value=config.get(f"{Context.plugin_name}_{k.name}", False))
                    nb.Checkbutton(prefsfr, text=k.desc, variable=self.pref_vars[k.name]).grid(row=row,   column=col, padx=10, pady=0, sticky=tk.W)
                case 'str':
                    nb.Label(prefsfr, text=k.name).grid(row=row, column=col, padx=10, pady=5, sticky=tk.W)
                    col += 1
                    tk.Entry(prefsfr, textvariable=vars[k.name], width=25, validate='all').grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)
                case 'dir':
                    dir = config.get(f"{Context.plugin_name}_{k.name}", str(Path(Context.plugin_dir) / ROUTE_DIR))
                    self.pref_vars[k.name] = tk.StringVar(value=dir)
                    nb.Label(prefsfr, text=k.desc).grid(row=row, column=col, padx=10, pady=5, sticky=tk.W)
                    col += 1
                    entry:tk.Entry = tk.Entry(prefsfr, textvariable=self.pref_vars[k.name], width=75)
                    entry.grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)
                    entry.bind("<Button-1>", lambda e, en=entry, v=self.pref_vars[k.name]: select_folder(en, v))

            col = 0;row += 1
        col = 0
        ttk.Separator(frame).grid(row=row, columnspan=3, pady=5 * 2, sticky=tk.EW)

        Context.overlay.prefs_display(frame)
        return frame


    def save_prefs(self) -> None:
        for k in PREFS:
            var:tk.Variable|None = self.pref_vars.get(k.name)
            config.set(f"{Context.plugin_name}_{k.name}", var.get() if var else getattr(self, k.name))
            setattr(self, k.name, config.get(f"{Context.plugin_name}_{k.name}"))
        Context.overlay.save_prefs()
        return


    def _load_prefs(self) -> None:
        """ Read frame data from the EDMC config. """
        for k in PREFS:
            res = config.get(f"{Context.plugin_name}_{k.name}")
            setattr(self, k.name, res)
