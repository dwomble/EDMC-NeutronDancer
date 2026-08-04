# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Navl's Neutron Dancer is a plugin for [EDMC (Elite Dangerous Market Connector)](https://github.com/EDCD/EDMarketConnector) — not a standalone application. It plots Spansh (spansh.co.uk) routes (Neutron, Galaxy, Road to Riches, Trade, Tourist, Fleet Carrier, etc.) directly from within EDMC, tracks progress, and copies the next waypoint to the clipboard. See `AGENTS.md` for release/CI workflow details and `README.md` for user-facing feature documentation.

Because it's a plugin, none of this code runs standalone — it's loaded by EDMC via `load.py`'s exported hook functions, and imports EDMC-provided modules (`config`, `myNotebook`, `edmc_data`) that don't exist in this repo. `tests/edmc/` stubs these out so the plugin can be exercised in isolation under pytest.

## Commands

Use the repo's `.venv`, not a bare `pytest`/`python` on PATH:

```bash
# Fast suite (mocked network, no live Spansh calls) -- run this before anything slower
.venv/bin/python -m pytest tests/test_suite.py -m "not slow and not manual_only" -q

# A single test
.venv/bin/python -m pytest tests/test_suite.py -k test_name -v

# Live/manual tests that hit the real Spansh API (slow, only run deliberately -- and never
# when the user says spansh.co.uk is busy/slow)
.venv/bin/python -m pytest tests/test_suite.py -m slow -v

# Type-check a file
.venv/bin/pyright Router/plotters.py

# Lint (matches CI -- only catches syntax errors/undefined names, not style)
flake8 . --extend-exclude .venv,Router/utils --count --select=E9,F63,F7,F82 --show-source --statistics
```

Test markers are declared in `tests/pytest.ini` (the top-level `pytest.ini` is not the one actually used — pytest resolves `tests/` as rootdir): `slow` (real network calls to spansh.co.uk, can take minutes), `manual_only` (excluded from CI), `live_requests`, `overlay`. CI (`.github/workflows/unit-tests.yml`) runs `-m "not manual_only"` — note this *does* include `slow` tests.

Release/build packaging (zip for distribution, VirusTotal scan, version bump on tag push) is documented in `AGENTS.md` — don't duplicate it here.

## Architecture

### Global state: `Context` + `@singleton`

Almost every major class (`Router`, `UI`, `CSV`, `Overlay`, `Hotkeys`, `Prefs`) is decorated `@singleton` (`Router/utils/misc.py`) and stored as a class attribute on `Router/context.py`'s `Context` dataclass (`Context.router`, `Context.ui`, `Context.route`, etc.) rather than instantiated and passed around. Any module reaches any other subsystem via `Context.xxx`. `Context.route` is the currently-plotted `Route`; everything else is a `@singleton` service object created once in `load.py`'s `plugin_app()`.

### EDMC plugin lifecycle (`load.py`)

EDMC calls these module-level functions directly; there's no `main()`:
- `plugin_start3` — one-time init (version, user agent, update check)
- `plugin_app` — builds every `Context.xxx` singleton, returns the root UI frame
- `journal_entry` — the real-time event loop; `match entry['event']` dispatches journal events (`FSDJump`, `CarrierJumpRequest`, `Loadout`, `SendText` for chat commands, etc.) to `Context.router`/`Context.route`
- `dashboard_entry`, `plugin_prefs`, `prefs_changed`, `plugin_stop` — the other EDMC-defined hooks

### `Router/` package

- `route_manager.py` (`Router`, `Context.router`): owns `route_params` (per-route-type persisted form state) and `plot_route()`/`_plotter()` — the async Spansh job-submit-and-poll flow, run on a background thread for every route type
- `plotters.py`: an abstract `Plotter` base class plus one subclass per route family (`NeutronPlotter`, `GalaxyPlotter`, `RichesPlotter` — backs Road to Riches, the body-type-filtered world routes, and Exobiology — `TradePlotter`, `TouristPlotter`, `FleetCarrierPlotter`). `PLOTTER_SPECS` is a dict of `PlotterSpec` dataclasses, one per route type, that's the single source of truth for its label, `Plotter` subclass, Spansh URL, and param key names — `Router.route_types`, `plot_route()`'s dispatch, and `ui.py`'s plotter instantiation all derive from this dict, so adding a route type is a registry entry, not new wiring. Plotters with a variable-length list of system entries (Neutron's via-points, Tourist's/Fleet Carrier's stops) share a hop-list widget built from `Plotter._create_system_entry()`/`_create_hop_row()`/`_rebuild_hop_rows()`
- `route.py` (`Route`, `Context.route`): the currently-plotted or -imported route — a row list plus a header list (`hdrs`), with column lookup by header name via `colind()` rather than fixed indices, so very different route shapes (Neutron's flat jumps, riches' nested bodies flattened to one row per body, Trade's paired hop legs) can all become one row list
- `ui.py` (`UI`, `Context.ui`): the Tkinter frame tree; `self.plotters`/`self.plot_frames` dicts keyed by route type
- `overlay.py`, `hotkeys.py`, `csv.py`, `prefs.py`, `route_window.py`, `ship.py`, `context.py`, `constants.py` — in-game overlay, hotkey integration, CSV import/export, the EDMC preferences pane, the route detail window, ship loadout modeling, the `Context` registry, and shared strings/HTTP endpoints/headers respectively

### Themed widgets (`Router/utils/th/`)

EDMC's dark/light theme system needs each widget to exist as a light/dark pair. `th.Base` wraps a light `obj` + dark `alt` widget pair, switched via `theme.register()`/`config.get_bool('dark_mode')`; most `th.*` widget classes (`Button`, `ComboBox`, `Listbox`, `Radiobutton`, `Checkbutton`, `Scale`, `Spinbox`) subclass `Base`. Gotchas worth knowing before touching this file: passing the same explicit Tk `name=` to both halves makes Tk silently alias one onto the other; `nametowidget()` can only ever return the raw wrapped widget, never the `Base` wrapper (`th.resolve()` recovers it when needed); `Base.__setattr__` silently *drops* any new attribute not already present on the wrapped widget(s) — no error, just a no-op — so new per-instance state must go through `object.__setattr__()` directly; a `tk.OptionMenu` (used for the dark half of `ComboBox`) has no `<<ComboboxSelected>>` virtual event, so cross-mode event wiring needs to hook the widget's own command, not a shared-variable trace (a trace fires on *every* write, including unrelated code syncing the same variable, and can create infinite callback loops).

### Error handling: `@catch_exceptions`

Most UI callback methods (in particular every `Plotter.plot()`) are decorated `@catch_exceptions` (`Router/utils/debug.py`), which logs and *swallows* any exception rather than raising. A bug inside one of these methods fails silently at runtime — it won't crash, the button just quietly does nothing. Check `Debug.logger`'s output rather than assuming a silent no-op means the code path wasn't reached.

### Test harness (`tests/harness.py`, `tests/edmc/`)

`TestHarness` is a `@singleton`-per-test-function fixture (`tests/test_suite.py`'s `harness` fixture calls `TestHarness.reset_instance()` before/after each test) that builds a real headless Tk root and drives the plugin through `load.py`'s actual hook functions — an integration harness, not unit mocks of the plugin's own code. `tests/edmc/` provides stand-ins for everything EDMC itself would normally supply (`config`, `myNotebook`, `edmc_data`, `companion`, `monitor`, etc.), inserted onto `sys.path` before the plugin package is imported. `tests/edmc/TkScheduler.py` and `tests/edmc/Clipboard.py` monkeypatch `tk.Misc.after`/`clipboard_*` at the class level so tests run thread-safely and never touch the real OS clipboard.
