import os
import tkinter as tk
from tkinter import ttk
import tkinter.messagebox as confirmDialog
from functools import partial
from pathlib import Path
from dataclasses import dataclass
import re
import requests
import json
import myNotebook as nb # type: ignore

from theme import theme # type: ignore
from config import config # type: ignore

import utils.th as th
from utils.debug import Debug, catch_exceptions
from utils.misc import singleton, hfplus, PopupNotice, copy_to_clipboard
from utils.tkrichtext import RichScrolledText

from .constants import NAME, SPANSH_SYSTEMS, ASSET_DIR, FONT, BOLD, lbls, btns, tts, errs
from .ship import Ship
from .route import Route
from .context import Context
from .route_window import RouteWindow
@singleton
class UI():
    """
        The main UI for the router.
        It has three states with three different frames.
          - Default, deliberately minimal for when the router isn't being used
          - Plot, a plot entry frame with neutron and galaxy route variants
          - Route, displays the route navigation
    """

    def __init__(self, parent:tk.Widget|None = None) -> None:
        # Initialise the UI.
        if parent == None:
            Debug.logger.info(f"No parent")
            return

        self.frwidth:int = int(375 * (config.get_int('ui_scale') / 100))
        self.parent:tk.Widget|None = parent
        self.window_route:RouteWindow = RouteWindow(self.parent.winfo_toplevel())

        self.frame:th.Frame = th.Frame(parent, borderwidth=2)
        self.frame.grid(sticky=tk.NSEW)

        self.update:th.Label

        self.help_img:tk.PhotoImage = tk.PhotoImage(file=os.path.join(Context.plugin_dir, ASSET_DIR, "help.png"))
        self.fuel_img:tk.PhotoImage = tk.PhotoImage(file=os.path.join(Context.plugin_dir, ASSET_DIR, "fuel.png"))
        self.neutron_img:tk.PhotoImage = tk.PhotoImage(file=os.path.join(Context.plugin_dir, ASSET_DIR, "neutron.png"))

        self.error_lbl:th.Label = th.Label(self.frame, text="", foreground='red', justify=tk.CENTER)
        self.error_lbl.grid(row=10, column=0, columnspan=2, padx=5, sticky=tk.W)
        self.hide_error()

        self.router:tk.StringVar = tk.StringVar()
        self.router.set('Neutron')  # Set default value

        self.progbar:ttk.Progressbar # Overall progress bar

        self.title_fr:th.Frame = self._create_title_fr(self.frame)
        self.busy_fr:th.Frame = self._create_busy_fr(self.frame)
        self.route_fr:th.Frame = self._create_route_fr(self.frame)

        self.plot_frames:dict[str, th.Frame] = {}
        self.plot_frames['Neutron'] = self._create_neutron_fr(self.frame)
        self.plot_frames['Galaxy'] = self._create_galaxy_fr(self.frame)
        self.plot_frames['Trade'] = self._create_trade_fr(self.frame)

        self.sub_fr:th.Frame = self.title_fr
        self.show_frame('Route' if Context.route.route != [] else 'Default')

        # Wait a while before deciding if we should show the update text
        parent.after(30000, lambda: self.show_plugin_update())


    @catch_exceptions
    def show_plugin_update(self) -> None:
        """ Display the update text if appropriate"""
        if Context.updater.update_available == False or Context.updater.install_update == False or Context.updater.zip_downloaded == "":
            return

        text:str = lbls['update_available'].format(v=str(Context.updater.update_version))
        self.update = th.Label(self.frame, text=text, anchor=tk.NW, justify=tk.LEFT, foreground='blue', font=FONT, cursor='hand2')
        if Context.updater.releasenotes != "":
            th.Tooltip(self.update, markdown=tts["releasenotes"].format(c=Context.updater.releasenotes))
        self.update.bind("<Button-1>", partial(self.cancel_plugin_update))
        self.update.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)


    @catch_exceptions
    def cancel_plugin_update(self, tkEvent = None) -> None:
        """ Cancel the update if they click """
        #webbrowser.open(GH_LATEST)
        Context.updater.install_update = False
        self.update.destroy()


    def _update_item(self, which:str, type:str, value:str = "") -> None:
        """ Update items of the given type from which source to all other destinations """
        if which != "all":
            sobj = self.plot_frames[which].nametowidget(type)
            value = sobj.get()
        for dest in self.plot_frames.values():
            try:
                if dest.nametowidget(type) == None:
                    continue
                if isinstance(dest.nametowidget(type), th.Placeholder):
                    dest.nametowidget(type).set_text(value, False)
                else:
                    dest.nametowidget(type).set(value)
                #Debug.logger.debug(f"Updated {dest} {type} to {value}")
            except Exception as e: # If the widget doesn't exist, just skip it
                pass

    def get_item(self, which:str, type:str) -> str:
        """ Get the value of the given type from the given source """
        try:
            sobj = self.plot_frames[which].nametowidget(type)
            return sobj.get()
        except Exception as e:
            return ""

    @catch_exceptions
    def show_frame(self, which:str = 'Default', destroy:bool = False) -> None:
        """ Display the chosen frame, recreating it if necessary """
        self.hide_error()
        self._show_busy_gui(False)
        Context.router.cancel_plot = True
        self.sub_fr.grid_remove()

        Context.router.neutron_params['range'] = f"{Context.router.ship.get_range(Context.router.cargo):.2f}" if Context.router.ship else "32.0"
        Context.router.neutron_params['supercharge_multiplier'] = Context.router.ship.supercharge_multiplier if Context.router.ship else 4
        if which in self.plot_frames: # Update corresponding fields in other plot frames
            self._update_item(which, "source_ac")
            self._update_item(which, "dest_ac")

        match which:
            case 'Route':
                self.sub_fr = self.route_fr
                self.update_progress()

            case 'Neutron':
                self.sub_fr = self.plot_frames['Neutron']
                self.router.set('Neutron')

            case 'Galaxy':
                self.sub_fr = self.plot_frames['Galaxy']
                self.router.set('Galaxy')

            case _:
                self.sub_fr = self.title_fr

        self.sub_fr.grid(row=2, column=0, sticky=tk.NSEW)


    def _create_title_fr(self, parent:th.Frame) -> th.Frame:
        """ Create the base/title frame """
        title_fr:th.Frame = th.Frame(parent)
        col:int = 0; row:int = 0
        self.lbl:th.Label = th.Label(title_fr, text=lbls["plot_title"], font=BOLD)
        self.lbl.grid(row=row, column=col, padx=(0,5), pady=5)
        col += 1
        plot_gui_btn:th.Button = th.Button(title_fr, text=" "+btns["plot_route"]+" ",
                                         command=lambda: self.show_frame(Context.router.last_plot))
        plot_gui_btn.grid(row=row, column=col, padx=(5,0), pady=5)

        return title_fr


    def _create_busy_fr(self, parent:th.Frame) -> th.Frame:
        """ Spinner image for route plotting """

        image:str = os.path.join(Context.plugin_dir, ASSET_DIR,
                                 "progress_animation_light.gif" if config.get_int('theme') == 0 else "progress_animation_dark.gif")
        self.frameCnt:int = 44
        self.frameSpd:int = 50

        self.frames:list = [tk.PhotoImage(file=image, format='gif -index %i' %(i)) for i in range(self.frameCnt)]
        busy_fr:th.Frame = th.Frame(parent)
        self.route_lbl:th.Label = th.Label(busy_fr, text=lbls["plotting"].format(s=Context.router.src, d=Context.router.dest),
                                                  justify=tk.CENTER, font=BOLD)
        self.route_lbl.grid(row=0, column=0, pady=5, sticky=tk.EW)
        self.busyimg:th.Label = th.Label(busy_fr, image=self.frames[0], justify=tk.CENTER)
        self.busyimg.grid(row=1, column=0, pady=10, sticky=tk.EW)
        cancel:th.Button = th.Button(busy_fr, text=btns["cancel"], command=lambda: self.show_frame(Context.router.last_plot))
        cancel.grid(row=2, column=0, pady=5, sticky=tk.EW)
        return busy_fr


    def _plot_switcher(self, fr:th.Frame, row:int, col:int) -> None:
        """ Switch between the two route plotters """
        sfr:th.Frame = th.Frame(fr, width=self.frwidth)
        r1:th.Radiobutton = th.Radiobutton(sfr, text=lbls["neutron_router"], variable=self.router, value='Neutron',
                                            command=lambda: self.show_frame('Neutron'))
        th.Tooltip(r1, tts['neutron_plotter'])
        r1.grid(row=0, column=0, padx=5, pady=5)

        r2:th.Radiobutton = th.Radiobutton(sfr, text=lbls["galaxy_router"], variable=self.router, value='Galaxy',
                                            command=lambda: self.show_frame('Galaxy'))
        th.Tooltip(r2, tts['galaxy_plotter'])
        r2.grid(row=0, column=1, padx=5, pady=5)
        # Use help.png image if available (prefer transparent PNG), fallback to text '!'
        # This has to be a tk.Button or EDMC's theme throws some kind of error about setting a foreground
        r3:th.Button = th.Button(sfr, image=self.help_img, cursor="hand2", command=lambda: self._show_help())
        th.Tooltip(r3, tts['help'])
        r3.grid(row=0, column=2, padx=5, pady=5)
        sfr.grid(row=row, column=col, columnspan=3, sticky=tk.EW)


    @catch_exceptions
    def _show_help(self) -> None:
        """ Help window """

        if self.parent == None: return

        if hasattr(self, 'help') and self.help.winfo_exists():
            self.help.lift()
            return

        self.help:tk.Toplevel = tk.Toplevel(self.parent.winfo_toplevel())
        self.help.title(f"{NAME} – {lbls['help']}")
        geometry:str = Context.router.window_geometries.get('help', "650x750")
        self.help.geometry(geometry)
        self.help.protocol("WM_DELETE_WINDOW", self.close)

        file:Path = Path(Context.plugin_dir, ASSET_DIR, "help.md")
        text:str = ""
        with open(file, encoding="utf-8") as infile:
            text = infile.read()
        text = text.replace("{version}", str(Context.plugin_version))
        html_label:RichScrolledText = RichScrolledText(self.help, markdown=text)
        html_label.pack(fill="both", expand=True, ipadx=5, ipady=5)
        html_label.fit_height()

    def close(self) -> None:
        """ On close save our geometry """
        Context.router.window_geometries['help'] = self.help.winfo_geometry()
        self.help.destroy()
        return


    def _create_galaxy_fr(self, parent:th.Frame) -> th.Frame:
        """ Create the galaxy route plotting frame """

        plot_fr:th.Frame = th.Frame(parent, width=self.frwidth)
        row:int = 2
        col:int = 0

        params:dict = Context.router.galaxy_params

        # Define the popup menu additions
        srcmenu:dict = {Context.router.system: [self.menu_callback, 'src']} if Context.router.system != '' else {}
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
        source_ac = th.Autocompleter(plot_fr, lbls["source_system"], width=30, menu=srcmenu, func=self.query_systems, name="source_ac")
        th.Tooltip(source_ac, tts["source_system"])
        if Context.router.src != '': self.set_entry(source_ac, Context.router.src)
        source_ac.grid(row=row, column=col, columnspan=2, padx=5, pady=5)
        col += 2

        self.gal_optionlist:list = ['is_supercharged', 'use_supercharge', 'use_injections', 'exclude_secondary', 'refuel_every_scoopable']
        self.gal_lb:th.Listbox = th.Listbox(plot_fr, [lbls[v] for v in self.gal_optionlist])
        th.Tooltip(self.gal_lb, tts['galaxy_options'])

        for i, item in enumerate(self.gal_optionlist):
            if params.get(item, False) == True:
                self.gal_lb.selection_set(i)
        self.gal_lb.grid(row=row, column=col, rowspan=3, padx=5, pady=5)

        # Row two
        row += 1; col = 0
        dest_ac = th.Autocompleter(plot_fr, lbls["dest_system"], width=30, menu=destmenu, func=self.query_systems, name="dest_ac")
        th.Tooltip(dest_ac, tts["dest_system"])
        if Context.router.dest != '': self.set_entry(dest_ac, Context.router.dest)
        dest_ac.grid(row=row, column=col, columnspan=2, padx=5, pady=5)

        # Row three
        row += 1; col = 0
        if Context.router.shiplist == {}: self.show_error(errs["no_ships"])
        names:list = Context.router.shipnames()
        init:str = params.get('ship_build', {}).get('ShipName', '')
        if init == "" and names != []:
            init = names[0]

        self.shipvar:tk.StringVar = tk.StringVar(plot_fr, value=init)
        self.shipvar.trace_add("write", self.ship_selected)
        self.shipdd:th.ComboBox = th.ComboBox(plot_fr, self.shipvar, values=names, width=10)
        th.Tooltip(self.shipdd, tts["select_ship"])
        self.shipdd.grid(row=row, column=col, padx=5, pady=5)

        col += 1

        cargo_entry:th.Placeholder = th.Placeholder(plot_fr, lbls['cargo'], width=11, justify=tk.CENTER, name="cargo_entry")
        self.set_entry(cargo_entry, str(Context.router.cargo))
        cargo_entry.grid(row=row, column=col, padx=5, pady=5)
        th.Tooltip(cargo_entry, tts["cargo"])

        # Row 4
        row += 1; col = 0
        algorithms:list = ['Fuel', 'Fuel Jumps', 'Guided', 'Optimistic', 'Pessimistic']
        self.algorithm:tk.StringVar = tk.StringVar(plot_fr, value=params.get('algorithm', 'Optimistic'))
        algodd:th.ComboBox = th.ComboBox(plot_fr, self.algorithm, values=algorithms, width=10)
        th.Tooltip(algodd, tts["select_algorithm"])
        algodd.grid(row=row, column=col, padx=5, pady=5)

        col += 1
        self.fuel_res:th.Placeholder = th.Placeholder(plot_fr, lbls['fuel_reserve'], width=11, justify=tk.CENTER)
        if params.get('reserve_size', 0) != 0:
            self.set_entry(self.fuel_res, str(params.get('reserve_size', 0)))
        th.Tooltip(self.fuel_res, tts["fuel_reserve"])
        self.fuel_res.grid(row=row, column=col, padx=5, pady=5)

        # Spansh ignores this unless you're logged in.
        #col += 1
        #self.time_limit:tk.Scale|ttk.Scale = scale(plot_fr, from_=60, to=120, resolution=5, orient=tk.HORIZONTAL)
        #th.Tooltip(self.time_limit, tts["calc_time"])
        #self.time_limit.grid(row=row, column=col, pady=5)
        #self.time_limit.set(params.get('max_time', 60))

        # Row 5
        row += 1; col = 0
        btn_frame:th.Frame = th.Frame(plot_fr)
        btn_frame.grid(row=row, column=col, columnspan=3, sticky=tk.EW, pady=(5,0))
        r = 0; col = 0

        #btn_frame.columnconfigure(col, weight=1)
        #col += 1

        self.gal_import_route_btn:th.Button = th.Button(btn_frame, text=btns["import_route"], command=lambda: self.import_route())
        self.gal_import_route_btn.grid(row=r, column=col, padx=5, sticky=tk.W)
        col += 1

        self.gal_plot_route_btn:th.Button = th.Button(btn_frame, text=btns["calculate_route"], command=lambda: self.galaxy_plot())
        self.gal_plot_route_btn.grid(row=r, column=col, padx=5, sticky=tk.W)
        col += 1

        self.gal_cancel_plot:th.Button  = th.Button(btn_frame, text=btns["cancel"], command=lambda: self.show_frame('Default'))
        self.gal_cancel_plot.grid(row=r, column=col, padx=5, sticky=tk.W)
        col += 1

        #btn_frame.columnconfigure(col, weight=1)

        return plot_fr


    def _create_neutron_fr(self, parent:th.Frame) -> th.Frame:
        """ Create the neutron route plotting frame """

        plot_fr:th.Frame = th.Frame(parent, width=self.frwidth)
        row:int = 2
        col:int = 0

        params:dict = Context.router.neutron_params

        # Define the popup menu additions
        srcmenu:dict = {Context.router.system: [self.menu_callback, 'src']} if Context.router.system != '' else {}
        destmenu:dict = {}

        if Context.router.system != '':
            srcmenu[Context.router.system] = [self.menu_callback, 'src']
        for sys in Context.router.history:
            if sys not in srcmenu:
                srcmenu[sys] = [self.menu_callback, 'src']
            if sys not in destmenu:
                destmenu[sys] = [self.menu_callback, 'dest']

        self._plot_switcher(plot_fr, row, col)

        row += 1; col = 0
        source_ac = th.Autocompleter(plot_fr, lbls["source_system"], width=30, menu=srcmenu, func=self.query_systems, name="source_ac")
        th.Tooltip(source_ac, tts["source_system"])
        if Context.router.src != '': self.set_entry(source_ac, Context.router.src)
        source_ac.grid(row=row, column=col, columnspan=2)
        col += 2

        range_entry:th.Placeholder = th.Placeholder(plot_fr, lbls['range'], width=11, menu=self._ship_dict(), justify=tk.CENTER, name="range_entry")
        range_entry.grid(row=row, column=col)
        th.Tooltip(range_entry, tts["range"])
        # Check if we're having a valid range on the fly
        range_entry.set_text(str(params.get('range', "32.00")), str(params.get('range', "32.00")) == "32.00")

        row += 1; col = 0
        dest_ac = th.Autocompleter(plot_fr, lbls["dest_system"], width=30, menu=destmenu, func=self.query_systems, name="dest_ac")
        th.Tooltip(dest_ac, tts["dest_system"])
        if Context.router.dest != '': self.set_entry(dest_ac, Context.router.dest)
        dest_ac.grid(row=row, column=col, columnspan=2)
        col += 2

        self.efficiency_slider:th.Scale = th.Scale(plot_fr, from_=0, to=100, resolution=5, orient=tk.HORIZONTAL)
        th.Tooltip(self.efficiency_slider, tts["efficiency"])
        self.efficiency_slider.grid(row=row, column=col, padx=5, pady=5, sticky=tk.EW)
        self.efficiency_slider.set(params.get('efficiency', 60))

        row += 1; col = 0
        self.multiplier = tk.IntVar() # Or StringVar() for string values
        self.multiplier.set(params.get('supercharge_multiplier', 4))  # Set default value

        # Create radio buttons
        l1:th.Label = th.Label(plot_fr, text=lbls["supercharge_label"])
        l1.grid(row=row, column=col, padx=5, pady=5)
        col += 1
        r1:th.Radiobutton = th.Radiobutton(plot_fr, text=lbls["standard_supercharge"], variable=self.multiplier, value=4)
        r1.bind('<Button-3>', lambda e: self.show_menu(e, 'Neutron'))
        th.Tooltip(r1, tts['standard_multiplier'])
        r1.grid(row=row, column=col, padx=5, pady=5)

        col += 1
        r2:th.Radiobutton = th.Radiobutton(plot_fr, text=lbls["overcharge_supercharge"], variable=self.multiplier, value=6)
        th.Tooltip(r2, tts['overcharge_multiplier'])
        r2.bind('<Button-3>', lambda e: self.show_menu(e, 'Neutron'))
        r2.grid(row=row, column=col, padx=5, pady=5)

        row += 1; col = 0
        btn_frame:th.Frame = th.Frame(plot_fr)
        btn_frame.grid(row=row, column=col, columnspan=3, sticky=tk.EW, pady=(5,0))

        r = 0; col = 0
        self.import_route_btn:th.Button = th.Button(btn_frame, text=btns["import_route"], command=lambda: self.import_route())
        self.import_route_btn.grid(row=r, column=col, padx=5, sticky=tk.W)
        col += 1

        self.plot_route_btn:th.Button = th.Button(btn_frame, text=btns["calculate_route"], command=lambda: self.neutron_plot())
        self.plot_route_btn.grid(row=r, column=col, padx=5, sticky=tk.W)
        col += 1

        self.cancel_plot:th.Button = th.Button(btn_frame, text=btns["cancel"], command=lambda: self.show_frame('Default'))
        self.cancel_plot.grid(row=r, column=col, padx=5, sticky=tk.W)

        return plot_fr

    def _create_rtor_fr(self, parent:th.Frame) -> th.Frame:
        plot_fr:th.Frame = th.Frame(parent, width=self.frwidth)
        row:int = 2
        col:int = 0
        # Source
        # Dest
        # Range
        # Radius
        # Max systems
        # Use mapping value
        # Avoid thargoids
        # Looop
        # Max dist to arrival
        # Min scan value
        return plot_fr


    def _create_trade_fr(self, parent:th.Frame) -> th.Frame:
        """ Create the trade route planning frame """

        plot_fr:th.Frame = th.Frame(parent, width=self.frwidth)
        row:int = 2
        col:int = 0

        params:dict = Context.router.trade_params

        # Define the popup menu additions
        srcmenu:dict = {Context.router.system: [self.menu_callback, 'src']} if Context.router.system != '' else {}
        destmenu:dict = {}

        if Context.router.system != '':
            srcmenu[Context.router.system] = [self.menu_callback, 'src']
        for sys in Context.router.history:
            if sys not in srcmenu:
                srcmenu[sys] = [self.menu_callback, 'src']
            if sys not in destmenu:
                destmenu[sys] = [self.menu_callback, 'dest']

        self._plot_switcher(plot_fr, row, col)

        row += 1; col = 0
        self.source_ac = th.Autocompleter(plot_fr, lbls["source_system"], width=30, menu=srcmenu, func=self.query_systems)
        th.Tooltip(self.source_ac, tts["source_system"])
        if Context.router.src != '': self.set_entry(self.source_ac, Context.router.src)
        self.source_ac.grid(row=row, column=col, columnspan=2)
        col += 2

        range_entry:th.Placeholder = th.Placeholder(plot_fr, lbls['range'], width=11, menu=self._ship_dict(), justify=tk.CENTER, name="range_entry")
        range_entry.grid(row=row, column=col)
        th.Tooltip(range_entry, tts["range"])
        # Check if we're having a valid range on the fly
        range_entry.set_text(str(params.get('range', "32.00")), str(params.get('range', "32.00")) == "32.00")

        row += 1; col = 0
        self.dest_ac = th.Autocompleter(plot_fr, lbls["dest_system"], width=30, menu=destmenu, func=self.query_systems)
        th.Tooltip(self.dest_ac, tts["dest_system"])
        if Context.router.dest != '': self.set_entry(self.dest_ac, Context.router.dest)
        self.dest_ac.grid(row=row, column=col, columnspan=2)
        col += 2

        self.efficiency_slider:th.Scale = th.Scale(plot_fr, from_=0, to=100, resolution=5, orient=tk.HORIZONTAL)
        th.Tooltip(self.efficiency_slider, tts["efficiency"])
        self.efficiency_slider.grid(row=row, column=col, padx=5, pady=5, sticky=tk.EW)
        self.efficiency_slider.set(params.get('efficiency', 60))

        row += 1; col = 0
        #self.multiplier = tk.IntVar() # Or StringVar() for string values
        #self.multiplier.set(params.get('supercharge_multiplier', 4))  # Set default value

        # Create radio buttons
        l1:th.Label = th.Label(plot_fr, text=lbls["supercharge_label"])
        l1.grid(row=row, column=col, padx=5, pady=5)
        col += 1
        r1:th.Radiobutton = th.Radiobutton(plot_fr, text=lbls["standard_supercharge"], variable=self.multiplier, value=4)
        r1.bind('<Button-3>', lambda e: self.show_menu(e, 'Trade'))
        th.Tooltip(r1, tts['standard_multiplier'])
        r1.grid(row=row, column=col, padx=5, pady=5)

        col += 1
        r2:th.Radiobutton = th.Radiobutton(plot_fr, text=lbls["overcharge_supercharge"], variable=self.multiplier, value=6)
        th.Tooltip(r2, tts['overcharge_multiplier'])
        r2.bind('<Button-3>', lambda e: self.show_menu(e, 'Trade'))
        r2.grid(row=row, column=col, padx=5, pady=5)

        row += 1; col = 0
        btn_frame:th.Frame = th.Frame(plot_fr)
        btn_frame.grid(row=row, column=col, columnspan=3, sticky=tk.EW, pady=(5,0))

        r = 0; col = 0
        self.import_route_btn:th.Button = th.Button(btn_frame, text=btns["import_route"], command=lambda: self.import_route())
        self.import_route_btn.grid(row=r, column=col, padx=5, sticky=tk.W)
        col += 1

        self.plot_route_btn:th.Button = th.Button(btn_frame, text=btns["calculate_route"], command=lambda: self.neutron_plot())
        self.plot_route_btn.grid(row=r, column=col, padx=5, sticky=tk.W)
        col += 1

        self.cancel_plot:th.Button = th.Button(btn_frame, text=btns["cancel"], command=lambda: self.show_frame('Default'))
        self.cancel_plot.grid(row=r, column=col, padx=5, sticky=tk.W)

        return plot_fr


    @catch_exceptions
    def show_menu(self, e, which:str='Neutron') -> str:
        # Create right click menu

        shipmenu:dict = self._ship_dict()

        if shipmenu != {}:
            menu:tk.Menu = tk.Menu(self.plot_frames[which], tearoff=0)
            for m, f in shipmenu.items():
                menu.add_command(label=m, command=partial(*f, m))
            menu.post(e.x_root, e.y_root)

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
        if Context.route.route == [] or not hasattr(self, "route_fr"):
            return

        # Create the tooltip with jumps/waypoints, distance, and speed depending on what we have
        tt:str = tts["jump"] if Context.route.jc != None else tts["waypoints"]
        j:str = ""; d:str = ""
        if Context.route.jumps_remaining() > 0:
            j = str(Context.route.jumps_remaining())
        if Context.route.dist_remaining() > 0:
            tmp:tuple = tuple([Context.route.dist_remaining(), 'float', '', ' Ly'])
            d = f"({hfplus(tmp)}) "
        tt = tt.format(j=j, d=d)

        if Context.route.jumps_per_hour() > 0:
            jr:tuple = tuple([Context.route.jumps_per_hour(), 'float'])
            dr:tuple = tuple([Context.route.dist_per_hour(), 'float'])
            if tt != "": tt += "\n"
            tt += tts['speed'].format(j=hfplus(jr), d=hfplus(dr))

        th.Tooltip(self.progbar, tt)

        self.progbar.configure(length=self.frwidth-3, value=self._progress())


    @catch_exceptions
    def update_progress(self) -> None:
        if Context.route.route == [] or not hasattr(self, 'waypoint_btn'):
            return
        route:Route = Context.route
        self.waypoint_prev_btn.config(state=tk.DISABLED if route.offset <= -1 else tk.NORMAL)
        self.waypoint_prev_tt = th.Tooltip(self.waypoint_prev_btn, route.get_waypoint(-1))
        self.waypoint_next_btn.config(state=tk.DISABLED if route.offset >= len(route.route) -1 else tk.NORMAL)
        dn:str = hfplus(tuple([Context.route.dist_to_next(), 'float', '0']))
        nstr:str = route.get_waypoint(1) if route.dist_to_next() == 0 else f"{route.get_waypoint(1)} ({dn} ly)"
        self.waypoint_next_tt = th.Tooltip(self.waypoint_next_btn, nstr)

        wp:str = route.next_stop()
        self._update_progbar()

        if route.jumps_remaining() > 0:
            copy_to_clipboard(self.parent, wp)
            # Show progress through route
            jumps:tuple = tuple([route.total_jumps() - route.jumps_remaining(), 'int', '-' if route.offset < 0 else '0'])
            tjumps:tuple = tuple([route.total_jumps(), 'int'])
            wp += f" ({hfplus(jumps)}/{hfplus(tjumps)})"

        # Set an icon if appropriate
        image:tk.PhotoImage = tk.PhotoImage(width=16, height=16)
        if route.is_neutron() == True:
            image = self.neutron_img

        if route.refuel() == True and not Context.route.fuel_full:
            image = self.fuel_img

        self.waypoint_btn.configure(text=wp, image=image, compound=tk.LEFT)


    def _create_route_fr(self, parent:th.Frame) -> th.Frame:
        """ Create the route display frame """

        route_fr:th.Frame = th.Frame(parent)
        self.bar_fr:th.LabelFrame = th.LabelFrame(route_fr, border=0, height=10, width=self.frwidth)
        self.bar_fr.grid_rowconfigure(0, weight=1)
        self.bar_fr.grid_propagate(False)
        self.bar_fr.grid(row=0, column=0, pady=0, sticky=tk.EW)

        self.progbar = ttk.Progressbar(self.bar_fr, orient=tk.HORIZONTAL, value=self._progress(), maximum=100, mode='determinate',
                                       length=self.frwidth-3)
        self.progtt:th.Tooltip = th.Tooltip(self.progbar, text=tts["progress"])
        self.progbar.rowconfigure(0, weight=1)
        self.progbar.grid(row=0, column=0, pady=0, ipady=0, sticky=tk.EW)
        self._update_progbar()

        parent.after(5000, self._update_progbar) # We may need to wait til TK has finished loading before updating the progress bar

        fr1:th.Frame = th.Frame(route_fr, width=self.frwidth-10)
        fr1.grid_columnconfigure(0, weight=0)
        fr1.grid_columnconfigure(1, weight=1)
        fr1.grid_columnconfigure(2, weight=0)
        fr1.grid(row=1, column=0, sticky=tk.EW)

        row:int = 0; col:int = 0
        self.waypoint_prev_btn:th.Button = th.Button(fr1, text=btns["prev"], width=3, command=lambda: Context.router.update_route(-1))
        self.waypoint_prev_tt:th.Tooltip = th.Tooltip(self.waypoint_prev_btn, Context.route.get_waypoint(-1))
        self.waypoint_prev_btn.grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)

        col += 1
        self.waypoint_btn:th.Button = th.Button(fr1, text=Context.route.next_stop(), width=32,
                                              command=lambda: copy_to_clipboard(self.parent, Context.route.next_stop()))
        self.waypoint_btn_tt:th.Tooltip = th.Tooltip(self.waypoint_btn, tts["copy_to_clipboard"])
        self.waypoint_btn.grid(row=row, column=col, padx=5, pady=5, sticky=tk.EW)

        col += 1
        self.waypoint_next_btn:th.Button = th.Button(fr1, text=btns["next"], width=3,
                                                     command=lambda: Context.router.update_route(1))
        self.waypoint_next_tt:th.Tooltip = th.Tooltip(self.waypoint_next_btn, Context.route.get_waypoint(1))
        self.waypoint_next_btn.grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)

        fr2:th.Frame = th.Frame(route_fr)
        fr2.grid_columnconfigure(0, weight=0)
        fr2.grid_columnconfigure(1, weight=0)
        fr2.grid(row=2, column=0, sticky=tk.W)
        row = 0; col = 0

        self.export_route_btn:th.Button = th.Button(fr2, text=btns["export_route"], command=lambda: self._export_route())
        self.export_route_btn.grid(row=row, column=col, padx=5, sticky=tk.W)

        col += 1
        self.show_route_btn:th.Button = th.Button(fr2, text=btns["show_route"],
                                                  command=lambda: self.window_route.show(Context.route))
        self.show_route_btn.grid(row=row, column=col, padx=5, sticky=tk.W)

        col += 1
        self.clear_route_btn:th.Button = th.Button(fr2, text=btns["clear_route"], command=lambda: self._clear_route())
        self.clear_route_btn.grid(row=row, column=col, padx=5, sticky=tk.W)

        return route_fr

    def _ship_dict(self) -> dict:
        """ Return a dictionary of ship names and their corresponding callback functions """
        shipmenu:dict = {}
        for name in Context.router.shipnames():
            shipmenu[name] = [self.menu_callback, 'ship']
        return shipmenu

    @catch_exceptions
    def menu_callback(self, field:str = "src", param:str = "None") -> None:
        """ Function called when a custom menu item is selected """
        match field:
            case 'src':
                self._update_item("all", "source_ac", param)
            case 'dest':
                self._update_item("all", "dest_ac", param)
            case _:

                param = self.shipvar.get() if param == "None" else param
                ship:Ship|None = Context.router.load_ship(param)
                if not ship: return

                self._update_item("all", "cargo_entry", str(Context.router.cargo if ship.id == Context.router.ship_id else 0))
                self._update_item("all", "range_entry", str(ship.get_range(Context.router.cargo)))
                self.multiplier.set(ship.supercharge_multiplier)
                return


    @catch_exceptions
    def ship_selected(self, *args) -> None:
        """ Update the galaxy plotter when the ship dropdown changes """
        ship_name:str = self.shipvar.get()
        self.menu_callback('ship', ship_name)


    def set_entry(self, which:th.Autocompleter|th.Placeholder|None, value:str) -> None:
        """ Set an autocompleter or placeholder entry's text and style """
        if which == None: return
        which.delete(0, tk.END)
        which.insert(0, value)
        which.set_default_style()


    def switch_ship(self, ship:Ship) -> None:
        """ Update the plotter items when the ship changes """

        # Neutron plotter
        self._update_item("all", "range_entry", str(ship.get_range(Context.router.cargo)))
        self.multiplier.set(ship.supercharge_multiplier)


        for dest in self.plot_frames.values():
            try:
                if dest.nametowidget("range_entry") == None:
                    continue
                dest.nametowidget("range_entry").set_menu(self._ship_dict())
            except Exception as e: # If the widget doesn't exist, just skip it
                pass

        # Galaxy plotter ship dropdown
        self.shipvar.set(ship.name)
        self.shipdd.set_menu(Context.router.shipnames())

    def update_cargo(self, cargo:int) -> None:
        """ Update the cargo entry when the cargo changes """

        if not Context.router.ship or self.shipvar.get() != Context.router.ship.name:
            return
        self._update_item("all", "cargo_entry", str(cargo))
        self._update_item("all", "range_entry", str(Context.router.ship.get_range(cargo)))

    @catch_exceptions
    def _export_route(self) -> None:
        if Context.router == None or Context.router.export_route() == False:
            Debug.logger.error(f"Failed to export route")
            return

        self.show_frame('Route')


    def _clear_route(self) -> None:
        """ Display a confirmation dialog for clearing the current route """
        clear:bool = confirmDialog.askyesno(Context.plugin_title, lbls["clear_route_yesno"])
        if not clear: return

        # Reverse the route
        if Context.router.dest == Context.router.system:
            Debug.logger.debug(f"Reversing route as we're at the end")
            self.dest_ac.set_text(Context.router.src, False)
            self.source_ac.set_text(Context.router.dest, False)

        self.show_frame(Context.router.last_plot)
        Context.router.clear_route()


    @catch_exceptions
    def import_route(self) -> None:
        if Context.router == None or Context.router.import_route() == False:
            Debug.logger.error(f"Failed to load route {self.error_lbl['text']}")
            self.show_frame(Context.router.last_plot)
            self.show_error(self.error_lbl['text'])
            return

        self.show_frame('Route')


    @catch_exceptions
    def neutron_plot(self) -> None:
        """ Perform a neutron plotter plot """
        self.hide_error()
        src_ac:th.Autocompleter = self.plot_frames['Neutron'].nametowidget("source_ac")
        dest_ac:th.Autocompleter = self.plot_frames['Neutron'].nametowidget("dest_ac")

        params:dict = {}

        frm:str = src_ac.get().strip()
        params["from"] = next((x for x in self.query_systems(frm) if x.casefold() == frm.casefold()), None)
        if params['from'] == None:
            self.show_frame('Neutron')
            src_ac.set_text(frm, False)
            src_ac.set_error_style()
            return

        to = dest_ac.get().strip()
        params["to"] = next((x for x in self.query_systems(to) if x.casefold() == to.casefold()), None)
        if params['to'] == None:
            self.show_frame('Neutron')
            dest_ac.set_text(to, False)
            dest_ac.set_error_style()
            return

        params['efficiency'] = int(self.efficiency_slider.get())
        params['supercharge_multiplier'] = self.multiplier.get()
        params['range'] = self.plot_frames['Neutron'].nametowidget("range_entry").var.get()
        if not re.match(r"^\d+(\.\d+)?$", params['range']):
            Debug.logger.info(f"Invalid range entry {params['range']}")
            self.show_frame('Neutron')
            self.plot_frames['Neutron'].nametowidget("range_entry").set_error_style()
            return

        Context.router.plot_route('Neutron', params)
        self._show_busy_gui(True)


    @catch_exceptions
    def galaxy_plot(self) -> None:
        """ Perform a galaxy plotter plot """
        self.hide_error()
        gal_fr:th.Frame = self.plot_frames['Galaxy']
        gal_fr.nametowidget("source_ac").hide_list()
        gal_fr.nametowidget("dest_ac").hide_list()

        ship_id:str = Context.router.shipid(self.shipvar.get())
        if ship_id == '':
            self.show_frame('Galaxy')
            self.show_error(errs['no_ship'])
            return

        ship:Ship|None = Context.router.load_ship(ship_id)
        if not ship: return

        params:dict = {
            'cargo': int(gal_fr.nametowidget("cargo_entry").get().strip()) if re.match(r"^\d+$", gal_fr.nametowidget("cargo_entry").get().strip()) else 0,
            #'max_time': int(self.time_limit.get()),
            'max_time': 60,
            'algorithm': self.algorithm.get(),
            'reserve_size': int(self.fuel_res.get().strip()) if re.match(r"^\d+(\.\d+)?$", self.fuel_res.get().strip()) else 0,
            'is_supercharged': 1 if self.gal_lb.selection_includes(self.gal_optionlist.index('is_supercharged')) else 0,
            'use_supercharge': 1 if self.gal_lb.selection_includes(self.gal_optionlist.index('use_supercharge')) else 0,
            'use_injections': 1 if self.gal_lb.selection_includes(self.gal_optionlist.index('use_injections')) else 0,
            'exclude_secondary': 1 if self.gal_lb.selection_includes(self.gal_optionlist.index('exclude_secondary')) else 0,
            'refuel_every_scoopable': 1 if self.gal_lb.selection_includes(self.gal_optionlist.index('refuel_every_scoopable')) else 0,
            'fuel_power': ship.fuel_power,
            'fuel_multiplier': ship.fuel_multiplier,
            'optimal_mass': ship.optimal_mass,
            'base_mass': ship.base_mass,
            'tank_size': ship.tank_size,
            'internal_tank_size': ship.internal_tank_size,
            'max_fuel_per_jump': ship.max_fuel_per_jump,
            'range_boost': ship.range_boost,
            'supercharge_multiplier': ship.supercharge_multiplier,
            'injection_multiplier': ship.injection_multiplier
            }

        src = gal_fr.nametowidget("source_ac").get().strip()
        params["source"] = next((x for x in self.query_systems(src) if x.casefold() == src.casefold()), None)
        if params['source'] == None:
            self.show_frame('Galaxy')
            gal_fr.nametowidget("source_ac").set_text(src, False)
            gal_fr.nametowidget("source_ac").set_error_style()
            return

        dest = gal_fr.nametowidget("dest_ac").get().strip()
        params['destination'] = next((x for x in self.query_systems(dest) if x.casefold() == dest.casefold()), None)
        if params['destination'] == None:
            self.show_frame('Galaxy')
            gal_fr.nametowidget("dest_ac").set_text(dest, False)
            gal_fr.nametowidget("dest_ac").set_error_style()
            return

        Context.router.plot_route('Galaxy', params)
        self._show_busy_gui(True)


    def show_error(self, error:str|None = None) -> None:
        """ Set and show the error text """
        if error == None: return
        Debug.logger.error(f"Showing error {error}")
        self.error_lbl['text'] = error
        self.error_lbl.grid(row=1, column=0, columnspan=2, padx=5, sticky=tk.EW)


    def hide_error(self) -> None:
        """ Hide the the error message """
        self.error_lbl.grid_remove()


    @catch_exceptions
    def _show_busy_gui(self, enable:bool) -> None:
        """ Activate/deactivate the plot gui (show a progress icon) """
        def update(ind) -> None:
            if self.busy_fr == None or self.show_spinner == False: return
            self.busyimg.configure(image=self.frames[ind], anchor=tk.CENTER)
            self.busy_fr.after(self.frameSpd, update, (ind + 1) % self.frameCnt)

        self.show_spinner:bool = enable
        # Show the busy image
        if enable == True:
            # In case the user has changed themes since loading, get the appropriate image
            image:str = os.path.join(Context.plugin_dir, ASSET_DIR,
                                     "progress_animation_light.gif" if config.get_int('theme') == 0 else "progress_animation_dark.gif")
            self.frames:list = [tk.PhotoImage(file=image, format='gif -index %i' %(i)) for i in range(self.frameCnt)]

            self.sub_fr.grid_remove()
            self.route_lbl['text'] = lbls["plotting"].format(s=Context.router.src, d=Context.router.dest)
            self.busy_fr.grid(row=2, column=0, padx=10, pady=10, sticky=tk.NSEW)
            self.busy_fr.after(0, update, 0)
            return

        self.busy_fr.grid_remove()
        self.sub_fr.grid()


    @catch_exceptions
    def query_systems(self, inp:str) -> list:
        """ Function called by Autocompleter """
        try:
            results:requests.Response = requests.get(SPANSH_SYSTEMS, params={'q': inp.strip()},
                                                     headers={'User-Agent': Context.plugin_useragent}, timeout=3)
        except:
            return [inp]
        return json.loads(results.content)


    @catch_exceptions
    def cooldown_complete(self) -> None:
        """ Show an informational messagebox indicating a carrier cooldown has completed. """
        Debug.logger.debug(f"Cooldown complete notification triggered.")

        self.update_progress()

        if self.parent == None or getattr(Context.prefs, 'cooldown_popup', False) == False: return
        message:str = NAME + "\n" + lbls['cooldown_complete']
        PopupNotice(message, 60000, self.parent)
