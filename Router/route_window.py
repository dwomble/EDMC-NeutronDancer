import tkinter as tk
from tkinter import ttk

from config import config  # type: ignore

from .utils.debug import Debug, catch_exceptions
from .utils.misc import singleton, hfplus
from .utils.treeviewplus import TreeviewPlus

from .constants import FONT, BOLD, NAME, HEADER_TYPES, lbls
from .route import Route
from .context import Context


LEFT_ALIGN:list = ['System Name', 'System', 'Body Type', 'Station Name', 'Station Type', 'Station Class', 'Station Faction',
                   'Station State', 'Station Government', 'Station Economy', 'Station Secondary Economy', 'Commodity',
                   'Species']

@singleton
class RouteWindow:
    """
    Display of the current route in a separate window with overview and details
    """

    def __init__(self, root:tk.Tk|tk.Toplevel) -> None:
        self.root:tk.Tk|tk.Toplevel = root
        self.window:tk.Toplevel|None = None


    @catch_exceptions
    def show(self, route:Route) -> None:
        """ Show our window """

        if self.window is not None and self.window.winfo_exists():
            self.close()
            self.window = None

        if route.hdrs == [] or route.route == []:
            return

        scale:float = config.get_int('ui_scale') / 100.00

        self.window = tk.Toplevel(self.root)
        self.window.title(f"{NAME} – {lbls['route']}")
        geometry:str = Context.router.window_geometries.get('route', f"{int(600*scale)}x{int(300*scale)}")

        self.window.geometry(geometry)
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        frame = tk.Frame(self.window, borderwidth=2)
        frame.pack(fill=tk.BOTH, expand=True)

        self._summary(frame, route, scale)
        w:int = self._table(frame, route, scale)

        # Make sure it's wide enough
        if self.window.winfo_width() < int(w) and self.window.winfo_height() > 1:
            self.window.geometry(f"{int(w)}x{self.window.winfo_height()}")


    def close(self) -> None:
        """ On close save our geometry """
        if self.window == None: return
        Context.router.window_geometries['route'] = self.window.winfo_geometry()
        self.window.destroy()
        return

    def _jump_summary(self, parent:tk.Frame, route:Route) -> None:
        """ Display a summary of the next jump """
        txt:str = lbls['jumps'] if route.jc != None else lbls['waypoints']
        ttl:ttk.Label = ttk.Label(parent, text=txt.title(), font=BOLD)
        ttl.pack(side=tk.LEFT, padx=5)

        jumps:tuple = tuple([route.total_jumps() - route.jumps_remaining(), 'int', '0'])
        tjumps:tuple = tuple([route.total_jumps(), 'int'])
        jstr:str = f"{hfplus(jumps)} / {hfplus(tjumps)}"
        lbl:ttk.Label = ttk.Label(parent, text=jstr, font=FONT)
        lbl.pack(side=tk.LEFT, padx=5)

    def _speed_summary(self, parent:tk.Frame, route:Route) -> None:
        """ Display a summary of the speed """
        ttl:ttk.Label = ttk.Label(parent, text=f"{lbls['speed'].title()}", font=BOLD)
        ttl.pack(side=tk.LEFT, padx=5)

        jph:tuple = tuple([route.jumps_per_hour(), 'int', '-', lbls['jumps_per_hour']])
        dph:tuple = tuple([route.dist_per_hour(), 'float', '-', lbls['dist_per_hour']])
        dstr:str = f"{hfplus(jph)} / {hfplus(dph)}"
        lbl:ttk.Label = ttk.Label(parent, text=dstr, font=FONT)
        lbl.pack(side=tk.LEFT, padx=5)

    def _distance_summary(self, parent:tk.Frame, route:Route) -> None:
        """ Display a summary of the distance """
        ttl:ttk.Label = ttk.Label(parent, text=f"{lbls['distance'].title()}", font=BOLD)
        ttl.pack(side=tk.LEFT, padx=5)

        dist:tuple = tuple([route.total_dist() - route.dist_remaining(), 'float', '0', ''])
        dstr:str = f"{hfplus(dist)} / {hfplus(route.total_dist())} ly"
        lbl:ttk.Label = ttk.Label(parent, text=dstr, font=FONT)
        lbl.pack(side=tk.LEFT, padx=5)

    def _value_summary(self, parent:tk.Frame, route:Route) -> None:
        """ Display a summary of the value """
        rv = route.route_value()
        if rv is None: return

        label, header = rv
        ttl:ttk.Label = ttk.Label(parent, text=label.title(), font=BOLD)
        ttl.pack(side=tk.LEFT, padx=5)

        so_far:tuple = tuple([route.sum_value(header, through=route.offset+1), 'float', '0', ' Cr'])
        total:tuple = tuple([route.sum_value(header, through=len(route.route)), 'float', '0', ' Cr'])
        vstr:str = f"{hfplus(so_far)} / {hfplus(total)}"
        lbl:ttk.Label = ttk.Label(parent, text=vstr, font=FONT)
        lbl.pack(side=tk.LEFT, padx=5)

    def _summary(self, parent:tk.Frame, route:Route, scale:float) -> None:
        """ Display a summary of the route """
        frm:tk.Frame = tk.Frame(parent)
        frm.pack(fill=tk.X, padx=5, pady=5)

        # Progress
        ttl:ttk.Label = ttk.Label(frm, text=f"{lbls['progress'].title()}", font=BOLD)
        ttl.pack(side=tk.LEFT, padx=5)

        pfl:float = route.perc_dist_rem() if route.dc != None else route.perc_jumps_rem()
        lbl:ttk.Label = ttk.Label(frm, text=f"{int(pfl)}%", font=FONT)
        lbl.pack(side=tk.LEFT, padx=5)

        # Jumps
        if route.total_jumps() > 0:
            self._jump_summary(frm, route)

        # Distance
        if route.total_dist() > 0:
            self._distance_summary(frm, route)

        # Value (Trade profit, Road to Riches/Exobiology scan/mapping/landmark value) --
        # blank for route types with no earned-value column (Neutron/Galaxy/Tourist/FleetCarrier)
        rv = route.route_value()
        if rv is not None:
            self._value_summary(frm, route)

        # Speed
        if route.jumps_per_hour() > -1:
            self._speed_summary(frm, route)

    @catch_exceptions
    def _table(self, parent:tk.Frame, route:Route, scale:float) -> int:
        """ Display the route table and return the width required """

        # On click copy the first column to the clipboard
        @catch_exceptions
        def _selected(values, column, tr:TreeviewPlus, iid:str) -> None:
            frm.clipboard_clear()
            frm.clipboard_append(values[0])

        frm:tk.Frame = tk.Frame(parent)
        frm.pack(fill=tk.BOTH, expand=tk.YES, padx=5, pady=5)

        style:ttk.Style = ttk.Style()
        style.configure("My.Treeview.Heading", font=BOLD, background='lightgrey')

        tree:ttk.Treeview = TreeviewPlus(frm, columns=route.hdrs, callback=_selected, show="headings", style="My.Treeview")
        sb:ttk.Scrollbar = ttk.Scrollbar(frm, orient=tk.VERTICAL, command=tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Do some route preprocessing to make sure the data is in a displayable format
        if 'Body' in route.hdrs: # Strip the system name from the body name column
            for i, row in enumerate(route.route):
                row[route.hdrs.index('Body')] = row[route.hdrs.index('Body')].replace(row[route.sc], '')

        # Calculate column widths based on header and data lengths, with some padding
        widths:list = [len(w)+4 for w in route.hdrs]
        for r in route.route:
            widths = [max(widths[i], len(str(w))+2) for i, w in enumerate(r)]

        for i, hdr in enumerate(route.hdrs):
            tree.heading(hdr, text=hdr, anchor=tk.W if hdr in LEFT_ALIGN else tk.E)
            tree.column(hdr, stretch=tk.NO, width=int(widths[i]*6.5*scale), anchor=tk.W if hdr in LEFT_ALIGN else tk.E)

        for i, row in enumerate(route.route):
            tmp:list[tuple] = [ tuple([val] + HEADER_TYPES.get(route.hdrs[col], ["-", ""])) for col, val in enumerate(row)]
            r:str = tree.insert("", 'end', values=[hfplus(c) for c in tmp])
            if i > 0 and i == route.offset:
                tree.selection_set(r)

        return sum([int(widths[i]*6.5*scale) for i in range(len(widths))]) + 30
