"""Spansh's engineering catalogue, a ship's current engineering, and the window for planning what to change."""
import json, time
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import Callable

from config import config  # type: ignore

from .constants import BOLD, DATA_DIR, NAME, SPANSH_ENGINEER_BLUEPRINTS, SPANSH_TIMEOUT, lbls, btns
from .context import Context
from .ship import Ship
from .utils import th
from .utils.debug import Debug, catch_exceptions
from .utils.treeviewplus import TreeviewPlus

NONE:str = '—'
GROUPS:tuple = ('hardpoint', 'utility', 'core', 'optional')  # outfitting's order, as lbls keys

class Catalogue:
    """Spansh's module types with their blueprints, grades and effects, and the engineers who apply them."""

    def __init__(self, data:dict) -> None:
        self.mods:dict = data['modules']
        self.engineers:list = data['engineers']
        self.types:dict = {i: t for t, m in self.mods.items() for i in m['items']}

    def kind(self, item:str) -> str|None:
        """The module type of a journal item name, if it can be engineered."""
        return self.types.get(item.lower())

    def key(self, kind:str, part:str, name:str|None) -> str|None:
        """The catalogue's key for a journal blueprint or effect name, which may be an older alias."""
        if not name: return None
        mod:dict = self.mods[kind]
        k:str = mod['aliases'].get(name.lower(), name.lower())
        return k if k in mod[part] else None

    def name(self, kind:str, part:str, key:str|None) -> str:
        """Display name for a blueprint or effect key."""
        return self.mods[kind][part][key]['name'] if key else NONE

    def region(self, region:str) -> list:
        """Names of the engineers in a region, or everywhere for an empty region."""
        return [e['name'] for e in self.engineers if not region or e['region'] == region]

    @staticmethod
    def path() -> Path:
        """Where the catalogue is cached."""
        return Path(Context.plugin_dir) / DATA_DIR / 'engineering.json'

    @staticmethod
    def fetch() -> None:
        """Download Spansh's catalogue if there's none cached or it's more than a week old."""
        file:Path = Catalogue.path()
        if file.exists() and file.stat().st_mtime > time.time() - 7 * 86400: return
        try:
            resp = Context.session.get(SPANSH_ENGINEER_BLUEPRINTS, headers={'User-Agent': Context.plugin_useragent}, timeout=SPANSH_TIMEOUT)
            resp.raise_for_status()
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(resp.text)
            Debug.logger.info("Downloaded the engineering catalogue")
        except Exception as e:
            Debug.logger.error("Couldn't fetch the engineering catalogue, exception info:", exc_info=e)

    @classmethod
    def load(cls) -> 'Catalogue|None':
        """The cached catalogue, or None if it hasn't been downloaded."""
        file:Path = cls.path()
        return cls(json.loads(file.read_text())['values']) if file.exists() else None

    def modules(self, ship:Ship) -> list:
        """The ship's engineerable modules with the blueprint, grade and effect each has now."""
        rows:list = []
        for m in ship.loadout.get('Modules', []):
            kind:str|None = self.kind(m.get('Item', ''))
            if not kind: continue
            eng:dict = m.get('Engineering', {})
            s:str = m['Slot'].lower()
            group:int = 1 if s.startswith('tinyhardpoint') else 0 if 'hardpoint' in s else 3 if s.startswith('slot') else 2
            rows.append({'slot': m['Slot'], 'group': group, 'item': m['Item'].lower(), 'kind': kind,
                         'blueprint': self.key(kind, 'blueprints', eng.get('BlueprintName')), 'grade': eng.get('Level', 0),
                         'effect': self.key(kind, 'effects', eng.get('ExperimentalEffect'))})
        return rows

    def request(self, ship:Ship, plan:list) -> list:
        """Spansh's blueprint entries for the plan's changes from the ship's current engineering."""
        now:dict = {r['slot']: r for r in self.modules(ship)}
        out:list = []
        for p in plan:
            c:dict|None = now.get(p['slot'])
            if c is None or c['item'] != p['item'] or not p['blueprint']: continue

            # A new blueprint clears the old effect, so it has to be applied again
            done:bool = c['blueprint'] == p['blueprint'] and c['grade'] >= p['grade']
            effect:bool = bool(p['effect']) and (p['effect'] != c['effect'] or c['blueprint'] != p['blueprint'])
            if done and not effect: continue

            e:dict = {'item': p['item'], 'blueprint': p['blueprint'], 'grade': p['grade']}
            if effect: e['effect'] = p['effect']
            if done: e['blueprint_done'] = True
            out.append(e)
        return out


class PlanWindow:
    """A sortable list of the ship's engineerable modules, with a form below it for the selected module's plan."""

    def __init__(self, root:tk.Misc, cat:Catalogue, ship:Ship, done:Callable[[], None]) -> None:
        self.cat:Catalogue = cat
        self.ship:Ship = ship
        self.done:Callable[[], None] = done
        self.mods:dict = {m['slot']: m for m in sorted(cat.modules(ship), key=lambda m: m['group'])}

        # Each module's planned (blueprint, grade, effect): its saved plan if still fitted, else what it has
        saved:dict = {p['slot']: p for p in Context.router.plans.get(ship.id, [])}
        self.plan:dict = {s: (p['blueprint'], p['grade'], p['effect']) if (p := saved.get(s)) and p['item'] == m['item']
                          else (m['blueprint'], m['grade'], m['effect']) for s, m in self.mods.items()}
        self.slot:str|None = None
        self.loading:bool = False
        self.bps:dict = {}
        self.fx:dict = {}

        self.window:tk.Toplevel = tk.Toplevel(root)
        self.window.title(f"{NAME} – {lbls['plan_title'].format(ship=ship.name)}")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        geometry:str|None = Context.router.window_geometries.get('plan')
        if geometry: self.window.geometry(geometry)
        scale:float = config.get_int('ui_scale') / 100.0

        outer:tk.Frame = tk.Frame(self.window)
        outer.pack(fill=tk.BOTH, expand=True)
        list_fr:tk.Frame = tk.Frame(outer)
        list_fr.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        ttk.Style().configure("My.Treeview.Heading", font=BOLD, background='lightgrey')
        cols:tuple = (('type', 'type', 'name', 80), ('module', 'module', 'name', 170), ('bp', 'blueprint', 'name', 200),
                      ('grade', 'grade', 'num', 50), ('effect', 'effect', 'name', 150), ('pbp', 'planned', 'name', 200),
                      ('pgrade', 'grade', 'num', 50), ('peffect', 'effect', 'name', 150))
        self.tree:TreeviewPlus = TreeviewPlus(list_fr, columns=[c[0] for c in cols], show='headings', style="My.Treeview",
                                              height=min(len(self.mods), 20))
        sb:ttk.Scrollbar = ttk.Scrollbar(list_fr, orient=tk.VERTICAL, command=self.tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for col, label, sort, w in cols:
            self.tree.heading(col, text=lbls[label], anchor=tk.W, sort_by=sort)
            self.tree.column(col, width=int(w * scale), anchor=tk.W)
        for s in self.mods: self.tree.insert('', 'end', iid=s, values=self._values(s))

        # TreeviewPlus only reports clicks on value columns; Tk's event also covers keyboard selection
        self.tree.bind('<<TreeviewSelect>>', self._selected)

        form:th.Frame = th.Frame(outer)
        form.pack(fill=tk.X, padx=5, pady=5)
        th.Separator(form).grid(row=0, column=0, columnspan=3, sticky=tk.EW, pady=(0, 10))
        self.name:th.Label = th.Label(form, text=lbls['choose_module'], font=BOLD)
        self.name.grid(row=1, column=0, columnspan=3, padx=5, sticky=tk.W)
        for col, h in enumerate(('blueprint', 'grade', 'effect')):
            th.Label(form, text=lbls[h]).grid(row=2, column=col, padx=5, pady=(5, 0), sticky=tk.W)

        self.bp, self.grade, self.effect = tk.StringVar(form), tk.IntVar(form, 1), tk.StringVar(form)
        self.bpdd:th.ComboBox = th.ComboBox(form, self.bp, values=[NONE], width=30)
        self.gscale:th.Scale = th.Scale(form, variable=self.grade, from_=1, to=5, resolution=1, orient=tk.HORIZONTAL, state=tk.DISABLED)
        self.fxdd:th.ComboBox = th.ComboBox(form, self.effect, values=[NONE], width=26)
        for col, dd in enumerate((self.bpdd, self.gscale, self.fxdd)): dd.grid(row=3, column=col, padx=5, pady=2, sticky=tk.SW)
        form.grid_columnconfigure(2, weight=1)

        # Done sits apart from the form, since each change applies as it's made
        th.Separator(form).grid(row=4, column=0, columnspan=3, sticky=tk.EW, pady=(15, 5))
        th.Button(form, text=btns['save_plan'], command=self.close).grid(row=5, column=0, columnspan=3, padx=5, pady=5, sticky=tk.E)

        self.bp.trace_add('write', self._bp_changed)
        self.grade.trace_add('write', self._edited)
        self.effect.trace_add('write', self._edited)


    def _cells(self, kind:str, bp:str|None, grade:int, effect:str|None) -> tuple:
        """Blueprint, grade and experimental effect as display text."""
        if not bp: return (NONE, '', '')
        return (self.cat.name(kind, 'blueprints', bp), str(grade), self.cat.name(kind, 'effects', effect) if effect else '')


    def _values(self, slot:str) -> tuple:
        """A module's row: its type and name, what it has, and the plan when that differs."""
        m:dict = self.mods[slot]
        now:tuple = (m['blueprint'], m['grade'], m['effect'])
        planned:tuple = ('', '', '') if self.plan[slot] == now else self._cells(m['kind'], *self.plan[slot])
        return (lbls[GROUPS[m['group']]], self.cat.mods[m['kind']]['name'], *self._cells(m['kind'], *now), *planned)


    def _grades(self, kind:str, key:str|None) -> list:
        """The grades a blueprint comes in, lowest first, spanned by the slider; no blueprint disables it."""
        grades:list = sorted(map(int, self.cat.mods[kind]['blueprints'][key]['grades'])) if key else []
        if grades: self.gscale.configure(from_=grades[0], to=grades[-1], state=tk.NORMAL)
        else: self.gscale.configure(state=tk.DISABLED)
        return grades


    @catch_exceptions
    def _selected(self, event:tk.Event) -> None:
        """Fill the form with the selected module's choices and plan."""
        sel:tuple = self.tree.selection()
        if not sel: return
        self.slot = sel[0]
        kind:str = self.mods[self.slot]['kind']
        bp, grade, effect = self.plan[self.slot]
        self.bps = {self.cat.name(kind, 'blueprints', k): k for k in [None, *self.cat.mods[kind]['blueprints']]}
        self.fx = {self.cat.name(kind, 'effects', k): k for k in [None, *self.cat.mods[kind]['effects']]}

        # The menus' own resets would otherwise write a half-loaded plan back
        self.loading = True
        self.name['text'] = self.cat.mods[kind]['name']
        self.bpdd.set_menu(list(self.bps))
        self.fxdd.set_menu(list(self.fx))
        grades:list = self._grades(kind, bp)
        self.bp.set(self.cat.name(kind, 'blueprints', bp))
        self.grade.set(grade if bp else grades[-1] if grades else 1)
        self.effect.set(self.cat.name(kind, 'effects', effect))
        self.loading = False


    @catch_exceptions
    def _bp_changed(self, *_) -> None:
        """A different blueprint offers different grades, so start it at its highest."""
        if self.loading or self.slot is None: return
        grades:list = self._grades(self.mods[self.slot]['kind'], self.bps.get(self.bp.get()))
        self.loading = True
        self.grade.set(grades[-1] if grades else 1)
        self.loading = False
        self._edited()


    @catch_exceptions
    def _edited(self, *_) -> None:
        """Keep the selected module's plan and row in step with the form."""
        if self.loading or self.slot is None: return
        key:str|None = self.bps.get(self.bp.get())
        grade:int = self.grade.get() if key else 0
        self.plan[self.slot] = (key, grade, self.fx.get(self.effect.get()) if key else None)
        self.tree.item(self.slot, values=self._values(self.slot))


    @catch_exceptions
    def close(self) -> None:
        """Save the plan for the ship, then close."""
        Context.router.plans[self.ship.id] = [{'slot': s, 'item': self.mods[s]['item'], 'blueprint': bp, 'grade': g, 'effect': fx}
                                              for s, (bp, g, fx) in self.plan.items()]
        Context.router.window_geometries['plan'] = self.window.winfo_geometry()
        Context.router.save()
        self.window.destroy()
        self.done()
