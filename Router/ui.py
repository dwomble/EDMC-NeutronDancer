import tkinter as tk
from tkinter import ttk
import tkinter.messagebox as confirmDialog
from functools import partial
import re
import requests
import json

from config import config # type: ignore
from theme import theme #type: ignore

from utils.tooltip import Tooltip
from utils.autocompleter import Autocompleter
from utils.placeholder import Placeholder
from utils.treeviewplus import TreeviewPlus
from utils.debug import Debug, catch_exceptions
from utils.misc import frame, labelframe, button, label, radiobutton, combobox, scale, listbox, hfplus

from .constants import NAME, HEADER_TYPES, lbls, btns, tts
from .ship import Ship
from .route import Route
from .context import Context

class UI():
    """
        The main UI for the router.
        It has three states with three different frames.
          - Default, deliberately minimal for when the router isn't being used
          - Plot, a plot entry frame with neutron and galaxy route variants
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
            Debug.logger.info(f"No parent")
            return

        self.parent:tk.Widget|None = parent
        self.window_route:RouteWindow = RouteWindow(self.parent.winfo_toplevel())
        self.frame:tk.Frame = frame(parent, borderwidth=2)
        self.frame.grid(sticky=tk.NSEW)

        self.update:tk.Label

        self.error_lbl:tk.Label|ttk.Label = label(self.frame, text="", foreground='red')
        self.error_lbl.grid(row=1, column=0, columnspan=2, padx=5, sticky=tk.W)

        self.router:tk.StringVar = tk.StringVar()
        self.router.set('Neutron')  # Set default value

        self.error_txt:tk.StringVar = tk.StringVar()
        self.hide_error()

        self.progbar:ttk.Progressbar # Overall progress bar

        self.title_fr:tk.Frame = self._create_title_fr(self.frame)
        self.neutron_fr:tk.Frame = self._create_neutron_fr(self.frame)
        self.galaxy_fr:tk.Frame = self._create_galaxy_fr(self.frame)
        self.route_fr:tk.Frame = self._create_route_fr(self.frame)

        self.subfr:tk.Frame = self.title_fr
        self.show_frame('Route' if Context.route.route != [] else 'Default')

        # Wait a while before deciding if we should show the update text
        parent.after(30000, lambda: self.show_update())
        self._initialized = True


    @catch_exceptions
    def show_update(self) -> None:
        """ Display the update text if appropriate"""
        if Context.updater.update_available == False or Context.updater.install_update == False or Context.updater.zip_downloaded == "":
            return

        text:str = lbls['update_available'].format(v=str(Context.updater.update_version))
        self.update = tk.Label(self.frame, text=text, anchor=tk.NW, justify=tk.LEFT, foreground='blue', font=("Helvetica", 9, "normal"), cursor='hand2')
        if Context.updater.releasenotes != "":
            Tooltip(self.update, text=tts["releasenotes"].format(c=Context.updater.releasenotes))
        self.update.bind("<Button-1>", partial(self.cancel_update))
        self.update.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)


    @catch_exceptions
    def cancel_update(self, tkEvent = None) -> None:
        """ Cancel the update if they click """
        #webbrowser.open(GIT_LATEST)
        Context.updater.install_update = False
        self.update.destroy()


    @catch_exceptions
    def show_frame(self, which:str = 'Default', destroy:bool = False) -> None:
        """ Display the chosen frame, recreating it if necessary """
        #Debug.logger.debug(f"Show_frame called: {which} Ship: {Context.router.ship} Current range: {Context.router.ship.get_range(Context.router.cargo)}")
        self.subfr.grid_remove()


        Context.router.neutron_params['range'] = f"{Context.router.ship.get_range(Context.router.cargo):.2f}" if Context.router.ship else "32.0"
        Context.router.neutron_params['supercharge_mult'] = Context.router.ship.supercharge_mult if Context.router.ship else 4
        if Context.router.cargo != 0 and Context.router.cargo != Context.router.galaxy_params.get('cargo', 0):
            Context.router.galaxy_params['cargo'] = Context.router.cargo

        match which:
            case 'Route':
                if destroy == True:
                    self.route_fr.destroy()
                    self.route_fr = self._create_route_fr(self.frame)
                self.subfr = self.route_fr
                self.update_waypoint()

            case 'Neutron':
                self.neutron_fr.destroy()
                self.neutron_fr = self._create_neutron_fr(self.frame)

                self.subfr = self.neutron_fr
                self.router.set('Neutron')
                self.enable_plot_gui(True)

            case 'Galaxy':
                self.galaxy_fr.destroy()
                self.galaxy_fr = self._create_galaxy_fr(self.frame)

                self.subfr = self.galaxy_fr
                self.router.set('Galaxy')
                self.enable_plot_gui(True)

            case _:
                self.title_fr.destroy()
                self.title_fr = self._create_title_fr(self.frame)
                self.subfr = self.title_fr

        self.subfr.grid(row=2, column=0)


    def _create_title_fr(self, parent:tk.Frame) -> tk.Frame:
        """ Create the base/title frame """
        title_fr:tk.Frame = frame(parent)
        col:int = 0; row:int = 0
        self.lbl:tk.Label|ttk.Label = label(title_fr, text=lbls["plot_title"], font=("Helvetica", 9, "bold"))
        self.lbl.grid(row=row, column=col, padx=(0,5), pady=5)
        col += 1
        plot_gui_btn:tk.Button|ttk.Button = button(title_fr, text=" "+btns["plot_route"]+" ", command=lambda: self.show_frame(Context.router.last_plot))
        plot_gui_btn.grid(row=row, column=col, sticky=tk.W)

        return title_fr


    def _plot_switcher(self, fr:tk.Frame, row:int, col:int) -> None:
        """ Switch between the two route plotters """
        sfr:tk.Frame = frame(fr)
        r1:tk.Radiobutton|ttk.Radiobutton = radiobutton(sfr, text=lbls["neutron_router"], variable=self.router, value='Neutron', command=lambda: self.show_frame('Neutron'))
        r1.grid(row=0, column=0, padx=5, pady=5)
        r2:tk.Radiobutton|ttk.Radiobutton = radiobutton(sfr, text=lbls["galaxy_router"], variable=self.router, value='Galaxy', command=lambda: self.show_frame('Galaxy'))
        r2.grid(row=0, column=1, padx=5, pady=5)
        sfr.grid(row=row, column=col, columnspan=3, sticky=tk.W)


    def _create_galaxy_fr(self, parent:tk.Frame) -> tk.Frame:
        """ Create the galaxy route plotting frame """

        plot_fr:tk.Frame = frame(parent)
        row:int = 2
        col:int = 0

        params:dict = Context.router.galaxy_params

        # Define the popup menu additions
        srcmenu:dict = {}
        destmenu:dict = {}

        if Context.router.system != '':
            srcmenu[Context.router.system] = [self.menu_callback, 'src']
        for sys in Context.router.history:
            if sys not in srcmenu:
                srcmenu[sys] = [self.menu_callback, 'src']
            if sys not in destmenu:
                destmenu[sys] = [self.menu_callback, 'dest']

        self._plot_switcher(plot_fr, row, col)

        row +=1; col = 0

        # First row
        self.gal_source_ac = Autocompleter(plot_fr, lbls["source_system"], width=30, menu=srcmenu, func=self.query_systems)
        Tooltip(self.gal_source_ac, tts["source_system"])
        if Context.router.src != '': self.set_entry(self.gal_source_ac, Context.router.src)
        self.gal_source_ac.grid(row=row, column=col, columnspan=2, padx=5, pady=5)
        col += 2

        self.optionlist:list = ['is_supercharged', 'use_supercharge', 'use_injections', 'exclude_secondary', 'refuel_every_scoopable']
        self.gallb:tk.Listbox = listbox(plot_fr, [lbls[v] for v in self.optionlist])
        Tooltip(self.gallb, tts['galaxy_options'])

        for i, item in enumerate(self.optionlist):
            if params.get(item, False) == True:
                self.gallb.selection_set(i)
        self.gallb.grid(row=row, column=col, rowspan=3, padx=5, pady=5)

        # Row two
        row += 1; col = 0
        self.gal_dest_ac = Autocompleter(plot_fr, lbls["dest_system"], width=30, menu=destmenu, func=self.query_systems)
        Tooltip(self.gal_dest_ac, tts["dest_system"])
        if Context.router.dest != '': self.set_entry(self.gal_dest_ac, Context.router.dest)
        self.gal_dest_ac.grid(row=row, column=col, columnspan=2, padx=5, pady=5)

        # Row three
        row += 1; col = 0
        shiplist:list = [s.name for s in Context.router.ships.values()]
        init:str = params.get('ship', '') if params.get('ship', '') in shiplist else shiplist[0] if len(shiplist) else ""
        self.ship:tk.StringVar = tk.StringVar(plot_fr, value=init)
        self.shipdd:ttk.Combobox|tk.OptionMenu = combobox(plot_fr, self.ship, values=shiplist, width=10)
        Tooltip(self.shipdd, tts["select_ship"])
        self.shipdd.grid(row=row, column=col, padx=5, pady=5)

        col += 1

        self.cargo_entry:Placeholder = Placeholder(plot_fr, lbls['cargo'], width=11, justify=tk.CENTER)
        if params.get('cargo', 0) != 0:
            self.set_entry(self.cargo_entry, str(params.get('cargo', 0)))
        elif Context.router.cargo != 0:
            self.set_entry(self.cargo_entry, str(Context.router.cargo))

        self.cargo_entry.grid(row=row, column=col, padx=5, pady=5)
        Tooltip(self.cargo_entry, tts["cargo"])

        row += 1; col = 0
        algorithms:list = ['Fuel', 'Fuel Jumps', 'Guided', 'Optimistic', 'Pessimistic']
        self.algorithm:tk.StringVar = tk.StringVar(plot_fr, value=params.get('algorithm', 'Optimistic'))
        algodd:ttk.Combobox|tk.OptionMenu = combobox(plot_fr, self.algorithm, values=algorithms, width=10)
        Tooltip(algodd, tts["select_algorithm"])
        algodd.grid(row=row, column=col, padx=5, pady=5)

        col += 1
        self.fuel_res:Placeholder = Placeholder(plot_fr, lbls['fuel_reserve'], width=11, justify=tk.CENTER)
        if params.get('fuel_reserve', 0) != 0:
            self.set_entry(self.fuel_res, str(params.get('fuel_reserve', 0)))
        Tooltip(self.fuel_res, tts["fuel_reserve"])
        self.fuel_res.grid(row=row, column=col, padx=5, pady=5)

        col += 1
        self.time_limit:tk.Scale|ttk.Scale = scale(plot_fr, from_=60, to=120, resolution=5, orient=tk.HORIZONTAL)
        Tooltip(self.time_limit, tts["calc_time"])
        self.time_limit.grid(row=row, column=col, pady=5)
        self.time_limit.set(params.get('max_time', 60))


        # Row ?
        row += 1; col = 0
        btn_frame:tk.Frame = frame(plot_fr)
        btn_frame.grid(row=row, column=col, columnspan=3, sticky=tk.W)

        r = 0; col = 0
        self.gal_import_route_btn:tk.Button|ttk.Button = button(btn_frame, text=btns["import_route"], command=lambda: self.import_route())
        self.gal_import_route_btn.grid(row=r, column=col, padx=5, sticky=tk.W)
        col += 1

        self.gal_plot_route_btn:tk.Button|ttk.Button = button(btn_frame, text=btns["calculate_route"], command=lambda: self.galaxy_plot())
        self.gal_plot_route_btn.grid(row=r, column=col, padx=5, sticky=tk.W)
        col += 1

        self.gal_cancel_plot:tk.Button|ttk.Button = button(btn_frame, text=btns["cancel"], command=lambda: self.show_frame('None'))
        self.gal_cancel_plot.grid(row=r, column=col, padx=5, sticky=tk.W)

        return plot_fr


    def _create_neutron_fr(self, parent:tk.Frame) -> tk.Frame:
        """ Create the neutron route plotting frame """

        plot_fr:tk.Frame = frame(parent)
        row:int = 2
        col:int = 0

        params:dict = Context.router.neutron_params

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

        # Create right click menu
        for id in Context.router.used_ships:
            if id in Context.router.ships.keys():
                ship:Ship = Context.router.ships[id]
                shipmenu[ship.name] = [self.menu_callback, 'ship']

        if shipmenu != {}:
            self.menu:tk.Menu = tk.Menu(plot_fr, tearoff=0)
            for m, f in shipmenu.items():
                self.menu.add_command(label=m, command=partial(*f, m))


        self._plot_switcher(plot_fr, row, col)

        row +=1; col = 0
        self.source_ac = Autocompleter(plot_fr, lbls["source_system"], width=30, menu=srcmenu, func=self.query_systems)
        Tooltip(self.source_ac, tts["source_system"])
        if Context.router.src != '': self.set_entry(self.source_ac, Context.router.src)
        self.source_ac.grid(row=row, column=col, columnspan=2)
        col += 2

        self.range_entry:Placeholder = Placeholder(plot_fr, lbls['range'], width=11, menu=shipmenu, justify=tk.CENTER)
        self.range_entry.grid(row=row, column=col)
        Tooltip(self.range_entry, tts["range"])
        # Check if we're having a valid range on the fly
        self.range_entry.var.trace_add('write', self.check_range)
        self.range_entry.set_text(str(params.get('range', None)), False)

        row += 1; col = 0
        self.dest_ac = Autocompleter(plot_fr, lbls["dest_system"], width=30, menu=destmenu, func=self.query_systems)
        Tooltip(self.dest_ac, tts["dest_system"])
        if Context.router.dest != '': self.set_entry(self.dest_ac, Context.router.dest)
        self.dest_ac.grid(row=row, column=col, columnspan=2)
        col += 2

        self.efficiency_slider:tk.Scale|ttk.Scale = scale(plot_fr, from_=0, to=100, resolution=5, orient=tk.HORIZONTAL)
        self.efficiency_slider.bind('<Button-3>', self.show_menu)
        Tooltip(self.efficiency_slider, tts["efficiency"])
        self.efficiency_slider.grid(row=row, column=col)
        self.efficiency_slider.set(params.get('efficiency', 60))

        row += 1; col = 0
        self.multiplier = tk.IntVar() # Or StringVar() for string values
        self.multiplier.set(params.get('supercharge_mult', 4))  # Set default value

        # Create radio buttons
        l1:tk.Label|ttk.Label = label(plot_fr, text=lbls["supercharge_label"])
        l1.grid(row=row, column=col, padx=5, pady=5)
        col += 1
        r1:tk.Radiobutton|ttk.Radiobutton = radiobutton(plot_fr, text=lbls["standard_supercharge"], variable=self.multiplier, value=4)
        r1.bind('<Button-3>', self.show_menu)
        Tooltip(r1, tts['standard_multiplier'])

        r1.grid(row=row, column=col)
        col += 1
        r2:tk.Radiobutton|ttk.Radiobutton = radiobutton(plot_fr, text=lbls["overcharge_supercharge"], variable=self.multiplier, value=6)
        Tooltip(r2, tts['overcharge_multiplier'])
        r2.bind('<Button-3>', self.show_menu)
        r2.grid(row=row, column=col)

        row += 1; col = 0
        btn_frame:tk.Frame = frame(plot_fr)
        btn_frame.grid(row=row, column=col, columnspan=3, sticky=tk.W)

        r = 0; col = 0
        self.import_route_btn:tk.Button|ttk.Button = button(btn_frame, text=btns["import_route"], command=lambda: self.import_route())
        self.import_route_btn.grid(row=r, column=col, padx=5, sticky=tk.W)
        col += 1

        self.plot_route_btn:tk.Button|ttk.Button = button(btn_frame, text=btns["calculate_route"], command=lambda: self.neutron_plot())
        self.plot_route_btn.grid(row=r, column=col, padx=5, sticky=tk.W)
        col += 1

        self.cancel_plot:tk.Button|ttk.Button = button(btn_frame, text=btns["cancel"], command=lambda: self.show_frame('Default'))
        self.cancel_plot.grid(row=r, column=col, padx=5, sticky=tk.W)

        return plot_fr


    @catch_exceptions
    def show_menu(self, e) -> str:
        #w = e.widget
        #self.menu.tk.call("tk_popup", self.menu, e.x_root, e.y_root)
        self.menu.post(e.x_root, e.y_root)
        return "break"


    def _progress(self) -> int:
        """ Return progress as a percentage """
        if Context.route.route == []: return 0

        if Context.route.jumps_remaining() == 0: return 100

        if Context.route.total_dist() > 0:
            return round(Context.route.perc_dist_rem())
        return round(Context.route.perc_jumps_rem())


    @catch_exceptions
    def _update_progbar(self) -> None:
        """ Update our progress tooltips and progress bar """
        if Context.route.route == []:
            return

        tt:str = ""
        if Context.route.jumps_remaining() > 0:
            tt = tts["jump"].format(j=str(Context.route.jumps_remaining()), d="")

        if Context.route.dist_remaining() > 0:
            d:tuple = tuple([Context.route.dist_remaining(), 'float', '', ' Ly'])
            tt = tts["jump"].format(j=str(Context.route.jumps_remaining()), d="("+hfplus(d)+") ")

        if Context.route.jumps_per_hour() > 0:
            j:tuple = tuple([Context.route.jumps_per_hour(), 'float'])
            d:tuple = tuple([Context.route.dist_per_hour(), 'float'])
            tt += "\n" + tts['speed'].format(j=hfplus(j), d=hfplus(d))

        Tooltip(self.progbar, tt)

        if not hasattr(self, "route_fr"): return
        # Update the progress bar's width to match our frame
        self.bar_fr.configure(width=self.route_fr.winfo_width()-5)
        self.progbar.configure(length=self.route_fr.winfo_width()-5, value=self._progress())


    @catch_exceptions
    def update_waypoint(self) -> None:
        if Context.route.route == [] or not hasattr(self, 'waypoint_btn'):
            return

        self.waypoint_prev_btn.config(state=tk.DISABLED if Context.route.offset == 0 else tk.NORMAL)
        self.waypoint_next_btn.config(state=tk.DISABLED if Context.route.offset >= len(Context.route.route) -1 else tk.NORMAL)
        wp:str = Context.route.next_stop()
        if Context.route.jumps_to_wp() != 0:
            wp += f" ({Context.route.jumps_to_wp()} {lbls['jumps'] if Context.route.jumps_to_wp() != 1 else lbls['jump']})"
        self.waypoint_btn.configure(text=wp, width=max(len(wp)-2, 40))
        self._update_progbar()
        self.ctc(Context.route.next_stop())


    def _create_route_fr(self, parent:tk.Frame) -> tk.Frame:
        """ Create the route display frame """

        route_fr:tk.Frame = frame(parent)
        self.bar_fr:tk.LabelFrame = labelframe(route_fr, border=0, height=10, width=400)
        self.bar_fr.grid_rowconfigure(0, weight=1)
        self.bar_fr.grid_propagate(False)
        self.bar_fr.grid(row=0, column=0, pady=0, sticky=tk.EW)

        self.progbar = ttk.Progressbar(self.bar_fr, orient=tk.HORIZONTAL, value=self._progress(), maximum=100, mode='determinate', length=400)
        self.progtt:Tooltip = Tooltip(self.progbar, text=tts["progress"])
        self.progbar.rowconfigure(0, weight=1)
        self.progbar.grid(row=0, column=0, pady=0, ipady=0, sticky=tk.EW)
        self._update_progbar()

        parent.after(5000, self._update_progbar) # We may need to wait til TK has finished loading before updating the progress bar

        fr1:tk.Frame = frame(route_fr)
        fr1.grid_columnconfigure(0, weight=0)
        fr1.grid_columnconfigure(1, weight=1)
        fr1.grid_columnconfigure(2, weight=0)
        fr1.grid_columnconfigure(3, weight=0)
        fr1.grid(row=1, column=0, sticky=tk.W)

        row:int = 0; col:int = 0
        self.waypoint_prev_btn:tk.Button|ttk.Button = button(fr1, text=btns["prev"], width=3, command=lambda: self.goto_prev_waypoint())
        self.waypoint_prev_btn.grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)

        col += 1
        self.waypoint_btn:tk.Button|ttk.Button = button(fr1, text=Context.route.next_stop(), width=40, command=lambda: self.ctc(Context.route.next_stop()))
        Tooltip(self.waypoint_btn, tts["copy_to_clipboard"])
        self.waypoint_btn.grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)

        col += 1
        self.waypoint_next_btn:tk.Button|ttk.Button = button(fr1, text=btns["next"], width=3, command=lambda: self.goto_next_waypoint())
        self.waypoint_next_btn.grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)

        fr2:tk.Frame = frame(route_fr)
        fr2.grid_columnconfigure(0, weight=0)
        fr2.grid_columnconfigure(1, weight=0)
        fr2.grid(row=2, column=0, sticky=tk.W)
        row = 0; col = 0

        self.export_route_btn:tk.Button|ttk.Button = button(fr2, text=btns["export_route"], command=lambda: self._export_route())
        self.export_route_btn.grid(row=row, column=col, padx=5, sticky=tk.W)

        col += 1
        self.show_route_btn:tk.Button|ttk.Button = button(fr2, text=btns["show_route"], command=lambda: self.window_route.show())
        self.show_route_btn.grid(row=row, column=col, padx=5, sticky=tk.W)

        col += 1
        self.clear_route_btn:tk.Button|ttk.Button = button(fr2, text=btns["clear_route"], command=lambda: self._clear_route())
        self.clear_route_btn.grid(row=row, column=col, padx=5, sticky=tk.W)

        return route_fr


    @catch_exceptions
    def menu_callback(self, field:str = "src", param:str = "None") -> None:
        """ Function called when a custom menu item is selected """
        match field:
            case 'src':
                self.source_ac.set_text(param, False)
                self.gal_source_ac.set_text(param, False)
            case 'dest':
                self.dest_ac.set_text(param, False)
                self.gal_dest_ac.set_text(param, False)
            case _:
                for ship in Context.router.ships.values():
                    if ship.name == param:
                        self.range_entry.set_text(ship.get_range(Context.router.cargo), False)
                        self.multiplier.set(ship.supercharge_mult)
                        # Set ship in the galaxy form
                        return


    def set_entry(self, which, text:str) -> None:
        """ Set a system """
        if which == None: return
        which.delete(0, tk.END)
        which.insert(0, text)
        which.set_default_style()


    def switch_ship(self, ship:Ship) -> None:
        """ Set the range display """

        self.range_entry.set_text(str(ship.get_range(Context.router.cargo)), False)
        self.multiplier.set(ship.supercharge_mult)
        if hasattr(self, "shipdd"): # Update the ships dropdown list
            self.shipdd['values'] = [s.name for s in Context.router.ships.values()] # This may error in dark mode.


    def _export_route(self) -> None:
        if Context.router == None or Context.router.export_route() == False:
            Debug.logger.error(f"Failed to load route")
            return

        self.show_frame('Route')


    def _clear_route(self) -> None:
        """ Display a confirmation dialog for clearing the current route """
        clear:bool = confirmDialog.askyesno(
            Context.plugin_name,
            lbls["clear_route_yesno"]
        )
        if clear == True:
            self.show_frame(Context.router.last_plot)
            Context.route = Route()
            self.enable_plot_gui(True)


    @catch_exceptions
    def import_route(self) -> None:
        if Context.router == None or Context.router.import_route() == False:
            Debug.logger.error(f"Failed to load route")
            self.show_frame(Context.router.last_plot)
            self.enable_plot_gui(True)
            return
        self.show_frame('Route')


    @catch_exceptions
    def neutron_plot(self) -> None:
        self.hide_error()
        self.enable_plot_gui(False)

        self.source_ac.hide_list()
        self.dest_ac.hide_list()

        params:dict = {}

        params['from'] = self.source_ac.get().strip()
        if params['from'] not in self.query_systems(params['from']):
            self.enable_plot_gui(True)
            self.source_ac.set_error_style()
            return

        params['to'] = self.dest_ac.get().strip()
        if params['to'] not in self.query_systems(params['to']):
            self.enable_plot_gui(True)
            self.dest_ac.set_error_style()
            return

        params['efficiency'] = int(self.efficiency_slider.get())
        params['supercharge_mult'] = self.multiplier.get()
        params['range'] = self.range_entry.var.get()
        if not re.match(r"^\d+(\.\d+)?$", params['range']):
            Debug.logger.debug(f"Invalid range entry {params['range']}")
            self.range_entry.set_error_style()
            return

        Context.router.plot_route('Neutron', params)


    @catch_exceptions
    def galaxy_plot(self) -> None:
        self.hide_error()
        self.enable_plot_gui(False)

        self.source_ac.hide_list()
        self.dest_ac.hide_list()

        ship_id:str = ''
        for id, ship in Context.router.ships.items():
            if ship.name == self.ship.get():
                ship_id = id
                break

        params:dict = {
            'source': self.gal_source_ac.get().strip(),
            'destination': self.gal_dest_ac.get().strip(),
            'cargo': int(self.cargo_entry.get().strip()) if re.match(r"^\d+$", self.cargo_entry.get().strip()) else 0,
            'max_time': int(self.time_limit.get()),
            'algorithm': self.algorithm.get(),
            'fuel_reserve': int(self.fuel_res.get().strip()) if re.match(r"^\d+(\.\d+)?$", self.fuel_res.get().strip()) else 0,
            'is_supercharged': self.gallb.selection_includes(self.optionlist.index('is_supercharged')),
            'use_supercharge': self.gallb.selection_includes(self.optionlist.index('use_supercharge')),
            'use_injections': self.gallb.selection_includes(self.optionlist.index('use_injections')),
            'exclude_secondary': self.gallb.selection_includes(self.optionlist.index('exclude_secondary')),
            'refuel_every_scoopable': self.gallb.selection_includes(self.optionlist.index('refuel_every_scoopable')),
            'fuel_power': Context.router.ships[ship_id].fuel_power,
            'fuel_multiplier': Context.router.ships[ship_id].fuel_multiplier,
            'optimal_mass': Context.router.ships[ship_id].optimal_mass,
            'base_mass': Context.router.ships[ship_id].base_mass,
            'tank_size': Context.router.ships[ship_id].tank_size,
            'internal_tank_size': Context.router.ships[ship_id].internal_tank_size,
            'max_fuel_per_jump': Context.router.ships[ship_id].max_fuel_per_jump,
            'range_boost': Context.router.ships[ship_id].range_boost,
            'ship_build': Context.router.ships[ship_id].loadout,
            'supercharge_multiplier': Context.router.ships[ship_id].supercharge_mult,
            'injection_multiplier': Context.router.ships[ship_id].injection_mult
            }

        Context.router.plot_route('Galaxy', params)


    def show_error(self, error:str|None = None) -> None:
        """ Set and show the error text """
        if error == None: return
        Debug.logger.debug(f"Showing error {error}")
        self.error_lbl['text'] = error
        self.error_lbl.grid()


    def hide_error(self) -> None:
        self.error_lbl.grid_remove()


    def enable_plot_gui(self, enable:bool) -> None:
        for elem in [self.source_ac, self.dest_ac, self.efficiency_slider, self.range_entry, self.import_route_btn, self.plot_route_btn, self.cancel_plot]:
            elem.config(state=tk.NORMAL if enable == True else tk.DISABLED)
            elem.update_idletasks()
        self.subfr.config(cursor="" if enable == True else "watch")


    def goto_next_waypoint(self) -> None:
        """ Move to the next waypoint """
        Context.route.update_route(1)
        self.update_waypoint()


    def goto_prev_waypoint(self) -> None:
        """ Move back to the previous waypoint """
        Context.route.update_route(-1)
        self.update_waypoint()


    def ctc(self, text:str = '') -> None:
        """ Copy text to the clipboard """
        if self.parent == None: return
        self.parent.clipboard_clear()
        self.parent.clipboard_append(text)
        self.parent.update()


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


    @catch_exceptions
    def query_systems(self, inp:str) -> list:
        """ Function called by Autocompleter """
        inp = inp.strip()
        url = "https://spansh.co.uk/api/systems?"
        results:requests.Response = requests.get(url, params={'q': inp}, headers={'User-Agent': Context.plugin_useragent}, timeout=3)
        return json.loads(results.content)


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

        if Context.route.hdrs == [] or Context.route.route == []:
            return

        self.scale = config.get_int('ui_scale') / 100.00
        self.window = tk.Toplevel(self.root)
        self.window.title(f"{NAME} – {lbls['route']}")
        self.window.geometry(f"{int(600*self.scale)}x{int(300*self.scale)}")

        self.frame = tk.Frame(self.window, borderwidth=2)
        self.frame.pack(fill=tk.BOTH, expand=True)
        style:ttk.Style = ttk.Style()
        style.configure("My.Treeview.Heading", font=("Helvetica", 9, "bold"), background='lightgrey')

        tree:ttk.Treeview = TreeviewPlus(self.frame, columns=Context.route.hdrs, show="headings", style="My.Treeview")
        sb:ttk.Scrollbar = ttk.Scrollbar(self.frame, orient=tk.VERTICAL, command=tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        widths:list = [len(w)+1 for w in Context.route.hdrs]
        for r in Context.route.route:
            widths = [max(widths[i], len(str(w))+1) for i, w in enumerate(r)]

        for i, hdr in enumerate(Context.route.hdrs):
            tree.heading(hdr, text=hdr, anchor=tk.W if i == 0 else tk.E)
            tree.column(hdr, stretch=tk.NO, width=int(widths[i]*8*self.scale), anchor=tk.W if i == 0 else tk.E)

        for i, row in enumerate(Context.route.route):
            tmp:list[tuple] = [ tuple([val] + HEADER_TYPES.get(Context.route.hdrs[col], ["-", ""])) for col, val in enumerate(row)]
            r:str = tree.insert("", 'end', values=[hfplus(c) for c in tmp])
            if i > 0 and i == Context.route.offset:
                tree.selection_set(r)

        w:int = sum([int(widths[i]*8*self.scale) for i in range(len(widths))]) + 30
        self.window.geometry(f"{int(w)}x{int(300*self.scale)}")
