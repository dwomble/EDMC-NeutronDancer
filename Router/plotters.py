
"""
Plotter classes for different route plotting strategies.

This module provides a base Plotter class and specialized implementations for:
- Neutron plotter
- Galaxy plotter
- Route-to-Route plotter
- Trade route plotter

Each plotter is responsible for creating its UI frame and handling its plotting logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import re
import tkinter as tk

import utils.th as th
from utils.debug import Debug, catch_exceptions

from .constants import lbls, btns, tts, errs, SPANSH_ROUTE, SPANSH_GALAXY_ROUTE, SPANSH_RICHES_ROUTE
from .context import Context
from .ship import Ship

@dataclass
class PlotterSpec:
    """ Everything that describes one route-plotting type. """
    label:str
    plotter_class:type
    url:str
    src_key:str = 'from'
    dest_key:str = 'to'
    options:list = field(default_factory=list)

class Plotter(ABC):
    """Base class for all route plotters."""

    def __init__(self, ui, frwidth:int, route_type:str) -> None:
        """ Initialize the plotter. """
        self.ui = ui
        self.frwidth = frwidth
        self.frame:th.Frame | None = None
        self.route_type = route_type
        self.options:list = PLOTTER_SPECS[route_type].options

    @abstractmethod
    def create_frame(self, parent:th.Frame) -> th.Frame:
        """ Create and return the plotter's UI frame. """
        pass

    @abstractmethod
    def plot(self) -> None:
        """Execute the plotting logic for this plotter."""
        pass

    def get_frame(self) -> th.Frame | None:
        """Get the plotter's frame."""
        return self.frame

    # Shared UI creation methods

    def _create_source(self, parent:th.Frame, row:int, col:int) -> None:
        """Create source system autocompleter widget."""
        srcmenu:dict = {Context.router.system: [self.ui.menu_callback, 'src']} if Context.router.system != '' else {}
        if Context.router.system != '':
            srcmenu[Context.router.system] = [self.ui.menu_callback, 'src']
        for sys in Context.router.history:
            if sys not in srcmenu:
                srcmenu[sys] = [self.ui.menu_callback, 'src']

        source_ac = th.Autocompleter(parent, lbls["source_system"], width=30, menu=srcmenu, func=self.ui.query_systems, name="source_ac")
        th.Tooltip(source_ac, tts["source_system"])
        if Context.router.src != '':
            self.ui.set_entry(source_ac, Context.router.src)
        source_ac.grid(row=row, column=col, columnspan=2, padx=5, pady=5)

    def _create_dest(self, parent:th.Frame, row:int, col:int) -> None:
        """Create destination system autocompleter widget."""
        destmenu:dict = {}
        for sys in Context.router.history:
            if sys not in destmenu:
                destmenu[sys] = [self.ui.menu_callback, 'dest']

        dest_ac = th.Autocompleter(parent, lbls["dest_system"], width=30, menu=destmenu, func=self.ui.query_systems, name="dest_ac")
        th.Tooltip(dest_ac, tts["dest_system"])
        if Context.router.dest != '':
            self.ui.set_entry(dest_ac, Context.router.dest)
        dest_ac.grid(row=row, column=col, columnspan=2, padx=5, pady=5)

    def _create_options(self, parent:th.Frame, row:int, col:int, options:list, params:dict) -> None:
        """Create options listbox widget."""
        lb:th.Listbox = th.Listbox(parent, [lbls[v] for v in options], name="options")
        th.Tooltip(lb, tts['galaxy_options'])

        for i, item in enumerate(options):
            if params.get(item, False) == True:
                lb.selection_set(i)
        lb.grid(row=row, column=col, rowspan=3, padx=5, pady=5)

    def _create_range(self, parent:th.Frame, row:int, col:int, range_val:str = "32.0") -> None:
        """Create range entry widget."""
        range_entry:th.Placeholder = th.Placeholder(parent, lbls['range'], width=11, menu=self.ui._ship_dict(), justify=tk.CENTER, name="range_entry")
        range_entry.grid(row=row, column=col)
        th.Tooltip(range_entry, tts["range"])
        range_entry.set_text(range_val, range_val == "32.00")

    def _plot_switcher(self, fr:th.Frame, row:int, col:int) -> None:
        """Create the route plotter type switcher."""
        routers:dict = Context.router.route_types

        @catch_exceptions
        def on_combo_change(e):
            which:str = next((k for k, v in routers.items() if v == routedd.get()), '')
            self.ui.show_frame(which)

        sfr:th.Frame = th.Frame(fr, width=self.frwidth)

        th.Label(sfr, text=lbls['route'], justify=tk.LEFT).grid(row=0, column=0, padx=5, pady=5)

        routedd:th.ComboBox = th.ComboBox(sfr, self.ui.router, values=list(routers.values()), width=25)
        routedd.bind("<<ComboboxSelected>>", on_combo_change)
        th.Tooltip(routedd, tts["route_type"])
        routedd.grid(row=0, column=1, padx=5, pady=5)

        r3:th.Button = th.Button(sfr, image=self.ui.help_img, cursor="hand2", command=lambda: self.ui._show_help())
        th.Tooltip(r3, tts['help'])
        r3.grid(row=0, column=2, padx=5, pady=5)

        sfr.grid(row=row, column=col, columnspan=3, sticky=tk.EW)

    def _validate_system(self, inp:str, widget:th.Autocompleter) -> str | None:
        """ Validate and return the exact system name. """
        validated = next((x for x in self.ui.query_systems(inp) if x.casefold() == inp.casefold()), None)
        if validated is None:
            widget.set_text(inp, False)
            widget.set_error_style()
        return validated

    def _create_buttons(self, parent:th.Frame, row:int, col:int) -> None:
        """Create standard plotting buttons (import, calculate, cancel)."""
        btn_frame:th.Frame = th.Frame(parent)
        btn_frame.grid(row=row, column=col, columnspan=3, sticky=tk.EW, pady=(5, 0))

        r = 0
        col = 0
        self.import_route_btn:th.Button = th.Button(btn_frame, text=btns["import_route"], command=lambda: self.ui.import_route())
        self.import_route_btn.grid(row=r, column=col, padx=5, sticky=tk.W)

        col += 1
        self.plot_route_btn:th.Button = th.Button(btn_frame, text=btns["calculate_route"], command=self.plot)
        self.plot_route_btn.grid(row=r, column=col, padx=5, sticky=tk.W)

        col += 1
        self.cancel_plot:th.Button = th.Button(btn_frame, text=btns["cancel"], command=lambda: self.ui.show_frame('Default'))
        self.cancel_plot.grid(row=r, column=col, padx=5, sticky=tk.W)


class NeutronPlotter(Plotter):
    """Plotter for neutron star routes."""

    def create_frame(self, parent:th.Frame) -> th.Frame:
        """Create the neutron plotter frame."""
        plot_fr:th.Frame = th.Frame(parent, width=self.frwidth)
        row:int = 2; col:int = 0

        params:dict = Context.router.route_params.get('Neutron', {})
        self._plot_switcher(plot_fr, row, col)

        # Source and range
        row += 1; col = 0
        self._create_source(plot_fr, row, col)
        col += 2
        self._create_range(plot_fr, row, col, str(params.get('range', "32.0")))

        # Destination and efficiency
        row += 1; col = 0
        self._create_dest(plot_fr, row, col)
        col += 2

        self.efficiency_slider:th.Scale = th.Scale(plot_fr, from_=0, to=100, resolution=5, orient=tk.HORIZONTAL)
        th.Tooltip(self.efficiency_slider, tts["efficiency"])
        self.efficiency_slider.grid(row=row, column=col, padx=5, pady=5, sticky=tk.EW)
        self.efficiency_slider.set(params.get('efficiency', 60))

        # Supercharge multiplier
        row += 1; col = 0
        self.multiplier = tk.IntVar()
        self.multiplier.set(params.get('supercharge_multiplier', 4))

        l1:th.Label = th.Label(plot_fr, text=lbls["supercharge_label"])
        l1.grid(row=row, column=col, padx=5, pady=5)

        col += 1
        r1:th.Radiobutton = th.Radiobutton(plot_fr, text=lbls["standard_supercharge"], variable=self.multiplier, value=4)
        r1.bind('<Button-3>', lambda e: self.ui.show_menu(e, 'Neutron'))
        th.Tooltip(r1, tts['standard_multiplier'])
        r1.grid(row=row, column=col, padx=5, pady=5)

        col += 1
        r2:th.Radiobutton = th.Radiobutton(plot_fr, text=lbls["overcharge_supercharge"], variable=self.multiplier, value=6)
        th.Tooltip(r2, tts['overcharge_multiplier'])
        r2.bind('<Button-3>', lambda e: self.ui.show_menu(e, 'Neutron'))
        r2.grid(row=row, column=col, padx=5, pady=5)

        # Buttons
        row += 1; col = 0
        self._create_buttons(plot_fr, row, col)

        self.frame = plot_fr
        return plot_fr

    @catch_exceptions
    def plot(self) -> None:
        """Perform neutron route plotting."""
        if not self.frame:
            return

        self.ui.hide_error()

        src_ac = self.frame.nametowidget("source_ac")
        dest_ac = self.frame.nametowidget("dest_ac")

        params:dict = {}

        frm:str = src_ac.get().strip()
        params["from"] = self._validate_system(frm, src_ac)
        if params['from'] is None:
            self.ui.show_frame('Neutron')
            return

        to:str = dest_ac.get().strip()
        params["to"] = self._validate_system(to, dest_ac)
        if params['to'] is None:
            self.ui.show_frame('Neutron')
            return

        params['efficiency'] = int(self.efficiency_slider.get())
        params['supercharge_multiplier'] = self.multiplier.get()
        range_entry = self.frame.nametowidget("range_entry")
        params['range'] = range_entry.var.get()

        if not re.match(r"^\d+(\.\d+)?$", params['range']):
            Debug.logger.info(f"Invalid range entry {params['range']}")
            self.ui.show_frame('Neutron')
            range_entry.set_error_style()
            return

        Context.router.plot_route('Neutron', params)
        self.ui._show_busy_gui(True)


class GalaxyPlotter(Plotter):
    """Plotter for galaxy-wide routes."""

    def create_frame(self, parent:th.Frame) -> th.Frame:
        """Create the galaxy plotter frame."""
        plot_fr:th.Frame = th.Frame(parent, width=self.frwidth)
        row:int = 2; col:int = 0

        params:dict = Context.router.route_params.get('Galaxy', {})

        self._plot_switcher(plot_fr, row, col)

        # First row: source and options
        row += 1; col = 0
        self._create_source(plot_fr, row, col)
        col += 2

        self._create_options(plot_fr, row, col, self.options, params)

        # Row two: destination
        row += 1; col = 0
        self._create_dest(plot_fr, row, col)

        # Row three: ship selection and cargo
        row += 1; col = 0
        if Context.router.shiplist == {}:
            self.ui.show_error(errs["no_ships"])

        names:list = Context.router.shipnames()
        init:str = params.get('ship_build', {}).get('ShipName', '')
        if init == "" and names != []:
            init = names[0]

        self.shipvar:tk.StringVar = tk.StringVar(plot_fr, value=init)
        self.shipvar.trace_add("write", self.ui.ship_selected)
        self.shipdd:th.ComboBox = th.ComboBox(plot_fr, self.shipvar, values=names, width=10)
        th.Tooltip(self.shipdd, tts["select_ship"])
        self.shipdd.grid(row=row, column=col, padx=5, pady=5)

        col += 1
        cargo_entry:th.Placeholder = th.Placeholder(plot_fr, lbls['cargo'], width=11, justify=tk.CENTER, name="cargo_entry")
        self.ui.set_entry(cargo_entry, str(Context.router.cargo))
        cargo_entry.grid(row=row, column=col, padx=5, pady=5)
        th.Tooltip(cargo_entry, tts["cargo"])

        # Row 4: algorithm and fuel reserve
        row += 1; col = 0
        algorithms:list = ['Fuel', 'Fuel Jumps', 'Guided', 'Optimistic', 'Pessimistic']
        self.algorithm:tk.StringVar = tk.StringVar(plot_fr, value=params.get('algorithm', 'Optimistic'))
        algodd:th.ComboBox = th.ComboBox(plot_fr, self.algorithm, values=algorithms, width=10)
        th.Tooltip(algodd, tts["select_algorithm"])
        algodd.grid(row=row, column=col, padx=5, pady=5)

        col += 1
        self.fuel_res:th.Placeholder = th.Placeholder(plot_fr, lbls['fuel_reserve'], width=11, justify=tk.CENTER)
        if params.get('reserve_size', 0) != 0:
            self.ui.set_entry(self.fuel_res, str(params.get('reserve_size', 0)))
        th.Tooltip(self.fuel_res, tts["fuel_reserve"])
        self.fuel_res.grid(row=row, column=col, padx=5, pady=5)

        # Row 5: buttons
        row += 1; col = 0
        self._create_buttons(plot_fr, row, col)

        self.frame = plot_fr
        return plot_fr

    @catch_exceptions
    def plot(self) -> None:
        """Perform galaxy route plotting."""
        if not self.frame:
            return

        self.ui.hide_error()
        gal_fr:th.Frame = self.frame

        src_ac = gal_fr.nametowidget("source_ac")
        dest_ac = gal_fr.nametowidget("dest_ac")

        if src_ac:
            src_ac.hide_list()
        if dest_ac:
            dest_ac.hide_list()

        ship_id:str = Context.router.shipid(self.shipvar.get())
        if ship_id == '':
            self.ui.show_frame('Galaxy')
            self.ui.show_error(errs['no_ship'])
            return

        ship:Ship | None = Context.router.load_ship(ship_id)
        if not ship:
            return

        options = gal_fr.nametowidget("options")

        params:dict = {
            'cargo':int(gal_fr.nametowidget("cargo_entry").get().strip()) if re.match(r"^\d+$", gal_fr.nametowidget("cargo_entry").get().strip()) else 0,
            'max_time': 60,
            'algorithm': self.algorithm.get(),
            'reserve_size':int(self.fuel_res.get().strip()) if re.match(r"^\d+(\.\d+)?$", self.fuel_res.get().strip()) else 0,
            'is_supercharged': 1 if options.selection_includes(self.options.index('is_supercharged')) else 0,
            'use_supercharge': 1 if options.selection_includes(self.options.index('use_supercharge')) else 0,
            'use_injections': 1 if options.selection_includes(self.options.index('use_injections')) else 0,
            'exclude_secondary': 1 if options.selection_includes(self.options.index('exclude_secondary')) else 0,
            'refuel_every_scoopable': 1 if options.selection_includes(self.options.index('refuel_every_scoopable')) else 0,
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

        src:str = gal_fr.nametowidget("source_ac").get().strip()
        params["source"] = self._validate_system(src, gal_fr.nametowidget("source_ac"))
        if params['source'] is None:
            self.ui.show_frame('Galaxy')
            return

        dest:str = gal_fr.nametowidget("dest_ac").get().strip()
        params['destination'] = self._validate_system(dest, gal_fr.nametowidget("dest_ac"))
        if params['destination'] is None:
            self.ui.show_frame('Galaxy')
            return

        Context.router.plot_route('Galaxy', params)
        self.ui._show_busy_gui(True)


class RtoRPlotter(Plotter):
    """Plotter for route-to-route calculations."""

    def create_frame(self, parent:th.Frame) -> th.Frame:
        """Create the route-to-route plotter frame."""
        plot_fr:th.Frame = th.Frame(parent, width=self.frwidth)
        row:int = 2
        col:int = 0

        params:dict = Context.router.route_params.get('RtoR', {})

        self._plot_switcher(plot_fr, row, col)

        row += 1; col = 0

        # Row 1: source and options
        self._create_source(plot_fr, row, col)
        col += 2
        self._create_options(plot_fr, row, col, self.options, params)

        # Row 2: destination
        row += 1; col = 0
        self._create_dest(plot_fr, row, col)

        # Row 3: range and radius
        row += 1; col = 0
        self._create_range(plot_fr, row, col, str(params.get('range', "32.0")))

        col += 1
        radius_entry:th.Placeholder = th.Placeholder(plot_fr, lbls['radius'], width=11, justify=tk.CENTER, name="radius_entry")
        self.ui.set_entry(radius_entry, str(params.get('radius', 25)))
        th.Tooltip(radius_entry, tts["radius"])
        radius_entry.grid(row=row, column=col, padx=5, pady=5)

        # Row 4: maximum systems
        row += 1; col = 0
        max_results_entry:th.Placeholder = th.Placeholder(plot_fr, lbls['max_results'], width=11, justify=tk.CENTER, name="max_results_entry")
        self.ui.set_entry(max_results_entry, str(params.get('max_results', 100)))
        th.Tooltip(max_results_entry, tts["max_results"])
        max_results_entry.grid(row=row, column=col, padx=5, pady=5)

        # Buttons
        row += 1; col = 0
        self._create_buttons(plot_fr, row, col)

        self.frame = plot_fr
        return plot_fr

    @catch_exceptions
    def plot(self) -> None:
        """Perform route-to-route plotting."""
        if not self.frame:
            return

        self.ui.hide_error()

        src_ac = self.frame.nametowidget("source_ac")
        dest_ac = self.frame.nametowidget("dest_ac")
        options = self.frame.nametowidget("options")

        params:dict = {}

        frm:str = src_ac.get().strip()
        params["from"] = self._validate_system(frm, src_ac)
        if params['from'] is None:
            self.ui.show_frame('RtoR')
            return

        # Leave destination blank for a circular tour starting and ending at the source
        to:str = dest_ac.get().strip()
        if to != '':
            params["to"] = self._validate_system(to, dest_ac)
            if params['to'] is None:
                self.ui.show_frame('RtoR')
                return

        range_entry = self.frame.nametowidget("range_entry")
        params['range'] = range_entry.var.get()
        if not re.match(r"^\d+(\.\d+)?$", params['range']):
            Debug.logger.info(f"Invalid range entry {params['range']}")
            self.ui.show_frame('RtoR')
            range_entry.set_error_style()
            return

        radius_entry = self.frame.nametowidget("radius_entry")
        params['radius'] = radius_entry.get().strip()
        if not re.match(r"^\d+(\.\d+)?$", params['radius']):
            Debug.logger.info(f"Invalid radius entry {params['radius']}")
            self.ui.show_frame('RtoR')
            radius_entry.set_error_style()
            return

        max_results_entry = self.frame.nametowidget("max_results_entry")
        params['max_results'] = max_results_entry.get().strip()
        if not re.match(r"^\d+$", params['max_results']):
            Debug.logger.info(f"Invalid max results entry {params['max_results']}")
            self.ui.show_frame('RtoR')
            max_results_entry.set_error_style()
            return

        params['use_mapping_value'] = 1 if options.selection_includes(self.options.index('use_mapping_value')) else 0
        params['avoid_thargoids'] = 1 if options.selection_includes(self.options.index('avoid_thargoids')) else 0
        params['loop'] = 1 if options.selection_includes(self.options.index('loop')) else 0

        Context.router.plot_route('RtoR', params)
        self.ui._show_busy_gui(True)


class TradePlotter(Plotter):
    """Plotter for trade route planning."""

    def create_frame(self, parent:th.Frame) -> th.Frame:
        """Create the trade route plotter frame."""
        plot_fr:th.Frame = th.Frame(parent, width=self.frwidth)
        row:int = 2; col:int = 0

        params:dict = Context.router.route_params.get('Trade', {})
        self._plot_switcher(plot_fr, row, col)

        row += 1; col = 0
        self._create_source(plot_fr, row, col)
        col += 2

        # Buttons
        row += 1; col = 0
        self._create_buttons(plot_fr, row, col)

        self.frame = plot_fr
        return plot_fr

    @catch_exceptions
    def plot(self) -> None:
        """Perform trade route plotting."""
        # TODO: Implement trade plotting logic
        self.ui.hide_error()
        Debug.logger.info("Trade plotter not yet implemented")


# Trade isn't included yet -- TradePlotter.plot() is still a stub, so it stays out of
# route_types (unselectable) and unbuilt in ui.py until it's actually implemented.
PLOTTER_SPECS:dict = {
    'Neutron': PlotterSpec(
        label='Neutron Plotter', plotter_class=NeutronPlotter, url=SPANSH_ROUTE
    ),
    'Galaxy': PlotterSpec(
        label='Galaxy Plotter', plotter_class=GalaxyPlotter, url=SPANSH_GALAXY_ROUTE,
        src_key='source', dest_key='destination',
        options=['is_supercharged', 'use_supercharge', 'use_injections', 'exclude_secondary', 'refuel_every_scoopable']
    ),
    'RtoR': PlotterSpec(
        label='Road to Riches', plotter_class=RtoRPlotter, url=SPANSH_RICHES_ROUTE,
        options=['use_mapping_value', 'avoid_thargoids', 'loop']
    ),
}
