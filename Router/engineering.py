"""
Support classes for the Spansh engineering router.

Spansh's engineering catalogue, a ship's current engineering
The popup window for planning the ship's engineering changes.
"""
import json, re, time
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import Callable

from config import config  # type: ignore

from .utils.debug import Debug, catch_exceptions
from .utils.treeviewplus import TreeviewPlus

from .constants import BOLD, DATA_DIR, NAME, SPANSH_TIMEOUT, SOURCES, EFFECTS, MATERIALS, lbls, btns
from .context import Context
from .ship import Ship

NONE:str = ''
GROUPS:tuple = ('hardpoint', 'utility', 'core', 'optional')  # outfitting's order, as lbls keys

def short(need:dict) -> dict:
    """ The needed materials you hold too few of, with how many you have. """
    have:dict = {n: Context.router.materials.get(MATERIALS.get(n, re.sub(r'[^a-z0-9]', '', n.lower())), 0) for n in need}
    return {n: h for n, h in have.items() if h < need[n]}


def trim(module:str, name:str) -> str:
    """ A blueprint or effect name without the module's name or initials. """
    words:list = module.split()
    pats:list = [re.escape(module)] + ([''.join(w[0] for w in words)] if len(words) > 1 else [])
    short:str = re.sub(r'\s+', ' ', re.sub(r'\b(' + '|'.join(pats) + r')\b', '', name, flags=re.I)).strip(' -')
    return short or name


class Catalogue:
    """ Spansh's module types with their blueprints, grades and effects, and the engineers who apply them. """

    def __init__(self, data:dict, blueprints:dict = {}, specials:dict = {}) -> None:
        self.mods:dict = data['modules']
        self.engineers:list = data['engineers']
        self.types:dict = {i: t for t, m in self.mods.items() for i in m['items']}
        self.grades:dict = {k.lower(): b['grades'] for k, b in blueprints.items()}
        self.specials:dict = specials

    def kind(self, item:str) -> str|None:
        """ The module type of a journal item name, if it can be engineered. """
        return self.types.get(item.lower())

    def key(self, kind:str, part:str, name:str|None) -> str|None:
        """ The catalogue's key for a journal blueprint or effect name, which may be an older alias. """
        if not name: return None
        mod:dict = self.mods[kind]
        k:str = mod['aliases'].get(name.lower(), name.lower())
        return k if k in mod[part] else None

    def name(self, kind:str, part:str, key:str|None) -> str:
        """ Display name for a blueprint or effect key. """
        return trim(self.mods[kind]['name'], self.mods[kind][part][key]['name']) if key else NONE

    def region(self, region:str) -> list:
        """ Names of the engineers in a region, or everywhere for an empty region. """
        return [e['name'] for e in self.engineers if not region or e['region'] == region]

    @staticmethod
    def path(name:str = 'engineering.json') -> Path:
        """ Where a catalogue file is cached. """
        return Path(Context.plugin_dir) / DATA_DIR / name

    @staticmethod
    def fetch() -> None:
        """ Download Spansh's catalogue and Coriolis's costs where none are cached or they're out of date. """
        for name, (url, days) in SOURCES.items():
            file:Path = Catalogue.path(name)
            if file.exists() and file.stat().st_mtime > time.time() - days * 86400: continue
            try:
                resp = Context.session.get(url, headers={'User-Agent': Context.plugin_useragent}, timeout=SPANSH_TIMEOUT)
                resp.raise_for_status()
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(resp.text)
                Debug.logger.info(f"Downloaded {name}")
            except Exception as e:
                Debug.logger.error(f"Couldn't fetch {name}, exception info:", exc_info=e)

    @classmethod
    def load(cls) -> 'Catalogue|None':
        """ The cached catalogue, or None if it hasn't been downloaded; costs are left out if they haven't been. """
        file:Path = cls.path()
        if not file.exists():
            Debug.logger.warning("Engineering catalogue not found at %s", file)
            cls.fetch()
        if not file.exists(): return None
        names:tuple = ('coriolis_blueprints.json', 'coriolis_specials.json')
        extra:list = [json.loads(p.read_text()) if (p := cls.path(n)).exists() else {} for n in names]
        return cls(json.loads(file.read_text())['values'], *extra)

    def cost(self, now:tuple, plan:tuple) -> dict|None:
        """ Materials to take a module from its current (blueprint, grade, effect) to the plan, or None if unknown. """
        bp, grade, effect = plan
        if not bp: return {}
        grades:dict|None = self.grades.get(bp)
        if grades is None: return None

        # Grade N is taken to need N rolls, which is typical with full engineer reputation
        need:dict = {}
        for g in range(now[1] + 1 if now[0] == bp else 1, grade + 1):
            for m, n in grades.get(str(g), {}).get('components', {}).items(): need[m] = need.get(m, 0) + n * g
        if effect and (effect != now[2] or now[0] != bp):
            for m, n in self.specials.get(effect, {}).get('components', {}).items(): need[m] = need.get(m, 0) + n
        return need

    def effects(self, bp:str|None, grade:int) -> list:
        """ What a blueprint grade's rolls change. """
        lines:list = []
        for k, v in (self.grades.get(bp, {}).get(str(grade), {}).get('features', {}) if bp else {}).items():
            if not isinstance(v, list) or v == [0, 0]: continue

            # Coriolis gives fractions for all but these few raw values
            raw:bool = k in ('burst', 'burstrof', 'fallofffromrange', 'jitter')
            vals:list = [f"{x:g}" if raw else f"{x * 100:+.0f}%" for x in v]
            lines.append(f"{EFFECTS.get(k, k)} {vals[0] if vals[0] == vals[1] else f'{vals[0]} to {vals[1]}'}")
        return lines

    def modules(self, ship:Ship) -> list:
        """ The ship's engineerable modules with the blueprint, grade and effect each has now. """
        rows:list = []
        for m in ship.loadout.get('Modules', []):
            kind:str|None = self.kind(m.get('Item', ''))
            if not kind: continue
            eng:dict = m.get('Engineering', {})
            s:str = m['Slot'].lower()
            group:int = 1 if s.startswith('tinyhardpoint') else 0 if 'hardpoint' in s else 3 if s.startswith('slot') else 2
            raw:str = eng.get('BlueprintName', '')

            # EngineerID 399999 marks a module bought pre-engineered, which can't be changed
            rows.append({'slot': m['Slot'], 'group': group, 'item': m['Item'].lower(), 'kind': kind,
                         'blueprint': self.key(kind, 'blueprints', raw), 'grade': eng.get('Level', 0),
                         'effect': self.key(kind, 'effects', eng.get('ExperimentalEffect')),
                         'fixed': eng.get('EngineerID') == 399999, 'raw': re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', raw.split('_', 1)[-1])})
        return rows

    def offered(self, kind:str, allowed:set) -> bool:
        """ Whether any of the allowed engineers apply blueprints to the module type. """
        return any(n in allowed for b in self.mods[kind]['blueprints'].values() for e in b['grades'].values() for n in e)

    def total(self, ship:Ship, plan:list, allowed:set) -> tuple:
        """ Materials for the plan's changes the allowed engineers can make, and how many of those have unknown costs. """
        now:dict = {r['slot']: r for r in self.modules(ship)}
        need:dict = {}
        unknown:int = 0
        for p in plan:
            c:dict|None = now.get(p['slot'])
            if c is None or c['item'] != p['item'] or c['fixed'] or not self.offered(c['kind'], allowed): continue
            cost:dict|None = self.cost((c['blueprint'], c['grade'], c['effect']), (p['blueprint'], p['grade'], p['effect']))
            if cost is None: unknown += 1
            for m, n in (cost or {}).items(): need[m] = need.get(m, 0) + n
        return need, unknown

    def request(self, ship:Ship, plan:list, allowed:set) -> list:
        """ Spansh's blueprint entries for the plan's changes that the allowed engineers can make. """
        now:dict = {r['slot']: r for r in self.modules(ship)}
        out:list = []
        for p in plan:
            c:dict|None = now.get(p['slot'])
            if c is None or c['item'] != p['item'] or c['fixed'] or not p['blueprint'] or not self.offered(c['kind'], allowed): continue

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
    """ A sortable list of the ship's engineerable modules, with a form below it for the selected module's plan. """

    def __init__(self, root:tk.Misc, cat:Catalogue, ship:Ship, allowed:set, done:Callable[[], None]) -> None:
        self.cat:Catalogue = cat
        self.allowed:set = allowed
        self.ship:Ship = ship
        self.done:Callable[[], None] = done
        mods:list = sorted(cat.modules(ship), key=lambda m: m['group'])
        self.mods:dict = {m['slot']: m for m in mods if m['fixed'] or cat.offered(m['kind'], allowed)}

        # Each module's planned (blueprint, grade, effect): its saved plan if still fitted, else what it has
        saved:dict = {p['slot']: p for p in Context.router.plans.get(ship.id, [])}
        self.plan:dict = {s: (p['blueprint'], p['grade'], p['effect']) if (p := saved.get(s)) and p['item'] == m['item'] and not m['fixed']
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

        outer:ttk.Frame = ttk.Frame(self.window)
        outer.pack(fill=tk.BOTH, expand=True)
        list_fr:tk.Frame = tk.Frame(outer)
        list_fr.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        ttk.Style().configure("My.Treeview.Heading", font=BOLD, background='lightgrey')
        cols:tuple = (('type', 'type', 'name', 80), ('module', 'module', 'name', 170), ('bp', 'blueprint', 'name', 200),
                      ('grade', 'grade', 'num', 50), ('effect', 'effect', 'name', 150), ('pbp', 'planned', 'name', 200),
                      ('pgrade', 'grade', 'num', 50), ('peffect', 'effect', 'name', 150), ('mats', 'materials', 'name', 70))
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

        form:ttk.Frame = ttk.Frame(outer)
        form.pack(fill=tk.X, padx=5, pady=5)
        ttk.Separator(form).grid(row=0, column=0, columnspan=6, sticky=tk.EW, pady=(0, 10))
        self.name:ttk.Label = ttk.Label(form, text=lbls['full_plan'], font=BOLD)
        self.name.grid(row=1, column=0, columnspan=6, padx=5, sticky=tk.W)

        # The choices line up with each other at the top, however long the lists beside them grow
        ctl:ttk.Frame = ttk.Frame(form)
        ctl.grid(row=2, column=0, rowspan=2, sticky=tk.NW)
        self.bp, self.grade, self.effect = tk.StringVar(form), tk.IntVar(form, 1), tk.StringVar(form)
        self.bpdd:ttk.Combobox = ttk.Combobox(ctl, textvariable=self.bp, values=[NONE], state='readonly', width=30)
        self.gscale:tk.Scale = tk.Scale(ctl, variable=self.grade, from_=1, to=5, resolution=1, orient=tk.HORIZONTAL, state=tk.DISABLED)
        self.fxdd:ttk.Combobox = ttk.Combobox(ctl, textvariable=self.effect, values=[NONE], state='readonly', width=30)
        for col, h in enumerate(('bp_and_fx', 'grade')):
            ttk.Label(ctl, text=lbls[h]).grid(row=0, column=col, padx=5, pady=(5, 0), sticky=tk.W)
        for row, col, dd in ((1, 0, self.bpdd), (1, 1, self.gscale), (2, 0, self.fxdd)):
            dd.grid(row=row, column=col, padx=5, pady=2, sticky=tk.SW)

        heads:list = [ttk.Label(form, text=lbls[h]) for h in ('effects', 'description', 'engineers', 'materials')]
        for col, h in enumerate(heads, 1): h.grid(row=2, column=col, columnspan=2 if col == 4 else 1, padx=5, pady=(5, 0), sticky=tk.W)
        self.fxl:ttk.Label = ttk.Label(form, text='', justify=tk.LEFT)
        self.desc:ttk.Label = ttk.Label(form, text='', justify=tk.LEFT, wraplength=int(220 * scale))
        self.who:ttk.Label = ttk.Label(form, text='', justify=tk.LEFT)
        self.mats:tuple = (ttk.Label(form, text='', justify=tk.LEFT), ttk.Label(form, text='', justify=tk.LEFT))
        for col, lbl in enumerate((self.fxl, self.desc, self.who, *self.mats), 1): lbl.grid(row=3, column=col, padx=5, pady=2, sticky=tk.NW)
        form.grid_columnconfigure(5, weight=1)
        self.details:list = [ctl, *heads[:2], self.desc, self.fxl]  # Hidden for the whole plan

        # Done sits apart from the form, since each change applies as it's made
        ttk.Separator(form).grid(row=4, column=0, columnspan=6, sticky=tk.EW, pady=(15, 5))
        bar:ttk.Frame = ttk.Frame(form)
        bar.grid(row=5, column=0, columnspan=6, sticky=tk.E)
        ttk.Button(bar, text=lbls['full_plan'], command=lambda: self.tree.selection_set(())).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(bar, text=btns['save_plan'], command=self.close).pack(side=tk.LEFT, padx=5, pady=5)

        self.bp.trace_add('write', self._bp_changed)
        self.grade.trace_add('write', self._edited)
        self.effect.trace_add('write', self._edited)
        self._selected()


    def _cells(self, kind:str, bp:str|None, grade:int, effect:str|None) -> tuple:
        """ Blueprint, grade and experimental effect as display text. """
        if not bp: return (NONE, '', '')
        return (self.cat.name(kind, 'blueprints', bp), str(grade), self.cat.name(kind, 'effects', effect) if effect else '')


    def _values(self, slot:str) -> tuple:
        """ A module's row: its type and name, what it has, and the plan when that differs. """
        m:dict = self.mods[slot]
        now:tuple = (m['blueprint'], m['grade'], m['effect'])
        cells:tuple = self._cells(m['kind'], *now) if m['blueprint'] or not m['raw'] else (m['raw'], str(m['grade']), '')
        planned:tuple = ('', '', '') if self.plan[slot] == now else self._cells(m['kind'], *self.plan[slot])
        if m['fixed']: planned = (lbls['pre_engineered'], '', '')
        need:dict|None = {} if m['fixed'] else self.cat.cost(now, self.plan[slot])
        mats:str = '?' if need is None else '' if not need else '✗' if short(need) else '✓'
        return (lbls[GROUPS[m['group']]], self.cat.mods[m['kind']]['name'], *cells, *planned, mats)


    def _who(self, names:list) -> list:
        """ Which of the named engineers can be visited. """
        return [n for n in names if n in self.allowed]


    def _grades(self, kind:str, key:str|None) -> list:
        """ The blueprint's grades on offer plus any already planned, lowest first, spanned by the slider. """
        bp, grade, _ = self.plan[self.slot] if self.slot else (None, 0, None)
        offered:dict = self.cat.mods[kind]['blueprints'][key]['grades'] if key else {}
        grades:list = sorted({int(g) for g, e in offered.items() if self._who(e)} | ({grade} if key == bp and grade else set()))
        if grades: self.gscale.configure(from_=grades[0], to=grades[-1], state=tk.NORMAL)
        else: self.gscale.configure(state=tk.DISABLED)
        return grades


    @catch_exceptions
    def _selected(self, event:tk.Event|None = None) -> None:
        """ Fill the form with the selected module's choices and plan, or the whole plan's materials if none is selected. """
        sel:tuple = self.tree.selection()
        self.slot = sel[0] if sel else None
        for w in self.details: (w.grid if self.slot else w.grid_remove)()
        fixed:bool = self.slot is None or self.mods[self.slot]['fixed']
        for dd in (self.bpdd, self.fxdd): dd.configure(state=tk.DISABLED if fixed else 'readonly')
        if fixed:
            self.loading = True
            name:str = self.cat.mods[self.mods[self.slot]['kind']]['name'] if self.slot else ''
            self.name['text'] = f"{name} – {lbls['pre_engineered']}" if self.slot else lbls['full_plan']
            self.bp.set('')
            self.effect.set('')
            self.gscale.configure(state=tk.DISABLED)
            self.who['text'] = ''
            self.fxl['text'] = ''
            self.desc['text'] = ''
            self.loading = False
            if self.slot is None: self._engineers()
            self._materials()
            return

        if self.slot is None: return
        kind:str = self.mods[self.slot]['kind']
        bp, grade, effect = self.plan[self.slot]
        mod:dict = self.cat.mods[kind]

        # Only what the region's engineers offer, though the plan's own choices stay listed
        bps:list = [k for k, b in mod['blueprints'].items() if k == bp or any(map(self._who, b['grades'].values()))]
        fx:list = [k for k, f in mod['effects'].items() if k == effect or self._who(f['engineers'])]
        self.bps = {self.cat.name(kind, 'blueprints', k): k for k in [None, *bps]}
        self.fx = {self.cat.name(kind, 'effects', k): k for k in [None, *fx]}

        # Each variable's trace would otherwise write a half-loaded plan back
        self.loading = True
        self.name['text'] = self.cat.mods[kind]['name']
        self.bpdd.configure(values=list(self.bps))
        self.fxdd.configure(values=list(self.fx))
        grades:list = self._grades(kind, bp)
        self.bp.set(self.cat.name(kind, 'blueprints', bp))
        self.grade.set(grade if bp else grades[-1] if grades else 1)
        self.effect.set(self.cat.name(kind, 'effects', effect))
        self.loading = False
        self._engineers()
        self._materials()


    def _engineers(self) -> None:
        """ List who offers the selected module's planned blueprint grade, and what the blueprint and experimental do. """
        if self.slot is None:
            self._plan_engineers()
            return
        bp, grade, _ = self.plan[self.slot]
        offered:list = self.cat.mods[self.mods[self.slot]['kind']]['blueprints'][bp]['grades'].get(str(grade), []) if bp else []
        self.who['text'] = '\n'.join(self._who(offered)) or (NONE if bp else '')
        self.fxl['text'] = '\n'.join(self.cat.effects(bp, grade))
        self.desc['text'] = self.cat.specials.get(self.plan[self.slot][2], {}).get('description', '')


    def _plan_engineers(self) -> None:
        """ List who can make any of the plan's changes, with how many of them, most first. """
        count:dict = {}
        for s, m in self.mods.items():
            now:tuple = (m['blueprint'], m['grade'], m['effect'])
            bp, grade, _ = self.plan[s]
            if m['fixed'] or not bp or self.plan[s] == now or self.cat.cost(now, self.plan[s]) == {}: continue
            for e in self._who(self.cat.mods[m['kind']]['blueprints'][bp]['grades'].get(str(grade), [])): count[e] = count.get(e, 0) + 1
        self.who['text'] = '\n'.join(f"{e} ({n})" for e, n in sorted(count.items(), key=lambda x: (-x[1], x[0])))


    def _materials(self) -> None:
        """ List the materials the selected module's plan, or the whole plan, needs, noting any you're short of. """
        need:dict|None
        unknown:int = 0
        if self.slot is None: need, unknown = self.cat.total(self.ship, self._entries(), self.allowed)
        elif self.mods[self.slot]['fixed']: need = {}
        else:
            m:dict = self.mods[self.slot]
            need = self.cat.cost((m['blueprint'], m['grade'], m['effect']), self.plan[self.slot])
        if need is None:
            self.mats[0]['text'] = lbls['cost_unknown']
            self.mats[1]['text'] = ''
            return

        lacking:dict = short(need)
        lines:list = [f"{n} {name}" + (f" ({lbls['have'].format(n=lacking[name])})" if name in lacking else '')
                      for name, n in sorted(need.items())]
        if unknown: lines.append(lbls['unknown_count'].format(n=unknown))
        half:int = (len(lines) + 1) // 2
        self.mats[0]['text'] = '\n'.join(lines[:half])
        self.mats[1]['text'] = '\n'.join(lines[half:])


    @catch_exceptions
    def _bp_changed(self, *_) -> None:
        """ A different blueprint offers different grades, so start it at its highest. """
        if self.loading or self.slot is None: return
        grades:list = self._grades(self.mods[self.slot]['kind'], self.bps.get(self.bp.get()))
        self.loading = True
        self.grade.set(grades[-1] if grades else 1)
        self.loading = False
        self._edited()


    @catch_exceptions
    def _edited(self, *_) -> None:
        """ Keep the selected module's plan and row in step with the form. """
        if self.loading or self.slot is None: return
        key:str|None = self.bps.get(self.bp.get())
        grade:int = self.grade.get() if key else 0
        self.plan[self.slot] = (key, grade, self.fx.get(self.effect.get()) if key else None)
        self.tree.item(self.slot, values=self._values(self.slot))
        self._engineers()
        self._materials()


    def _entries(self) -> list:
        """ The shown modules' plans as saved plan entries. """
        return [{'slot': s, 'item': self.mods[s]['item'], 'blueprint': bp, 'grade': g, 'effect': fx}
                for s, (bp, g, fx) in self.plan.items()]


    @catch_exceptions
    def close(self) -> None:
        """ Save the plan for the ship, keeping plans for modules hidden by the region, then close. """
        hidden:list = [p for p in Context.router.plans.get(self.ship.id, []) if p['slot'] not in self.mods]
        Context.router.plans[self.ship.id] = hidden + self._entries()
        Context.router.window_geometries['plan'] = self.window.winfo_geometry()
        Context.router.save()
        self.window.destroy()
        self.done()
