import os
import tkinter as tk
from tkinter import ttk, font
import tkinter.messagebox as confirmDialog
from functools import partial
from pathlib import Path
import re
import requests
import json
import myNotebook as nb # type: ignore

from theme import theme # type: ignore
from config import config # type: ignore

from .utils import th
from .utils.debug import Debug, catch_exceptions
from .utils.misc import singleton, hfplus, str_truncate, PopupNotice, copy_to_clipboard
from .utils.tkrichtext import RichScrolledText

from .constants import NAME, SPANSH_SYSTEMS, SPANSH_STATIONS_NAME, SPANSH_SEARCH_SYSTEMS, ASSET_DIR, FONT, BOLD, lbls, btns, tts, errs
from .ship import Ship
from .route import Route
from .context import Context
from .route_manager import SESSION
from .route_window import RouteWindow
from .plotters import PLOTTER_SPECS

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

        # Plotters reference Context.ui directly (rather than a constructor-passed reference),
        # so it must point here before they're constructed below -- not just after load.py's
        # `Context.ui = UI(parent)` assignment, which only runs once this constructor returns.
        Context.ui = self

        self.frwidth:int = int(375 * (config.get_int('ui_scale') / 100))
        self.parent:tk.Widget|None = parent
        self.window_route:RouteWindow = RouteWindow(self.parent.winfo_toplevel())

        self.frame:th.Frame = th.Frame(parent, borderwidth=2)
        self.frame.grid(sticky=tk.NSEW)
        self.frame.grid_columnconfigure(0, minsize=self.frwidth)

        self.update:th.Label

        self.help_img:tk.PhotoImage = tk.PhotoImage(file=os.path.join(Context.plugin_dir, ASSET_DIR, "help.png"))
        self.fuel_img:tk.PhotoImage = tk.PhotoImage(file=os.path.join(Context.plugin_dir, ASSET_DIR, "fuel.png"))
        self.star:tk.PhotoImage = tk.PhotoImage(file=os.path.join(Context.plugin_dir, ASSET_DIR, "star.png"))
        self.neutron_img:tk.PhotoImage = tk.PhotoImage(file=os.path.join(Context.plugin_dir, ASSET_DIR, "neutron.png"))
        self.blank_img:tk.PhotoImage = tk.PhotoImage(width=16, height=16)

        self.error_lbl:th.Label = th.Label(self.frame, text="", foreground='red', justify=tk.CENTER)
        self.error_lbl.grid(row=10, column=0, columnspan=2, padx=5, sticky=tk.W)
        self.hide_error()

        self.router:tk.StringVar = tk.StringVar()
        self.router.set('Galaxy Plotter')  # Set default value

        self.progbar:ttk.Progressbar # Overall progress bar

        self.title_fr:th.Frame = self._create_title_fr(self.frame)
        self.busy_fr:th.Frame = self._create_busy_fr(self.frame)
        self.route_fr:th.Frame = self._create_route_fr(self.frame)

        # Create plotter instances, one per entry in the PLOTTER_SPECS registry
        self.plotters:dict = {
            name: spec.plotter_class(name)
            for name, spec in PLOTTER_SPECS.items()
        }

        # Create frames for all plotters
        self.plot_frames:dict[str, th.Frame] = {}
        for name, plotter in self.plotters.items():
            self.plot_frames[name] = plotter.create_frame(self.frame)

        self.sub_fr:th.Frame = self.title_fr
        self.show_frame('Route' if Context.route.route != [] else 'Default')

        # Wait a while before deciding if we should show the update text
        parent.after(30000, lambda: self.show_plugin_update())
        parent.after(15000, lambda: self.show_notice())


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


    @catch_exceptions
    def show_notice(self) -> None:
        """ Display pending NOTICES.md entry, if any """
        if not Context.notices or not Context.notices.pending_notice:
            return
        notice:str = Context.notices.pending_notice
        w:int = max(len(l) for l in notice.split("\n"))
        h:int = len(notice.replace("\n\n", "\n").split("\n"))
        self.notice:th.RichText = th.RichText(self.frame, width=w, height=h, markdown=notice, relief=tk.FLAT)
        self.notice.bind("<Button-1>", partial(self.dismiss_notice))
        self.notice.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)

    @catch_exceptions
    def dismiss_notice(self, tkEvent = None) -> None:
        """ Hide the notice on click and never show it again """
        Context.notices.dismiss_notice()
        self.notice.grid_remove()
        self.notice.destroy()
        self.frame.update_idletasks()

    def _update_item(self, which:str, type:str, value:str = "") -> None:
        """ Update items of the given type from which source to all other plot types """
        if which != "all":
            try:
                sobj = self.plot_frames[which].nametowidget(type)
            except KeyError: # This plotter doesn't have this widget (e.g. Trade has no dest_ac)
                return
            value = sobj.get()
        for dest in self.plot_frames.values():
            try:
                obj = dest.nametowidget(type)
                if obj == None:
                    continue
                if isinstance(obj, (th.Placeholder, th.Spinbox)):
                    obj.set_text(value, False)
                else:
                    obj.set(value)
            except Exception as e: # If the widget doesn't exist, just skip it
                #Debug.logger.debug(f"_update_item exception: {e}")
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
        Context.router.cancel_plot = True # tell router to stop plotting if it's currently doing so
        self.sub_fr.grid_remove()

        Context.router.route_params['Neutron']['range'] = f"{Context.router.ship.get_range(Context.router.cargo):.2f}" if Context.router.ship else "32.0"
        Context.router.route_params['Neutron']['supercharge_multiplier'] = Context.router.ship.supercharge_multiplier if Context.router.ship else 4

        # Figure out which frame is currently visible
        current:str|None = next((key for key, val in self.plot_frames.items() if val == self.sub_fr), None)

        if current in self.plot_frames: # Update corresponding fields in other plot frames
            self._update_item(current, "source_ac")
            self._update_item(current, "dest_ac")

        match which:
            case 'Route':
                self.sub_fr = self.route_fr
                self.update_progress()

            case 'Default':
                self.sub_fr = self.title_fr

            case _:
                self.sub_fr = self.plot_frames[which]
                self.router.set(Context.router.route_types[which])

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
        busy_fr.grid_columnconfigure(0, weight=1)
        self.route_lbl:th.Label = th.Label(busy_fr, text=lbls["plotting"].format(s=Context.router.src, d=Context.router.dest),
                                                  justify=tk.CENTER, font=BOLD)
        self.route_lbl.grid(row=0, column=0, pady=5)
        self.busyimg:th.Label = th.Label(busy_fr, image=self.frames[0], justify=tk.CENTER)
        self.busyimg.grid(row=1, column=0, pady=10)
        cancel:th.Button = th.Button(busy_fr, text=btns["cancel"], command=lambda: self.show_frame(Context.router.last_plot))
        cancel.grid(row=2, column=0, pady=5)
        return busy_fr


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

        self.progtt.set_text(tt)

        self.progbar.configure(length=self.frwidth-3, value=self._progress())


    @catch_exceptions
    def update_progress(self) -> None:
        if Context.route.route == [] or not hasattr(self, 'waypoint_btn'):
            return
        route:Route = Context.route
        self.waypoint_prev_btn.config(state=tk.DISABLED if route.offset <= -1 else tk.NORMAL)
        self.waypoint_prev_tt.set_text(route.get_waypoint(-1))
        self.waypoint_next_btn.config(state=tk.DISABLED if route.offset >= len(route.route) -1 else tk.NORMAL)
        dn:str = hfplus(tuple([Context.route.dist_to_next(), 'float', '0']))
        nstr:str = route.get_waypoint(1) if route.dist_to_next() == 0 else f"{route.get_waypoint(1)} ({dn} ly)"
        self.waypoint_next_tt.set_text(nstr)

        primary:str = route.next_stop_display()
        detail:str = route.next_stop_station()
        wp:str = f"{primary} · {detail}" if detail else primary
        self._update_progbar()

        if route.jumps_remaining() > 0:
            # Show progress through route
            jumps:tuple = tuple([route.total_jumps() - route.jumps_remaining(), 'int', '-' if route.offset < 0 else '0'])
            tjumps:tuple = tuple([route.total_jumps(), 'int'])
            suffix:str = f" ({hfplus(jumps)}/{hfplus(tjumps)})"
            #wp = str_truncate(wp, length=int(self.waypoint_btn.cget('width')) - len(suffix), loc='middle') + suffix
            wp = str_truncate(wp, length=40 - len(suffix)) + suffix
        else:
            wp = str_truncate(wp, length=40)

        # Set an icon if appropriate, default to "regular" star
        image:tk.PhotoImage = self.star
        if route.is_neutron() == True:
            image = self.neutron_img

        if route.refuel() == True and not Context.route.fuel_full:
            image = self.fuel_img

        self.waypoint_btn.configure(text=wp, image=image, compound=tk.LEFT)
        self.waypoint_btn_tt.set_text(self._waypoint_tooltip(route))


    def _waypoint_tooltip(self, route:Route) -> str:
        """ Full next-waypoint detail for the waypoint button's tooltip """
        lines:list = route.next_stop_details()
        lines.append(tts['copy_to_clipboard'])

        return "\n".join(lines)


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
        self.waypoint_btn:th.Button = th.Button(fr1, text=Context.route.next_stop_display(), width=32,
                                              command=lambda: copy_to_clipboard(self.parent, Context.route.next_system()))
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
        self.clear_route_btn:th.Button = th.Button(fr2, text=btns["clear_route"], command=lambda: self.clear_route())
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
            case 'boxel':
                self._update_item("all", "boxel_ac", param)
            case _:
                # Ship selection
                galaxy_plotter = self.plotters.get('Galaxy')
                if not galaxy_plotter or not hasattr(galaxy_plotter, 'shipvar'):
                    return

                param = galaxy_plotter.shipvar.get() if param == "None" else param
                ship:Ship|None = Context.router.load_ship(param)
                if not ship:
                    return

                self._update_item("all", "cargo_entry", str(Context.router.cargo if ship.id == Context.router.ship_id else 0))
                self._update_item("all", "range_entry", str(ship.get_range(Context.router.cargo)))

                # Update neutron plotter multiplier if it exists
                neutron_plotter = self.plotters.get('Neutron')
                if neutron_plotter and hasattr(neutron_plotter, 'multiplier'):
                    neutron_plotter.multiplier.set(ship.supercharge_multiplier)
                return


    @catch_exceptions
    def ship_selected(self, *args) -> None:
        """ Update the galaxy plotter when the ship dropdown changes """
        galaxy_plotter = self.plotters.get('Galaxy')
        if not galaxy_plotter or not hasattr(galaxy_plotter, 'shipvar'):
            return
        ship_name:str = galaxy_plotter.shipvar.get()
        self.menu_callback('ship', ship_name)


    def set_entry(self, which:th.Autocompleter|th.Placeholder|th.Spinbox|None, value:str) -> None:
        """ Set an autocompleter, placeholder or spinbox entry's text and style """
        if which == None: return
        which.set_text(value, False)


    def switch_ship(self, ship:Ship) -> None:
        """ Update the plotter items when the ship changes """

        # Update all plotters with new range and multiplier
        self._update_item("all", "range_entry", str(ship.get_range(Context.router.cargo)))

        # Update neutron plotter multiplier if it exists
        neutron_plotter = self.plotters.get('Neutron')
        if neutron_plotter and hasattr(neutron_plotter, 'multiplier'):
            neutron_plotter.multiplier.set(ship.supercharge_multiplier)

        Context.router.route_params['Neutron']['supercharge_multiplier'] = ship.supercharge_multiplier
        Context.router.route_params['Neutron']['range'] = ship.range

        # Update range entry menus in all plot frames
        for dest in self.plot_frames.values():
            try:
                range_entry = dest.nametowidget("range_entry")
                if range_entry == None:
                    continue
                range_entry.set_menu(self._ship_dict())
            except Exception as e:
                pass

        # Update galaxy plotter ship dropdown if it exists
        galaxy_plotter = self.plotters.get('Galaxy')
        if galaxy_plotter and hasattr(galaxy_plotter, 'shipvar') and hasattr(galaxy_plotter, 'shipdd'):
            galaxy_plotter.shipvar.set(ship.name)
            galaxy_plotter.shipdd.set_menu(Context.router.shipnames())

    def update_cargo(self, cargo:int) -> None:
        """ Update the cargo entry when the cargo changes """

        galaxy_plotter = self.plotters.get('Galaxy')
        if not galaxy_plotter or not hasattr(galaxy_plotter, 'shipvar'):
            return

        if not Context.router.ship or galaxy_plotter.shipvar.get() != Context.router.ship.name:
            return

        self._update_item("all", "cargo_entry", str(cargo))
        self._update_item("all", "range_entry", str(Context.router.ship.get_range(cargo)))

    @catch_exceptions
    def _export_route(self) -> None:
        if Context.router == None or Context.router.export_route() == False:
            Debug.logger.error(f"Failed to export route")
            return

        self.show_frame('Route')


    def clear_route(self) -> None:
        """ Display a confirmation dialog for clearing the current route """
        clear:bool = confirmDialog.askyesno(Context.plugin_title, lbls["clear_route_yesno"])
        if not clear: return

        # Reverse the route
        if Context.router.dest == Context.router.system:
            self._update_item('all', 'source_ac', Context.router.dest)
            self._update_item('all', 'dest_ac', Context.router.src)

        self.show_frame(Context.router.last_plot)
        Context.router.clear_route()


    def cancel_plot(self) -> None:
        """ Cancel the plot planning and return to the default frame """
        Context.router.cancel_plot = True
        Context.router.clear_route()
        self.show_frame('Default')

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
        self.plotters['Neutron'].plot()

    @catch_exceptions
    def galaxy_plot(self) -> None:
        """ Perform a galaxy plotter plot """
        self.plotters['Galaxy'].plot()


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
            results:requests.Response = SESSION.get(SPANSH_SYSTEMS, params={'q': inp.strip()},
                                                     headers={'User-Agent': Context.plugin_useragent}, timeout=3)
        except:
            return [inp]
        return json.loads(results.content)

    @catch_exceptions
    def query_boxels(self, inp:str) -> list:
        """ Function called by Autocompleter """
        res:list = []
        try:
            results:requests.Response = SESSION.get(SPANSH_SYSTEMS, params={'q': inp.strip()},
                                                     headers={'User-Agent': Context.plugin_useragent}, timeout=3)
            for sys in json.loads(results.content):
                if re.match(r"^.+ [A-Za-z]{2}-[A-Za-z] [a-h]\d*-?", sys) and re.sub(r"[\-\d]+$", "", sys.strip()) not in res:
                    res.append(re.sub(r"[\-\d]+$", "", sys.strip()))
        except:
            return [inp]
        return res


    @catch_exceptions
    def query_station_names(self, inp:str) -> list:
        """ Function called by the Trade Planner's Autocompleter """
        try:
            results:requests.Response = SESSION.get(SPANSH_STATIONS_NAME, params={'q': inp.strip()},
                                                      headers={'User-Agent': Context.plugin_useragent}, timeout=3)
            return [f"{s['system']} / {s['name']}" for s in json.loads(results.content)]
        except:
            return [inp]


    @catch_exceptions
    def cooldown_complete(self) -> None:
        """ Show an informational messagebox indicating a carrier cooldown has completed. """
        Debug.logger.debug(f"Cooldown complete notification triggered.")

        self.update_progress()

        if self.parent == None or getattr(Context.prefs, 'cooldown_popup', False) == False: return
        message:str = NAME + "\n" + lbls['cooldown_complete']
        PopupNotice(message, 60000, self.parent)
