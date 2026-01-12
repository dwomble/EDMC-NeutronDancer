from config import config # type: ignore
import tkinter as tk
from tkinter import ttk, colorchooser as tkColorChooser
from ttkHyperlinkLabel import HyperlinkLabel # type: ignore
import myNotebook as nb # type: ignore

from .constants import GIT_RELEASES, BOLD, cnf
from .context import Context


def prefs_setup() -> None:
    """ Initialise preferences from config """
    Context.overlay = tk.IntVar(value=config.get_bool(key='neutrondancer-overlay', default=False))
    Context.overlay_color = tk.StringVar(value=config.get(key='neutrondancer-overlay-color', default='#FFFFFF'))
    Context.overlay_x = tk.IntVar(value=config.get(key='neutrondancer-overlay-x', default=300))
    Context.overlay_y = tk.IntVar(value=config.get(key='neutrondancer-overlay-y', default=900))


def prefs_display(parent: ttk.Notebook) -> nb.Frame:
    """ EDMC settings pane hook."""

    def color_picker() -> None:
        (_, color) = tkColorChooser.askcolor(Context.overlay_color.get(), title='Overlay Color', parent=Context.parent)

        if color:
            Context.overlay_color.set(color)
            if colour_button is not None:
                colour_button['foreground'] = color

    def validate_int(val:str) -> bool:
        return True if val.isdigit() or val == '' else False


    Context.parent = parent
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
