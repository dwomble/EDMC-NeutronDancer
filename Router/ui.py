import tkinter as tk
from tkinter import ttk
import tkinter.messagebox as confirmDialog
from typing import TYPE_CHECKING
import re

from config import appname, config # type: ignore

from utils.Tooltip import ToolTip
from utils.Autocompleter import Autocompleter
from utils.Placeholder import Placeholder
from .strings import lbls, btns

from .context import Context, Debug, catch_exceptions

class UI():
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
        self.frame.pack(fill=tk.BOTH, expand=True)
        self.title_fr = None
        self.route_fr = None
        self.plot_fr = None

        Debug.logger.debug(f"Creating Frame")

        self.title_fr = tk.Frame(self.frame)
        self.title_fr.grid(row=0, column=0)
        col:int = 0; row:int = 0
        self.lbl = ttk.Label(self.title_fr, text=lbls["plot_title"], font=("Helvetica", 9, "bold"))
        self.lbl.grid(row=row, column=col, padx=(0,5), pady=5)
        col += 1
        self.plot_gui_btn = ttk.Button(self.title_fr, text=" "+btns["plot_route"]+" ", command=lambda: self.show_frame('Plot'))
        self.plot_gui_btn.grid(row=row, column=col)

        self.route_fr = self._create_route_fr(self.frame)
        self.plot_fr = self._create_plot_fr(self.frame)

        self.csv_route_btn = ttk.Button(self.frame, text=btns["import_file"], command=lambda: Context.router.import_csv)

        self.update_display(True)
        self._initialized = True


    @catch_exceptions
    def update_display(self, show:bool = True) -> None:
        """ Update the display UI """

        self.hide_error()
        if show == False or Context.router.route == []: # We don't have a route so show the plot UI
            self.show_frame('None')
            return

        self.show_frame('Route')
        self.waypoint_btn.configure(text=Context.router.next_stop)
        if Context.router.jumps_left > 0:
            ToolTip(self.waypoint_btn, lbls["jump_tooltip"] + " " + str(Context.router.jumps_left))
#            self.jumpcounttxt_lbl.configure(text=lbls["jumps_remaining"] + str(Context.router.jumps_left))
#        else:
#            self.jumpcounttxt_lbl.grid_remove()

        #if Context.router.roadtoriches:
        #    self.bodies_lbl.configure(text=lbls["body_count"] + Context.router.bodies)
        #else:
        #    self.bodies_lbl.grid_remove()

        #self.fleetrestock_lbl.grid_remove()
        #if Context.router.fleetcarrier:
        #    if Context.router.offset > 0:
        #        restock = Context.router.route[Context.router.offset - 1][2]
        #        if restock.lower() == "yes":
        #            self.fleetrestock_lbl.configure(text=f"At: {Context.router.route[Context.router.offset - 1][0]}\n   {lbls['restock_tritium']}")
        #            self.fleetrestock_lbl.grid()

        self.waypoint_prev_btn.config(state= tk.DISABLED if Context.router.offset == 0 else tk.NORMAL)
        self.waypoint_next_btn.config(state=tk.DISABLED if Context.router.offset == len(Context.router.route) - 1 else tk.NORMAL)


    def set_source_ac(self, text: str):
        self.source_ac.delete(0, tk.END)
        self.source_ac.insert(0, text)
        self.source_ac.set_default_style()

    def set_dest_ac(self, text: str):
        self.dest_ac.delete(0, tk.END)
        self.dest_ac.insert(0, text)
        self.dest_ac.set_default_style()


    def _clear_route(self) -> None:
        clear: bool = confirmDialog.askyesno(
            "SpanshRouterRE",
            "Are you sure you want to clear the current route?"
        )
        if clear == True:
            Context.router.clear_route()
            self.enable_plot_gui(True)


    def _create_route_fr(self, frame:tk.Frame) -> tk.Frame:
        """ Route display frame """

        route_fr:tk.Frame = tk.Frame(frame)
        fr1:tk.Frame = tk.Frame(route_fr)
        fr1.grid_columnconfigure(0, weight=0)
        fr1.grid_columnconfigure(1, weight=1)
        fr1.grid_columnconfigure(2, weight=0)
        fr1.grid_columnconfigure(3, weight=0)
        fr1.grid(row=0, column=0)
        row:int = 0
        col:int = 0
        self.waypoint_prev_btn = ttk.Button(fr1, text=btns["prev"], width=3, command=lambda: Context.router.goto_prev_waypoint())
        self.waypoint_prev_btn.grid(row=row, column=col, padx=5, pady=5)
        col += 1
        self.waypoint_btn = ttk.Button(fr1, text=Context.router.next_stop, width=30, command=lambda: Context.router.copy_waypoint())
        ToolTip(self.waypoint_btn, lbls["jump_tooltip"] + " " + str(Context.router.jumps_left))
        self.waypoint_btn.grid(row=row, column=col, padx=5, pady=5)
        col += 1
        self.waypoint_next_btn = ttk.Button(fr1, text=btns["next"], width=3, command=lambda: Context.router.goto_next_waypoint())
        self.waypoint_next_btn.grid(row=row, column=col, padx=5, pady=5)
        #row +=1
        #col -= 1
        #self.jumpcounttxt_lbl = ttk.Label(fr1, text=lbls["jumps_remaining"] + " " + str(Context.router.jumps_left))
        #self.jumpcounttxt_lbl.grid(row=row, column=col, padx=5, pady=5)

        fr2:tk.Frame = tk.Frame(route_fr)
        fr2.grid_columnconfigure(0, weight=0)
        fr2.grid_columnconfigure(1, weight=1)
        fr2.grid(row=1, column=0)
        row = 0
        col = 0
        #self.bodies_lbl = ttk.Label(fr2, justify=tk.LEFT, text=lbls["body_count"] + ": " + Context.router.bodies)
        #self.bodies_lbl.grid(row=row, column=col, padx=5, pady=5)
        #col += 1
        #self.fleetrestock_lbl = ttk.Label(fr2, justify=tk.LEFT, text=lbls["restock_tritium"])
        #self.fleetrestock_lbl.grid(row=row, column=col, padx=5, pady=5)

        #row += 1
        #col = 0
        #self.export_route_btn = ttk.Button(fr2, text=btns["export_route"], command=lambda: Context.router.export_route())
        #self.export_route_btn.grid(row=row, column=col)

        self.show_route_btn = ttk.Button(fr2, text=btns["show_route"], command=lambda: self.window_route.show())
        self.show_route_btn.grid(row=row, column=col)
        col += 1
        self.clear_route_btn = ttk.Button(fr2, text=btns["clear_route"], command=lambda: self._clear_route())
        self.clear_route_btn.grid(row=row, column=col)


        row += 1; col = 0
        self.error_lbl = ttk.Label(fr2, textvariable=self.error_txt)
        self.error_lbl.grid(row=row, column=col, padx=5, pady=5)

        return route_fr


    def _create_plot_fr(self, frame:tk.Frame) -> tk.Frame:
        """ Route plotting frame """

        plot_fr:tk.Frame = tk.Frame(frame)
        row:int = 0
        col:int = 0

        self.source_ac = Autocompleter(plot_fr, lbls["source_system"], width=30)
        if Context.router.src != '': self.set_source_ac(Context.router.src)
        self.source_ac.grid(row=row, column=col, columnspan=2)
        col += 2

        self.range_entry:Placeholder = Placeholder(plot_fr, lbls['range'], width=10)
        self.range_entry.grid(row=row, column=col)
        ToolTip(self.range_entry, lbls["range_tooltip"])
        # Check if we're having a valid range on the fly
        self.range_entry.var.trace_add('write', self.check_range)
        if Context.router.range > 0: self.range_entry.var.set(str(Context.router.range))

        row += 1; col = 0
        self.dest_ac = Autocompleter(plot_fr, lbls["dest_system"], width=30)
        if Context.router.dest != '': self.set_dest_ac(Context.router.dest)
        self.dest_ac.grid(row=row, column=col, columnspan=2)
        col += 2

        self.efficiency_slider = tk.Scale(plot_fr, from_=1, to=100, orient=tk.HORIZONTAL)
        ToolTip(self.efficiency_slider, lbls["efficiency_tooltip"])
        self.efficiency_slider.grid(row=row, column=col)
        self.efficiency_slider.set(Context.router.efficiency)

        row += 1; col = 0
        self.multiplier = tk.IntVar() # Or StringVar() for string values
        self.multiplier.set(Context.router.supercharge_mult)  # Set default value

        # Create radio buttons
        l1 = ttk.Label(plot_fr, text=lbls["supercharge_label"])
        l1.grid(row=row, column=col, padx=5, pady=5)
        col += 1
        r1 = tk.Radiobutton(plot_fr, text=lbls["standard_supercharge"], variable=self.multiplier, value=4)
        r1.grid(row=row, column=col)
        col += 1
        r2 = tk.Radiobutton(plot_fr, text=lbls["overcharge_supercharge"], variable=self.multiplier, value=6)
        r2.grid(row=row, column=col)

        row += 1; col = 0
        self.plot_route_btn = ttk.Button(plot_fr, text=btns["calculate_route"], command=lambda: self.plot_route())
        self.plot_route_btn.grid(row=row, column=col)
        col += 1

        self.cancel_plot = ttk.Button(plot_fr, text=btns["cancel"], command=lambda: self.show_frame('None'))
        self.cancel_plot.grid(row=row, column=col)
        return plot_fr


    def show_frame(self, which:str = 'None') -> str:
        if self.route_fr == None or self.plot_fr == None or self.title_fr == None: return 'Ok'

        Debug.logger.debug(f"Show_frame {which}")
        match which:
            case 'Route':
                self.route_fr.grid()
                self.plot_fr.grid_forget()
                self.title_fr.grid_forget()
            case 'Plot':
                self.route_fr.grid_forget()
                self.plot_fr.grid()
                self.title_fr.grid_forget()
            case _:
                self.plot_fr.grid_forget()
                self.route_fr.grid_forget()
                self.title_fr.grid()
        return 'Ok'


    @catch_exceptions
    def plot_route(self) -> None:
        Debug.logger.debug(f"UI plotting route")
        self.hide_error()

        src:str = self.source_ac.get().strip()
        dest:str = self.dest_ac.get().strip()
        eff:int = int(self.efficiency_slider.get())
        supercharge_mult:int = self.multiplier.get()
        # Hide autocomplete lists in case they're still shown
        if src == '' or dest == '' or dest == self.dest_ac.placeholder:
            Debug.logger.debug(f"src {src} dest {dest} {self.dest_ac.placeholder}")
            return

        try:
            range = float(self.range_entry.get())
        except ValueError:
            self.set_error("Invalid range")
            return

        self.source_ac.hide_list()
        self.dest_ac.hide_list()
        res:bool = Context.router.plot_route(src, dest, eff, range, supercharge_mult)
        self.show_frame('Route' if res == True else 'Plot')
        self.update_display()


    def set_error(self, text:str) -> None:
        """ Set the error text """
        self.error_txt.set(text)


    def show_error(self, error:str|None = None) -> None:
        """ Set and show the error text """
        if error != None:
            self.error_txt.set(error)
        self.error_lbl.grid()


    def hide_error(self):
        self.error_lbl.grid_remove()


    def enable_plot_gui(self, enable:bool) -> None:
        for elem in [self.source_ac, self.dest_ac, self.efficiency_slider, self.range_entry, self.plot_route_btn, self.cancel_plot]:
            elem.config(state=tk.NORMAL if enable == True else tk.DISABLED)
            elem.update_idletasks()


    def ctc(self, text:str) -> None:
        """ Copy text to the clipboard """
        if self.parent == None:
            return

        self.parent.clipboard_clear()
        self.parent.clipboard_append(text)
        self.parent.update()


    @catch_exceptions
    def check_range(self, one, two, three) -> None:
        """ Validate the range entry"""
        Context.ui.hide_error()
        self.range_entry.set_default_style()

        value:str = self.range_entry.var.get()
        if value == '' or value == self.range_entry.placeholder:
            return

        if not re.match(r"^\d+(\.\d+)?$", value):
            Debug.logger.debug(f"Invalid range entry {value}")
            self.range_entry.set_error_style()
            return

        ship:str = str(Context.router.ship)
        if ship not in Context.router.ships:
            Debug.logger.debug(f"No ship selected or ship {Context.router.ship} not in ships list")
            return

        diff:int = abs(float(value) - Context.router.ships[ship])
        Debug.logger.debug(f"Range {value} Ly for ship {Context.router.ship} {diff}")
        # if the entered value is within 10% of the current ships range we assume it's accurate for this ship
        if abs(float(value) - Context.router.ships[ship]) < (Context.router.ships[ship] / 7):
            Debug.logger.debug(f"Setting range to {value} Ly for ship {ship}")
            Context.router.ships[ship] = float(value)



class RouteWindow:
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

        # On click copy the first column to the clipboard
        def _selected(values, column, tr:ttk.Treeview, iid:str) -> None:
            #Debug.logger.debug(f"Values: {values}, Column: {column}, iid: {iid}")
            if self.frame == None: return
            self.frame.clipboard_clear()
            self.frame.clipboard_append(values[0])

        tree:ttk.Treeview = ttk.Treeview(self.frame, columns=Context.router.headers, show="headings", style="My.Treeview")
        sb:ttk.Scrollbar = ttk.Scrollbar(self.frame, orient=tk.VERTICAL, command=tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for hdr in Context.router.headers:
            tree.heading(hdr, text=hdr, anchor=tk.W)
            tree.column(hdr, anchor=tk.W, stretch=tk.NO, width=int(120*self.scale))

        for row in Context.router.route:
            tree.insert("", 'end', values=row)
