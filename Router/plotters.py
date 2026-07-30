
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

from .constants import lbls, btns, tts, errs, SPANSH_ROUTE, SPANSH_GALAXY_ROUTE, SPANSH_RICHES_ROUTE, SPANSH_EXOBIOLOGY_ROUTE, SPANSH_TRADE_ROUTE, SPANSH_TOURIST_ROUTE, SPANSH_FLEETCARRIER_ROUTE, FLEET_CARRIER_STATS
from .context import Context
from .ship import Ship

WIDTH3:int = 9
@dataclass
class PlotterSpec:
    """ Everything that describes one route-plotting type. """
    label:str
    plotter_class:type
    url:str
    src_key:str = 'from'
    dest_key:str = 'to'
    options:list = field(default_factory=list)
    body_types:list|None = None  # riches-family body_types filter, e.g. ["Ammonia world"]
    min_value:int|None = None    # min_value threshold: fixed always-sent value, or the slider's
                                  # initial position (raw credits) when min_value_slider is True
    min_value_slider:bool = False  # show an actual "Minimum Landmark Value" slider (Exobiology only --
                                    # the other riches-family types fix min_value with no UI control)

class Plotter(ABC):
    """Base class for all route plotters."""

    def __init__(self, ui, frwidth:int, route_type:str) -> None:
        """ Initialize the plotter. """
        self.ui = ui
        self.frwidth = frwidth
        self.frame:th.Frame | None = None
        self.route_type = route_type
        self.options:list = PLOTTER_SPECS[route_type].options

        # Declared for subclasses that use the shared hop-list widget; each sets these in its
        # own create_frame() before calling _rebuild_hop_rows() (see _create_hop_row etc.)
        self.hop_label:str = ''
        self.hop_tooltip:str = ''
        self.hops_frame:th.Frame
        self.hop_rows:list[dict] = []

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

    def _create_system_entry(self, parent:th.Frame, row:int, col:int, label:str, tooltip:str, *,
                              name:str = '', menu:dict|None = None, initial:str = '',
                              add_cmd=None, remove_cmd=None, pady:int = 5) -> th.Autocompleter:
        """ One system-entry row: an autocompleter, optionally named (source/dest) or menued
        (right-click history), optionally with -/+ buttons in the two columns after it. """
        kw:dict = {'width': 30, 'func': self.ui.query_systems}
        if menu:
            kw['menu'] = menu
        if name:
            kw['name'] = name

        ac:th.Autocompleter = th.Autocompleter(parent, label, **kw)
        th.Tooltip(ac, tooltip)
        if initial:
            self.ui.set_entry(ac, initial)
        ac.grid(row=row, column=col, columnspan=3, padx=5, pady=pady)

        spwidth:int = 0
        if add_cmd is not None:
            add_btn:th.Button = th.Button(parent, text=lbls['add_hop'], width=2, command=add_cmd)
            th.Tooltip(add_btn, tts['add_hop'])
            add_btn.grid(row=row, column=col+3, padx=2, pady=2, sticky=tk.W)
            spwidth = add_btn.winfo_reqwidth()

        rb:th.Button|th.Frame
        if remove_cmd is not None:
            rb = th.Button(parent, text=lbls['remove_hop'], width=2, command=remove_cmd)
            th.Tooltip(rb, tts['remove_hop'])
        else:
            rb = th.Frame(parent, width=spwidth, height=1, bg='yellow')
            rb.grid_propagate(False)

        rb.grid(row=row, column=col+4, padx=2, pady=2)

        return ac

    def _create_source(self, parent:th.Frame, row:int, col:int, add_cmd=None) -> None:
        """Create source system autocompleter widget."""
        srcmenu:dict = {}
        if Context.router.system != '':
            srcmenu[Context.router.system] = [self.ui.menu_callback, 'src']
        for sys in Context.router.history:
            if sys not in srcmenu:
                srcmenu[sys] = [self.ui.menu_callback, 'src']

        self._create_system_entry(parent, row, col, lbls["source_system"], tts["source_system"],
                                   name="source_ac", menu=srcmenu, initial=Context.router.src, add_cmd=add_cmd)

    def _create_dest(self, parent:th.Frame, row:int, col:int) -> None:
        """Create destination system autocompleter widget."""
        destmenu:dict = {}
        for sys in Context.router.history:
            if sys not in destmenu:
                destmenu[sys] = [self.ui.menu_callback, 'dest']

        self._create_system_entry(parent, row, col, lbls["dest_system"], tts["dest_system"],
                                   name="dest_ac", menu=destmenu, initial=Context.router.dest)

    def _create_options(self, parent:th.Frame, row:int, col:int, options:list, params:dict) -> None:
        """Create options listbox widget."""
        lb:th.Listbox = th.Listbox(parent, [lbls[v] for v in options], name="options")
        th.Tooltip(lb, tts['galaxy_options'])

        for i, item in enumerate(options):
            if params.get(item, False) == True:
                lb.selection_set(i)
        lb.grid(row=row, column=col, rowspan=int(len(options) / 2)+1, padx=5, pady=5)

    def _create_range(self, parent:th.Frame, row:int, col:int, range_val:str = "32.0", width:int=9) -> None:
        """Create range entry widget."""
        range_entry:th.Spinbox = th.Spinbox(parent, placeholder=lbls['range'], from_=5.0, to=120.0, increment=5.0, width=width-2, menu=self.ui._ship_dict(), justify=tk.CENTER, name="range_entry")
        range_entry.set_text(str(range_val), False)
        range_entry.grid(row=row, column=col, padx=5, pady=5, sticky=tk.NW)

        th.Tooltip(range_entry, tts["range"])

    # Shared hop-list widget: a caller-placed "+" beside the source field starts the list
    # (_add_hop_row(-1)); each row then gets its own "-"/"+" to remove itself or insert below.

    def _row_value(self, ac:th.Autocompleter) -> str:
        """ An empty Autocompleter's .get() returns its placeholder text, not "". Treat that as blank. """
        text:str = ac.get().strip()
        return '' if text == ac.placeholder else text

    def _create_hop_row(self, parent:th.Frame, row:int, index:int, value:str) -> dict:
        """ One hop row: entry spans cols 0-2 (matching the source field above), -/+ in cols 3/4. """
        row_fr:th.Frame = th.Frame(parent)
        ac:th.Autocompleter = self._create_system_entry(row_fr, 0, 0, self.hop_label, self.hop_tooltip,
                                                          initial=value, pady=2,
                                                          remove_cmd=lambda: self._remove_hop_row(index),
                                                          add_cmd=lambda: self._add_hop_row(index))
        row_fr.grid(row=row, column=0, sticky=tk.W)
        return {'frame': row_fr, 'ac': ac}

    def _rebuild_hop_rows(self, values:list[str]) -> None:
        """ Destroy and recreate every hop row from `values` (empty is valid -- no forced
        minimum). Rebuilt from scratch so each row's -/+ closes over the right index. """
        for hop in self.hop_rows:
            hop['ac'].popup.destroy()  # the typeahead popup is a Toplevel, not a row child
            hop['frame'].destroy()

        # Tk's grid geometry manager only recomputes hops_frame's requested size while it still
        # has at least one slave -- dropping the last row leaves the container's reqheight stuck
        # at its old (non-empty) size even though grid_bbox correctly reports zero slaves. Forcing
        # an explicit size here resets that stale value; grid_propagate (on by default) then
        # immediately overrides it again once/if new rows are gridded below.
        self.hops_frame.configure(width=1, height=1)

        self.hop_rows = [self._create_hop_row(self.hops_frame, i, i, value) for i, value in enumerate(values)]

    def _add_hop_row(self, index:int) -> None:
        """ Insert a blank hop row immediately after `index` (-1 to insert as the very first
        hop, via the source field's own + button). """
        values:list = [self._row_value(hop['ac']) for hop in self.hop_rows]
        values.insert(index + 1, '')
        self._rebuild_hop_rows(values)

    def _remove_hop_row(self, index:int) -> None:
        """ Remove the hop row at `index`. """
        values:list = [self._row_value(hop['ac']) for i, hop in enumerate(self.hop_rows) if i != index]
        self._rebuild_hop_rows(values)

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

        sfr.grid(row=row, column=col, columnspan=5, sticky=tk.EW)

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
        btn_frame.grid(row=row, column=col, columnspan=5, sticky=tk.EW, pady=(5, 0))

        row = 0; col = 0
        self.import_route_btn:th.Button = th.Button(btn_frame, text=btns["import_route"], command=lambda: self.ui.import_route())
        self.import_route_btn.grid(row=row, column=col, padx=5, sticky=tk.W)

        col += 1
        self.plot_route_btn:th.Button = th.Button(btn_frame, text=btns["calculate_route"], command=self.plot)
        self.plot_route_btn.grid(row=row, column=col, padx=5, sticky=tk.W)

        col += 1
        self.cancel_plot:th.Button = th.Button(btn_frame, text=btns["cancel"], command=lambda: self.ui.show_frame('Default'))
        self.cancel_plot.grid(row=row, column=col, padx=5, sticky=tk.W)


class NeutronPlotter(Plotter):
    """Plotter for neutron star routes."""

    def create_frame(self, parent:th.Frame) -> th.Frame:
        """Create the neutron plotter frame."""
        plot_fr:th.Frame = th.Frame(parent, width=self.frwidth)
        row:int = 0; col:int = 0

        params:dict = Context.router.route_params.get('Neutron', {})
        self._plot_switcher(plot_fr, row, col)

        # Source, via-point hops, and destination all live in their own frame -- their column
        # layout stays self-contained instead of fighting range/efficiency/supercharge for
        # columns on shared rows.
        row += 1; col = 0
        route_fr:th.Frame = th.Frame(plot_fr)
        self._create_source(route_fr, 0, 0, add_cmd=lambda: self._add_hop_row(-1))

        self.hop_label = lbls['via_system']; self.hop_tooltip = tts['via_system']
        self.hops_frame = th.Frame(route_fr)
        self.hop_rows = []
        self._rebuild_hop_rows(params.get('via', []))
        self.hops_frame.grid(row=1, column=0, columnspan=5, sticky=tk.W)

        self._create_dest(route_fr, 2, 0)
        route_fr.grid(row=row, column=col, columnspan=3, sticky=tk.W)

        # Range and efficiency
        col2_fr:th.Frame = th.Frame(plot_fr)
        self._create_range(col2_fr, 0, 0, str(params.get('range', "32.0")), 13)

        self.efficiency_slider:th.Scale = th.Scale(col2_fr, from_=0, to=100, resolution=5, orient=tk.HORIZONTAL)
        th.Tooltip(self.efficiency_slider, tts["efficiency"])
        self.efficiency_slider.grid(row=1, column=0, padx=5, pady=5, sticky=tk.NW)
        self.efficiency_slider.set(params.get('efficiency', 60))
        col2_fr.grid(row=row, column=3, sticky=tk.NW)

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
        r2.grid(row=row, column=col, columnspan=4, padx=5, pady=5)

        # Buttons
        row += 1; col = 0
        self._create_buttons(plot_fr, row, col)
        #debug_grid(plot_fr)
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
        range_entry = th.resolve(self.frame.nametowidget("range_entry"))
        params['range'] = range_entry.var.get()

        if not re.match(r"^\d+(\.\d+)?$", params['range']):
            Debug.logger.info(f"Invalid range entry {params['range']}")
            self.ui.show_frame('Neutron')
            range_entry.set_error_style()
            return

        # No pre-validation per via system -- Spansh errors on a bad name regardless.
        params['via'] = [v for hop in self.hop_rows if (v := self._row_value(hop['ac'])) != '']

        Context.router.plot_route('Neutron', params)
        self.ui._show_busy_gui(True)


class GalaxyPlotter(Plotter):
    """Plotter for galaxy-wide routes."""

    def create_frame(self, parent:th.Frame) -> th.Frame:
        """Create the galaxy plotter frame."""
        plot_fr:th.Frame = th.Frame(parent, width=self.frwidth)
        row:int = 0; col:int = 0

        params:dict = Context.router.route_params.get('Galaxy', {})

        self._plot_switcher(plot_fr, row, col)

        # First row: source and options
        row += 1; col = 0
        self._create_source(plot_fr, row, col)
        col += 3

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
        self.shipdd:th.ComboBox = th.ComboBox(plot_fr, self.shipvar, values=names, width=WIDTH3)
        th.Tooltip(self.shipdd, tts["select_ship"])
        self.shipdd.grid(row=row, column=col, padx=5, pady=5)

        col += 1
        cargo_entry:th.Spinbox = th.Spinbox(plot_fr, placeholder=lbls['cargo'], from_=0, to=1500, increment=2, width=WIDTH3-2, justify=tk.CENTER, name="cargo_entry")
        self.ui.set_entry(cargo_entry, str(Context.router.cargo))
        cargo_entry.grid(row=row, column=col, padx=5, pady=5)
        th.Tooltip(cargo_entry, tts["cargo"])

        # Row 4: algorithm and fuel reserve
        row += 1; col = 0
        algorithms:list = ['Fuel', 'Fuel Jumps', 'Guided', 'Optimistic', 'Pessimistic']
        self.algorithm:tk.StringVar = tk.StringVar(plot_fr, value=params.get('algorithm', 'Optimistic'))
        algodd:th.ComboBox = th.ComboBox(plot_fr, self.algorithm, values=algorithms, width=WIDTH3)
        th.Tooltip(algodd, tts["select_algorithm"])
        algodd.grid(row=row, column=col, padx=5, pady=5)

        col += 1
        #self.fuel_res:th.Placeholder = th.Placeholder(plot_fr, lbls['fuel_reserve'], width=WIDTH3, justify=tk.CENTER)
        self.fuel_res:th.Spinbox = th.Spinbox(plot_fr, lbls['fuel_reserve'], width=WIDTH3-2, from_=0, to=64, justify=tk.CENTER)
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


class RichesPlotter(Plotter):
    """Plotter for the "systems containing bodies" route family: Road to Riches and its
    body-type-filtered variants (Ammonia World, Earth-like World, Rocky/HMC World) on
    /api/riches/route, plus Exobiology (Expressway to Exomastery) on /api/exobiology/route."""

    def create_frame(self, parent:th.Frame) -> th.Frame:
        """Create the riches-family plotter frame."""
        plot_fr:th.Frame = th.Frame(parent, width=self.frwidth)
        row:int = 0; col:int = 0

        params:dict = Context.router.route_params.get(self.route_type, {})
        spec = PLOTTER_SPECS[self.route_type]

        self._plot_switcher(plot_fr, row, col)

        row += 1; col = 0

        # Row 1: source and options
        self._create_source(plot_fr, row, col)

        col = 4
        self._create_options(plot_fr, row, col, self.options, params)

        # Exobiology's real filtering criterion
        if spec.min_value_slider:
            min_value_slider:th.Scale = th.Scale(plot_fr, from_=0, to=20, resolution=1, orient=tk.HORIZONTAL, name="min_value_entry")
            th.Tooltip(min_value_slider, tts["min_landmark_value"])
            min_value_slider.grid(row=row+1, column=col, padx=5, pady=5, sticky=tk.EW)
            min_value_slider.set(int(params.get('min_value', spec.min_value or 0)) // 1_000_000)

        # Row 2: destination
        row += 1; col = 0
        self._create_dest(plot_fr, row, col)

        # Row 3: range and radius
        row += 1; col = 0
        self._create_range(plot_fr, row, col, str(params.get('range', "32.0")), 11)

        col += 1
        #radius_entry:th.Placeholder = th.Placeholder(plot_fr, lbls['radius'], width=WIDTH3, justify=tk.CENTER, name="radius_entry")
        radius_entry:th.Spinbox = th.Spinbox(plot_fr, lbls['radius'], width=WIDTH3-2, from_=1, to=99, justify=tk.CENTER, name="radius_entry")
        self.ui.set_entry(radius_entry, str(params.get('radius', 25)))
        th.Tooltip(radius_entry, tts["radius"])
        radius_entry.grid(row=row, column=col, padx=5, pady=5)

        col += 1
        #max_results_entry:th.Placeholder = th.Placeholder(plot_fr, lbls['max_results'], width=WIDTH3, justify=tk.CENTER, name="max_results_entry")
        max_results_entry:th.Spinbox = th.Spinbox(plot_fr, lbls['max_results'], from_=1, to=999, width=WIDTH3-2, justify=tk.CENTER, name="max_results_entry")
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
        """Perform riches-family route plotting."""
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
            self.ui.show_frame(self.route_type)
            return

        # Leave destination blank for a circular tour starting and ending at the source
        to:str = dest_ac.get().strip()
        if to != '':
            params["to"] = self._validate_system(to, dest_ac)
            if params['to'] is None:
                self.ui.show_frame(self.route_type)
                return

        range_entry = th.resolve(self.frame.nametowidget("range_entry"))
        params['range'] = range_entry.var.get()
        if not re.match(r"^\d+(\.\d+)?$", params['range']):
            Debug.logger.info(f"Invalid range entry {params['range']}")
            self.ui.show_frame(self.route_type)
            range_entry.set_error_style()
            return

        radius_entry = self.frame.nametowidget("radius_entry")
        params['radius'] = radius_entry.get().strip()
        if not re.match(r"^\d+(\.\d+)?$", params['radius']):
            Debug.logger.info(f"Invalid radius entry {params['radius']}")
            self.ui.show_frame(self.route_type)
            radius_entry.set_error_style()
            return

        max_results_entry = self.frame.nametowidget("max_results_entry")
        params['max_results'] = max_results_entry.get().strip()
        if not re.match(r"^\d+$", params['max_results']):
            Debug.logger.info(f"Invalid max results entry {params['max_results']}")
            self.ui.show_frame(self.route_type)
            max_results_entry.set_error_style()
            return

        for opt in self.options:
            params[opt] = 1 if options.selection_includes(self.options.index(opt)) else 0

        # Body-type-filtered variants (Ammonia/Earth-like/Rocky-metal) fix a body_types filter;
        # Exobiology instead has a real "Minimum Landmark Value" slider (its filtering criterion,
        # since there's no body type to filter by there); plain Road to Riches sends neither, so
        # Spansh finds any valuable body.
        spec = PLOTTER_SPECS[self.route_type]
        if spec.body_types:
            params['body_types'] = spec.body_types
        if spec.min_value_slider:
            min_value_slider = self.frame.nametowidget("min_value_entry")
            params['min_value'] = int(min_value_slider.get()) * 1_000_000
        elif spec.min_value is not None:
            params['min_value'] = spec.min_value

        Context.router.plot_route(self.route_type, params)
        self.ui._show_busy_gui(True)


class TradePlotter(Plotter):
    """Plotter for /api/trade/route. Unlike every other route type, this starts from a
    specific station (not just a system) and has no destination or ship range -- it's a
    closed loop of up to max_hops trade legs, each capped at max_hop_distance."""

    def create_frame(self, parent:th.Frame) -> th.Frame:
        """Create the trade route plotter frame."""
        plot_fr:th.Frame = th.Frame(parent, width=self.frwidth)
        row:int = 0; col:int = 0

        params:dict = Context.router.route_params.get('Trade', {})
        self._plot_switcher(plot_fr, row, col)

        # Row 1: source station -- a single field, like Spansh's own "Source Station" combobox,
        # rather than picking a system first and a station within it second.
        row += 1; col = 0
        station_ac = th.Autocompleter(plot_fr, lbls["station"], width=30, func=self.ui.query_station_names, name="station_ac")
        th.Tooltip(station_ac, tts["station"])
        if params.get('station'):
            self.ui.set_entry(station_ac, params['station'])
        station_ac.grid(row=row, column=col, columnspan=3, padx=5, pady=5)

        col += 3
        self._create_options(plot_fr, row, col, self.options, params)

        # Row 2: starting capital and cargo capacity
        row += 1; col = 0
        #starting_capital_entry:th.Placeholder = th.Placeholder(plot_fr, lbls['starting_capital'], width=WIDTH3, justify=tk.CENTER, name="starting_capital_entry")
        starting_capital_entry:th.Spinbox = th.Spinbox(plot_fr, lbls['starting_capital'], from_=1000, to=10000000, increment=1000, width=WIDTH3-2, justify=tk.CENTER, name="starting_capital_entry")
        self.ui.set_entry(starting_capital_entry, str(params.get('starting_capital', 1000)))
        th.Tooltip(starting_capital_entry, tts["starting_capital"])
        starting_capital_entry.grid(row=row, column=col, padx=5, pady=5)

        col += 1
        #max_cargo_entry:th.Placeholder = th.Placeholder(plot_fr, lbls['max_cargo'], width=WIDTH3, justify=tk.CENTER,
        # name="max_cargo_entry")
        max_cargo_entry:th.Spinbox = th.Spinbox(plot_fr, placeholder=lbls['cargo'], from_=0, to=1500, increment=2, width=WIDTH3-2, justify=tk.CENTER, name="max_cargo_entry")
        self.ui.set_entry(max_cargo_entry, str(params.get('max_cargo', 7)))
        th.Tooltip(max_cargo_entry, tts["max_cargo"])
        max_cargo_entry.grid(row=row, column=col, padx=5, pady=5)

        col += 1
        #max_hops_entry:th.Placeholder = th.Placeholder(plot_fr, lbls['max_hops'], width=WIDTH3, justify=tk.CENTER, name="max_hops_entry")
        max_hops_entry:th.Spinbox = th.Spinbox(plot_fr, lbls['max_hops'], from_=1, to=100, width=WIDTH3-2, justify=tk.CENTER, name="max_hops_entry")
        self.ui.set_entry(max_hops_entry, str(params.get('max_hops', 5)))
        th.Tooltip(max_hops_entry, tts["max_hops"])
        max_hops_entry.grid(row=row, column=col, padx=5, pady=5)

        # Row 3: max hops and max hop distance

        row += 1; col = 0
        #max_hop_distance_entry:th.Placeholder = th.Placeholder(plot_fr, lbls['max_hop_distance'], width=WIDTH3, justify=tk.CENTER, name="max_hop_distance_entry")
        max_hop_distance_entry:th.Spinbox = th.Spinbox(plot_fr, lbls['max_hop_distance'], from_=5, to=120, width=WIDTH3-2, justify=tk.CENTER, name="max_hop_distance_entry")
        self.ui.set_entry(max_hop_distance_entry, str(params.get('max_hop_distance', 50)))
        th.Tooltip(max_hop_distance_entry, tts["max_hop_distance"])
        max_hop_distance_entry.grid(row=row, column=col, padx=5, pady=5)

        # Row 4: max distance to arrival and max market age
        col += 1
        #max_system_distance_entry:th.Placeholder = th.Placeholder(plot_fr, lbls['max_system_distance'], width=WIDTH3, justify=tk.CENTER, name="max_system_distance_entry")
        max_system_distance_entry:th.Spinbox = th.Spinbox(plot_fr, lbls['max_system_distance'], from_=0, to=1000000, increment=100, width=WIDTH3-2, justify=tk.CENTER, name="max_system_distance_entry")
        self.ui.set_entry(max_system_distance_entry, str(params.get('max_system_distance', 10000000)))
        th.Tooltip(max_system_distance_entry, tts["max_system_distance"])
        max_system_distance_entry.grid(row=row, column=col, padx=5, pady=5)

        col += 1
        #max_price_age_entry:th.Placeholder = th.Placeholder(plot_fr, lbls['max_price_age'], width=WIDTH3, justify=tk.CENTER, name="max_price_age_entry")
        max_price_age_entry:th.Spinbox = th.Spinbox(plot_fr, lbls['max_price_age'], from_=0, to=720, width=WIDTH3-2, justify=tk.CENTER, name="max_price_age_entry")
        if params.get('max_price_age_days'):
            self.ui.set_entry(max_price_age_entry, str(params.get('max_price_age_days')))
        th.Tooltip(max_price_age_entry, tts["max_price_age"])
        max_price_age_entry.grid(row=row, column=col, padx=5, pady=5)

        # Buttons
        row += 4; col = 0
        self._create_buttons(plot_fr, row, col)

        self.frame = plot_fr
        return plot_fr


    @catch_exceptions
    def plot(self) -> None:
        """Perform trade route plotting."""
        if not self.frame:
            return

        self.ui.hide_error()

        station_ac = self.frame.nametowidget("station_ac")
        options = self.frame.nametowidget("options")

        params:dict = {}

        station:str = station_ac.get().strip()

        # query_station_names() already returns "System / Station" combined strings (matching
        # Spansh's own single-field UI), so a validated match already carries both names --
        # no need for a second Spansh roundtrip just to resolve the system name. Spansh's own
        # /api/trade/route call will error out on a bad system/station combo regardless.
        params["system"], _, params["station"] = station.partition(" / ")

        for entry_name, param_name in [("starting_capital_entry", "starting_capital"), ("max_cargo_entry", "max_cargo"),
                                        ("max_hops_entry", "max_hops"), ("max_hop_distance_entry", "max_hop_distance"),
                                        ("max_system_distance_entry", "max_system_distance")]:
            entry = self.frame.nametowidget(entry_name)
            value:str = entry.get().strip()
            if not re.match(r"^\d+(\.\d+)?$", value):
                Debug.logger.info(f"Invalid {param_name} entry {value}")
                self.ui.show_frame('Trade')
                entry.set_error_style()
                return
            params[param_name] = value

        # Optional: same convention as Galaxy's fuel_res -- if it's blank or still showing
        # placeholder text, the regex just won't match and we silently omit it (no error
        # state, no aborting the plot), since "leave it unset" is a valid, common choice here.
        max_price_age_entry = self.frame.nametowidget("max_price_age_entry")
        max_price_age_days:str = max_price_age_entry.get().strip()
        if re.match(r"^\d+(\.\d+)?$", max_price_age_days):
            # Spansh wants "seconds since that time" rather than an age directly, and we only
            # keep a day count in route_params (for re-populating the field), not a timestamp.
            params['max_price_age'] = int(float(max_price_age_days) * 86400)
            params['max_price_age_days'] = max_price_age_days

        for opt in self.options:
            params[opt] = 1 if options.selection_includes(self.options.index(opt)) else 0

        Context.router.plot_route('Trade', params)
        self.ui._show_busy_gui(True)


class TouristPlotter(Plotter):
    """Plotter for /api/tourist/route -- visits a variable-length list of specific systems
    (e.g. tourist beacons) starting from a source, optionally ending at a final destination
    (dest_ac, left blank for a one-way/looped route)."""

    def create_frame(self, parent:th.Frame) -> th.Frame:
        """Create the tourist route plotter frame."""
        plot_fr:th.Frame = th.Frame(parent, width=self.frwidth)
        row:int = 0; col:int = 0

        params:dict = Context.router.route_params.get('Tourist', {})
        self._plot_switcher(plot_fr, row, col)

        # Source, stop list, and optional final destination all live in their own frame --
        # their column layout stays self-contained instead of fighting range/options for
        # columns on shared rows.
        row += 1; col = 0
        route_fr:th.Frame = th.Frame(plot_fr)
        self._create_source(route_fr, 0, 0, add_cmd=lambda: self._add_hop_row(-1))

        self.hop_label = lbls['destination']; self.hop_tooltip = tts['destination']
        self.hops_frame = th.Frame(route_fr)
        self.hop_rows = []
        self._rebuild_hop_rows(params.get('destination', []))
        self.hops_frame.grid(row=1, column=0, columnspan=5, sticky=tk.W)

        self._create_dest(route_fr, 2, 0)
        route_fr.grid(row=row, column=col, columnspan=3, sticky=tk.W)

        # Range and loop -- Tourist only ever has this one option, so a checkbox beats a
        # single-item options listbox.
        col2_fr:th.Frame = th.Frame(plot_fr)
        self._create_range(col2_fr, 0, 0, str(params.get('range', "32.0")), 13)

        self.loop_var:tk.IntVar = tk.IntVar(value=1 if params.get('loop', False) else 0)
        loop_cb:th.Checkbutton = th.Checkbutton(col2_fr, text=lbls['loop'], variable=self.loop_var)
        th.Tooltip(loop_cb, tts['loop'])
        loop_cb.grid(row=1, column=0, padx=5, pady=5)
        col2_fr.grid(row=row, column=3, sticky=tk.NW)

        # Buttons
        row += 1; col = 0
        self._create_buttons(plot_fr, row, col)

        self.frame = plot_fr
        return plot_fr

    @catch_exceptions
    def plot(self) -> None:
        """Perform tourist route plotting."""
        if not self.frame:
            return

        self.ui.hide_error()

        src_ac = self.frame.nametowidget("source_ac")
        dest_ac = self.frame.nametowidget("dest_ac")

        params:dict = {}

        frm:str = src_ac.get().strip()
        params["source"] = self._validate_system(frm, src_ac)
        if params['source'] is None:
            self.ui.show_frame('Tourist')
            return

        # Leave blank for a one-way/looped route ending back at the source
        to:str = self._row_value(dest_ac)
        if to != '':
            params["final_destination"] = self._validate_system(to, dest_ac)
            if params['final_destination'] is None:
                self.ui.show_frame('Tourist')
                return

        range_entry = th.resolve(self.frame.nametowidget("range_entry"))
        params['range'] = range_entry.var.get()
        if not re.match(r"^\d+(\.\d+)?$", params['range']):
            Debug.logger.info(f"Invalid range entry {params['range']}")
            self.ui.show_frame('Tourist')
            range_entry.set_error_style()
            return

        # No pre-validation per destination -- Spansh errors on a bad name regardless.
        params['destination'] = [v for hop in self.hop_rows if (v := self._row_value(hop['ac'])) != '']

        params['loop'] = self.loop_var.get()

        Context.router.plot_route('Tourist', params)
        self.ui._show_busy_gui(True)

class FleetCarrierPlotter(Plotter):
    """Plotter for /api/fleetcarrier/route -- an ordered list of systems to visit and refuel
    at. Unlike every other route type, Spansh needs each system's id64 here, not its name, so
    plot() resolves each validated name via ui.resolve_system_id64() before submitting. Starting
    fuel is always auto-calculated by Spansh; there's no manual fuel-loaded/tritium input."""

    def create_frame(self, parent:th.Frame) -> th.Frame:
        """Create the fleet carrier plotter frame."""
        plot_fr:th.Frame = th.Frame(parent, width=self.frwidth)
        row:int = 0; col:int = 0

        params:dict = Context.router.route_params.get('FleetCarrier', {})
        self._plot_switcher(plot_fr, row, col)

        # Source and the destination list live in their own frame -- their column layout
        # stays self-contained instead of fighting the carrier-type/capacity rows for columns.
        row += 1; col = 0
        route_fr:th.Frame = th.Frame(plot_fr)
        self._create_source(route_fr, 0, 0, add_cmd=lambda: self._add_hop_row(-1))

        self.hop_label = lbls['destination']; self.hop_tooltip = tts['destination']
        self.hops_frame = th.Frame(route_fr)
        self.hop_rows = []
        self._rebuild_hop_rows(params.get('destination_names', []))
        self.hops_frame.grid(row=1, column=0, columnspan=5, sticky=tk.W)

        route_fr.grid(row=row, column=col, columnspan=4, sticky=tk.W)

        # Row 3
        col = 4
        capacity_used_entry:th.Spinbox = th.Spinbox(plot_fr, lbls['capacity_used'], from_=0, to=100000, increment=10, width=WIDTH3, justify=tk.CENTER, name="capacity_used_entry")
        self.ui.set_entry(capacity_used_entry, str(params.get('capacity_used', 0)))
        th.Tooltip(capacity_used_entry, tts["capacity_used"])
        capacity_used_entry.grid(row=row, column=col, padx=5, pady=5)

        self.carrier_type:tk.StringVar = tk.StringVar()
        self.carrier_type.set(params.get('carrier_type', 'fleet'))

        row += 1; col = 0
        l1:th.Label = th.Label(plot_fr, text=lbls["carrier_type"])
        l1.grid(row=row, column=col, padx=5, pady=5)

        col += 1
        r1:th.Radiobutton = th.Radiobutton(plot_fr, text=lbls["fleet_carrier"], variable=self.carrier_type, value='fleet')
        th.Tooltip(r1, tts['carrier_type'])
        r1.grid(row=row, column=col, columnspan=2, padx=5, pady=5)

        col = 4
        r2:th.Radiobutton = th.Radiobutton(plot_fr, text=lbls["squadron_carrier"], variable=self.carrier_type, value='squadron')
        th.Tooltip(r2, tts['carrier_type'])
        r2.grid(row=row, column=col, padx=5, pady=5)

        # Buttons
        row += 1; col = 0
        self._create_buttons(plot_fr, row, col)

        self.frame = plot_fr
        return plot_fr

    @catch_exceptions
    def plot(self) -> None:
        """Perform fleet carrier route plotting."""
        if not self.frame:
            return

        self.ui.hide_error()

        src_ac = self.frame.nametowidget("source_ac")

        params:dict = {}

        frm:str = src_ac.get().strip()
        source_name = self._validate_system(frm, src_ac)
        if source_name is None:
            self.ui.show_frame('FleetCarrier')
            return

        source_id64 = self.ui.resolve_system_id64(source_name)
        if source_id64 is None:
            self.ui.show_error(errs['no_system_id'])
            self.ui.show_frame('FleetCarrier')
            return

        # No pre-validation per destination name -- Spansh errors on a bad one regardless.
        dest_names:list = [v for hop in self.hop_rows if (v := self._row_value(hop['ac'])) != '']
        dest_id64s:list = []
        for name in dest_names:
            id64 = self.ui.resolve_system_id64(name)
            if id64 is None:
                self.ui.show_error(errs['no_system_id'])
                self.ui.show_frame('FleetCarrier')
                return
            dest_id64s.append(id64)

        capacity_used_entry = self.frame.nametowidget("capacity_used_entry")
        capacity_used:str = capacity_used_entry.get().strip()
        if not re.match(r"^\d+(\.\d+)?$", capacity_used):
            Debug.logger.info(f"Invalid capacity_used entry {capacity_used}")
            self.ui.show_frame('FleetCarrier')
            capacity_used_entry.set_error_style()
            return

        carrier_type:str = self.carrier_type.get()
        stats:dict = FLEET_CARRIER_STATS[carrier_type]

        params['source_name'] = source_name
        params['source'] = source_id64
        params['destination_names'] = dest_names
        params['destinations'] = dest_id64s
        params['carrier_type'] = carrier_type
        params['capacity'] = stats['capacity']
        params['mass'] = stats['mass']
        params['capacity_used'] = capacity_used
        params['calculate_starting_fuel'] = 1

        Context.router.plot_route('FleetCarrier', params)
        self.ui._show_busy_gui(True)


PLOTTER_SPECS:dict = {
    'Galaxy': PlotterSpec(
        label='Galaxy Plotter', plotter_class=GalaxyPlotter, url=SPANSH_GALAXY_ROUTE,
        src_key='source', dest_key='destination',
        options=['is_supercharged', 'use_supercharge', 'use_injections', 'exclude_secondary', 'refuel_every_scoopable']
    ),
    'Neutron': PlotterSpec(
        label='Neutron Plotter', plotter_class=NeutronPlotter, url=SPANSH_ROUTE
    ),
    'RtoR': PlotterSpec(
        label='Road to Riches', plotter_class=RichesPlotter, url=SPANSH_RICHES_ROUTE,
        options=['use_mapping_value', 'avoid_thargoids', 'loop']
    ),
    'Exobiology': PlotterSpec(
        label='Expressway to Exomastery', plotter_class=RichesPlotter, url=SPANSH_EXOBIOLOGY_ROUTE,
        options=['avoid_thargoids', 'loop'], min_value=100000, min_value_slider=True
    ),
    'Trade': PlotterSpec(
        label='Trade Planner', plotter_class=TradePlotter, url=SPANSH_TRADE_ROUTE,
        src_key='system',
        options=['requires_large_pad', 'allow_prohibited', 'allow_planetary', 'allow_player_owned',
                 'allow_restricted_access', 'unique', 'permit']
    ),
    'EarthLike': PlotterSpec(
        label='Earth-like World Route', plotter_class=RichesPlotter, url=SPANSH_RICHES_ROUTE,
        options=['avoid_thargoids', 'loop'], body_types=['Earth-like world'], min_value=1
    ),
    'Ammonia': PlotterSpec(
        label='Ammonia World Route', plotter_class=RichesPlotter, url=SPANSH_RICHES_ROUTE,
        options=['avoid_thargoids', 'loop'], body_types=['Ammonia world'], min_value=1
    ),
    'RockyMetal': PlotterSpec(
        label='Rocky/HMC World Route', plotter_class=RichesPlotter, url=SPANSH_RICHES_ROUTE,
        options=['avoid_thargoids', 'loop'], body_types=['Rocky body', 'High metal content world'], min_value=1
    ),
    'Tourist': PlotterSpec(
        label='Tourist Route', plotter_class=TouristPlotter, url=SPANSH_TOURIST_ROUTE,
        src_key='source', dest_key='final_destination'
    ),
    'FleetCarrier': PlotterSpec(
        label='Fleet Carrier Route', plotter_class=FleetCarrierPlotter, url=SPANSH_FLEETCARRIER_ROUTE,
        src_key='source_name'
    )
}
