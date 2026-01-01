import tkinter as tk
from functools import partial
from config import config  # type: ignore

class Placeholder(tk.Entry):
    """
        An Entry widget with placeholder text functionality
        Borrowed/stolen and modified from https://github.com/CMDR-Kiel42/EDMC_SpanshRouter
    """
    def __init__(self, parent, placeholder, **kw) -> None:
        menu:dict = {}
        if 'menu' in kw:
            menu = kw['menu']
            del kw['menu']

        if parent is not None:
            tk.Entry.__init__(self, parent, **kw)

        self.var = tk.StringVar()
        self["textvariable"] = self.var

        self.placeholder = placeholder
        self.placeholder_color = "grey"
        # Create right click menu
        # @TODO: Use the _rc_menu_install function instead but generalize it for this and EntryPlus use
        self.menu:tk.Menu = tk.Menu(parent, tearoff=0)
        self.menu.add_command(label="Cut")
        self.menu.add_command(label="Copy")
        self.menu.add_command(label="Paste")
        if menu != {}:
            self.menu.add_separator()
            for m, f in menu.items():
                self.menu.add_command(label=m, command=partial(*f, m))
        self.bind('<Button-3>', partial(self.show_menu))

        self.bind("<FocusIn>", self.focus_in)
        self.bind("<FocusOut>", self.focus_out)
        self.bind('<Control-KeyRelease-a>', self.select_all)
        self.bind('<Control-KeyRelease-c>', self.copy)
        self.put_placeholder()

    def show_menu(self, e) -> None:
        self.focus_in(e)
        w = e.widget
        self.menu.entryconfigure("Cut", command=lambda: w.event_generate("<<Cut>>"))
        self.menu.entryconfigure("Copy", command=lambda: w.event_generate("<<Copy>>"))
        self.menu.entryconfigure("Paste", command=lambda: w.event_generate("<<Paste>>"))

        self.menu.tk.call("tk_popup", self.menu, e.x_root, e.y_root)

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
        self['fg'] = config.get_str('dark_text') if config.get_int('theme') > 0 else "black"

    def set_error_style(self, error=True) -> None:
        if error:
            self['fg'] = "red"
        else:
            self.set_default_style()

    def focus_in(self, e, *args) -> None:
        if self['fg'] == "red" or self['fg'] == self.placeholder_color:
            self.set_default_style()
            if self.get() == self.placeholder:
                self.delete('0', 'end')
            return
        self.select_all(e)

    def focus_out(self, *args) -> None:
        if not self.get():
            self.put_placeholder()

    def select_all(self, event) -> None:
        event.widget.event_generate('<<SelectAll>>')

    def copy(self, event) -> None:
        event.widget.event_generate('<<Copy>>')
