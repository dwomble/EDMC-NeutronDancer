import tkinter as tk
from tkinter import ttk
from typing import Any
from functools import reduce
import operator

from config import config # type: ignore
from theme import theme #type: ignore

"""
  Miscellaneous utility functions
"""
def get_by_path(dic:dict[str, Any], keys:list[str], default:Any = None) -> Any:
    """ Return an element from a nested object by item sequence. """
    try:
        return reduce(operator.getitem, keys, dic) or default
    except (KeyError, IndexError, TypeError):
        return default

""" UI helpers for dealing with EDMC dark mode """
def frame(parent:tk.Widget, **kw) -> tk.Frame:
    """ Deal with EDMC theme/color weirdness """
    fr:tk.Frame = tk.Frame(parent, kw)
    match config.get_int('theme'):
        case 2:
            fr.config(bg='')
        case 1:
            fr.config(bg='black')
    return fr


def button(fr:tk.Frame, **kw) -> tk.Button|ttk.Button:
    """ Deal with EDMC theme/color weirdness by creating tk buttons for dark mode """
    if config.get_int('theme') == 0: return ttk.Button(fr, **kw)
    btn:tk.Button = tk.Button(fr, **kw, fg=config.get_str('dark_text'), activebackground='black')
    return btn


def label(fr:tk.Frame, **kw) -> tk.Label|ttk.Label:
    """ Deal with EDMC theme/color weirdness by creating tk labels for dark mode """
    if config.get_int('theme') == 0: return ttk.Label(fr, **kw)
    lbl:tk.Label = tk.Label(fr, **kw, fg=config.get_str('dark_text'), activebackground='black')

    return lbl


def radiobutton(fr:tk.Frame, **kw) -> tk.Radiobutton|ttk.Radiobutton:
    """ Deal with EDMC theme/color weirdness by creating tk buttons for dark mode """
    if config.get_int('theme') == 0: return ttk.Radiobutton(fr, **kw)

    rb:tk.Radiobutton = tk.Radiobutton(fr, **kw, fg=config.get_str('dark_text'), activebackground='black', highlightbackground='yellow')
    return rb


def combobox(fr:tk.Frame, v:tk.StringVar, **kw) -> ttk.Combobox|tk.OptionMenu:
    """ Deal with EDMC theme/color weirdness by creating tk.optionmenu for dark mode """
    if config.get_int('theme') == 0:
        return ttk.Combobox(fr, textvariable=v, state='readonly', **kw)


    value:str = kw['values'][0]
    values:list = kw['values'][1:]
    om:tk.OptionMenu = tk.OptionMenu(fr, v, value, *values)
    #om.configure(borderwidth=0, border=0, relief=tk.FLAT)
    om.configure(foreground=config.get_str('dark_text'), highlightbackground='black', activebackground='black', border=0, borderwidth=0, highlightthickness=0, relief=tk.FLAT)
    return om


def listbox(fr:tk.Frame, items:list) -> tk.Listbox:
    """ Deal with EDMC theme/color weirdness by creating tk listbox for dark mode """
    # @TODO: Switch the plain mode for a treeview?
    rows:int = min(len(items), 10)
    if config.get_int('theme') == 0:
        lb:tk.Listbox = tk.Listbox(fr, height=rows, selectmode=tk.MULTIPLE, exportselection=False)
        lb.configure(border=0, borderwidth=0, highlightthickness=0, activestyle=tk.NONE, relief=tk.FLAT)
        for i in range(len(items)):
            lb.insert(tk.END, items[i])
        return lb

    lb:tk.Listbox = tk.Listbox(fr, height=rows, selectmode=tk.MULTIPLE)
    lb.configure(foreground=config.get_str('dark_text'), activestyle=tk.NONE, highlightbackground='black', border=0, borderwidth=0, highlightthickness=0, relief=tk.FLAT, exportselection=False)
    for i in range(len(items)):
        lb.insert(tk.END, items[i])
    return lb


def checkbox(fr:tk.Frame, **kw) -> ttk.Checkbutton|tk.Checkbutton:
    """ Deal with EDMC theme/color weirdness by creating tk for dark mode """
    if config.get_int('theme') == 0:
        return ttk.Checkbutton(fr, **kw)

    box:tk.Checkbutton = tk.Checkbutton(fr, **kw)
    #box.configure(foreground=config.get_str('dark_text'), highlightbackground='black', activebackground='black', border=0, borderwidth=0, highlightthickness=0, relief=tk.FLAT)
    return box


def scale(fr:tk.Frame, **kw) -> tk.Scale|ttk.Scale:
    """ Deal with EDMC theme/color weirdness by creating tk buttons for dark mode """
    if config.get_int('theme') == 0: return tk.Scale(fr, kw, border=0)

    sc:tk.Scale = tk.Scale(fr, kw)
    sc.configure(foreground=config.get_str('dark_text'), troughcolor='gray25', highlightbackground='black', activebackground='black', border=0, borderwidth=0, highlightthickness=0, relief=tk.FLAT)
    return sc
