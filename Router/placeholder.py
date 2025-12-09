import tkinter as tk
from config import config  # type: ignore


class Placeholder(tk.Entry):
    """
        An Entry widget with placeholder text functionality
        Borrowed/stolen and modified from https://github.com/CMDR-Kiel42/EDMC_SpanshRouter
    """
    def __init__(self, parent, placeholder, **kw) -> None:
        if parent is not None:
            tk.Entry.__init__(self, parent, **kw)
        self.var = tk.StringVar()
        self["textvariable"] = self.var

        self.placeholder = placeholder
        self.placeholder_color = "grey"

        self.bind("<FocusIn>", self.focus_in)
        self.bind("<FocusOut>", self.focus_out)

        self.put_placeholder()

    def put_placeholder(self) -> None:
        if self.get() != self.placeholder:
            self.set_text(self.placeholder, True)

    def set_text(self, text, placeholder_style=True) -> None:
        if placeholder_style:
            self['fg'] = self.placeholder_color
        else:
            self.set_default_style()
        self.delete(0, tk.END)
        self.insert(0, text)

    def force_placeholder_color(self) -> None:
        self['fg'] = self.placeholder_color

    def set_default_style(self) -> None:
        #theme = config.get_int('theme')
        #self['fg'] = config.get_str('dark_text') if theme else "black"
        self['fg'] = 'black'

    def set_error_style(self, error=True) -> None:
        if error:
            self['fg'] = "red"
        else:
            self.set_default_style()

    def focus_in(self, *args) -> None:
        if self['fg'] == "red" or self['fg'] == self.placeholder_color:
            self.set_default_style()
            if self.get() == self.placeholder:
                self.delete('0', 'end')

    def focus_out(self, *args) -> None:
        if not self.get():
            self.put_placeholder()
