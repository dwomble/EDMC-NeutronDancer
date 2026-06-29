# -*- coding: utf-8 -*-
from typing import Any

import tkinter as tk
from tkinter import ttk

from theme import theme # type: ignore
from config import config # type: ignore

__all__ = ["TopLevel", "Frame", "LabelFrame", "Label", "Button", "Radiobutton", "ComboBox", "Listbox", "Checkbutton", "Scale"]

""" UI helpers for dealing with EDMC dark mode """
class Base:
    """ A base class for themed widgets that can switch between light and dark mode. """
    def __init__(self, obj:ttk.Widget|tk.Widget, alt:ttk.Widget|tk.Widget|None = None, gopts:dict|None = None) -> None:
        object.__setattr__(self, 'obj', obj)
        object.__setattr__(self, 'alt', alt)
        object.__setattr__(self, 'gopts', gopts)

        theme.register(obj)
        if alt is not None:
            theme.register(alt)
            if gopts is not None:
                theme.register_alternate((obj, alt, alt), gopts)

    def grid(self, *args, **kw) -> Any:
        """ theme.register_alternate() needs grid options, so we intercept grid() calls to register them. """
        result = self.obj.grid(*args, **kw)
        if self.alt is not None:
            gridopts:dict = {}

            if len(args) > 0 and isinstance(args[0], dict):
                gridopts.update(args[0])
            if len(kw) > 0:
                gridopts.update(kw)

            if len(gridopts) > 0:
                theme.register_alternate((self.obj, self.alt, self.alt), gridopts)

        return result

    def callable_attr(self, name:str, *args, **kw) -> Any:
        """Call a same-named method on both widgets, returning the primary result."""
        method = getattr(self.obj, name)
        result = method(*args, **kw)

        if self.alt is not None:
            alt_method = getattr(self.alt, name, None)
            if callable(alt_method):
                alt_method(*args, **kw)

        return result

    def __getattr__(self, name:str) -> Any:
        """Fallback proxy so themedItem behaves like its wrapped widget."""
        attr = getattr(self.obj, name, None)
        if attr is None and self.alt is not None:
            attr = getattr(self.alt, name, None)
        if attr is None:
            raise AttributeError(name)
        if callable(attr):
            return lambda *args, **kw: self.callable_attr(name, *args, **kw)

        return attr

    def __setattr__(self, name:str, value:Any) -> None:
        """Fallback proxy so themedItem behaves like its wrapped widget."""
        if name in {'obj', 'alt', 'gopts'}:
            object.__setattr__(self, name, value)
            return

        if getattr(self.obj, name, None) is not None:
            setattr(self.obj, name, value)
        if self.alt is not None and getattr(self.alt, name, None) is not None:
            setattr(self.alt, name, value)

    def __getitem__(self, key):
        """Support subscript notation for themedItem."""
        return self.obj[key]


class TopLevel(tk.Toplevel):
    """ A themed toplevel window that can switch between light and dark mode. """
    def __init__(self, master:tk.Widget, **kw) -> None:
        tk.Toplevel.__init__(self, master, **kw)
        theme.update(self)

class Frame(tk.Frame):
    """ A themed frame that can switch between light and dark mode. """
    def __init__(self, master:tk.Widget, **kw) -> None:
        tk.Frame.__init__(self, master, **kw)
        theme.update(self)

class LabelFrame(tk.LabelFrame):
    """ A themed label frame that can switch between light and dark mode. """
    def __init__(self, master:tk.Widget, **kw) -> None:
        tk.LabelFrame.__init__(self, master, **kw)
        theme.update(self)

class Label(tk.Label):
    """ A themed label that can switch between light and dark mode. """
    def __init__(self, master:tk.Widget, **kw) -> None:
        tk.Label.__init__(self, master, **kw)
        theme.update(self)

class Button(Base):
    """ A themed button that can switch between light and dark mode. """
    def __init__(self, master:tk.Widget, gopts:dict|None = None, **kw) -> None:
        Base.__init__(self, ttk.Button(master, **kw), tk.Button(master, **kw), gopts)

class Radiobutton(Base):
    """ A themed radiobutton that can switch between light and dark mode. """
    def __init__(self, master:tk.Widget, gopts:dict|None = None, **kw) -> None:
        super().__init__(tk.Radiobutton(master, **kw), tk.Radiobutton(master, **kw), gopts)

class ComboBox(Base):
    """ A themed combobox that can switch between light and dark mode. """
    def __init__(self, master:tk.Widget, v:tk.StringVar, gopts:dict|None = None, **kw) -> None:
        ttkcb:ttk.Combobox = ttk.Combobox(master, textvariable=v, state='readonly', **kw)

        value:str = ''
        values:list = []
        if len(kw.get('values', [])) > 0:
            value = kw['values'][0]
        if len(kw.get('values', [])) > 1:
            values = kw['values'][1:]

        tkcb:tk.OptionMenu = tk.OptionMenu(master, v, value, *values)
        tkcb.configure(activeforeground=config.get_str('dark_text'), highlightbackground='black', activebackground='black', border=0, borderwidth=0, highlightthickness=0, relief=tk.FLAT)
        tkcb["menu"].config(bg='black', fg=config.get_str('dark_text'), activebackground=config.get_str('dark_text'), activeforeground="BLACK")

        Base.__init__(self, ttkcb, tkcb, gopts)

class Listbox(Base):
    """ A themed listbox that can switch between light and dark mode. """
    def __init__(self, master:tk.Widget, items:list, gopts:dict|None = None, **kw) -> None:
        # @TODO: Switch the plain mode for a treeview?
        rows:int = min(len(items), 10)

        lb1:tk.Listbox = tk.Listbox(master, height=rows, selectmode=tk.MULTIPLE, exportselection=False)
        lb1.configure(border=0, borderwidth=0, activestyle=tk.NONE, relief=tk.FLAT, highlightthickness=0)

        lb2:tk.Listbox = tk.Listbox(master, height=rows, selectmode=tk.MULTIPLE, exportselection=False)
        lb2.configure(border=0, borderwidth=0, activestyle=tk.NONE, relief=tk.FLAT, highlightthickness=0)
        lb2.configure(selectbackground='gray25', highlightbackground='black', background='black')

        for i in range(len(items)):
            lb1.insert(tk.END, items[i])
            lb2.insert(tk.END, items[i])

        Base.__init__(self, lb1, lb2, gopts)

class Checkbutton(Base):
    """ A themed checkbutton that can switch between light and dark mode. """
    def __init__(self, master:tk.Widget, gopts:dict|None = None, **kw) -> None:
        super().__init__(tk.Checkbutton(master, **kw), tk.Checkbutton(master, **kw), gopts)

class Scale(Base):
    """ A themed scale that can switch between light and dark mode. """
    def __init__(self, master:tk.Widget, gopts:dict|None = None, **kw) -> None:
        tksc1:tk.Scale = tk.Scale(master, **kw, border=0, borderwidth=0, highlightthickness=0, relief=tk.FLAT)
        tksc2:tk.Scale = tk.Scale(master, **kw, border=0, borderwidth=0, highlightthickness=0, relief=tk.FLAT)
        tksc2.configure(troughcolor='gray25', highlightbackground='black', activebackground='black')
        Base.__init__(self, tksc1, tksc2, gopts)
