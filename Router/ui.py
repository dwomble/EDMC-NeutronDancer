import subprocess
import sys
import tkinter as tk
from tkinter import ttk
import tkinter.messagebox as confirmDialog
from functools import partial
import re
import webbrowser

from config import config # type: ignore

from utils.Tooltip import ToolTip
from utils.Autocompleter import Autocompleter
from utils.Placeholder import Placeholder
from utils.Debug import Debug, catch_exceptions
from .constants import lbls, btns, tts, errs, GIT_LATEST

from .context import Context

class UI():
    """
        The main UI for the router.
        It has three states with three different frames.
          - Default, deliberately minimal for when the router isn't being used
          - Plot, a plot entry frame
          - Route, displays the route navigation
    """
    # Singleton pattern
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance


    def __init__(self, parent:tk.Widget|None = None) -> None:
        # Only initialize if it's the first time
        if hasattr(self, '_initialized'): return

        # Initialise the UI
        if parent == None:
            Debug.logger.debug(f"no parent")
            return

        self.error_txt:tk.StringVar = tk.StringVar()
        self.parent:tk.Widget|None = parent
        self.window_route:RouteWindow = RouteWindow(self.parent.winfo_toplevel())
        self.frame:tk.Frame = tk.Frame(parent, borderwidth=2)
        self.frame.grid(sticky=tk.NSEW)
        self.title_fr = None
        self.route_fr = None
        self.plot_fr = None
        self.update:tk.Label

        if Context.updater and Context.updater.update_available:
            Debug.logger.debug(f"UI: Update available")
            Context.updater.install_update = False # We aren't doing auto installs right now
            text:str = lbls['update_available'].format(v=str(Context.updater.update_version))
            self.update = tk.Label(self.frame, text=text, anchor=tk.NW, justify=tk.LEFT, font=("Helvetica", 9, "normal"), cursor='hand2')
            self.update.bind("<Button-1>", partial(self.cancel_update))
            self.update.grid(row=0, column=0, sticky=tk.W)

        self.error_lbl:tk.Label|ttk.Label = self._label(self.frame, textvariable=self.error_txt)
        self.error_lbl.grid(row=1, column=0, columnspan=2)

        self.hide_error()
        self.show_frame('Route' if Context.router.route != [] else 'Default')

        self._initialized = True


    @catch_exceptions
    def cancel_update(self, tkEvent = None) -> None:
        """ Cancel the update if they click """
        webbrowser.open(GIT_LATEST)
        Context.updater.install_update = False
        self.update.destroy()


    @catch_exceptions
    def show_frame(self, which:str = 'Default'):
        """ Display the chosen frame, creating it if necessary """
        Debug.logger.debug(f"Show_frame {which}")
        match which:
            case 'Route':
                if self.route_fr == None:
                    self.route_fr = self._create_route_fr()
                self._update_waypoint()
                Debug.logger.debug(f"Route frame {self.route_fr}")
                self.route_fr.grid()
                if self.plot_fr != None: self.plot_fr.grid_remove()
                self.plot_fr = None
                if self.title_fr != None: self.title_fr.grid_remove()
                self.title_fr = None
            case 'Plot':
                if self.route_fr != None: self.route_fr.grid_remove()
                self.route_fr = None
                if self.plot_fr == None:
                    self.plot_fr = self._create_plot_fr()
                self.plot_fr.grid()
                self.enable_plot_gui(True)
                if self.title_fr != None: self.title_fr.grid_remove()
                self.title_fr = None
            case _:
                if self.route_fr != None: self.route_fr.grid_remove()
                self.route_fr = None
                if self.plot_fr != None: self.plot_fr.grid_remove()
                self.plot_fr = None
                if self.title_fr == None:
                    self.title_fr = self._create_title_fr()
                self.title_fr.grid()


    def _create_title_fr(self) -> tk.Frame:
        """ Create the base/title frame """
        title_fr:tk.Frame = tk.Frame(self.frame)
        if config.get_int('theme') == 1: title_fr.config(bg='black')
        title_fr.grid(row=2, column=0)
        col:int = 0; row:int = 0
        self.lbl = self._label(title_fr, text=lbls["plot_title"], font=("Helvetica", 9, "bold"))
        self.lbl.grid(row=row, column=col, padx=(0,5), pady=5)
        col += 1
        self.plot_gui_btn = self._button(title_fr, text=" "+btns["plot_route"]+" ", command=lambda: self.show_frame('Plot'))
        Debug.logger.debug(f"plot_gui_btn created {self.plot_gui_btn}")
        self.plot_gui_btn.grid(row=row, column=col, sticky=tk.W)
        return title_fr


    def _create_plot_fr(self) -> tk.Frame:
        """ Create the route plotting frame """
        Debug.logger.debug(f"Creating plot frame")
        plot_fr:tk.Frame = tk.Frame(self.frame)
        if config.get_int('theme') == 1: plot_fr.config(bg='black')
        row:int = 2
        col:int = 0

        # Define the popup menu additions
        srcmenu:dict = {}
        destmenu:dict = {}
        shipmenu:dict = {}
        if Context.router.system != '':
            srcmenu[Context.router.system] = [self.menu_callback, 'src']
        for sys in Context.router.history:
            if sys not in srcmenu:
                srcmenu[sys] = [self.menu_callback, 'src']
            if sys not in destmenu:
                destmenu[sys] = [self.menu_callback, 'dest']

        for id, ship in Context.router.ships.items():
            shipmenu[ship.get('name')] = [self.menu_callback, 'ship']

        self.source_ac = Autocompleter(plot_fr, lbls["source_system"], width=30, menu=srcmenu)
        ToolTip(self.source_ac, tts["source_system"])
        if Context.router.src != '': self.set_source_ac(Context.router.src)
        self.source_ac.grid(row=row, column=col, columnspan=2)
        col += 2

        self.range_entry:Placeholder = Placeholder(plot_fr, lbls['range'], width=10, menu=shipmenu,)
        self.range_entry.grid(row=row, column=col)
        ToolTip(self.range_entry, tts["range"])
        # Check if we're having a valid range on the fly
        self.range_entry.var.trace_add('write', self.check_range)
        if Context.router.range > 0: self.range_entry.set_text(str(Context.router.range), False)

        row += 1; col = 0
        self.dest_ac = Autocompleter(plot_fr, lbls["dest_system"], width=30, menu=destmenu)
        ToolTip(self.source_ac, tts["dest_system"])
        if Context.router.dest != '': self.set_dest_ac(Context.router.dest)
        self.dest_ac.grid(row=row, column=col, columnspan=2)
        col += 2

        self.efficiency_slider = tk.Scale(plot_fr, from_=0, to=100, resolution=5, orient=tk.HORIZONTAL, fg='black')
        if config.get_int('theme') == 1: self.efficiency_slider.configure(fg=config.get_str('dark_text'),bg='black', troughcolor='darkgrey', highlightbackground='black', border=0)
        if config.get_int('theme') == 2: self.efficiency_slider.configure(fg=config.get_str('dark_text'), border=0)
        ToolTip(self.efficiency_slider, tts["efficiency"])
        self.efficiency_slider.grid(row=row, column=col)
        self.efficiency_slider.set(Context.router.efficiency)

        row += 1; col = 0
        self.multiplier = tk.IntVar() # Or StringVar() for string values
        self.multiplier.set(Context.router.supercharge_mult)  # Set default value

        # Create radio buttons
        l1 = self._label(plot_fr, text=lbls["supercharge_label"])
        l1.grid(row=row, column=col, padx=5, pady=5)
        col += 1
        r1 = tk.Radiobutton(plot_fr, text=lbls["standard_supercharge"], variable=self.multiplier, value=4)
        if config.get_int('theme') == 1: r1.configure(bg='black', fg=config.get_str('dark_text'))
        r1.grid(row=row, column=col)
        col += 1
        r2 = tk.Radiobutton(plot_fr, text=lbls["overcharge_supercharge"], variable=self.multiplier, value=6)
        if config.get_int('theme') == 1: r2.configure(bg='black', fg=config.get_str('dark_text'))
        r2.grid(row=row, column=col)

        row += 1; col = 0
        self.plot_route_btn = self._button(plot_fr, text=btns["calculate_route"], command=lambda: self.plot_route())
        self.plot_route_btn.grid(row=row, column=col, padx=5, sticky=tk.W)
        col += 1

        self.cancel_plot = self._button(plot_fr, text=btns["cancel"], command=lambda: self.show_frame('None'))
        self.cancel_plot.grid(row=row, column=col, padx=5, sticky=tk.W)
        return plot_fr


    def _update_waypoint(self) -> None:
        if Context.router.route == []:
            return
        self.waypoint_prev_btn.config(state=tk.DISABLED if Context.router.offset == 0 else tk.NORMAL)
        self.waypoint_next_btn.config(state=tk.DISABLED if Context.router.offset >= len(Context.router.route) -1 else tk.NORMAL)
        wp:str = Context.router.next_stop
        if Context.router.jumps != 0:
            wp += f" ({Context.router.jumps} {lbls['jumps'] if Context.router.jumps != 1 else lbls['jump']})"
        self.waypoint_btn.configure(text=wp)
        if Context.router.jumps_left > 0:
            ToolTip(self.waypoint_btn, tts["jump"] + " " + str(Context.router.jumps_left))
        self.ctc(Context.router.next_stop)


    def _create_route_fr(self) -> tk.Frame:
        """ Create the route display frame """
        Debug.logger.debug(f"Creating route frame")
        route_fr:tk.Frame = tk.Frame(self.frame)
        if config.get_int('theme') == 1: route_fr.config(bg='black')
        fr1:tk.Frame = tk.Frame(route_fr)
        if config.get_int('theme') == 1: fr1.config(bg='black')
        fr1.grid_columnconfigure(0, weight=0)
        fr1.grid_columnconfigure(1, weight=1)
        fr1.grid_columnconfigure(2, weight=0)
        fr1.grid_columnconfigure(3, weight=0)
        fr1.grid(row=0, column=0, sticky=tk.W)
        row:int = 2
        col:int = 0
        self.waypoint_prev_btn = self._button(fr1, text=btns["prev"], width=3, command=lambda: Context.router.goto_prev_waypoint())
        self.waypoint_prev_btn.grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)
        Debug.logger.debug(f"waypoint_prev_btn created {self.waypoint_prev_btn}")
        col += 1
        self.waypoint_btn = self._button(fr1, text=Context.router.next_stop, width=30, command=lambda: self.ctc(Context.router.next_stop))
        ToolTip(self.waypoint_btn, tts["jump"] + " " + str(Context.router.jumps_left))
        self.waypoint_btn.grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)
        Debug.logger.debug(f"waypoint_btn created {self.waypoint_btn}")
        col += 1
        self.waypoint_next_btn = self._button(fr1, text=btns["next"], width=3, command=lambda: Context.router.goto_next_waypoint())
        self.waypoint_next_btn.grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)
        Debug.logger.debug(f"waypoint_next_btn created {self.waypoint_next_btn}")
        #row +=1
        #col -= 1
        #self.jumpcounttxt_lbl = self._label(fr1, text=lbls["jumps_remaining"] + " " + str(Context.router.jumps_left))
        #self.jumpcounttxt_lbl.grid(row=row, column=col, padx=5, pady=5)

        fr2:tk.Frame = tk.Frame(route_fr)
        if config.get_int('theme') == 1: fr2.config(bg='black')
        fr2.grid_columnconfigure(0, weight=0)
        fr2.grid_columnconfigure(1, weight=0)
        fr2.grid(row=1, column=0, sticky=tk.W)
        row = 0
        col = 0

        self.show_route_btn = self._button(fr2, text=btns["show_route"], command=lambda: self.window_route.show())
        self.show_route_btn.grid(row=row, column=col, padx=5, sticky=tk.W)
        col += 1
        self.clear_route_btn = self._button(fr2, text=btns["clear_route"], command=lambda: self._clear_route())
        self.clear_route_btn.grid(row=row, column=col, padx=5, sticky=tk.W)

        Debug.logger.debug(f"show_route_btn created {self.show_route_btn}")
        Debug.logger.debug(f"clear_route_btn created {self.clear_route_btn}")

        row += 1; col = 0
        return route_fr


    @catch_exceptions
    def menu_callback(self, field:str = "src", param:str = "None") -> None:
        """ Function called when a custom menu item is selected """
        match field:
            case 'src':
                self.source_ac.set_text(param, False)
            case 'dest':
                self.dest_ac.set_text(param, False)
            case _:
                for id, ship in Context.router.ships.items():
                    if ship.get('name', '') == param:
                        Debug.logger.debug(f"Range set to {param} {ship.get('range', '0.0')}")
                        self.range_entry.set_text(str(ship.get('range', '0.0')), False)
                        self.multiplier.set(6 if ship.get('type', '') in ('explorer_nx') else 4)
                        return


    def set_source_ac(self, text: str) -> None:
        """ Set the start system display """
        if self.source_ac == None: return
        #self.source_ac.set_text(str(range), False)
        self.source_ac.delete(0, tk.END)
        self.source_ac.insert(0, text)
        self.source_ac.set_default_style()


    def set_dest_ac(self, text: str) -> None:
        """ Set the destination system display """
        if self.dest_ac == None: return
        #self.dest_ac.set_text(str(range), False)
        self.dest_ac.delete(0, tk.END)
        self.dest_ac.insert(0, text)
        self.dest_ac.set_default_style()



    def set_range(self, range:float, supercharge_mult:int) -> None:
        """ Set the range display """
        if self.plot_fr == None: return
        self.range_entry.set_text(str(range), False)
        self.multiplier.set(supercharge_mult)


    def _clear_route(self) -> None:
        """ Display a confirmation dialog for clearing the current route """
        clear: bool = confirmDialog.askyesno(
            Context.plugin_name,
            lbls["clear_route_yesno"]
        )
        if clear == True:
            Context.router.clear_route()
            self.show_frame('Plot')
            self.enable_plot_gui(True)


    @catch_exceptions
    def plot_route(self) -> None:
        Debug.logger.debug(f"UI plotting route")
        self.enable_plot_gui(False)
        self.hide_error()

        src:str = self.source_ac.get().strip()
        dest:str = self.dest_ac.get().strip()
        eff:int = int(self.efficiency_slider.get())
        supercharge_mult:int = self.multiplier.get()
        # Hide autocomplete lists in case they're still shown
        if src == '' or dest == '' or dest == self.dest_ac.placeholder:
            Debug.logger.debug(f"src {src} dest {dest} {self.dest_ac.placeholder}")
            self.enable_plot_gui(True)
            return

        try:
            range = float(self.range_entry.var.get())
        except ValueError as e:
            Debug.logger.debug(f"Range error {e}")
            self.show_error(errs["invalid_range"])
            self.enable_plot_gui(True)
            return

        self.source_ac.hide_list()
        self.dest_ac.hide_list()
        res:bool = Context.router.plot_route(src, dest, eff, range, supercharge_mult)
        Debug.logger.debug(f"Route plotted {res}")
        if res == True:
            self.ctc(Context.router.next_stop)
            self.show_frame('Route')
            return
        self.enable_plot_gui(True)


    def show_error(self, error:str|None = None) -> None:
        """ Set and show the error text """
        if error != None:
            self.error_txt.set(error)
        self.error_lbl.grid()


    def hide_error(self) -> None:
        self.error_lbl.grid_remove()


    def enable_plot_gui(self, enable:bool) -> None:
        for elem in [self.source_ac, self.dest_ac, self.efficiency_slider, self.range_entry, self.plot_route_btn, self.cancel_plot]:
            elem.config(state=tk.NORMAL if enable == True else tk.DISABLED)
            elem.update_idletasks()


    def ctc(self, text:str = '') -> None:
        """ Copy text to the clipboard """
        if self.parent == None:
            return
        if text == '': text = Context.router.next_stop

        if Context.router.next_stop == lbls['route_complete']:
            Debug.logger.debug("No next stop to copy, clearing route")
            Context.router.clear_route()
            self.show_frame('None')
            return

        if sys.platform == "linux" or sys.platform == "linux2":
            command = subprocess.Popen(["echo", "-n", text], stdout=subprocess.PIPE)
            subprocess.Popen(["xclip", "-selection", "c"], stdin=command.stdout)
            self.parent.update()
            return

        self.parent.clipboard_clear()
        self.parent.clipboard_append(text)
        self.parent.update()


    def _button(self, fr:tk.Frame, **kw) -> tk.Button|ttk.Button:
        """ Deal with EDMC theme/color weirdness by creating tk buttons for dark mode """
        if config.get_int('theme') == 0: return ttk.Button(fr, **kw)

        return tk.Button(fr, **kw, fg=config.get_str('dark_text'), bg='black', activebackground='black')


    def _label(self, fr:tk.Frame, **kw) -> tk.Label|ttk.Label:
        """ Deal with EDMC theme/color weirdness by creating tk labels for dark mode """
        if config.get_int('theme') == 0: return ttk.Label(fr, **kw)

        return tk.Label(fr, **kw, fg=config.get_str('dark_text'), bg='black')


    @catch_exceptions
    def check_range(self, one, two, three) -> None:
        """ Validate the range entry """

        self.hide_error()
        self.range_entry.set_default_style()

        value:str = self.range_entry.var.get()
        if value == '' or value == self.range_entry.placeholder:
            return

        if not re.match(r"^\d+(\.\d+)?$", value):
            Debug.logger.debug(f"Invalid range entry {value}")
            self.range_entry.set_error_style()
        return


class RouteWindow:
    """
    Treeview display of the current route.
    """
    # Singleton pattern
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance


    def __init__(self, root:tk.Tk|tk.Toplevel) -> None:
        # Only initialize if it's the first time
        if hasattr(self, '_initialized'): return

        self.root:tk.Tk|tk.Toplevel = root
        self.window:tk.Toplevel|None = None
        self.frame:tk.Frame|None = None
        self.scale:float = 1.0

        self._initialized = True


    @catch_exceptions
    def show(self) -> None:
        """ Show our window """

        if self.window is not None and self.window.winfo_exists():
            self.window.destroy()

        if Context.router.headers == [] or Context.router.route == []:
            return

        self.scale = config.get_int('ui_scale') / 100.00
        self.window = tk.Toplevel(self.root)
        self.window.title()
        #self.window.iconphoto(False, 32x32, 16x16)
        self.window.geometry(f"{int(600*self.scale)}x{int(300*self.scale)}")

        self.frame = tk.Frame(self.window, borderwidth=2)
        self.frame.pack(fill=tk.BOTH, expand=True)
        style:ttk.Style = ttk.Style()
        style.configure("My.Treeview.Heading", font=("Helvetica", 9, "bold"), background='lightgrey')

        tree:ttk.Treeview = ttk.Treeview(self.frame, columns=Context.router.headers, show="headings", style="My.Treeview")
        sb:ttk.Scrollbar = ttk.Scrollbar(self.frame, orient=tk.VERTICAL, command=tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        widths:list = [len(w)+1 for w in Context.router.headers]
        for r in Context.router.route:
            widths = [max(widths[i], len(str(w))+1) for i, w in enumerate(r)]

        for i, hdr in enumerate(Context.router.headers):
            tree.heading(hdr, text=hdr, anchor=tk.W if i == 0 else tk.E)
            tree.column(hdr, stretch=tk.NO, width=int(widths[i]*8*self.scale), anchor=tk.W if i == 0 else tk.E)

        for row in Context.router.route:
            tree.insert("", 'end', values=row)

        w:int = sum([int(widths[i]*8*self.scale) for i in range(len(widths))]) + 30
        self.window.geometry(f"{int(w)}x{int(300*self.scale)}")
