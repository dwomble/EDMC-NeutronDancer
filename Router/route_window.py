import tkinter as tk
from tkinter import ttk

from config import config  # type: ignore

from utils.debug import Debug, catch_exceptions
from utils.misc import hfplus
from utils.treeviewplus import TreeviewPlus

from .constants import FONT, BOLD, NAME, HEADER_TYPES, lbls
from .route import Route

class RouteWindow:
    """
    Display of the current route in a separate window with overview and details
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

        self._initialized = True


    @catch_exceptions
    def show(self, route:Route) -> None:
        """ Show our window """

        if self.window is not None and self.window.winfo_exists():
            self.window.destroy()
            self.window = None

        if route.hdrs == [] or route.route == []:
            return

        scale = config.get_int('ui_scale') / 100.00

        self.window = tk.Toplevel(self.root)
        self.window.title(f"{NAME} – {lbls['route']}")
        self.window.geometry(f"{int(600*scale)}x{int(300*scale)}")

        frame = tk.Frame(self.window, borderwidth=2)
        frame.pack(fill=tk.BOTH, expand=True)

        self._summary(frame, route, scale)
        w:int = self._table(frame, route, scale)

        self.window.geometry(f"{int(w)}x{int(300*scale)}")


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
            txt:str = lbls['jumps'] if route.jc != None else lbls['waypoints']
            ttl:ttk.Label = ttk.Label(frm, text=txt.title(), font=BOLD)
            ttl.pack(side=tk.LEFT, padx=5)

            jumps:tuple = tuple([route.total_jumps() - route.jumps_remaining(), 'int', '0'])
            tjumps:tuple = tuple([route.total_jumps(), 'int'])
            jstr:str = f"{hfplus(jumps)} / {hfplus(tjumps)}"
            lbl:ttk.Label = ttk.Label(frm, text=jstr, font=FONT)
            lbl.pack(side=tk.LEFT, padx=5)

        # Distance
        if route.total_dist() > 0:
            ttl = ttk.Label(frm, text=f"{lbls['distance'].title()}", font=BOLD)
            ttl.pack(side=tk.LEFT, padx=5)

            dist:tuple = tuple([route.total_dist() - route.dist_remaining(), 'float', '0', ''])
            dstr:str = f"{hfplus(dist)} / {hfplus(route.total_dist())} Ly"
            lbl = ttk.Label(frm, text=dstr, font=FONT)
            lbl.pack(side=tk.LEFT, padx=5)

        # Speed
        if route.jumps_per_hour() > -1:
            ttl = ttk.Label(frm, text=f"{lbls['speed'].title()}", font=BOLD)
            ttl.pack(side=tk.LEFT, padx=5)

            jph:tuple = tuple([route.jumps_per_hour(), 'int', '-', lbls['jumps_per_hour']])
            dph:tuple = tuple([route.dist_per_hour(), 'float', '-', lbls['dist_per_hour']])
            dstr:str = f"{hfplus(jph)} / {hfplus(dph)}"
            lbl = ttk.Label(frm, text=dstr, font=FONT)
            lbl.pack(side=tk.LEFT, padx=5)


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

        widths:list = [len(w)+2 for w in route.hdrs]
        for r in route.route:
            widths = [max(widths[i], len(str(w))+1) for i, w in enumerate(r)]

        for i, hdr in enumerate(route.hdrs):
            tree.heading(hdr, text=hdr, anchor=tk.W if i == 0 else tk.E)
            tree.column(hdr, stretch=tk.NO, width=int(widths[i]*8*scale), anchor=tk.W if i == 0 else tk.E)

        for i, row in enumerate(route.route):
            tmp:list[tuple] = [ tuple([val] + HEADER_TYPES.get(route.hdrs[col], ["-", ""])) for col, val in enumerate(row)]
            r:str = tree.insert("", 'end', values=[hfplus(c) for c in tmp])
            if i > 0 and i == route.offset:
                tree.selection_set(r)

        return sum([int(widths[i]*8*scale) for i in range(len(widths))]) + 30
