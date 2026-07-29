# -*- coding: utf-8 -*-
from typing import Any, cast
from functools import partial

import tkinter as tk
from tkinter import ttk

from theme import theme # type: ignore
from config import config # type: ignore

from .autocompleter import Autocompleter
from .placeholder import Placeholder, PlaceholderMixin
from .tooltip import Tooltip

__all__ = ["TopLevel", "Frame", "LabelFrame", "Label", "Button", "Radiobutton", "ComboBox", "Listbox", "Checkbutton", "Scale", "Spinbox", "Tooltip", "Autocompleter", "Placeholder", "resolve"]

def _strip_name(kw:dict) -> dict:
    """ Strip an explicit Tk 'name' from kwargs meant for a themed widget's second (alt) half. """
    return {k: v for k, v in kw.items() if k != 'name'}

def _bind_hover(btn:tk.Button) -> None:
    """ A plain tk.Button only applies its active* colors while the mouse is pressed, not on
    mouseover, unlike a themed ttk.Button which highlights on hover natively. Button falls back
    to tk.Button for images (ttk.Button can't have its foreground set once it has one) and
    always uses tk.Button for the dark-mode alt, so both need this to match ttk.Button's hover
    behaviour.

    Combines a background/foreground color swap (works on macOS/Linux, where tk.Button honors
    explicit color overrides -- verified empirically) with a relief toggle, because on Windows
    tk.Button is drawn by the native visual-styles theme engine by default, which ignores
    -background/-foreground overrides for the button face entirely. relief is the one state
    Windows' native theme still honors, since raised/sunken bevels are literally how it renders
    idle vs. pressed -- so it's the part that actually shows something there. Colors are re-read
    on every <Enter> (rather than captured once) so this stays correct across theme switches;
    the normal relief is captured once since nothing else in this codebase changes a button's
    relief after construction. """
    normal_relief = btn.cget('relief')
    hover_relief = tk.SUNKEN if normal_relief == tk.RAISED else tk.RAISED

    def on_enter(e:tk.Event) -> None:
        # tk.Event[tk.Button] would be a cleaner annotation, but it's a runtime subscript --
        # tkinter.Event only gained __class_getitem__ in newer Python builds, so it raises
        # "TypeError: type 'Event' is not subscriptable" on whatever older Python this plugin's
        # EDMC install bundles. cast() is purely for the type checker, never evaluated at runtime.
        w = cast(tk.Button, e.widget)
        setattr(w, '_th_normal', (w['background'], w['foreground']))
        w.configure(background=w['activebackground'], foreground=w['activeforeground'], relief=hover_relief)
    def on_leave(e:tk.Event) -> None:
        w = cast(tk.Button, e.widget)
        bg, fg = getattr(w, '_th_normal', (w['background'], w['foreground']))
        w.configure(background=bg, foreground=fg, relief=normal_relief)
    btn.bind('<Enter>', on_enter)
    btn.bind('<Leave>', on_leave)

def resolve(widget:Any) -> Any:
    """ Resolve the actual base object for a tk nametowidget() lookup. """
    return getattr(widget, 'themed', widget)

""" A set of UI objects to handle themed widgets for dealing with EDMC dark mode """
class Base:
    """ A base class for themed widgets that can switch between light and dark mode. """
    def __init__(self, obj:ttk.Widget|tk.Widget, alt:ttk.Widget|tk.Widget|None = None) -> None:
        object.__setattr__(self, 'images', [])
        object.__setattr__(self, 'obj', obj)
        object.__setattr__(self, 'alt', alt)

        # Back-reference so th.resolve() can recover this wrapper from a nametowidget() lookup.
        setattr(obj, 'themed', self)
        if alt is not None:
            setattr(alt, 'themed', self)

        theme.register(obj)
        if alt is not None:
            theme.register(alt)

    def grid(self, *args, **kw) -> Any:
        """ theme.register_alternate() needs grid options, so we intercept grid() calls to register them. """
        if self.alt is None:
            return self.obj.grid(*args, **kw)

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

    def _callable_attr(self, name:str, *args, **kw) -> Any:
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
            return lambda *args, **kw: self._callable_attr(name, *args, **kw)

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

    def __setitem__(self, key, value) -> None:
        """Support subscript assignment for themedItem, e.g. widget['fg'] = 'red'."""
        self.configure(**{key: value})

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
        if isinstance(btn, tk.Button):
            _bind_hover(btn)

        alt:tk.Button = tk.Button(master, **_strip_name(kw))
        _bind_hover(alt)

        super().__init__(btn, alt)

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
        tkrb:tk.Radiobutton = tk.Radiobutton(master, **_strip_name(kw))
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
        object.__setattr__(self, '_select_func', None)

    def _wire_alt_menu(self) -> None:
        """ (Re-)apply the bound <<ComboboxSelected>> callback, if any, to every entry in the
        alt's menu. """
        func = self._select_func
        if self.alt is None or func is None:
            return
        menu = self.alt["menu"]
        last:int|None = menu.index("end")
        if last is None:
            return
        for i in range(last + 1):
            label = menu.entrycget(i, "label")
            menu.entryconfigure(i, command=lambda label=label: (self._variable.set(label), func(None)))

    def set_menu(self, menu:list[str]) -> None:
        """ Set the menu for the themed combobox. """
        self.obj["values"] = menu
        if self.alt is not None:
            self.alt['menu'].delete(0, 'end')
            for item in menu:
                self.alt['menu'].add_command(label=item, command=tk._setit(self._variable, item))
            self._variable.set(menu[0])
            self._wire_alt_menu()

    def bind(self, sequence:str, func, **kw) -> None:
        """ ttk.Combobox fires <<ComboboxSelected>> as a real virtual event on selection, but
        tk.OptionMenu (the dark-mode alt) has no equivalent -- see _wire_alt_menu() for why
        that means hooking each entry's command rather than the variable itself. """
        self.obj.bind(sequence, func, **kw)
        if self.alt is None:
            return
        if sequence == "<<ComboboxSelected>>":
            object.__setattr__(self, '_select_func', func)
            self._wire_alt_menu()
        else:
            self.alt.bind(sequence, func, **kw)

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

        lb2:tk.Listbox = tk.Listbox(master, height=rows, **_strip_name(kw))
        lb2.configure(border=0, borderwidth=0, activestyle=tk.NONE, highlightthickness=0)
        lb2.configure(selectbackground='gray25', highlightbackground='black', background='black')

        for i in range(len(items)):
            lb1.insert(tk.END, items[i])
            lb2.insert(tk.END, items[i])

        super().__init__(lb1, lb2)

class Checkbutton(Base):
    """ A themed checkbutton that can switch between light and dark mode. """
    def __init__(self, master:tk.Widget, **kw) -> None:
        super().__init__(tk.Checkbutton(master, **kw), tk.Checkbutton(master, **_strip_name(kw)))

class Scale(Base):
    """ A themed scale that can switch between light and dark mode. """
    def __init__(self, master:tk.Widget, **kw) -> None:
        tksc1:tk.Scale = tk.Scale(master, **kw, border=0, borderwidth=0, highlightthickness=0)
        tksc2:tk.Scale = tk.Scale(master, **_strip_name(kw), border=0, borderwidth=0, highlightthickness=0)
        tksc2.configure(troughcolor='gray25', highlightbackground='black', activebackground='black')
        super().__init__(tksc1, tksc2)

class Spinbox(PlaceholderMixin, Base):
    """ A themed spinbox that can switch between light and dark mode.

        Unlike tk.Entry, a themed Spinbox is two separate tk.Spinbox widgets (light/dark),
        so it takes PlaceholderMixin's placeholder/menu features via a shared textvariable
        (see PlaceholderMixin.init_placeholder) rather than Placeholder's single-widget approach.
        Takes the same parameters as a tk.Spinbox object plus the optional placeholder/menu/
        placeholder_color/error_color kwargs described in PlaceholderMixin.

        Once placeholder support is wired up, content changes must go through set_text() rather
        than raw insert()/delete() -- those get mirrored onto both light/dark widgets, which
        double-applies on top of the automatic sync from the shared textvariable.
    """
    def __init__(self, master:tk.Widget, placeholder:str = "", **kw) -> None:
        menu:dict = kw.pop('menu', {})
        placeholder_color:str = kw.pop('placeholder_color', "grey")
        error_color:str = kw.pop('error_color', "red")

        rgb = master.winfo_rgb(master['background'])
        background:str = '#{:02x}{:02x}{:02x}'.format(rgb[0] // 256, rgb[1] // 256, rgb[2] // 256)

        sb1:tk.Spinbox = tk.Spinbox(master, **kw, border=0, borderwidth=1, highlightthickness=0, background=background)
        sb2:tk.Spinbox = tk.Spinbox(master, **_strip_name(kw), border=0, borderwidth=1, highlightthickness=0)
        sb2.configure(background='black', buttonbackground='black', highlightbackground='black',
                      foreground=config.get_str('dark_text'), insertbackground=config.get_str('dark_text'))
        super().__init__(sb1, sb2)

        self.init_placeholder(master, placeholder, menu, placeholder_color, error_color)
