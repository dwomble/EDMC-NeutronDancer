# -*- coding: utf-8 -*-
from typing import Any

import tkinter as tk
from tkinter import ttk

from theme import theme # type: ignore
from config import config # type: ignore

from .autocompleter import Autocompleter
from .placeholder import Placeholder
from .tooltip import Tooltip

from utils.debug import Debug

__all__ = ["TopLevel", "Frame", "LabelFrame", "Label", "Button", "Radiobutton", "ComboBox", "Listbox", "Checkbutton", "Scale", "Tooltip", "Autocompleter", "Placeholder"]

""" A set of UI objects to handle themed widgets for dealing with EDMC dark mode """
class Base:
    """ A base class for themed widgets that can switch between light and dark mode. """
    def __init__(self, obj:ttk.Widget|tk.Widget, alt:ttk.Widget|tk.Widget|None = None) -> None:
        object.__setattr__(self, 'images', [])
        object.__setattr__(self, 'obj', obj)
        object.__setattr__(self, 'alt', alt)

        theme.register(obj)
        if alt is not None:
            theme.register(alt)


    def grid(self, *args, **kw) -> Any:
        """ theme.register_alternate() needs grid options, so we intercept grid() calls to register them. """
        if self.alt is not None:
            gridopts:dict = {}

            if len(args) > 0 and isinstance(args[0], dict):
                gridopts.update(args[0])
            if len(kw) > 0:
                gridopts.update(kw)

            if len(gridopts) > 0:
                theme.register_alternate((self.obj, self.alt, self.alt), gridopts)

        return self.alt.grid(*args, **kw) if config.get_bool('dark_mode') else self.obj.grid(*args, **kw)

    def configure(self, cnf=None, **kw) -> None:
        """ Override configure to handle themed buttons. """

        if 'image' in kw and self.alt is not None:
            object.__setattr__(self, 'images', getattr(self, 'images', []) + [kw['image']])
        if self.alt is not None:
            self.alt.configure(cnf, **kw)
        self.obj.configure(cnf, **kw)


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
        if getattr(self.obj, name, None) is not None:
            setattr(self.obj, name, value)
        if self.alt is not None and getattr(self.alt, name, None) is not None:
            setattr(self.alt, name, value)

    def __getitem__(self, key):
        """Support subscript notation for themedItem."""
        if key in self.obj.keys():
            return self.obj[key]
        if self.alt is not None and key in self.alt.keys():
            return self.alt[key]
        raise KeyError(key)

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
    def __init__(self, master:tk.Widget, **kw) -> None:
        # EDMC theme throws an error trying to set a foreground on a ttk.Button if it has an image.
        btn:ttk.Button|tk.Button = tk.Button(master, **kw) if 'image' in kw else ttk.Button(master, **kw)

        super().__init__(btn, tk.Button(master, **kw))

    def grid(self, *args, **kw) -> Any:
        """ Override grid to handle themed buttons. """
        gridopts:dict = {}

        if len(args) > 0 and isinstance(args[0], dict):
            gridopts.update(args[0])
        if len(kw) > 0:
            gridopts.update(kw)

        theme.register_alternate((self.obj, self.alt, self.alt), gridopts)

        return self.alt.grid(*args, **kw) if config.get_bool('dark_mode') else self.obj.grid(*args, **kw)

class Radiobutton(Base):
    """ A themed radiobutton that can switch between light and dark mode. """
    def __init__(self, master:tk.Widget, **kw) -> None:
        tkrb:tk.Radiobutton = tk.Radiobutton(master, **kw)
        tkrb.configure(foreground=config.get_str('dark_text'), highlightthickness=0, activebackground='black', highlightbackground='black', selectcolor='black', border=0, borderwidth=0)
        super().__init__(ttk.Radiobutton(master, **kw), tkrb)

class ComboBox(Base):
    """ A themed combobox that can switch between light and dark mode. """
    def __init__(self, master:tk.Widget, v:tk.StringVar, **kw) -> None:
        ttkcb:ttk.Combobox = ttk.Combobox(master, textvariable=v, state='readonly', **kw)

        value:str = ''
        values:list = []
        if len(kw.get('values', [])) > 0:
            value = kw['values'][0]
        if len(kw.get('values', [])) > 1:
            values = kw['values'][1:]

        tkcb:tk.OptionMenu = tk.OptionMenu(master, v, value, *values)
        tkcb.configure(activeforeground=config.get_str('dark_text'), highlightbackground='black', activebackground='black', border=0, borderwidth=0, highlightthickness=0)
        tkcb["menu"].config(bg='black', fg=config.get_str('dark_text'), activebackground=config.get_str('dark_text'), activeforeground="BLACK")

        super().__init__(ttkcb, tkcb)
        object.__setattr__(self, '_variable', v)

    def set_menu(self, menu:list[str]) -> None:
        """ Set the menu for the themed combobox. """
        self.obj["values"] = menu
        if self.alt is not None:
            self.alt['menu'].delete(0, 'end')
            for item in menu:
                self.alt['menu'].add_command(label=item, command=tk._setit(self._variable, item))
            self._variable.set(menu[0])

class Listbox(Base):
    """ A themed listbox that can switch between light and dark mode. """
    def __init__(self, master:tk.Widget, items:list, **kw) -> None:
        # @TODO: Switch the plain mode for a treeview?
        rows:int = min(len(items), 10)
        if 'selectmode' not in kw:
            kw['selectmode'] = tk.MULTIPLE
        if 'exportselection' not in kw:
            kw['exportselection'] = False

        lb1:tk.Listbox = tk.Listbox(master, height=rows, **kw)
        lb1.configure(border=0, borderwidth=0, activestyle=tk.NONE, highlightthickness=0)

        lb2:tk.Listbox = tk.Listbox(master, height=rows, **kw)
        lb2.configure(border=0, borderwidth=0, activestyle=tk.NONE, highlightthickness=0)
        lb2.configure(selectbackground='gray25', highlightbackground='black', background='black')

        for i in range(len(items)):
            lb1.insert(tk.END, items[i])
            lb2.insert(tk.END, items[i])

        super().__init__(lb1, lb2)

class Checkbutton(Base):
    """ A themed checkbutton that can switch between light and dark mode. """
    def __init__(self, master:tk.Widget, **kw) -> None:
        super().__init__(tk.Checkbutton(master, **kw), tk.Checkbutton(master, **kw))

class Scale(Base):
    """ A themed scale that can switch between light and dark mode. """
    def __init__(self, master:tk.Widget, **kw) -> None:
        tksc1:tk.Scale = tk.Scale(master, **kw, border=0, borderwidth=0, highlightthickness=0)
        tksc2:tk.Scale = tk.Scale(master, **kw, border=0, borderwidth=0, highlightthickness=0)
        tksc2.configure(troughcolor='gray25', highlightbackground='black', activebackground='black')
        super().__init__(tksc1, tksc2)
