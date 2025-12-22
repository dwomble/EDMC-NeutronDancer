import queue
import threading
import tkinter as tk

from config import config # type: ignore

from .Placeholder import Placeholder

class Autocompleter(Placeholder):
    """
        An Entry widget with autocompletion functionality for system names
        Borrowed/stolen and modified from https://github.com/CMDR-Kiel42/EDMC_SpanshRouter

        @TODO: Modify to support a configurable function to query an API and return a list
    """
    def __init__(self, parent:tk.Frame, placeholder:str, **kw) -> None:
        self.parent:tk.Frame = parent


        self.func = None
        if 'func' in kw:
            self.func = kw['func']
            del kw['func']

        Placeholder.__init__(self, parent, placeholder, **kw)
        self.traceid:str = self.var.trace_add('write', self.changed)

        if 'menu' in kw:
            del kw['menu']
        self.popup:tk.Toplevel = tk.Toplevel(self.parent.winfo_toplevel())
        self.popup.wm_overrideredirect(True)
        self.lb:tk.Listbox = tk.Listbox(self.popup, selectmode=tk.SINGLE, **kw)

        #if config.get_int('theme') > 1: self.lb.configure(fg=config.get("dark_text"))
        #elif config.get_int('theme') > 0:
        #    self.lb.configure(fg=config.get("dark_text"), bg='black')

        self.lb.pack(fill=tk.BOTH, expand=True)
        self.popup.withdraw()
        self.lb_up = False
        self.has_selected = False
        self.queue:queue.Queue = queue.Queue()

        self.bind("<Any-Key>", self.keypressed)
        self.lb.bind("<Any-Key>", self.keypressed)
        self.lb.bind("<ButtonRelease-1>", self.selection)
        self.bind("<FocusOut>", self.ac_focus_out)
        self.lb.bind("<FocusOut>", self.ac_focus_out)
        self.update_me()

    def ac_focus_out(self, event=None) -> None:
        x, y = self.parent.winfo_pointerxy()
        widget_under_cursor:tk.Misc|None = self.parent.winfo_containing(x, y)
        if (widget_under_cursor != self.lb and widget_under_cursor != self) or event is None:
            self.focus_out()
            self.hide_list()

    def keypressed(self, event) -> None:
        key = event.keysym
        if key == 'Down':
            self.down(event.widget.widgetName)
        elif key == 'Up':
            self.up(event.widget.widgetName)
        elif key in ['Return', 'Right']:
            if self.lb_up:
                self.selection()
        elif key in ['Escape', 'Tab', 'ISO_Left_Tab'] and self.lb_up:
            self.hide_list()

    def changed(self, name=None, index=None, mode=None) -> None:
        value:str = self.var.get()
        if value.__len__() < 3 and self.lb_up or self.has_selected:
            self.hide_list()
            self.has_selected = False
        else:
            t = threading.Thread(target=self.get_list, args=[value])
            t.start()

    def selection(self, event=None) -> None:
        if self.lb_up:
            self.has_selected = True
            index = self.lb.curselection()
            self.var.trace_remove("write", self.traceid)

            self.var.set(self.lb.get(index))
            self.hide_list()
            self.icursor(tk.END)
            self.traceid = self.var.trace_add('write', self.changed)

    def up(self, widget) -> None:
        if self.lb_up:
            if self.lb.curselection() == ():
                index = '0'
            else:
                index = self.lb.curselection()[0]
            if index != '0':
                self.lb.selection_clear(first=index)
                index = str(int(index) - 1)
                self.lb.selection_set(first=index)
                if widget != "listbox":
                    self.lb.activate(index)

    def down(self, widget) -> None:
        if self.lb_up:
            if self.lb.curselection() == ():
                index = '0'
            else:
                index = self.lb.curselection()[0]
                if int(index + 1) != tk.END:
                    self.lb.selection_clear(first=index)
                    index = str(int(index + 1))

            self.lb.selection_set(first=index)
            if widget != "listbox":
                self.lb.activate(index)
        else:
            self.changed()

    def show_results(self, results) -> None:
        if results:
            self.lb.delete(0, tk.END)
            for w in results:
                self.lb.insert(tk.END, w)

            self.show_list(len(results))
        else:
            if self.lb_up:
                self.hide_list()

    def show_list(self, height) -> None:
        self.lb["height"] = height
        if not self.lb_up and self.parent.focus_get() is self:
            x:int = self.winfo_rootx()
            y:int = self.winfo_rooty() + self.winfo_height()
            self.popup.wm_geometry(f"+{x}+{y}")
            self.popup.deiconify() # Show the popup
            self.lb_up = True

    def hide_list(self) -> None:
        if self.lb_up:
            self.popup.withdraw()
            self.lb_up = False

    def get_list(self, inp:str) -> None:
        inp = inp.strip()
        if inp != self.placeholder and inp.__len__() >= 3 and self.func != None:
            lista = self.func(inp)
            if lista:
                self.queue.put(lista)

    def update_me(self) -> None:
        try:
            while 1:
                lista = self.queue.get_nowait()
                self.show_results(lista)
                self.update_idletasks()
        except queue.Empty:
            pass
        self.after(100, self.update_me)

    def set_text(self, text, placeholder_style=True) -> None:
        if placeholder_style:
            self['fg'] = self.placeholder_color
        else:
            self.set_default_style()

        try:
            self.var.trace_remove("write", self.traceid)
        except:
            pass
        finally:
            self.delete(0, tk.END)
            self.insert(0, text)
            self.traceid = self.var.trace_add('write', self.changed)
