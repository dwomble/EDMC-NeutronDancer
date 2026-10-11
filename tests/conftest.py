# Sections marked PLUGIN need editing to reuse this file for another plugin; the rest is generic.
import shutil
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest
from harness import TestHarness, reset_plugin_modules

# GENERIC: must run in a fixture, as the pool workers are joined before atexit handlers run
@pytest.fixture(scope="session", autouse=True)
def _stop_lookups() -> Generator[None, None, None]:
    """Cancel queued autocompleter lookups at session end so they can't hold up interpreter exit."""
    yield
    TestHarness.stop_lookups()

# PLUGIN: wires TestHarness to your plugin; edit the marked steps, keep the harness, yield and teardown
@pytest.fixture
def harness(request, monkeypatch) -> Generator:
    """Provide a fresh test harness for each test."""

    # Keep module_data.json, or every test forces a live Coriolis download, not just one.
    data_dir:Path = Path(__file__).parent / "data"
    (data_dir / "route.json").unlink(missing_ok=True)
    shutil.rmtree(data_dir / "ships", ignore_errors=True)

    param = getattr(request, 'param', ('route_init.json', 'ships'))
    init_file, ships_dir = param if isinstance(param, tuple) else (param, None)
    if init_file != 'None' or ships_dir:
        data_dir.mkdir(exist_ok=True)
        if init_file != 'None':
            shutil.copy(Path(__file__).parent / "config" / init_file, data_dir / "route.json")
        if ships_dir:
            shutil.copytree(Path(__file__).parent / "config" / ships_dir, data_dir / "ships")

    overlay = 'Modern'
    if request.node.get_closest_marker('overlay'):
        overlay = request.node.get_closest_marker('overlay').args[0]

    hotkeys = request.node.get_closest_marker('hotkeys') or True

    TestHarness.reset_instance()
    reset_plugin_modules()

    live:bool = any(request.node.get_closest_marker(m) for m in ('live_requests', 'slow'))
    test_harness = TestHarness(live_requests=live, overlay=overlay, hotkeys=hotkeys)

    # This is ND-specific. /assets is where the images are stored
    import Router.constants
    Router.constants.ASSET_DIR = "../assets"

    from load import plugin_start3, plugin_app, journal_entry, dashboard_entry

    # Avoid live update/notice threads hanging teardown.
    with patch('load.Updater.check_for_update', return_value=None), \
         patch('load.Notices.check_for_notices', return_value=None):
        plugin_start3(str(test_harness.plugin_dir))
    plugin_app(test_harness.parent)

    # ND-specific, this is our plugin object
    import Router.context
    test_harness.plugin = Router.context.Context

    # Default to a no-op so tests that just construct/load a route avoid real network calls.
    monkeypatch.setattr(test_harness.plugin.spansh, 'start_fetch', lambda ids: None)

    # ND-specific, this is the journal handling function and the default journal params
    test_harness.load_events("journal_events.json")
    test_harness.register_journal_handler(journal_entry, 'Testy', 'Sol', True)

    # This is the dashboard handlling function
    test_harness.register_dashboard_handler(dashboard_entry, 'Testy', True)

    yield test_harness

    # Cheap, local teardown only; lookup pools are stopped once at session end (see _stop_lookups).
    test_harness.plugin.overlay.stop_countdowns()
    test_harness.assert_no_unhandled_exceptions()
    TestHarness.reset_instance()
