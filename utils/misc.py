import subprocess
import os
import sys
import shutil
import tkinter as tk
from tkinter import ttk
import re
from datetime import datetime
from math import floor
from typing import Any
from functools import reduce
import operator

from theme import theme # type: ignore
from config import config # type: ignore

from utils.debug import Debug, catch_exceptions

"""
  Miscellaneous utility functions
"""
def get_by_path(dic:dict[str, Any], keys:list[str], default:Any = None) -> Any:
    """ Return an element from a nested object by item sequence. """
    try:
        return reduce(operator.getitem, keys, dic) or default
    except (KeyError, IndexError, TypeError):
        return default

@catch_exceptions
def copy_to_clipboard(parent:tk.Widget|None, text:str = '') -> None:
    """ Copy text to the clipboard """
    if parent == None: return

    # Non-linux is easy.
    if sys.platform not in ['linux', 'linux2']:
        # Use the native clipboard method
        parent.clipboard_clear()
        parent.clipboard_append(text)
        parent.update()
        return

    cmds:dict = { "wl-copy": "wayland",
                "xsel --clipboard --input": "x11",
                "xclip -selection c -target UTF8_STRING": "x11"}

    # Try to use the appropriate CLI clipboard tool
    clipboard_cli:str|None = os.getenv("EDMC_CLIPBOARD_CLI", None)
    if clipboard_cli == None:
        for cmd, session in cmds.items():
            if os.getenv("XDG_SESSION_TYPE") == session and shutil.which(cmd.split()[0]):
                clipboard_cli = cmd
                break

    if clipboard_cli != None:
        Debug.logger.debug(f"Using linux clipboard: {clipboard_cli}")
        try:
            subprocess.run(clipboard_cli.split(), input=text.encode('utf-8'), check=True)
        except subprocess.CalledProcessError as e:
            Debug.logger.error(f"Failed to run {clipboard_cli}: {e}")
        return

    # Still nothing? Then run all the ones we can find regardless of session type.
    for cmd in cmds:
        if shutil.which(cmd.split()[0]):
            cli:str = cmd
            try:
                subprocess.run(cli.split(), input=text.encode('utf-8'), check=True)
            except subprocess.CalledProcessError as e:
                Debug.logger.error(f"Failed to run {cli}: {e}")

    if clipboard_cli != None:
        return

    # Final fallback to the tkinter version
    Debug.logger.debug(f"Using linux tkinter clipboard fallback")
    parent.clipboard_clear()
    parent.clipboard_append(text)
    parent.update()


""" UI helpers for dealing with EDMC dark mode """

def frame(parent:tk.Widget, **kw) -> tk.Frame:
    """ Deal with EDMC theme/color weirdness """
    fr:tk.Frame = tk.Frame(parent, kw)
    theme.update(fr)
    return fr


def labelframe(parent:tk.Widget, **kw) -> tk.LabelFrame:
    """ Deal with EDMC theme/color weirdness """
    fr:tk.LabelFrame = tk.LabelFrame(parent, kw)
    theme.update(fr)
    return fr


def button(fr:tk.Frame|tk.Toplevel, gopts:dict|None = None, **kw) -> tk.Button|ttk.Button:
    """ Deal with EDMC theme/color weirdness by creating tk buttons for dark mode """
    ttkb:ttk.Button = ttk.Button(fr, **kw)
    theme.register(ttkb)
    tkb:tk.Button = tk.Button(fr, padx=10, **kw)
    theme.register(tkb)
    if gopts is not None:
        theme.register_alternate((ttkb, tkb, tkb), gopts)

    return ttkb if config.get_int('theme') == 0 else tkb


def label(fr:tk.Frame|tk.Toplevel, **kw) -> tk.Label|ttk.Label:
    """ Deal with EDMC theme/color weirdness by creating tk labels for dark mode """
    ttkl:ttk.Label = ttk.Label(fr, **kw)
    theme.update(ttkl)
    return ttkl


def radiobutton(fr:tk.Frame, gopts:dict|None = None, **kw) -> tk.Radiobutton|ttk.Radiobutton:
    """ Deal with EDMC theme/color weirdness by creating tk buttons for dark mode """
    ttkrb:ttk.Radiobutton = ttk.Radiobutton(fr, **kw)
    theme.register(ttkrb)
    tkrb:tk.Radiobutton = tk.Radiobutton(fr, **kw)
    tkrb.config(fg=config.get_str('dark_text'))
    theme.register(tkrb)
    if gopts is not None:
        theme.register_alternate((ttkrb, tkrb, tkrb), gopts)

    return ttkrb if config.get_int('theme') == 0 else tkrb


def combobox(fr:tk.Frame, v:tk.StringVar, gopts:dict|None = None, **kw) -> ttk.Combobox|tk.OptionMenu:
    """ Deal with EDMC theme/color weirdness by creating tk.optionmenu for dark mode """
    ttkcb:ttk.Combobox = ttk.Combobox(fr, textvariable=v, state='readonly', **kw)
    theme.register(ttkcb)

    value:str = ''
    values:list = []
    if len(kw.get('values', [])) > 0:
        value = kw['values'][0]
    if len(kw.get('values', [])) > 1:
        values = kw['values'][1:]

    tkcb:tk.OptionMenu = tk.OptionMenu(fr, v, value, *values)
    tkcb.configure(activeforeground=config.get_str('dark_text'), highlightbackground='black', activebackground='black', border=0, borderwidth=0, highlightthickness=0, relief=tk.FLAT)
    tkcb["menu"].config(bg='black', fg=config.get_str('dark_text'), activebackground=config.get_str('dark_text'), activeforeground="BLACK")
    theme.register(tkcb)

    if gopts is not None:
        theme.register_alternate((ttkcb, tkcb, tkcb), gopts)

    return ttkcb if config.get_int('theme') == 0 else tkcb


def listbox(fr:tk.Frame, items:list, getopts:dict|None = None) -> tk.Listbox:
    """ Deal with EDMC theme/color weirdness by creating tk listbox for dark mode """
    # @TODO: Switch the plain mode for a treeview?
    rows:int = min(len(items), 10)

    lb1:tk.Listbox = tk.Listbox(fr, height=rows, selectmode=tk.MULTIPLE, exportselection=False)
    lb1.configure(border=0, borderwidth=0, activestyle=tk.NONE, relief=tk.FLAT, highlightthickness=0)
    theme.register(lb1)

    lb2:tk.Listbox = tk.Listbox(fr, height=rows, selectmode=tk.MULTIPLE, exportselection=False)
    lb2.configure(border=0, borderwidth=0, activestyle=tk.NONE, relief=tk.FLAT, highlightthickness=0)
    lb2.configure(selectbackground='gray25', highlightbackground='black', background='black')
    theme.register(lb2)

    for i in range(len(items)):
        lb1.insert(tk.END, items[i])
        lb2.insert(tk.END, items[i])

    if getopts is not None:
        theme.register_alternate((lb1, lb2, lb2), getopts)

    return lb1 if config.get_int('theme') == 0 else lb2


def checkbox(fr:tk.Frame, getopts:dict|None = None, **kw) -> ttk.Checkbutton|tk.Checkbutton:
    """ Deal with EDMC theme/color weirdness by creating tk for dark mode """
    ttkcb:ttk.Checkbutton = ttk.Checkbutton(fr, **kw)
    theme.register(ttkcb)

    tkcb:tk.Checkbutton = tk.Checkbutton(fr, **kw)
    theme.register(tkcb)
    if getopts is not None:
        theme.register_alternate((ttkcb, tkcb, tkcb), getopts)

    return ttkcb if config.get_int('theme') == 0 else tkcb


def scale(fr:tk.Frame, gopts:dict|None, **kw) -> tk.Scale|ttk.Scale:
    """ Deal with EDMC theme/color weirdness by creating tk buttons for dark mode """
    tksc1:tk.Scale = tk.Scale(fr, kw, border=0, borderwidth=0, highlightthickness=0, relief=tk.FLAT)
    theme.register(tksc1)
    tksc2:tk.Scale = tk.Scale(fr, kw, border=0, borderwidth=0, highlightthickness=0, relief=tk.FLAT)
    tksc2.configure(troughcolor='gray25', highlightbackground='black', activebackground='black')
    theme.register(tksc2)
    if gopts is not None:
        theme.register_alternate((tksc1, tksc2, tksc2), gopts)

    return tksc1 if config.get_int('theme') == 0 else tksc2


def hfplus(val:int|float|str|bool|tuple, type:str|None = None) -> str:
    """
        A general customized formatting function.
        Args:
            val (int|float|str|bool|tuple): A tuple or a value
            tuple can contain up to 4 elements: (value, type, default, units)
            'int' and 'float' force types, 'num' will decide based on the value
            'fixed' will return the value modified
        Returns:
            str: The human-readable friendly/readable result
    """
    units:str = ''
    default:str = ''

    if isinstance(val, tuple): # Handle a tuple of 1-4 elements: (value, type, default, units)
        if len(val) > 1: type = val[1]
        if len(val) > 2: default = val[2]
        if len(val) > 3: units = val[3]
        if len(val) > 0: value = val[0]
    else:
        value:int|float|str|bool = val
        if (isinstance(value, str) and re.match(value, r"^\d+-\d+-\d+ \d+\:\d+")): type = 'datetime'
        if isinstance(value, bool): type = 'bool'
        if isinstance(value, int) or isinstance(value, float): type = 'num'

    # Fixed is left entirely alone
    if type == 'fixed': return str(value) + units

    # Empty, zero or false we return the default so the display isn't full of "No" and "0" etc.
    if value in [None, False, 'False', 'false', 'NO', 'No', 'no', 0, '0', '', ' ', 'Null', 'null']: return default

    ret:str = ""
    match type:
        case 'bool': # We're going to display Yes (blanks and False are handled above)
            ret = "Yes"

        case 'datetime': # If it's a datetime convert it from the json date format to our date format
            ret = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M")

        case 'interval': # Approximated interval (no seconds, only show minutes if it's less than a day)
            days , rem = divmod(int(value), 60*60*24)
            hours, rem = divmod(rem, 60*60)
            mins, rem = divmod(rem, 60)
            tmp:list = []
            if floor(days) > 1: tmp.append(f"{floor(days)} days")
            elif int(days) > 0: tmp.append(f"1 day")
            if floor(hours) > 1: tmp.append(f"{floor(hours)} hours")
            elif int(hours) > 0: tmp.append(f" 1 hour")
            if len(tmp) < 2:
                if floor(mins) > 1: tmp.append(f" {int(mins)} minutes")
                elif mins > 0: tmp.append(f" 1 minute")
            ret = ' '.join(tmp)

        case 'num' | 'float' | 'int': # We only shorten/simplify numbers over 100k. Smaller ones we just display with commas at thousands
            if float(value) > 10000:
                abbrs:list[str] = ['', 'K', 'M', 'B', 'T']  # Abbreviations for thousands, millions, billions, trillions
                fnum:float = float('{:.3g}'.format(value))
                magnitude = 0
                while abs(fnum) >= 1000:
                    if magnitude >= len(abbrs) - 1: break
                    magnitude += 1
                    fnum /= 1000.0
                ret = '{}{}'.format('{:f}'.format(fnum).rstrip('0').rstrip('.'), abbrs[magnitude])
            elif float(value) > 100 or type == 'int': # No decimals above 100
                ret = f"{value:,.0f}"
            elif float(value) > 10: # Only 1 above 10
                ret = f"{value:,.1f}"
            elif type == 'float': # Two if it's <10 and a float.
                ret = f"{value:,.2f}"
            else:
                ret = f"{value:,}"

        case _: # Title case two words, leave longer strings as is
            ret = str(value).title() if str(value).count(' ') < 2 and re.search(r"[A-Z0-9]", str(value)) == None else str(value)

    return ret + units


class PopupNotice:
    """ Create a temporary popup window """

    def __init__(self, notice:str = '', timeout:int = 0, config = None) -> None:
        self.config = config

        self.root = tk.Tk()

        if os.environ.get('XDG_SESSION_TYPE', 'x11').lower() == 'wayland':
            print("Wayland detected: Using window types for borderless effect.")
            # 'splash' or 'tooltip' usually removes decorations in Wayland
            self.root.attributes('-type', 'splash')
        else:
            self.root.overrideredirect(True)

        self.root.attributes("-alpha", 0.6)
        self.root.geometry("350x150-1+0")
        self.root.attributes("-topmost", True)

        self.frame = tk.Frame(self.root, bg='red4', relief="raised")
        self.frame.pack(fill="both", expand=True)

        label = tk.Label(self.frame, text=notice, fg="white", bg="red4", font=("Helvetica", 12, "bold"), justify=tk.CENTER)
        label.pack(pady=20, anchor=tk.CENTER)
        exit_btn = tk.Button(self.frame, text="Close", fg="white", bg="red4", command=self.close)
        exit_btn.pack(pady=10)

        if timeout > 0: self.root.after(timeout, self.close)
        self.frame.bind("<Button-1>", self.start_move)
        self.frame.bind("<B1-Motion>", self.do_move)

    def start_move(self, event) -> None:
        self.x:int = event.x
        self.y:int = event.y

    def do_move(self, event) -> None:
        deltax:int = event.x - self.x
        deltay:int = event.y - self.y
        x:int = self.root.winfo_x() + deltax
        y:int = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    @catch_exceptions
    def close(self) -> None:
        if self.root and self.root.winfo_exists():
            #self.config.window_geometries['Alert'] = self.root.winfo_geometry()
            self.root.destroy()
