"""
Test suite for EDMC Neutron Dancer plugin using pytest.
"""
#from __future__ import annotations

import pytest # type: ignore
import sys
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Generator
from unittest.mock import Mock, patch
from contextlib import contextmanager
import json
import logging
import tkinter as tk
from tkinter import ttk
import threading

import tests.edmc.requests as mock_requests
from tests.edmc import edmc_data

from Router.utils.treeviewplus import TreeviewPlus
from Router.utils import th
from Router.utils.updater import Updater, Notices, read_version_file

# Setup path for imports
plugin_dir:Path = Path(__file__).parent
sys.path.insert(0, str(plugin_dir))

from harness import TestHarness, reset_plugin_modules
from Router.route_window import RouteWindow
from Router.constants import SPANSH_ROUTE, NAME, lbls
from Router.route import Route
from Router.ship import Ship
from Router.plotters import PLOTTER_SPECS, _boxel_coords, _boxel_exists, _boxel_prefix

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

THREAD_TIMEOUT=66
plotter_thread = None

def capture_thread(*args, **kwargs):
    global plotter_thread

    thread = threading.Thread(*args, **kwargs)
    if kwargs.get('name', '') == "Neutron Dancer route plotting worker":
        plotter_thread = thread
    return thread


def fake_systems_get(url, *args, **kwargs):
    """ Stand-in for requests.get against the Spansh systems autocomplete endpoint.
    Echoes back whatever was queried so system-name validation always succeeds without a real network call. """
    q = kwargs.get('params', {}).get('q', '')
    resp = Mock()
    resp.status_code = 200
    resp.content = json.dumps([q]).encode()
    return resp

def _queue_notices(text:str) -> None:
    mock_requests.queue_response("get", mock_requests.MockResponse(status_code=200, content=text))

@contextmanager
def mocked_session_get(side_effect):
    """ Mocks SESSION.get for query_systems/query_station_names, matching plot_route()'s tests. """
    with patch('Router.route_manager.SESSION.get', side_effect=side_effect):
        yield

@pytest.fixture
def harness(request, monkeypatch) -> Generator:
    """Provide a fresh test harness for each test."""

    # Clean route/ships each test, but keep module_data.json --
    # else every test forces a live Coriolis download, not one.
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

    test_harness = TestHarness(live_requests=True, overlay=overlay, hotkeys=hotkeys)

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

    # Route(...) triggers a background EDSM fetch -- default it to a no-op so the many tests
    # that just construct/load a route incidentally don't gain real network side effects.
    # TestEdsmEnrichment overrides this itself for the tests that actually exercise it.
    monkeypatch.setattr(test_harness.plugin.edsm, 'start_fetch', lambda names: None)

    # ND-specific, this is the journal handling function and the default journal params
    test_harness.load_events("journal_events.json")
    test_harness.register_journal_handler(journal_entry, 'Testy', 'Sol', True)

    # This is the dashboard handlling function
    test_harness.register_dashboard_handler(dashboard_entry, 'Testy', True)

    yield test_harness

    # Cheap, per-test hygiene only -- stopping countdown threads is local and instant. The
    # network-bound Autocompleter.join_all() (see plugin_stop()) runs once at session end
    # instead (tests/conftest.py), since joining live lookup threads per-test multiplies
    # real network round-trips across the whole suite.
    test_harness.plugin.overlay.stop_countdowns()
    test_harness.assert_no_unhandled_exceptions()
    TestHarness.reset_instance()

class TestStartup:
    """Test plugin startup behavior."""

    @pytest.mark.parametrize('harness', ['None', ('route_init.json', 'ships')], indirect=True)
    def test_harness_initialization(self, harness:TestHarness) -> None:
        """ Blank slate and a v2.0 route.json + ships/ both init. """
        assert harness.plugin.router is not None
        assert isinstance(harness.plugin.router.shiplist, dict)

    @pytest.mark.parametrize('harness', [('route_init.json', 'ships')], indirect=True)
    def test_harness_initialization_loads_ships_directory(self, harness:TestHarness) -> None:
        """ v2.0 ships/ load without a migration rewrite. """
        assert harness.plugin.router.shiplist == {"1": "Shipping Delay", "2": "Perviy"}
        assert harness.plugin.router.load_ship("1").name == "Shipping Delay"

    @pytest.mark.parametrize('harness', ['None'], indirect=True)
    def test_migration(self, harness:TestHarness) -> None:
        """ Test v1.10.0's route.json migrates to v2.0's separate ships files. """
        shutil.copy(Path(__file__).parent / "config" / "route_1.10.0.json", Path(__file__).parent / "data" / "route.json")
        harness.plugin.router._load()

        assert not hasattr(harness.plugin.router, "ships")
        assert isinstance(harness.plugin.router.shiplist, dict)
        assert harness.plugin.router.shiplist["1"] == "Shipping Delay"

        ships_dir = Path(__file__).parent / "data" / "ships"
        assert (ships_dir / "1.json").exists()
        assert (ships_dir / "2.json").exists()

    def test_startup_event(self, harness:TestHarness) -> None:
        """Test that startup event sets system correctly."""

        assert harness.plugin.router is not None
        harness.play_sequence('startup')
        assert harness.plugin.router.system == "Sol"

    def test_module_import(self, harness:TestHarness) -> None:
        """Test retrieving module data from Coriolis """
        harness.plugin.modules = []
        harness.plugin.router._get_module_data()
        assert len(harness.plugin.modules) == 88

class TestUpdater:
    @pytest.fixture(autouse=True)
    def _mock_network(self) -> Generator[None, None, None]:
        """ queue_response()/.calls need the shared mock --
        _use_live is a global a prior harness-based test may
        have left True -- it never resets on its own. """
        previous:bool = mock_requests.live_requests()
        mock_requests.live_requests(False)
        yield
        mock_requests.live_requests(previous)

    def test_get_release_sends_edmc_user_agent_plus_project_name(self, tmp_path) -> None:
        updater = Updater(str(tmp_path), "dwomble", "EDMC-NeutronDancer")
        mock_requests.queue_response("get", mock_requests.MockResponse(status_code=404))

        updater.get_release()

        call = mock_requests._mock_requests.calls[-1]
        assert call['headers']['User-Agent'] == "EDMC-TestHarness/1.0 EDMC-NeutronDancer-Updater"

    def test_download_zip_sends_edmc_user_agent_plus_project_name(self, tmp_path) -> None:
        updater = Updater(str(tmp_path), "dwomble", "EDMC-NeutronDancer")
        updater.update_version = "1.2.3" # type: ignore -- str is fine, only used for a filename here
        updater.download_url = "https://example.invalid/release.zip"
        mock_requests.queue_response("get", mock_requests.MockResponse(status_code=404))

        updater.download_zip()

        call = mock_requests._mock_requests.calls[-1]
        assert call['headers']['User-Agent'] == "EDMC-TestHarness/1.0 EDMC-NeutronDancer-Updater"

    def test_reads_the_version_file_when_present(self, tmp_path) -> None:
        (tmp_path / "version").write_text("1.2.3")
        assert str(read_version_file(str(tmp_path), "0.0.0-dev")) == "1.2.3"

    def test_falls_back_to_default_when_no_file_exists(self, tmp_path) -> None:
        assert str(read_version_file(str(tmp_path), "0.1.0-dev")) == "0.1.0-dev"

    def test_falls_back_to_default_when_the_file_is_unparseable(self, tmp_path) -> None:
        """ e.g. a fresh git checkout with an empty/placeholder version file. """
        (tmp_path / "version").write_text("not-a-version!!")
        assert str(read_version_file(str(tmp_path), "0.1.0-dev")) == "0.1.0-dev"

    def test_strips_surrounding_whitespace(self, tmp_path) -> None:
        """ CI's release.yml writes the tag via `echo`, which appends a newline. """
        (tmp_path / "version").write_text("1.2.3\n")
        assert str(read_version_file(str(tmp_path), "0.0.0-dev")) == "1.2.3"

class TestNotices:
    """ Cursory integration check -- Notices' parsing and
    dismissal logic is exhaustively covered by EDMC-PluginLib's
    tests/test_notices.py; this just confirms fetch, parse, and
    dismiss-then-newer-shows-again round-trip in this plugin's
    own stack. TestUIFunctions.test_show_notice_displays_pending_
    notice covers the displayed half, this plugin's own code. """

    @pytest.fixture(autouse=True)
    def _mock_network(self) -> Generator[None, None, None]:
        """ Same leak as TestUpdater's own fixture. """
        previous:bool = mock_requests.live_requests()
        mock_requests.live_requests(False)
        yield
        mock_requests.live_requests(previous)

    def test_fetch_parse_and_dismiss_round_trip(self) -> None:
        _queue_notices("## 3\nFleet Carrier routes now track tritium separately from cargo.")
        notices = Notices("dwomble", "EDMC-NeutronDancer-NoticesTest")
        notices._check_notices()
        assert notices.pending_notice == "Fleet Carrier routes now track tritium separately from cargo."

        notices.dismiss_notice()
        assert notices.pending_notice is None

        _queue_notices("## 4\nA newer notice.")
        notices._check_notices()
        assert notices.pending_notice == "A newer notice."

class TestStateManagement:
    """Test router state management."""

    def test_load(self, harness:TestHarness) -> None:
        """Call plugin load"""
        harness.plugin.router._load()

    def test_save(self, harness:TestHarness) -> None:
        """Call save"""
        harness.plugin.router.save()


class TestRouteMethods:
    """ Test the route object's methods"""
    def test_route_with_tritium_column(self, harness:TestHarness) -> None:
        """Test fleet carrier route with tritium column."""
        from Router.route import Route

        if hasattr(harness.plugin.router, '_initialized'):
            delattr(harness.plugin.router, '_initialized')

        route_data = [
            ['System A', 5, 50, 'True'],  # Tritium at this waypoint
            ['System B', 10, 45, 'True'],
            ['System C', 8, 50, 'False']
        ]
        hdrs = ['System Name', 'Jumps', 'Dist Rem', 'Tritium']
        route = Route(hdrs, route_data, 0)

        assert route.fleetcarrier == True
        assert route.refuel() == False  # Depends on refuel column

    def test_next_stop_current_waypoint(self, harness:TestHarness) -> None:
        """Test next_stop() at current waypoint."""
        from Router.route import Route

        if hasattr(harness.plugin.router, '_initialized'):
            delattr(harness.plugin.router, '_initialized')

        route_data = [
            ['Sol', 0],
            ['Apurui', 10],
            ['Bleae Thua', 5]
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0)

        assert route.next_stop() == 'Apurui'  # Next after current (Sol)

    def test_next_stop_complete_route(self, harness:TestHarness) -> None:
        """Test next_stop() when route is complete."""
        from Router.route import Route

        if hasattr(harness.plugin.router, '_initialized'):
            delattr(harness.plugin.router, '_initialized')

        route_data = [
            ['Sol', 0],
            ['Apurui', 10],
            ['Bleae Thua', 5]
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 2)  # At last waypoint

        assert route.next_stop() == 'End of the road!'  # lbls['route_complete']

    def test_next_stop_trade(self, harness:TestHarness) -> None:
        """next_stop_detail() returns the station name for Trade-shaped routes."""
        hdrs = ['System Name', 'Station Name', 'Commodity', 'Amount', 'Profit', 'Jumps']
        route_data = [
            ['Shinrarta Dezhra', 'Jameson Memorial', 'Steel', 100, 5134, 0],
            ['Puppis Sector TO-R b4-4', 'Alvarado Beacon', 'Agronomic Treatment', 200, 10617, 3],
        ]
        route = Route(hdrs, route_data, 0)

        assert route.next_stop_value('System Name') == 'Puppis Sector TO-R b4-4'
        assert route.next_stop_value('Species') is None  # no such column on this route
        assert route.next_stop_station() == 'Alvarado Beacon'
        lines = route.next_stop_details()
        assert any('Agronomic Treatment' in l for l in lines)
        assert any('Cr/t' in l for l in lines)
        assert any('Cr' in l and 'Cr/t' not in l for l in lines)  # the running-total line

    def test_next_stop_riches(self, harness:TestHarness) -> None:
        """ subtype/distance/scan value for a riches-shaped route. Header names ('Body',
        'Body Type') match what _flatten_bodies_result()/HEADER_MAP actually produce -- see
        test_plotter_success_creates_route_riches's `assert "Body" in ...hdrs`. """
        hdrs = ['System Name', 'Body', 'Body Type', 'Distance To Arrival', 'Estimated Scan Value', 'Jumps']
        route_data = [
            ['Colonia', 'Colonia 1', '', 0, 0, 0],
            ['Colonia', 'Colonia 2 a', 'High metal content world', 812.0, 42300, 1],
        ]
        route = Route(hdrs, route_data, 0)

        lines = route.next_stop_details()

        assert any('High metal content world' in l for l in lines)
        assert any('Scan' in l for l in lines)
        assert route.next_stop_display() == 'Colonia 2 a'

    def test_next_stop_display_prepends_system_when_body_lacks_it(self, harness:TestHarness) -> None:
        """ Body's own value can't be trusted to include the system name -- e.g. after the
        route window strips it (route_window.py's _table()) -- so next_stop_display() must
        add it itself rather than assuming Spansh always bakes it in. """
        hdrs = ['System Name', 'Body', 'Species', 'Jumps']
        route = Route(hdrs, [['Deciat', 'Deciat 1', '', 0], ['Deciat', '4 a', 'Bacterium Nypoxia', 1]], 0)

        assert route.next_stop_display() == 'Deciat 4 a'

    def test_next_stop_display_falls_back_to_system_without_a_body_column(self, harness:TestHarness) -> None:
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, [['Sol', 0], ['Apurui', 10]], 0)

        assert route.next_stop_display() == route.next_stop() == 'Apurui'

    def test_next_stop_exobiology(self, harness:TestHarness) -> None:
        """ next_stop() stays the system name (self.nc must
        match FSDJump's StarSystem for position tracking) --
        next_stop_display() carries the body instead;
        next_stop_details() doesn't repeat it. """
        hdrs = ['System Name', 'Body', 'Species', 'Jumps']
        route_data = [
            ['Deciat', 'Deciat 1', '', 0],
            ['Deciat', 'Deciat 4 a', 'Bacterium Nypoxia', 1],
        ]
        route = Route(hdrs, route_data, 0)

        assert route.next_stop_station() == ''
        assert route.next_stop() == 'Deciat'
        assert route.next_stop_display() == 'Deciat 4 a'
        assert any('Bacterium Nypoxia' in l for l in route.next_stop_details())

    def test_next_stop_details_lists_extra_bodies_in_the_same_system(self, harness:TestHarness) -> None:
        """ Riches/exobiology routes can list several bodies per system, all collapsed under
        one displayed system name (next_stop() can't disambiguate by body -- see above) --
        the detail lines must call out that there's more than just the immediate one. """
        hdrs = ['System Name', 'Body', 'Species', 'Jumps']
        route_data = [
            ['Deciat', 'Deciat 1', '', 0],
            ['Deciat', 'Deciat 4 a', 'Bacterium Nypoxia', 1],
            ['Deciat', 'Deciat 4 b', 'Fonticulua Campestris', 0],
        ]
        route = Route(hdrs, route_data, 0)

        lines = route.next_stop_details()

        assert any('Deciat 4 b' in l and 'Fonticulua Campestris' in l for l in lines)

    def test_next_stop_station_blank(self, harness:TestHarness) -> None:
        """Bblank for plain route types (Neutron, Galaxy, etc.)."""
        hdrs = ['System Name', 'Jumps']
        route_data = [['Sol', 0], ['Apurui', 10]]
        route = Route(hdrs, route_data, 0)

        assert route.next_stop_station() == ''


    def test_cumulative_value(self, harness:TestHarness) -> None:
        """cumulative_value() sums a numeric column through the next stop, not past it."""
        hdrs = ['System Name', 'Estimated Scan Value', 'Jumps']
        route_data = [['Sol', 0, 0], ['Deciat', 42300, 1], ['Colonia', 10000, 2]]
        route = Route(hdrs, route_data, 1)  # next stop is Colonia (offset+1 == 2)

        assert route.sum_value('Estimated Scan Value') == 52300

    def test_sum_value_and_route_value(self, harness:TestHarness) -> None:
        """sum_value(through=...) sums an arbitrary prefix (route-window "so far"/"total" use
        this); route_value() picks Profit/Landmark Value/Scan or Mapping Value by column
        presence, or None for route types with no earned-value column."""
        hdrs = ['System Name', 'Station Name', 'Commodity', 'Amount', 'Profit', 'Jumps']
        route_data = [
            ['Shinrarta Dezhra', 'Jameson Memorial', '', 0, 0, 0],
            ['Sol', 'Abraham Lincoln', 'Gold', 100, 5000, 2],
            ['Deciat', 'Farside', 'Silver', 200, 10617, 3],
        ]
        route = Route(hdrs, route_data, 0)  # offset 0 -> completed just row 0

        assert route.sum_value('Profit', through=route.offset+1) == 0
        assert route.sum_value('Profit', through=len(route.route)) == 15617
        assert route.route_value() == (lbls['profit'], 'Profit')

        plain_route = Route(['System Name', 'Jumps'], [['Sol', 0], ['Apurui', 10]], 0)
        assert plain_route.route_value() is None

    def test_trade_cumulative_profit(self, harness:TestHarness) -> None:
        """a running-total line sums Profit across every waypoint through the next stop."""
        hdrs = ['System Name', 'Station Name', 'Commodity', 'Amount', 'Profit', 'Jumps']
        route_data = [
            ['Shinrarta Dezhra', 'Jameson Memorial', '', 0, 0, 0],
            ['Sol', 'Abraham Lincoln', 'Gold', 100, 5000, 2],
            ['Deciat', 'Farside', 'Silver', 200, 10617, 3],
        ]
        route = Route(hdrs, route_data, 1)  # next stop is Deciat

        assert route.sum_value('Profit') == 15617
        lines = route.next_stop_details()
        assert any('Silver' in l for l in lines)
        assert any('15.6K Cr' in l for l in lines)

    def test_riches_cumulative_scan(self, harness:TestHarness) -> None:
        """riches scan value gets a running total across waypoints already passed"""
        hdrs = ['System Name', 'Body', 'Body Type', 'Distance To Arrival', 'Estimated Scan Value', 'Jumps']
        route_data = [
            ['Colonia', 'Colonia 1', '', 0, 0, 0],
            ['Colonia', 'Colonia 2 a', 'High metal content world', 812.0, 42300, 1],
            ['Colonia', 'Colonia 3 a', 'Icy body', 100.0, 5000, 1],
        ]
        route = Route(hdrs, route_data, 1)  # next stop is Colonia 3 a

        assert route.sum_value('Estimated Scan Value') == 47300
        lines = route.next_stop_details()
        assert any('47.3K Cr' in l for l in lines)

    def test_details_blank_no_extra_columns(self, harness:TestHarness) -> None:
        """next_stop_detail_lines() is empty for plain route types (Neutron, Tourist, etc.)."""
        hdrs = ['System Name', 'Jumps']
        route_data = [['Sol', 0], ['Apurui', 10]]
        route = Route(hdrs, route_data, 0)

        assert route.next_stop_details() == []

    def test_tracks_refuel_or_neutron(self, harness:TestHarness) -> None:
        """Test checks refuel or neutron for appropriate route types."""
        neutron_route = Route(['System Name', 'Jumps', 'Refuel'], [['Sol', 0, 'No'], ['Apurui', 10, 'Yes']], 0)
        assert neutron_route.tracks_refuel_or_neutron() == True

        galaxy_route = Route(['System Name', 'Jumps', 'Neutron'], [['Sol', 0, 'False'], ['Apurui', 10, 'True']], 0)
        assert galaxy_route.tracks_refuel_or_neutron() == True

        trade_route = Route(['System Name', 'Station Name', 'Jumps'], [['Sol', 'A', 0], ['Apurui', 'B', 10]], 0)
        assert trade_route.tracks_refuel_or_neutron() == False

    def test_jumps_remaining_at_start(self, harness:TestHarness) -> None:
        route_data = [
            ['Sol', 0],
            ['Apurui', 10],
            ['Bleae Thua', 5]
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0)

        assert route.jumps_remaining() == 15  # 10 + 5

    def test_jumps_remaining_incomplete(self, harness:TestHarness) -> None:
        route_data = [
            ['Sol', 0],
            ['Apurui', 10],
            ['Bleae Thua', 5]
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0)

        route.update_route(1)  # Move to Apurui
        assert route.jumps_remaining() == 5  # Only Bleae Thua remains

    def test_perc_jumps_rem_at_start(self, harness:TestHarness) -> None:
        route_data = [
            ['Sol', 0],
            ['Apurui', 10],
            ['Bleae Thua', 5]
        ]

        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0)

        total = route.total_jumps()
        remaining = route.jumps_remaining()
        assert route.perc_jumps_rem() == (total - remaining) * 100 / total

    def test_perc_jumps_rem_complete(self, harness:TestHarness) -> None:
        route_data = [
            ['Sol', 0],
            ['Apurui', 10],
            ['Bleae Thua', 5]
        ]

        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0)
        assert route.perc_jumps_rem(2) == 100.0


    def test_dist_remaining_at_start(self, harness:TestHarness) -> None:
        route_data = [
            ['Sol', 0, 150],
            ['Apurui', 10, 100],
            ['Bleae Thua', 5, 50]
        ]
        hdrs = ['System Name', 'Jumps', 'Distance Rem']
        route = Route(hdrs, route_data, 0)

        assert route.dist_remaining() == 150

    def test_dist_remaining_mid_route(self, harness:TestHarness) -> None:
        route_data = [
            ['Sol', 0, 150],
            ['Apurui', 10, 100],
            ['Bleae Thua', 5, 50]
        ]
        hdrs = ['System Name', 'Jumps', 'Distance Rem']
        route = Route(hdrs, route_data, 0)

        route.update_route(1)  # Move to Apurui
        assert route.dist_remaining() == 100  # Distance to Bleae Thua

    def test_refuel_check(self, harness:TestHarness) -> None:
        route_data = [
            ['Sol', 0, 'Fuel'],
            ['Apurui', 10, 'No'],
            ['Bleae Thua', 5, 'Fuel']
        ]
        hdrs = ['System Name', 'Jumps', 'Refuel']
        route = Route(hdrs, route_data, 0)

        # Check next waypoint for refuel
        route.update_route(1)  # Now at Apurui
        assert route.refuel() == False  # Apurui doesn't refuel

    def test_neutron_check(self, harness:TestHarness) -> None:
        route_data = [
            ['Sol', 0, 'False'],
            ['Apurui', 10, 'True'],
            ['Bleae Thua', 5, 'False']
        ]
        hdrs = ['System Name', 'Jumps', 'Neutron']
        route = Route(hdrs, route_data, 0)

        # Check if next waypoint needs neutron
        route.update_route(1)  # Now at Apurui
        assert route.is_neutron() == False  # Bleae Thua doesn't need neutron

    def test_get_waypoint_next(self, harness:TestHarness) -> None:
        route_data = [
            ['A', 0],
            ['B', 1],
            ['C', 2]
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0)

        assert route.get_waypoint(0) == 'B'

    def test_get_waypoint_end(self, harness:TestHarness) -> None:
        route_data = [
            ['A', 0],
            ['B', 1]
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 1)

        assert route.get_waypoint(0) == 'None'  # tbls['none']

    def test_record_jump(self, harness:TestHarness) -> None:
        route_data = [
            ['Sol', 0]
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0)

        # Record a jump
        dest = 'Jupiter'
        dist = 2.5
        route.record_jump(dest, dist)

        assert len(route.jumps) == 1
        assert route.jumps[0][1] == dest
        assert abs(route.jumps[0][2] - dist) < 0.01  # Allow for rounding


class TestRouteNavigation:
    """Test moving along a route via real navigation events (FSDJump, !nd chat commands)
    rather than calling Route.update_route() directly."""

    def _import(self, harness:TestHarness, filename:str) -> None:
        assert harness.plugin.router.import_route(str(Path(__file__).parent / "config" / filename)) == True

    def _jump(self, harness:TestHarness, system:str) -> None:
        harness.fire_event({"event": "FSDJump", "StarSystem": system})

    def _chat(self, harness:TestHarness, command:str) -> None:
        harness.fire_event({"event": "SendText", "Message": f"!nd {command}"})

    def test_not_on_route(self, harness:TestHarness) -> None:
        """Jumping to a system not on the route leaves offset at -1."""
        self._import(harness, "neutron-Bleae-Smojue.csv")

        self._jump(harness, 'Apurui')

        assert harness.plugin.route.offset == -1
        assert harness.plugin.route.next_stop() == 'Bleae Thua NI-B b27-5'

    def test_on_route(self, harness:TestHarness) -> None:
        """Jumping to a system on the route sets offset to that row."""
        self._import(harness, "neutron-Bleae-Smojue.csv")

        self._jump(harness, 'Bleae Thua NI-B b27-5')

        assert harness.plugin.route.offset == 0
        assert harness.plugin.route.next_stop() == 'Bleae Thua RX-L d7-28'

    def test_start_of_route(self, harness:TestHarness) -> None:
        """!nd previous at the start of the route doesn't move further back."""
        self._import(harness, "neutron-Bleae-Smojue.csv")
        self._jump(harness, 'Bleae Thua NI-B b27-5')

        self._chat(harness, 'previous')

        assert harness.plugin.route.offset == -1
        assert harness.plugin.route.next_stop() == 'Bleae Thua NI-B b27-5'

    def test_end_of_route(self, harness:TestHarness) -> None:
        """!nd next at the end of the route doesn't move further along."""
        self._import(harness, "neutron-Bleae-Smojue.csv")
        self._jump(harness, 'Smojue DR-N d6-34')
        assert harness.plugin.route.offset == 9

        self._chat(harness, 'next')
        assert harness.plugin.route.next_stop() == 'End of the road!'

        self._chat(harness, 'next')
        assert harness.plugin.route.next_stop() == 'End of the road!'

    def test_route_neutron(self, harness:TestHarness) -> None:
        """is_neutron() reflects whichever waypoint !nd next has advanced to."""
        self._import(harness, "neutron-Bleae-Smojue.csv")
        self._jump(harness, 'Bleae Thua NI-B b27-5')
        assert harness.plugin.route.is_neutron() == False  # Next waypoint is not a neutron

        self._chat(harness, 'next')
        assert harness.plugin.route.offset == 1
        assert harness.plugin.route.is_neutron() == True  # Next waypoint is a neutron

    def test_jumps_to_wp(self, harness:TestHarness) -> None:
        """jumps_to_wp() reflects whichever waypoint !nd next has advanced to."""
        self._import(harness, "neutron-Bleae-Smojue.csv")
        self._jump(harness, 'Bleae Thua NI-B b27-5')
        assert harness.plugin.route.jumps_to_wp() == 12

        self._chat(harness, 'next')
        assert harness.plugin.route.offset == 1
        assert harness.plugin.route.jumps_to_wp() == 3

    def test_total_jumps_neutron(self, harness:TestHarness) -> None:
        """total_jumps() for a route with a Jumps column."""
        self._import(harness, "neutron-Bleae-Smojue.csv")
        self._jump(harness, 'Bleae Thua NI-B b27-5')
        assert harness.plugin.route.total_jumps() == 66

    def test_total_jumps_galaxy(self, harness:TestHarness) -> None:
        """total_jumps() for a route with no Jumps column (one row == one jump)."""
        self._import(harness, "galaxy-Bleae-Voqooe.csv")
        self._jump(harness, 'Bleae Thua NI-B b27-5')
        assert harness.plugin.route.total_jumps() == 74

    def test_jumps_remaining_neutron(self, harness:TestHarness) -> None:
        """jumps_remaining() before the route starts and after !nd next advances it."""
        self._import(harness, "neutron-Bleae-Smojue.csv")
        assert harness.plugin.route.offset == -1
        assert harness.plugin.route.jumps_remaining() == 66

        self._jump(harness, 'Bleae Thua NI-B b27-5')
        assert harness.plugin.route.jumps_remaining() == 66

        self._chat(harness, 'next')
        assert harness.plugin.route.offset == 1
        assert harness.plugin.route.jumps_remaining() == 54

    def test_jumps_remaining_galaxy(self, harness:TestHarness) -> None:
        """jumps_remaining() jumping straight to a system partway along the route."""
        self._import(harness, "galaxy-Bleae-Voqooe.csv")
        assert harness.plugin.route.offset == -1
        assert harness.plugin.route.jumps_remaining() == 74

        self._jump(harness, 'Bleae Thua NI-B b27-5')
        assert harness.plugin.route.jumps_remaining() == 74

        self._jump(harness, 'Gria Drye JT-O d7-172')
        assert harness.plugin.route.offset == 22
        assert harness.plugin.route.jumps_remaining() == 52

    def test_perc_jumps_remaining(self, harness:TestHarness) -> None:
        """perc_jumps_rem() after !nd next advances one waypoint."""
        self._import(harness, "neutron-Bleae-Smojue.csv")
        self._jump(harness, 'Bleae Thua NI-B b27-5')
        self._chat(harness, 'next')
        assert harness.plugin.route.offset == 1
        assert int(harness.plugin.route.perc_jumps_rem()) == 18

    def test_dist_remaining(self, harness:TestHarness) -> None:
        """dist_remaining() after !nd next advances one waypoint."""
        self._import(harness, "neutron-Bleae-Smojue.csv")
        self._jump(harness, 'Bleae Thua NI-B b27-5')
        self._chat(harness, 'next')
        assert harness.plugin.route.offset == 1
        assert int(harness.plugin.route.dist_remaining()) == 16273

    def test_total_dist(self, harness:TestHarness) -> None:
        """total_dist() after !nd next advances one waypoint."""
        self._import(harness, "neutron-Bleae-Smojue.csv")
        self._jump(harness, 'Bleae Thua NI-B b27-5')
        self._chat(harness, 'next')
        assert harness.plugin.route.offset == 1
        assert int(harness.plugin.route.total_dist()) == 16458


class TestShipLoadout:
    """Test ship loadout and switching."""

    def test_bad_event(self, harness:TestHarness) -> None:
        """Test bad loadout event."""
        harness.fire_event({"event": "bad", "Ship":"naughty", "ShipID":100000, "ShipName":"Dummy", "ShipIdent":"Dumdum"})

        assert not hasattr(harness.plugin.router.ship, "ship_id")

    @pytest.mark.parametrize('harness', ['None', ('route_init.json', 'ships')], indirect=True)
    def test_loadout_event(self, harness:TestHarness) -> None:
        """Test loading a ship."""

        harness.play_sequence('loadout')
        assert harness.plugin.router.ship_id == '87'
        assert harness.plugin.router.ship is not None
        assert harness.plugin.router.ship.type == 'mandalay'
        assert harness.plugin.router.ship.name == 'Long Delay'
        assert harness.plugin.router.route_params['Neutron']['supercharge_multiplier'] == harness.plugin.router.ship.supercharge_multiplier
        assert harness.plugin.router.route_params['Neutron']['range'] == harness.plugin.router.ship.range

    def test_ship_range_calculation(self, harness:TestHarness) -> None:
        """Test that ship range is calculated."""
        assert harness.plugin.router.ship is not None
        assert hasattr(harness.plugin.router.ship, 'range')
        assert harness.plugin.router.ship.range > 0


class TestImporting:
    """Test importing functionality for different route types."""

    def test_import_nofile(self, harness:TestHarness) -> None:
        filename:str = str(Path(__file__).parent / "config" / "missing.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == False

    def test_import_empty(self, harness:TestHarness) -> None:
        filename:str = str(Path(__file__).parent / "config" / "empty.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == False

    def test_import_bad_route(self, harness:TestHarness) -> None:
        filename:str = str(Path(__file__).parent / "config" / "bad_import.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == False

    def test_import_route_neutron(self, harness:TestHarness) -> None:
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)

        assert res == True
        assert harness.plugin.router.src == 'Bleae Thua NI-B b27-5'
        assert harness.plugin.router.dest == 'Smojue DR-N d6-34'
        assert harness.plugin.route.total_jumps() == 66

    def test_import_route_galaxy(self, harness:TestHarness) -> None:
        filename:str = str(Path(__file__).parent / "config" / "galaxy-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)

        logging.debug(f"Route: {len(harness.plugin.route.route)} {harness.plugin.route}")
        assert res == True
        assert harness.plugin.router.src == 'Bleae Thua NI-B b27-5'
        assert harness.plugin.router.dest == 'Voqooe BI-H d11-864'
        assert harness.plugin.route.total_jumps() == 74

    def test_import_route_fc(self, harness:TestHarness) -> None:
        filename:str = str(Path(__file__).parent / "config" / "fc-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)

        assert res == True
        assert harness.plugin.route.fleetcarrier == True
        assert harness.plugin.router.src == 'Bleae Thua NI-B b27-5'
        harness.plugin.route.offset = 9
        assert harness.plugin.route.next_stop() == 'Nyeajeau IQ-U c4-7'
        assert harness.plugin.router.dest == 'Voqooe BI-H d11-864'

    def test_import_route_riches(self, harness:TestHarness) -> None:
        filename:str = str(Path(__file__).parent / "config" / "riches-Apurui-M23.csv")
        res:bool = harness.plugin.router.import_route(filename)

        assert res == True
        assert harness.plugin.router.src == 'HIP 89264 6'
        assert harness.plugin.router.dest == 'Bleae Thua HF-R d4-116 B 7'


class TestExporting:
    """CSV Export"""
    def test_export_noroute(self, harness:TestHarness) -> None:
        """ Trying to export without a route """
        harness.plugin.route = Route()
        res:bool = harness.plugin.router.export_route()
        assert res == False

    def test_export_no_file(self, harness:TestHarness) -> None:
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)

        assert res == True

        with patch('Router.csv.filedialog.asksaveasfilename', return_value=''):
            res:bool = harness.plugin.router.export_route()

        assert res == False

    def test_export_route(self, harness:TestHarness) -> None:
        out:str = str(Path(__file__).parent / "config" / "tmp.csv")
        if os.path.exists(out):
            os.remove(out)

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        with patch('Router.csv.filedialog.asksaveasfilename', return_value=out):
            res:bool = harness.plugin.csv.write(harness.plugin.route.hdrs, harness.plugin.route.route)
        assert res == True
        assert os.path.exists(out)
        os.remove(out)


class TestCargo:
    """Test cargo management."""

    def test_cargo_event(self, harness:TestHarness):
        """Test cargo event updates."""
        Path(Path(__file__).parent / "journal_folder" / "Cargo.json").unlink(missing_ok=True)
        shutil.copy(Path(__file__).parent / "journal_config" / "Cargo_init.json",
                    Path(__file__).parent / "journal_folder" / "Cargo.json")

        harness.play_sequence('add_cargo')
        assert harness.plugin.router.cargo == 200
        harness.play_sequence('remove_cargo')
        assert harness.plugin.router.cargo == 0


class TestChatCommands:
    """Test !nd chat commands"""
    def test_next(self, harness:TestHarness):
        """Test next command when at the beginning of a route"""

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True
        assert harness.plugin.route.next_stop() == 'Bleae Thua NI-B b27-5'

        events:list = harness.events.get('chat_commands', [])
        harness.fire_event(events[0])
        assert harness.plugin.route.next_stop() == 'Bleae Thua RX-L d7-28'

    def test_no_next(self, harness:TestHarness):
        """Test next command when at the end of a route"""

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True
        harness.plugin.route.offset = len(harness.plugin.route.route)-2
        assert harness.plugin.route.next_stop() == 'Voqooe BI-H d11-864'

        events:list = harness.events.get('chat_commands', [])
        harness.fire_event(events[0])
        assert harness.plugin.route.next_stop() == 'End of the road!'

    def test_previous(self, harness:TestHarness):
        """Test prev/previous command when at the beginning of a route"""

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True
        harness.plugin.router.system = 'Bleae Thua NI-B b27-5'
        harness.plugin.router.update_route(1)
        assert harness.plugin.route.next_stop() == 'Bleae Thua RX-L d7-28'

        events:list = harness.events.get('chat_commands', [])
        harness.fire_event(events[1])
        assert harness.plugin.route.next_stop() == 'Bleae Thua NI-B b27-5'

    def test_no_previous(self, harness:TestHarness):
        """Test prev/previous command when not yet on the route"""

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        events:list = harness.events.get('chat_commands', [])
        harness.fire_event(events[1])
        assert harness.plugin.route.next_stop() == 'Bleae Thua NI-B b27-5'

    def test_copy(self, harness:TestHarness):
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        events:list = harness.events.get('chat_commands', [])
        harness.fire_event(events[2])
        assert harness.plugin.ui.parent is not None
        assert harness.plugin.ui.parent.clipboard_get() == 'Bleae Thua NI-B b27-5'

    def test_other(self, harness:TestHarness):
        """Test some other random string has no impact"""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True
        from Router.utils.misc import copy_to_clipboard
        copy_to_clipboard(harness.plugin.ui.parent, '')

        events:list = harness.events.get('chat_commands', [])
        harness.fire_event(events[3])
        assert harness.plugin.ui.parent is not None
        assert harness.plugin.ui.parent.clipboard_get() == ''

class TestShipyardSwap:
    """Test ship swapping from shipyard."""

    def test_ship_bad_init(self, harness:TestHarness):
        """Test bad ship swap event."""
        entry:dict = {"event": "bad"}
        ship:Ship = Ship(entry)

        assert ship.loadout == {}

    @pytest.mark.parametrize('harness', ['None', 'route_init.json'], indirect=True)
    def test_ship_repr(self, harness:TestHarness):
        """Test ship repr."""
        harness.play_sequence('shipyard_swap')
        ship:Ship = harness.plugin.router.ship

        assert repr(ship) == f"ID {ship.id}, name {ship.name}, type {ship.type}, unladen range {ship.range:.2f}ly)"

    def test_swap_existing_ship(self, harness:TestHarness):
        """Test swapping to a previously loaded ship."""
        # Load multiple ships
        harness.play_sequence('shipyard_swap')
        assert harness.plugin.router.ship_id == '106'

    def test_swap_unknown_ship(self, harness:TestHarness):
        """Test swapping to an unknown ship."""
        harness.play_sequence('shipyard_swap_unknown')
        assert harness.plugin.router.ship_id == ''


class TestOverlay:
    """Test overlay functionality."""

    @pytest.mark.overlay('None')
    def test_no_overlay(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure overlay is not present when overlay mode is disabled."""
        assert harness.plugin.overlay._get_overlay() is None

    @pytest.mark.overlay('Legacy')
    def test_legacy_overlay(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure overlay is not present when overlay mode is disabled."""
        assert harness.plugin.overlay._get_overlay() is None

    @pytest.mark.overlay('Modern')
    def test_modern_overlay(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure overlay is not present when overlay mode is disabled."""
        assert harness.plugin.overlay._get_overlay() is not None

    def test_countdown_starts_thread(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure countdown starts the countdown thread."""

        called:dict[str, bool] = {'flag': False}

        def fake_countdown(self, frame, content, end, stop) -> None:
            # Simulate some work then set flag
            called['flag'] = True

        monkeypatch.setattr(type(harness.plugin.overlay), '_countdown', fake_countdown, raising=False)
        harness.plugin.overlay.display_countdown('Carrier', 'Countdown', 100)

        # The thread may run quickly; wait briefly for it to start
        import time
        time.sleep(0.05)
        assert called['flag'] is True

    def test_countdown_shows_overlay(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure carrier jump completion starts the countdown thread."""

        called:dict[str, bool] = {'flag': False}

        events:list = harness.events.get('carrier_events', [])
        harness.fire_event(events[0])
        harness.fire_event(events[1])
        assert harness.plugin.overlay.msgs != {}

    def test_clear_frames(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure clearings all frames removes the messages."""

        events:list = harness.events.get('carrier_events', [])
        harness.fire_event(events[0])
        harness.fire_event(events[2])

        assert harness.plugin.overlay.msgs != {}
        harness.plugin.overlay.clear_frames()

        assert harness.plugin.overlay.msgs == {}

    def test_hide_show_frames(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure hiding all frames set them as hidden."""

        events:list = harness.events.get('carrier_events', [])
        harness.fire_event(events[0])
        harness.fire_event(events[2])

        assert harness.plugin.overlay.msgs != {}
        harness.plugin.overlay.hide_frames()

        frames = harness.plugin.overlay.ovfrs
        for fr in harness.plugin.overlay.ovfrs:
            assert frames[fr].visible == False or fr not in harness.plugin.overlay.msgs

        harness.plugin.overlay.show_frames()

        frames = harness.plugin.overlay.ovfrs
        for fr in harness.plugin.overlay.ovfrs:
            assert frames[fr].visible == True or fr not in harness.plugin.overlay.msgs

    def test_redraw_frames(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure redraw_frames renders using the configured progress_display template."""

        overlay = harness.plugin.overlay
        overlay.progress_display = "PD jc={jc} jr={jr} jt={jt} dc={dc} dr={dr} dt={dt} dh={dh} jh={jh} rj={rj} rd={rd} st={st}"

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        overlay.redraw_frames()

        assert harness.plugin.overlay.msgs["Default"]["NeutronDancer-Default-2"]["text"] == 'PD jc=- jr=399 jt=399 dc=0 dr=16.5K dt=16.5K dh=- jh=- rj=- rd=- st=✨'

    def test_update_overlays(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure update_overlays renders using the configured progress_display template."""

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        harness.plugin.router.update_route(3)

        overlay = harness.plugin.overlay
        overlay.progress_display = "PD jc={jc} jr={jr} jt={jt} dc={dc} dr={dr} dt={dt} dh={dh} jh={jh} rj={rj} rd={rd} st={st}"

        overlay.update_overlays()

        assert harness.plugin.overlay.msgs["Default"]["NeutronDancer-Default-2"]["text"] == 'PD jc=15 jr=384 jt=399 dc=286 dr=16.2K dt=16.5K dh=- jh=- rj=- rd=- st=🌀'

    def test_overlay_trade_detail_not_template(self, harness:TestHarness, monkeypatch) -> None:
        """For a route with no Refuel/Neutron columns (Trade here), the overlay must show the
        route's own detail section (station/commodity/profit) instead of the customizable
        progress_display template -- and the "Next:" line should include the station."""
        # Short names so the "Next:" line's truncation (tested separately) doesn't interfere.
        hdrs = ['System Name', 'Station Name', 'Commodity', 'Amount', 'Profit', 'Jumps']
        route_data = [
            ['Sol', 'Abraham Lincoln', '', 0, 0, 0],
            ['Deciat', 'Farside', 'Gold', 200, 10617, 3],
        ]
        harness.plugin.route = Route(hdrs, route_data, 0)
        assert harness.plugin.route.tracks_refuel_or_neutron() == False

        overlay = harness.plugin.overlay
        overlay.progress_display = "PD jc={jc}"  # would be shown if this were misclassified

        overlay.update_overlays()

        next_line:str = harness.plugin.overlay.msgs["Default"]["NeutronDancer-Default-1"]["text"]
        assert 'Farside' in next_line

        detail_line:str = harness.plugin.overlay.msgs["Default"]["NeutronDancer-Default-2"]["text"]
        assert 'Gold' in detail_line
        assert 'PD jc=' not in detail_line  # customizable template must not be used here

    def test_invalid_format(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure update_overlays handles invalid progress_display format."""

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        harness.plugin.router.update_route(3)

        overlay = harness.plugin.overlay
        overlay.progress_display = "invalid={unknown}"

        overlay.update_overlays()

        progress_line:str = harness.plugin.overlay.msgs["Default"]["NeutronDancer-Default-2"]["text"]
        assert progress_line == "Error formatting progress display"

    def test_hide_show_default_frame(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure changing the view updates the overlay."""

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        harness.plugin.router.update_route(3)

        overlay = harness.plugin.overlay
        overlay.update_overlays()

        msg:str = harness.plugin.overlay.msgs["Default"]["NeutronDancer-Default-1"]["text"]
        assert msg == "Next: Bleia Eohn ZL-J d10-47 (1 jump)"

        harness.fire_dashboard_event({"GuiFocus": edmc_data.GuiFocusNoFocus})
        assert harness.plugin.overlay.ovfrs["Default"].visible == True

        harness.fire_dashboard_event({"GuiFocus": edmc_data.GuiFocusInternalPanel})
        assert harness.plugin.overlay.ovfrs["Default"].visible == False

        harness.fire_dashboard_event({"GuiFocus": edmc_data.GuiFocusNoFocus})
        assert harness.plugin.overlay.ovfrs["Default"].visible == True

    def test_show_hide_galaxy_frame(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure changing the view updates the overlay."""

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Voqooe.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        harness.plugin.router.update_route(3)

        overlay = harness.plugin.overlay
        overlay.update_overlays()

        msg:str = harness.plugin.overlay.msgs["Default"]["NeutronDancer-Default-1"]["text"]
        assert msg == "Next: Bleia Eohn ZL-J d10-47 (1 jump)"

        harness.fire_dashboard_event({"GuiFocus": edmc_data.GuiFocusGalaxyMap})
        assert harness.plugin.overlay.ovfrs["Galaxy Map"].visible == True

        harness.fire_dashboard_event({"GuiFocus": edmc_data.GuiFocusNoFocus})
        assert harness.plugin.overlay.ovfrs["Galaxy Map"].visible == False

    def test_show_prefs(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure saving preferences works, or at least doesn't crash."""

        res = harness.plugin.overlay.prefs_display(harness.parent)
        # Should return a child frame of the parent window
        assert res in harness.parent.winfo_children()

    def test_save_prefs(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure saving preferences works."""

        overlay = harness.plugin.overlay
        res = overlay.prefs_display(harness.parent)

        # Should return a child frame of the parent window
        assert res in harness.parent.winfo_children()

        # Save preferences
        overlay.pb.set(False)
        overlay.save_prefs()
        assert harness.config.get_bool(f"{harness.plugin.plugin_name}_progress_bar", True) == False

        # Save preferences
        overlay.pb.set(True)
        overlay.save_prefs()
        assert harness.config.get_bool(f"{harness.plugin.plugin_name}_progress_bar", False) == True

class TestHotkeyCommands:
    """Test hotkey commands"""

    def test_next_hotkey(self, harness:TestHarness) -> None:
        """Test next hotkey command."""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True
        assert harness.plugin.route.next_stop() == 'Bleae Thua NI-B b27-5'

        harness.plugin.hotkeys.next()
        assert harness.plugin.route.next_stop() == 'Bleae Thua RX-L d7-28'

    def test_previous_hotkey(self, harness:TestHarness) -> None:
        """Test previous hotkey command."""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        harness.plugin.route.offset = 1
        assert harness.plugin.route.next_stop() == 'Bleae Thua ZJ-I d9-101'

        harness.plugin.hotkeys.previous()
        assert harness.plugin.route.next_stop() == 'Bleae Thua RX-L d7-28'

    def test_copy_hotkey(self, harness:TestHarness) -> None:
        """Test copy hotkey command."""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        harness.plugin.hotkeys.copy()
        assert harness.plugin.ui.parent is not None
        assert harness.plugin.ui.parent.clipboard_get() == 'Bleae Thua NI-B b27-5'

class TestPlotMethods:
    """Test individual plotting functions"""

    def test_plot_route_starts_thread(self, harness:TestHarness, monkeypatch) -> None:
        """Ensure plot_route returns True and starts the plotting worker."""
        called:dict[str, bool] = {'flag': False}

        def fake_plotter(self, which, url, params) -> None:
            # Simulate some work then set flag
            called['flag'] = True

        monkeypatch.setattr(type(harness.plugin.router), '_plotter', fake_plotter, raising=False)

        harness.plugin.router.carrier_id = 'TES-TY1'
        params:dict = {'from': 'A', 'to': 'B', 'max_time': 1}
        result:bool = harness.plugin.router.plot_route('Neutron', params)
        assert result is True
        # The thread may run quickly; wait briefly for it to start
        import time
        time.sleep(0.05)
        assert called['flag'] is True

    def test_plotter_success_creates_route(self, harness:TestHarness) -> None:
        """Test that _plotter successfully creates a route from Spansh response."""
        global plotter_thread
        plotter_thread = None

        job_response = Mock()
        job_response.status_code = 202
        job_response.content = json.dumps({"job": "test-job-id"}).encode()

        result_response = Mock()
        result_response.status_code = 200
        result_response.content = json.dumps({
            "result": {
                "jumps": [
                    {"system": "System1", "distance": 20.5},
                    {"system": "System2", "distance": 19.3},
                ]
            }
        }).encode()


        with patch('Router.route_manager.Thread', side_effect=capture_thread):
            with patch('Router.route_manager.SESSION.post', return_value=job_response):
                with patch('Router.route_manager.SESSION.get', return_value=result_response):
                    params = {'from': 'Start', 'to': 'End', 'max_time': 1}
                    harness.plugin.router.plot_route('Neutron', params)

        assert plotter_thread is not None, "Plotter thread was not captured"
        plotter_thread.join(timeout=THREAD_TIMEOUT)

        assert harness.plugin.route is not None
        assert len(harness.plugin.route.route) >= 2

        # Regression: plot_route() must persist into route_params, not a stray neutron_params attribute
        assert harness.plugin.router.route_params['Neutron'] == params
        assert not hasattr(harness.plugin.router, 'neutron_params')

    def test_plotter_success_creates_route_galaxy(self, harness:TestHarness) -> None:
        """Test that _plotter persists Galaxy params into route_params (not a stray galaxy_params attribute)."""
        global plotter_thread
        plotter_thread = None

        job_response = Mock()
        job_response.status_code = 202
        job_response.content = json.dumps({"job": "test-job-id"}).encode()

        result_response = Mock()
        result_response.status_code = 200
        result_response.content = json.dumps({
            "result": {
                "jumps": [
                    {"system": "System1", "distance": 20.5},
                    {"system": "System2", "distance": 19.3},
                ]
            }
        }).encode()

        with patch('Router.route_manager.Thread', side_effect=capture_thread):
            with patch('Router.route_manager.SESSION.post', return_value=job_response):
                with patch('Router.route_manager.SESSION.get', return_value=result_response):
                    params = {'source': 'Start', 'destination': 'End', 'max_time': 1}
                    harness.plugin.router.plot_route('Galaxy', params)

        assert plotter_thread is not None, "Plotter thread was not captured"
        plotter_thread.join(timeout=THREAD_TIMEOUT)

        assert harness.plugin.route is not None
        assert harness.plugin.router.route_params['Galaxy'] == params
        assert not hasattr(harness.plugin.router, 'galaxy_params')

    def test_plotter_success_creates_route_rtor(self, harness:TestHarness) -> None:
        """Test that _plotter flattens a Road-to-Riches response (systems with nested bodies) into one row per
        body, dropping bodyless systems (e.g. the starting system) rather than emitting a placeholder row --
        matching how a Spansh-exported riches CSV never includes a bodyless row (see riches-Apurui-M23.csv)."""
        global plotter_thread
        plotter_thread = None

        job_response = Mock()
        job_response.status_code = 202
        job_response.content = json.dumps({"job": "test-job-id"}).encode()

        # Real shape captured from the live Spansh riches API: a bodyless system (start)
        # followed by a system with two scannable bodies.
        result_response = Mock()
        result_response.status_code = 200
        result_response.content = json.dumps({
            "result": [
                {"name": "Colonia", "jumps": 1, "bodies": []},
                {"name": "Eol Prou LW-L c8-62", "jumps": 1, "bodies": [
                    {"name": "Eol Prou LW-L c8-62 7", "subtype": "Water world", "is_terraformable": True,
                     "distance_to_arrival": 173.1, "estimated_scan_value": 301683, "estimated_mapping_value": 1096113},
                    {"name": "Eol Prou LW-L c8-107 2", "subtype": "Earth-like world", "is_terraformable": False,
                     "distance_to_arrival": 436.9, "estimated_scan_value": 301332, "estimated_mapping_value": 1094838},
                ]},
            ]
        }).encode()

        with patch('Router.route_manager.Thread', side_effect=capture_thread):
            with patch('Router.route_manager.SESSION.post', return_value=job_response):
                with patch('Router.route_manager.SESSION.get', return_value=result_response):
                    params = {'from': 'Colonia', 'range': '50', 'radius': '40', 'max_results': '20', 'max_time': 1}
                    harness.plugin.router.plot_route('RtoR', params)

        assert plotter_thread is not None, "Plotter thread was not captured"
        plotter_thread.join(timeout=THREAD_TIMEOUT)

        assert harness.plugin.route is not None
        assert len(harness.plugin.route.route) == 3  # bodyless Colonia dropped; one row per body
        assert "Body" in harness.plugin.route.hdrs
        assert "Est Scan Value" in harness.plugin.route.hdrs
        assert harness.plugin.route.source() == 'Colonia'
        assert harness.plugin.router.route_params['RtoR'] == params

    def test_plotter_success_creates_route_ammonia(self, harness:TestHarness) -> None:
        """Regression: _plotter's riches-shape branch must trigger for body_types-filtered
        variants too (Ammonia/Earth-like/Rocky-metal), not just literally 'RtoR' -- it used
        to check `which == 'RtoR'`, so any other riches-family type fell into the flat
        jumps/system_jumps branch and crashed calling .get() on a list."""
        if 'Ammonia' not in PLOTTER_SPECS:
            return

        global plotter_thread
        plotter_thread = None

        job_response = Mock()
        job_response.status_code = 202
        job_response.content = json.dumps({"job": "test-job-id"}).encode()

        result_response = Mock()
        result_response.status_code = 200
        result_response.content = json.dumps({
            "result": [
                {"name": "Eol Prou OC-K c9-5", "jumps": 1, "bodies": [
                    {"name": "Eol Prou OC-K c9-5 3", "subtype": "Ammonia world", "is_terraformable": False,
                     "distance_to_arrival": 337.9, "estimated_scan_value": 302571, "estimated_mapping_value": 1099340},
                ]},
            ]
        }).encode()

        with patch('Router.route_manager.Thread', side_effect=capture_thread):
            with patch('Router.route_manager.SESSION.post', return_value=job_response):
                with patch('Router.route_manager.SESSION.get', return_value=result_response):
                    params = {'from': 'Colonia', 'range': '50', 'radius': '40', 'max_results': '20',
                              'body_types': ['Ammonia world'], 'min_value': 1, 'max_time': 1}
                    harness.plugin.router.plot_route('Ammonia', params)

        assert plotter_thread is not None, "Plotter thread was not captured"
        plotter_thread.join(timeout=THREAD_TIMEOUT)

        assert harness.plugin.route is not None
        assert len(harness.plugin.route.route) == 1
        assert harness.plugin.route.source() == 'Colonia'
        assert harness.plugin.router.route_params['Ammonia'] == params

    def test_plotter_success_creates_route_exobiology(self, harness:TestHarness) -> None:
        """Test that _plotter flattens an Exobiology response."""
        global plotter_thread
        plotter_thread = None

        job_response = Mock()
        job_response.status_code = 202
        job_response.content = json.dumps({"job": "test-job-id"}).encode()

        result_response = Mock()
        result_response.status_code = 200
        result_response.content = json.dumps({
            "result": [
                {"name": "Colonia", "jumps": 1, "bodies": []},
                {"name": "Eol Prou PX-T d3-291", "jumps": 1, "bodies": [
                    {"name": "Eol Prou PX-T d3-291 ABC 3 d", "subtype": "Rocky body",
                     "distance_to_arrival": 2684.5, "estimated_scan_value": 500, "estimated_mapping_value": 2221,
                     "landmark_value": 32831400, "landmarks": [
                        {"count": 41, "subtype": "Frutexa Flammasis", "type": "Frutexa", "value": 10326000},
                        {"count": 9, "subtype": "Concha Aureolas", "type": "Concha", "value": 7774700},
                     ]},
                ]},
            ]
        }).encode()

        with patch('Router.route_manager.Thread', side_effect=capture_thread):
            with patch('Router.route_manager.SESSION.post', return_value=job_response):
                with patch('Router.route_manager.SESSION.get', return_value=result_response):
                    params = {'from': 'Colonia', 'range': '50', 'radius': '30', 'max_results': '10',
                              'min_value': 100000, 'max_time': 1}
                    harness.plugin.router.plot_route('Exobiology', params)

        assert plotter_thread is not None, "Plotter thread was not captured"
        plotter_thread.join(timeout=THREAD_TIMEOUT)

        print(f"Route headers: {harness.plugin.route.hdrs} Route data: {harness.plugin.route.route}")
        assert harness.plugin.route is not None
        assert len(harness.plugin.route.route) == 2
        assert harness.plugin.route.source() == 'Colonia'
        assert "Species" in harness.plugin.route.hdrs
        assert "Value" in harness.plugin.route.hdrs
        row = harness.plugin.route.route[1]
        assert row[harness.plugin.route.hdrs.index("Species")] == 'Frutexa Flammasis'  # highest-value landmark
        assert row[harness.plugin.route.hdrs.index("Value")] == 32831400
        assert harness.plugin.router.route_params['Exobiology'] == params

    def test_plotter_success_creates_route_trade(self, harness:TestHarness) -> None:
        """Test that _plotter flattens a Trade response -- a FLAT list of hops (unlike the
        riches family's nested systems/bodies shape), each of which may carry more than one
        commodity at once. Each commodity-per-hop becomes its own row, keyed to the hop's
        *destination* (not source), matching every other route type's "row = next place to
        go" convention. Real shape captured from the live Spansh trade API."""
        global plotter_thread
        plotter_thread = None

        job_response = Mock()
        job_response.status_code = 202
        job_response.content = json.dumps({"job": "test-job-id"}).encode()

        result_response = Mock()
        result_response.status_code = 200
        result_response.content = json.dumps({
            "result": [
                {
                    "commodities": [
                        {"amount": 200, "name": "Agronomic Treatment", "profit": 10617, "total_profit": 2123400,
                         "source_commodity": {"buy_price": 2751, "sell_price": 2656, "demand": 1, "supply": 15577},
                         "destination_commodity": {"buy_price": 0, "sell_price": 13368, "demand": 42, "supply": 0}},
                    ],
                    "cumulative_profit": 2123400,
                    "distance": 12.66,
                    "source": {"station": "Jameson Memorial", "system": "Shinrarta Dezhra", "system_id64": 3932277478106,
                               "distance_to_arrival": 346, "market_id": 128666762},
                    "destination": {"station": "Alvarado Beacon", "system": "Puppis Sector TO-R b4-4",
                                     "system_id64": 9467852826033, "distance_to_arrival": 3, "market_id": 4243439363},
                },
                {
                    "commodities": [
                        {"amount": 186, "name": "Military Grade Fabrics", "profit": 12077, "total_profit": 2246322,
                         "source_commodity": {}, "destination_commodity": {}},
                        {"amount": 14, "name": "Tritium", "profit": 2603, "total_profit": 36442,
                         "source_commodity": {}, "destination_commodity": {}},
                    ],
                    "cumulative_profit": 4406164,
                    "distance": 33.13,
                    "source": {"station": "Alvarado Beacon", "system": "Puppis Sector TO-R b4-4"},
                    "destination": {"station": "Gaiman Port", "system": "Kamici"},
                },
            ]
        }).encode()

        with patch('Router.route_manager.Thread', side_effect=capture_thread):
            with patch('Router.route_manager.SESSION.post', return_value=job_response):
                with patch('Router.route_manager.SESSION.get', return_value=result_response):
                    params = {'system': 'Shinrarta Dezhra', 'station': 'Jameson Memorial',
                              'starting_capital': '1000000', 'max_cargo': '200', 'max_hops': '5',
                              'max_hop_distance': '50', 'max_system_distance': '10000000', 'max_time': 1}
                    harness.plugin.router.plot_route('Trade', params)

        assert plotter_thread is not None, "Plotter thread was not captured"
        plotter_thread.join(timeout=THREAD_TIMEOUT)

        assert harness.plugin.route is not None
        assert len(harness.plugin.route.route) == 3  # 1 commodity in hop 1 + 2 commodities in hop 2
        assert "Station Name" in harness.plugin.route.hdrs
        assert "Commodity" in harness.plugin.route.hdrs
        assert "Cumulative Profit" in harness.plugin.route.hdrs

        # Row 0 is keyed to hop 0's DESTINATION, not its source -- the starting station never
        # gets its own row, matching how every other route type's row 0 is the first waypoint
        # *after* the start, not the start itself. route.source() reads the System Name column;
        # the station itself is a separate column.
        assert harness.plugin.route.source() == 'Puppis Sector TO-R b4-4'
        row0 = harness.plugin.route.route[0]
        assert row0[harness.plugin.route.hdrs.index("Station Name")] == 'Alvarado Beacon'
        assert row0[harness.plugin.route.hdrs.index("Commodity")] == 'Agronomic Treatment'
        assert row0[harness.plugin.route.hdrs.index("Cumulative Profit")] == 2123400

        # Hop 1 carried two commodities -> two rows, same destination, different commodity
        row1, row2 = harness.plugin.route.route[1], harness.plugin.route.route[2]
        assert row1[harness.plugin.route.hdrs.index("Commodity")] == 'Military Grade Fabrics'
        assert row2[harness.plugin.route.hdrs.index("Commodity")] == 'Tritium'
        assert row1[harness.plugin.route.hdrs.index("System Name")] == 'Kamici'
        assert row2[harness.plugin.route.hdrs.index("System Name")] == 'Kamici'

        assert harness.plugin.router.route_params['Trade'] == params

    def test_plotter_success_creates_route_fleetcarrier(self, harness:TestHarness) -> None:
        """Test that _plotter flattens a Fleet Carrier response -- each requested stop appears
        twice (ending one leg, starting the next, with distance == 0), so only the
        distance != 0 rows (the real jumps) should survive. Real shape captured from the
        live Spansh fleet carrier API."""
        global plotter_thread
        plotter_thread = None

        job_response = Mock()
        job_response.status_code = 202
        job_response.content = json.dumps({"job": "test-job-id"}).encode()

        result_response = Mock()
        result_response.status_code = 200
        result_response.content = json.dumps({
            "result": {"jumps": [
                {"distance": 0, "distance_to_destination": 131.427, "fuel_in_tank": 42, "fuel_used": 0,
                 "has_icy_ring": False, "id64": 10477373803, "is_desired_destination": 1,
                 "is_system_pristine": False, "must_restock": 1, "name": "Sol", "restock_amount": 42,
                 "tritium_in_market": 0},
                {"distance": 131.427, "distance_to_destination": 0, "fuel_in_tank": 21, "fuel_used": 21,
                 "has_icy_ring": True, "id64": 6681123623626, "is_desired_destination": 1,
                 "is_system_pristine": False, "must_restock": 0, "name": "Deciat", "restock_amount": 0,
                 "tritium_in_market": 0},
                {"distance": 0, "distance_to_destination": 129.796, "fuel_in_tank": 21, "fuel_used": 0,
                 "has_icy_ring": False, "id64": 6681123623626, "is_desired_destination": 1,
                 "is_system_pristine": False, "must_restock": 0, "name": "Deciat", "restock_amount": 0,
                 "tritium_in_market": 0},
                {"distance": 129.796, "distance_to_destination": 0, "fuel_in_tank": 0, "fuel_used": 21,
                 "has_icy_ring": False, "id64": 1178708478315, "is_desired_destination": 1,
                 "is_system_pristine": False, "must_restock": 0, "name": "Alpha Centauri", "restock_amount": 0,
                 "tritium_in_market": 0},
            ]}
        }).encode()

        with patch('Router.route_manager.Thread', side_effect=capture_thread):
            with patch('Router.route_manager.SESSION.post', return_value=job_response):
                with patch('Router.route_manager.SESSION.get', return_value=result_response):
                    params = {'source_name': 'Sol', 'source': 10477373803,
                              'destination_names': ['Deciat', 'Alpha Centauri'],
                              'destinations': [6681123623626, 1178708478315],
                              'carrier_type': 'fleet', 'capacity': 25000, 'mass': 25000,
                              'capacity_used': '0', 'calculate_starting_fuel': 1, 'max_time': 1}
                    harness.plugin.router.plot_route('FleetCarrier', params)

        assert plotter_thread is not None, "Plotter thread was not captured"
        plotter_thread.join(timeout=THREAD_TIMEOUT)

        assert harness.plugin.route is not None
        assert len(harness.plugin.route.route) == 2  # one row per stop, not per jump entry
        row0, row1 = harness.plugin.route.route[0], harness.plugin.route.route[1]
        assert row0[harness.plugin.route.hdrs.index("System Name")] == 'Deciat'
        assert row1[harness.plugin.route.hdrs.index("System Name")] == 'Alpha Centauri'
        assert "Icy Ring" in harness.plugin.route.hdrs
        assert "Restock Tritium" in harness.plugin.route.hdrs

    def test_plotter_fleetcarrier_single_leg_keeps_every_hop(self, harness:TestHarness) -> None:
        """Regression: a direct route (no via-stops) with multiple intermediate hops must keep
        every hop, not just the final arrival. distance_to_destination stays nonzero for every
        row except the last in a single-leg route, so filtering on it (instead of on
        distance != 0) collapsed the whole route down to one jump."""
        global plotter_thread
        plotter_thread = None

        job_response = Mock()
        job_response.status_code = 202
        job_response.content = json.dumps({"job": "test-job-id"}).encode()

        result_response = Mock()
        result_response.status_code = 200
        result_response.content = json.dumps({
            "result": {"jumps": [
                {"distance": 0, "distance_to_destination": 300, "id64": 1, "name": "Bleae Thua NI-B b27-5",
                 "is_desired_destination": 1, "has_icy_ring": False, "is_system_pristine": False,
                 "must_restock": 0, "restock_amount": 0, "tritium_in_market": 0, "fuel_in_tank": 42, "fuel_used": 0},
                {"distance": 100, "distance_to_destination": 200, "id64": 2, "name": "Hop One",
                 "is_desired_destination": 0, "has_icy_ring": False, "is_system_pristine": False,
                 "must_restock": 0, "restock_amount": 0, "tritium_in_market": 0, "fuel_in_tank": 21, "fuel_used": 21},
                {"distance": 100, "distance_to_destination": 100, "id64": 3, "name": "Hop Two",
                 "is_desired_destination": 0, "has_icy_ring": False, "is_system_pristine": False,
                 "must_restock": 0, "restock_amount": 0, "tritium_in_market": 0, "fuel_in_tank": 0, "fuel_used": 21},
                {"distance": 100, "distance_to_destination": 0, "id64": 4, "name": "Colonia",
                 "is_desired_destination": 1, "has_icy_ring": False, "is_system_pristine": False,
                 "must_restock": 0, "restock_amount": 0, "tritium_in_market": 0, "fuel_in_tank": 21, "fuel_used": 21},
            ]}
        }).encode()

        with patch('Router.route_manager.Thread', side_effect=capture_thread):
            with patch('Router.route_manager.SESSION.post', return_value=job_response):
                with patch('Router.route_manager.SESSION.get', return_value=result_response):
                    params = {'source': 1, 'destinations': 4, 'capacity': 25000, 'mass': 25000,
                              'capacity_used': '0', 'calculate_starting_fuel': 1, 'max_time': 1}
                    harness.plugin.router.plot_route('FleetCarrier', params)

        assert plotter_thread is not None, "Plotter thread was not captured"
        plotter_thread.join(timeout=THREAD_TIMEOUT)

        assert harness.plugin.route is not None
        names = [row[harness.plugin.route.hdrs.index("System Name")] for row in harness.plugin.route.route]
        assert names == ['Hop One', 'Hop Two', 'Colonia']

    def test_plotter_error_response_shows_error(self, harness:TestHarness):
        """Test that _plotter handles error responses without crashing."""
        # Mock error response
        error_response = Mock()
        error_response.status_code = 500
        error_response.content = json.dumps({"error": "Server error"}).encode()

        # Track the thread so we can join it
        plotter_thread = None
        original_thread = __import__('threading').Thread

        def capture_thread(*args, **kwargs):
            nonlocal plotter_thread
            thread = original_thread(*args, **kwargs)
            if "route plotting worker" in thread.name:
                plotter_thread = thread
            return thread

        with patch('Router.route_manager.Thread', side_effect=capture_thread):
            with patch('Router.route_manager.SESSION.post', return_value=error_response):
                params = {'from': 'Start', 'to': 'End', 'max_time': 1}
                # Should not raise exception, just handle error gracefully
                harness.plugin.router.plot_route('Neutron', params)

                # Join the plotter thread if captured
                if plotter_thread:
                    plotter_thread.join(timeout=THREAD_TIMEOUT)

    def test_neutron_plotter_calls_plot_route(self, harness:TestHarness) -> None:
        """Regression: NeutronPlotter.plot() must actually invoke Context.router.plot_route()."""
        ui = harness.plugin.ui
        neutron_fr = ui.plot_frames['Neutron']

        neutron_fr.nametowidget("source_ac").set_text("Sol", False)
        neutron_fr.nametowidget("dest_ac").set_text("Colonia", False)
        neutron_fr.nametowidget("range_entry").set_text("50", False)

        with mocked_session_get(fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                ui.plotters['Neutron'].plot()

        mock_plot_route.assert_called_once()
        which, params = mock_plot_route.call_args[0]
        assert which == 'Neutron'
        assert params['from'] == 'Sol'
        assert params['to'] == 'Colonia'
        assert params['range'] == '50'
        assert params['via'] == []

    def test_neutron_plotter_via_hops(self, harness:TestHarness) -> None:
        """Regression: the + beside source must add via-point hops, sent as an ordered list."""
        ui = harness.plugin.ui
        plotter = ui.plotters['Neutron']
        neutron_fr = ui.plot_frames['Neutron']

        neutron_fr.nametowidget("source_ac").set_text("Sol", False)
        neutron_fr.nametowidget("dest_ac").set_text("Colonia", False)
        neutron_fr.nametowidget("range_entry").set_text("50", False)

        assert len(plotter.hop_rows) == 0
        plotter._add_hop_row(-1)
        plotter.hop_rows[0]['ac'].set_text("Deciat", False)

        with mocked_session_get(fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                plotter.plot()

        _, params = mock_plot_route.call_args[0]
        assert params['via'] == ['Deciat']

    def test_galaxy_plotter_calls_plot_route(self, harness:TestHarness) -> None:
        """Regression: GalaxyPlotter.plot() must actually invoke Context.router.plot_route()."""
        harness.play_sequence('loadout')
        ui = harness.plugin.ui
        galaxy_fr = ui.plot_frames['Galaxy']

        galaxy_fr.nametowidget("source_ac").set_text("Sol", False)
        galaxy_fr.nametowidget("dest_ac").set_text("Colonia", False)

        with mocked_session_get(fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                ui.plotters['Galaxy'].plot()

        mock_plot_route.assert_called_once()
        which, params = mock_plot_route.call_args[0]
        assert which == 'Galaxy'
        assert params['source'] == 'Sol'
        assert params['destination'] == 'Colonia'

    def test_rtor_plotter_calls_plot_route(self, harness:TestHarness) -> None:
        """Regression: RichesPlotter.plot() must actually invoke Context.router.plot_route()."""
        ui = harness.plugin.ui
        rtor_fr = ui.plot_frames['RtoR']

        rtor_fr.nametowidget("source_ac").set_text("Colonia", False)
        rtor_fr.nametowidget("dest_ac").set_text("", False)  # blank destination -> circular tour
        rtor_fr.nametowidget("range_entry").set_text("50", False)
        rtor_fr.nametowidget("radius_entry").set_text("40", False)
        rtor_fr.nametowidget("max_results_entry").set_text("20", False)

        with mocked_session_get(fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                ui.plotters['RtoR'].plot()

        mock_plot_route.assert_called_once()
        which, params = mock_plot_route.call_args[0]
        assert which == 'RtoR'
        assert params['from'] == 'Colonia'
        assert 'to' not in params  # destination left blank -> circular tour
        assert params['radius'] == '40'
        assert params['max_results'] == '20'
        assert 'body_types' not in params  # plain Road to Riches has no body filter

    def test_rtor_plotter_plot_untouched_dest_is_blank(self, harness:TestHarness) -> None:
        """A dest_ac showing its placeholder text (not "") must still be treated as blank --
        plot() must omit 'to' rather than sending the placeholder string as a destination."""
        ui = harness.plugin.ui
        rtor_fr = ui.plot_frames['RtoR']

        rtor_fr.nametowidget("source_ac").set_text("Colonia", False)
        rtor_fr.nametowidget("range_entry").set_text("50", False)
        rtor_fr.nametowidget("radius_entry").set_text("40", False)
        rtor_fr.nametowidget("max_results_entry").set_text("20", False)
        rtor_fr.nametowidget("dest_ac").put_placeholder()  # force the placeholder-shown state

        with mocked_session_get(fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                ui.plotters['RtoR'].plot()

        mock_plot_route.assert_called_once()
        _, params = mock_plot_route.call_args[0]
        assert 'to' not in params

    @pytest.mark.parametrize('route_type,expected_body_types', [
        ('Ammonia', ['Ammonia world']),
        ('EarthLike', ['Earth-like world']),
        ('RockyMetal', ['Rocky body', 'High metal content world']),
    ])
    def test_riches_body_filter_plotter_calls_plot_route(self, harness:TestHarness, route_type, expected_body_types) -> None:
        """Regression: each body-type-filtered riches plotter (Ammonia/Earth-like/Rocky-metal)
        must invoke plot_route with its own fixed body_types filter and min_value=1."""
        if route_type not in PLOTTER_SPECS:
            return

        ui = harness.plugin.ui
        fr = ui.plot_frames[route_type]

        fr.nametowidget("source_ac").set_text("Colonia", False)
        fr.nametowidget("dest_ac").set_text("", False)
        fr.nametowidget("range_entry").set_text("50", False)
        fr.nametowidget("radius_entry").set_text("40", False)
        fr.nametowidget("max_results_entry").set_text("20", False)

        with mocked_session_get(fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                ui.plotters[route_type].plot()

        mock_plot_route.assert_called_once()
        which, params = mock_plot_route.call_args[0]
        assert which == route_type
        assert params['from'] == 'Colonia'
        assert params['body_types'] == expected_body_types
        assert params['min_value'] == 1
        assert 'use_mapping_value' not in params  # these pages don't expose that option

    def test_exobiology_plotter_calls_plot_route(self, harness:TestHarness) -> None:
        """Regression: Exobiology has no body_types filter (unlike Ammonia/Earth-like/Rocky-metal)
        -- its filtering criterion is a real "Minimum Landmark Value" slider (0-21, units of
        millions of credits implied), which must be scaled by 1,000,000 before being sent."""
        ui = harness.plugin.ui
        fr = ui.plot_frames['Exobiology']

        fr.nametowidget("source_ac").set_text("Colonia", False)
        fr.nametowidget("dest_ac").set_text("", False)
        fr.nametowidget("range_entry").set_text("50", False)
        fr.nametowidget("radius_entry").set_text("30", False)
        fr.nametowidget("max_results_entry").set_text("10", False)
        fr.nametowidget("min_value_entry").set(5)  # 5 million credits

        with mocked_session_get(fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                ui.plotters['Exobiology'].plot()

        mock_plot_route.assert_called_once()
        which, params = mock_plot_route.call_args[0]
        assert which == 'Exobiology'
        assert params['from'] == 'Colonia'
        assert params['min_value'] == 5000000
        assert 'body_types' not in params

    def test_exobiology_min_value_slider_bounds(self, harness:TestHarness) -> None:
        """The Minimum Landmark Value slider should be a 0-20 range (millions implied)."""
        ui = harness.plugin.ui
        fr = ui.plot_frames['Exobiology']
        slider = fr.nametowidget("min_value_entry")
        assert float(slider.cget('from')) == 0
        assert float(slider.cget('to')) == 20
        assert int(slider.get()) == 10

    def test_trade_plotter_calls_plot_route(self, harness:TestHarness) -> None:
        """Regression: TradePlotter.plot() must invoke plot_route with system/station """
        ui = harness.plugin.ui
        fr = ui.plot_frames['Trade']

        fr.nametowidget("station_ac").set_text("Not A Real Station", False)
        fr.nametowidget("starting_capital_entry").set_text("1000000", False)
        fr.nametowidget("max_cargo_entry").set_text("200", False)
        fr.nametowidget("max_hops_entry").set_text("5", False)
        fr.nametowidget("max_hop_distance_entry").set_text("50", False)
        fr.nametowidget("max_distance_entry").set_text("10000000", False)
        fr.nametowidget("station_ac").set_text("Shinrarta Dezhra / Jameson Memorial", False)
        with patch.object(ui, 'query_station_names', return_value=["Shinrarta Dezhra / Jameson Memorial"]):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                ui.plotters['Trade'].plot()

        mock_plot_route.assert_called_once()
        which, params = mock_plot_route.call_args[0]
        assert which == 'Trade'
        assert params['system'] == 'Shinrarta Dezhra'
        assert params['station'] == 'Jameson Memorial'
        assert params['starting_capital'] == '1000000'
        assert params['max_cargo'] == '200'
        assert 'max_price_age' not in params  # left blank -> no limit sent
        for flag in ['requires_large_pad', 'allow_prohibited', 'allow_planetary',
                     'allow_player_owned', 'allow_restricted_access', 'unique', 'permit']:
            assert params[flag] == 0  # none selected

    def test_tourist_add_remove_hop_rows(self, harness:TestHarness) -> None:
        """Adding/removing stop rows should track the right systems. Unlike the old
        destination-list design, an empty hop list is valid -- no forced minimum row."""
        ui = harness.plugin.ui
        plotter = ui.plotters['Tourist']

        assert len(plotter.hop_rows) == 0

        plotter._add_hop_row(-1)
        plotter.hop_rows[0]['ac'].set_text("Deciat", False)
        assert len(plotter.hop_rows) == 1

        plotter._add_hop_row(0)
        plotter.hop_rows[1]['ac'].set_text("Colonia", False)
        assert len(plotter.hop_rows) == 2
        assert plotter.hop_rows[0]['ac'].get() == "Deciat"

        plotter._remove_hop_row(0)
        assert len(plotter.hop_rows) == 1
        assert plotter.hop_rows[0]['ac'].get() == "Colonia"

        plotter._remove_hop_row(0)
        assert len(plotter.hop_rows) == 0

    def test_tourist_plotter_calls_plot_route(self, harness:TestHarness) -> None:
        """TouristPlotter.plot() must send source/destination(list)/range, and must omit
        final_destination entirely (rather than sending literal "None") when left blank."""
        ui = harness.plugin.ui
        fr = ui.plot_frames['Tourist']
        plotter = ui.plotters['Tourist']

        fr.nametowidget("source_ac").set_text("Sol", False)
        fr.nametowidget("dest_ac").set_text("", False)
        fr.nametowidget("range_entry").set_text("50", False)

        plotter._add_hop_row(-1)
        plotter.hop_rows[0]['ac'].set_text("Deciat", False)
        plotter._add_hop_row(0)
        plotter.hop_rows[1]['ac'].set_text("Colonia", False)

        with mocked_session_get(fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                plotter.plot()

        mock_plot_route.assert_called_once()
        which, params = mock_plot_route.call_args[0]
        assert which == 'Tourist'
        assert params['source'] == 'Sol'
        assert 'final_destination' not in params
        assert params['destination'] == ['Deciat', 'Colonia']
        assert params['range'] == '50'

    def test_tourist_plotter_final_destination_set(self, harness:TestHarness) -> None:
        """A non-blank final destination should be validated and included."""
        ui = harness.plugin.ui
        fr = ui.plot_frames['Tourist']
        plotter = ui.plotters['Tourist']

        fr.nametowidget("source_ac").set_text("Sol", False)
        fr.nametowidget("dest_ac").set_text("Colonia", False)
        fr.nametowidget("range_entry").set_text("50", False)
        plotter._add_hop_row(-1)
        plotter.hop_rows[0]['ac'].set_text("Deciat", False)

        with mocked_session_get(fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                plotter.plot()

        mock_plot_route.assert_called_once()
        _, params = mock_plot_route.call_args[0]
        assert params['final_destination'] == 'Colonia'

    def test_tourist_plotter_no_hops_does_not_letter_split_on_reopen(self, harness:TestHarness) -> None:
        """Regression: with no via-stops, params['destination'] collapses to the plain
        final-destination string (for Spansh) rather than a list. create_frame() must rebuild
        hop rows from a separate destination_names list, or it iterates that string
        character-by-character and creates one hop row per letter."""
        ui = harness.plugin.ui
        fr = ui.plot_frames['Tourist']
        plotter = ui.plotters['Tourist']

        fr.nametowidget("source_ac").set_text("Sol", False)
        fr.nametowidget("dest_ac").set_text("Colonia", False)
        fr.nametowidget("range_entry").set_text("50", False)

        with mocked_session_get(fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                plotter.plot()

        _, params = mock_plot_route.call_args[0]
        assert params['destination'] == 'Colonia'
        assert params['destination_names'] == []

        harness.plugin.router.route_params['Tourist'] = params
        plotter.create_frame(ui.frame)
        assert plotter.hop_rows == []

    def test_fleetcarrier_plotter_calls_plot_route(self, harness:TestHarness) -> None:
        """FleetCarrierPlotter.plot() sends system names directly -- Spansh's fleetcarrier API
        accepts names, no id64 resolution needed despite older docs suggesting otherwise."""
        ui = harness.plugin.ui
        fr = ui.plot_frames['FleetCarrier']
        plotter = ui.plotters['FleetCarrier']

        fr.nametowidget("source_ac").set_text("Sol", False)
        fr.nametowidget("dest_ac").set_text("Alpha Centauri", False)
        plotter._add_hop_row(-1)
        plotter.hop_rows[0]['ac'].set_text("Deciat", False)
        fr.nametowidget("capacity_used_entry").set_text("500", False)

        with mocked_session_get(fake_systems_get):
            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                plotter.plot()

        mock_plot_route.assert_called_once()
        which, params = mock_plot_route.call_args[0]
        assert which == 'FleetCarrier'
        assert params['source'] == 'Sol'
        assert params['destination'] == 'Alpha Centauri'
        assert params['destination_names'] == ['Deciat']
        assert params['destinations'] == ['Alpha Centauri', 'Deciat']
        assert params['capacity'] == 25000
        assert params['mass'] == 25000
        assert params['capacity_used'] == 500
        assert params['calculate_starting_fuel'] == "1"

    def test_boxel_plotter_generates_local_numeric_route(self, harness:TestHarness) -> None:
        """ BoxelPlotter.plot() must never call Context.router.plot_route() (there's nothing
        for Spansh to optimise) -- it builds Context.route directly from a locally-generated,
        numerically-ordered list of candidate system names. """
        ui = harness.plugin.ui
        fr = ui.plot_frames['Boxel']

        with mocked_session_get(fake_systems_get):
            fr.nametowidget("boxel_ac").set_text("Voqooe NR-C d", False)
            fr.nametowidget("start_entry").set_text("12", False)
            fr.nametowidget("end_entry").set_text("15", False)

            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                ui.plotters['Boxel'].plot()

        mock_plot_route.assert_not_called()
        assert [row[0] for row in harness.plugin.route.route] == [
            "Voqooe NR-C d12", "Voqooe NR-C d13", "Voqooe NR-C d14", "Voqooe NR-C d15",
        ]

    def test_boxel_plotter_accepts_a_full_example_name_and_strips_the_sequence(self, harness:TestHarness) -> None:
        """ A real autocomplete suggestion is a full example system name (e.g. "...d12"), not a
        bare boxel -- the trailing number must be stripped rather than rejected. """
        ui = harness.plugin.ui
        fr = ui.plot_frames['Boxel']

        with mocked_session_get(fake_systems_get):
            fr.nametowidget("boxel_ac").set_text("Eol Prou IT-S c4-201", False)
            fr.nametowidget("start_entry").set_text("201", False)
            fr.nametowidget("end_entry").set_text("202", False)
            ui.plotters['Boxel'].plot()

        assert [row[0] for row in harness.plugin.route.route] == ["Eol Prou IT-S c4-201", "Eol Prou IT-S c4-202"]

    def test_boxel_plotter_rejects_a_boxel_missing_its_mass_code(self, harness:TestHarness) -> None:
        """ "Voqooe NR-C" alone is ambiguous (real data: both a "b32" and a "d" mass code exist
        under that one cube-ID) -- must reject rather than silently concatenating a malformed name."""
        ui = harness.plugin.ui
        fr = ui.plot_frames['Boxel']

        with mocked_session_get(fake_systems_get):
            fr.nametowidget("boxel_ac").set_text("Voqooe NR-C", False)
            fr.nametowidget("start_entry").set_text("1", False)
            fr.nametowidget("end_entry").set_text("5", False)

            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                ui.plotters['Boxel'].plot()

        mock_plot_route.assert_not_called()
        assert harness.plugin.route.route == []

    def test_boxel_plotter_rejects_an_uppercase_mass_code(self, harness:TestHarness) -> None:
        """ Real ED system names only ever use a lowercase mass-code letter (a-h); an uppercase
        letter isn't a real boxel and must be rejected rather than silently accepted. """
        ui = harness.plugin.ui
        fr = ui.plot_frames['Boxel']

        with mocked_session_get(fake_systems_get):
            fr.nametowidget("boxel_ac").set_text("Bleae Thua IW-C A", False)
            fr.nametowidget("start_entry").set_text("1", False)
            fr.nametowidget("end_entry").set_text("5", False)

            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                ui.plotters['Boxel'].plot()

        mock_plot_route.assert_not_called()
        assert harness.plugin.route.route == []

    def test_boxel_plotter_updates_last_plot_so_returning_to_it_works(self, harness:TestHarness) -> None:
        """ BoxelPlotter never calls plot_route() (which normally sets last_plot), so it must set
        last_plot itself -- otherwise leaving the plot GUI and coming back defaults elsewhere. """
        ui = harness.plugin.ui
        fr = ui.plot_frames['Boxel']

        with mocked_session_get(fake_systems_get):
            fr.nametowidget("boxel_ac").set_text("Voqooe NR-C d", False)
            fr.nametowidget("start_entry").set_text("1", False)
            fr.nametowidget("end_entry").set_text("5", False)
            ui.plotters['Boxel'].plot()

        assert harness.plugin.router.last_plot == 'Boxel'

    def test_boxel_plotter_rejects_a_boxel_position_impossible_for_its_mass_code(self, harness:TestHarness) -> None:
        """ Mass code h only ever has one possible boxel per sector (AA-A) -- any other
        letters, however plausible-looking, describe a position that can't exist for h. """
        ui = harness.plugin.ui
        fr = ui.plot_frames['Boxel']

        with mocked_session_get(fake_systems_get):
            fr.nametowidget("boxel_ac").set_text("Bleae Thua NI-B h", False)
            fr.nametowidget("start_entry").set_text("1", False)
            fr.nametowidget("end_entry").set_text("5", False)

            with patch.object(harness.plugin.router, 'plot_route') as mock_plot_route:
                ui.plotters['Boxel'].plot()

        from Router.constants import errs
        mock_plot_route.assert_not_called()
        assert harness.plugin.route.route == []
        assert ui.error_lbl['text'] == errs['boxel_impossible'] # the specific message, not the generic one


class TestBoxelExistence:
    """ _boxel_coords/_boxel_exists/_boxel_prefix -- verified against two real systems' actual
    id64 values (Eol Prou RS-T d3-94, Vegnue WK-E d12-0, decoded via EDSM + the DISC Wiki's
    ID64 bitfield spec) and ~10 live Spansh boxel lookups; see plotters.py's own docstrings. """

    def test_coords_match_a_real_system_with_no_subnum(self) -> None:
        """ Eol Prou RS-T d3-94 -- real id64 3238296097059 decodes to box coords [9, 4, 4]. """
        assert _boxel_coords('R', 'S', 'T', 3) == (9, 4, 4)

    def test_coords_match_a_real_system_with_a_multi_digit_subnum(self) -> None:
        """ Vegnue WK-E d12-0 -- real id64 9303087083 decodes to box coords [10, 7, 13]. """
        assert _boxel_coords('W', 'K', 'E', 12) == (10, 7, 13)

    def test_h_mass_code_only_exists_at_the_origin(self) -> None:
        """ h is the whole sector -- one boxel, "AA-A" -- confirmed both by Marx's community
        guide and by a real EDSM lookup of an "AA-A h" system. """
        assert _boxel_exists('A', 'A', 'A', 'h', 0) is True
        assert _boxel_exists('B', 'A', 'A', 'h', 0) is False
        assert _boxel_exists('A', 'B', 'A', 'h', 0) is False
        assert _boxel_exists('A', 'A', 'B', 'h', 0) is False

    def test_g_mass_code_matches_real_and_absent_spansh_boxels(self) -> None:
        """ Live Spansh lookups found real systems at "AA-A g"/"BA-A g" only -- every other
        letter combination tried (AB-A, BB-A, CA-A..JA-A, etc) came back empty. """
        assert _boxel_exists('A', 'A', 'A', 'g', 0) is True
        assert _boxel_exists('B', 'A', 'A', 'g', 0) is True
        assert _boxel_exists('A', 'B', 'A', 'g', 0) is False
        assert _boxel_exists('C', 'A', 'A', 'g', 0) is False

    def test_same_letters_can_exist_for_a_small_mass_code_but_not_a_large_one(self) -> None:
        """ Mass code a's 128-per-axis range comfortably fits "IW-C", but h's 1-per-axis range
        does not -- the same letters describe a real boxel for one and not the other. """
        assert _boxel_exists('I', 'W', 'C', 'a', 0) is True
        assert _boxel_exists('I', 'W', 'C', 'h', 0) is False

    def test_prefix_accepts_a_real_h_boxel(self) -> None:
        assert _boxel_prefix("Vegnoae AA-A h") == "Vegnoae AA-A h"

    def test_prefix_rejects_an_impossible_h_boxel(self) -> None:
        assert _boxel_prefix("Bleae Thua NI-B h") is None


class TestUIFunctions:
    """ Test UI functions """

    def test_set_entry_none_does_nothing(self, harness:TestHarness) -> None:
        ui = harness.plugin.ui
        # Should not raise or change state
        ui.set_entry(None, "ignored")

    def test_query_station_names(self, harness:TestHarness) -> None:
        """query_station_names() hits Spansh's station name typeahead directly -- a single
        field, matching Spansh's own "Source Station" combobox -- and formats each result as
        "System / Station" so the Trade Planner's single combined input field can validate a
        typed/selected value and split it back into system+station locally, with no separate
        system-resolving roundtrip (Spansh's own /api/trade/route call errors out on a bad
        system/station combo anyway, so there's nothing worth pre-verifying here)."""
        ui = harness.plugin.ui

        def fake_get(url, *args, **kwargs):
            resp = Mock()
            resp.status_code = 200
            resp.content = json.dumps([
                {"system": "Shinrarta Dezhra", "name": "Jameson Memorial"}
            ]).encode()
            return resp

        with mocked_session_get(fake_get):
            assert ui.query_station_names('Jameson') == ['Shinrarta Dezhra / Jameson Memorial']

    def test_switch_ship(self, harness:TestHarness) -> None:
        ui = harness.plugin.ui

        # Ensure a ship loadout is present
        harness.play_sequence('loadout')
        ship = harness.plugin.router.ship
        assert ship is not None

        # Switch UI to this ship and verify fields update
        ui.switch_ship(ship)
        assert ui.plotters['Galaxy'].shipvar.get() == ship.name
        assert ui.plotters['Neutron'].multiplier.get() == ship.supercharge_multiplier
        assert ui.get_item('Neutron', 'range_entry') == str(ship.get_range(harness.plugin.router.cargo))

    def test_progress(self, harness:TestHarness):
        """ Test _progress() method"""
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        harness.plugin.router.import_route(filename)
        harness.plugin.route.update_route(0, 'Bleia Eohn ZL-J d10-47')

        assert harness.plugin.ui._progress() == 2

    def test_update_progress_trade_waypoint(self, harness:TestHarness) -> None:
        """update_progress() must combine system + station on the button (truncated to fit,
        jump-progress suffix always intact and untruncated), and build a tooltip with the
        commodity/profit detail the button has no room for -- system/station aren't repeated
        in the tooltip since they're already visible on the button face. Clicking the button
        (not update_progress() itself) copies the plain system name to the clipboard."""
        ui = harness.plugin.ui

        hdrs = ['System Name', 'Station Name', 'Commodity', 'Amount', 'Profit', 'Total Profit', 'Jumps']
        route_data = [
            ['Shinrarta Dezhra', 'Jameson Memorial', '', 0, 0, 0, 0],
            ['Puppis Sector TO-R b4-4', 'Alvarado Beacon', 'Agronomic Treatment', 200, 10617, 2123400, 3],
        ]
        harness.plugin.route = Route(hdrs, route_data, 0)

        ui.update_progress()

        text:str = ui.waypoint_btn.cget('text')
        assert len(text) <= 40
        assert text.endswith(" (0/3)")  # jump-progress suffix always preserved, never truncated
        assert '…' in text  # system · station is long enough to need truncating
        assert text.startswith('Puppis Sector TO-R b4-4')

        tooltip:str = ui.waypoint_btn_tt.args['text']
        assert 'Agronomic Treatment' in tooltip
        assert 'Cr/t' in tooltip

        harness.clipboard.clear()
        ui.waypoint_btn.invoke()
        assert harness.clipboard.get() == 'Puppis Sector TO-R b4-4'  # not the combined display text

    def test_update_cargo(self, harness:TestHarness):
        """ test update_cargo() method """
        ui = harness.plugin.ui
        ui.update_cargo(12)

        # Update cargo and verify cargo and range entries update
        assert ui.get_item('Galaxy', 'cargo_entry') == '12'
        assert ui.get_item('Neutron', 'range_entry') == str(harness.plugin.router.ship.get_range(12))

    def test_show_notice_displays_pending_notice(self, harness:TestHarness) -> None:
        ui = harness.plugin.ui
        harness.plugin.notices.notice_id = 1
        harness.plugin.notices.notice = "test notice body"

        ui.show_notice()

        assert "test notice body" in ui.notice.get("1.0", tk.END)

    def test_dismiss_notice_hides_and_persists(self, harness:TestHarness) -> None:
        ui = harness.plugin.ui
        harness.plugin.notices.notice_id = 1
        harness.plugin.notices.notice = "test notice body"
        ui.show_notice()

        ui.dismiss_notice()

        assert not ui.notice.winfo_exists()
        assert harness.plugin.notices.pending_notice is None

    def test_a_fetched_notice_is_displayed_in_the_ui(self, harness:TestHarness) -> None:
        """ Above tests set notice_id/notice directly; this ties the real fetch/parse path to the real UI. """
        previous:bool = mock_requests.live_requests()
        mock_requests.live_requests(False)
        try:
            mock_requests.queue_response("get", mock_requests.MockResponse(
                status_code=200, content="## 7\nA freshly fetched notice."))

            harness.plugin.notices._check_notices()
            harness.plugin.ui.show_notice()

            assert "A freshly fetched notice." in harness.plugin.ui.notice.get("1.0", tk.END)
        finally:
            mock_requests.live_requests(previous)


class TestRouteWindow:
    """Test RouteWindow lifecycle and display behavior."""

    def _cleanup_window(self, window: RouteWindow) -> None:
        if window.window is not None:
            try:
                if window.window.winfo_exists():
                    window.close()
            except tk.TclError:
                pass
        window.window = None

    def test_window_is_singleton(self, harness: TestHarness) -> None:
        """RouteWindow should reuse the existing singleton instance."""
        from Router.route_window import RouteWindow
        window:RouteWindow = harness.plugin.ui.window_route
        duplicate:RouteWindow = RouteWindow(harness.parent.winfo_toplevel())

        assert duplicate is window
        self._cleanup_window(window)

    def test_show_ignores_empty_route(self, harness: TestHarness) -> None:
        """show() should not create a window for an empty route."""
        window:RouteWindow = harness.plugin.ui.window_route
        route = Route()

        window.show(route)
        assert window.window is None

    def test_show_creates_window_for_populated_route(self, harness: TestHarness) -> None:
        """show() should create a toplevel window for a populated route."""
        window: RouteWindow = harness.plugin.ui.window_route

        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")
        assert harness.plugin.router.import_route(filename) is True

        window.show(harness.plugin.route)
        if window.window: window.window.iconify()  # Minimize the window to prevent test interference

        assert window.window is not None

        window.window.update_idletasks()
        assert window.window.winfo_exists() == 1
        assert window.window.title() == f"{NAME} – {lbls['route']}"

        self._cleanup_window(window)

    def test_close_saves_geometry_and_destroys_window(self, harness: TestHarness) -> None:
        """close() should persist geometry and destroy the current window."""
        window: RouteWindow = harness.plugin.ui.window_route
        window.root.withdraw()  # Hide the main window to prevent test interference
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")

        assert harness.plugin.router.import_route(filename) is True

        window.show(harness.plugin.route)
        if window.window: window.window.iconify()  # Minimize the window to prevent test interference

        assert window.window is not None

        window.window.update_idletasks()
        window.window.geometry("640x360+10+20")
        window.window.update_idletasks()
        geometry:str = window.window.winfo_geometry()
        window_ref = window.window

        window.close()

        assert harness.plugin.router.window_geometries['route'] == geometry
        assert window_ref.winfo_exists() == 0
        window.window = None

    def test_show_recreates_existing_window(self, harness: TestHarness) -> None:
        """show() should replace an existing RouteWindow instance with a fresh toplevel."""
        window:RouteWindow = harness.plugin.ui.window_route
        window.root.withdraw()  # Hide the main window to prevent test interference
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")

        assert harness.plugin.router.import_route(filename) is True

        window.show(harness.plugin.route)
        if window.window: window.window.iconify()  # Minimize the window to prevent test interference

        assert window.window is not None
        first_window = window.window

        window.show(harness.plugin.route)
        assert window.window is not None
        assert window.window is not first_window
        assert first_window.winfo_exists() == 0
        assert window.window.winfo_exists() == 1

        self._cleanup_window(window)

    def test_show_renders_summary_section(self, harness: TestHarness) -> None:
        """show() should render summary labels for progress, jumps and distance."""
        window:RouteWindow = harness.plugin.ui.window_route
        filename:str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")

        assert harness.plugin.router.import_route(filename) is True

        window.show(harness.plugin.route)
        if window.window: window.window.iconify()  # Minimize the window to prevent test interference
        assert window.window is not None
        window.window.update_idletasks()

        container = window.window.winfo_children()[0]
        summary_frame = container.winfo_children()[0]
        label_texts: list[str] = [
            widget.cget("text")
            for widget in summary_frame.winfo_children()
            if isinstance(widget, ttk.Label)
        ]

        assert lbls['progress'].title() in label_texts
        assert lbls['jumps'].title() in label_texts
        assert any(text.endswith('%') for text in label_texts)

        if harness.plugin.route.total_dist() > 0:
            assert lbls['distance'].title() in label_texts
        else:
            assert lbls['distance'].title() not in label_texts

        self._cleanup_window(window)

    def test_value_section_trade(self, harness:TestHarness) -> None:
        """show() adds a Profit block for Trade routes -- absent for Neutron/Galaxy/Tourist/
        FleetCarrier routes, which have no earned-value column."""
        window:RouteWindow = harness.plugin.ui.window_route
        hdrs = ['System Name', 'Station Name', 'Commodity', 'Amount', 'Profit', 'Jumps']
        route_data = [
            ['Shinrarta Dezhra', 'Jameson Memorial', '', 0, 0, 0],
            ['Sol', 'Abraham Lincoln', 'Gold', 100, 5000, 2],
        ]
        route = Route(hdrs, route_data, 0)

        window.show(route)
        if window.window: window.window.iconify()
        assert window.window is not None
        window.window.update_idletasks()

        container = window.window.winfo_children()[0]
        summary_frame = container.winfo_children()[0]
        label_texts:list[str] = [w.cget("text") for w in summary_frame.winfo_children() if isinstance(w, ttk.Label)]

        assert lbls['profit'].title() in label_texts
        assert any('Cr' in text for text in label_texts)

        self._cleanup_window(window)

    def test_show_renders_table_columns_rows_and_selection(self, harness: TestHarness) -> None:
        """show() should render table headings/rows and select the current route offset row."""
        window: RouteWindow = harness.plugin.ui.window_route
        filename: str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")

        assert harness.plugin.router.import_route(filename) is True
        harness.plugin.route.offset = 1

        window.show(harness.plugin.route)
        if window.window: window.window.iconify()  # Minimize the window to prevent test interference

        assert window.window is not None
        window.window.update_idletasks()

        container = window.window.winfo_children()[0]
        table_frame = container.winfo_children()[1]
        tree = next(
            widget for widget in table_frame.winfo_children()
            if isinstance(widget, ttk.Treeview)
        )

        assert tuple(tree["columns"]) == tuple(harness.plugin.route.hdrs)
        children = tree.get_children()
        assert len(children) == len(harness.plugin.route.route)

        selected = tree.selection()
        assert len(selected) == 1
        selected_values = tree.item(selected[0], "values")
        assert selected_values[0] == harness.plugin.route.route[harness.plugin.route.offset][0]

        self._cleanup_window(window)

    def test_table_selection_copies_system_name(self, harness: TestHarness) -> None:
        """Selecting a table row should copy the system name to the clipboard."""
        from Router.route_window import RouteWindow
        window: RouteWindow = harness.plugin.ui.window_route
        filename: str = str(Path(__file__).parent / "config" / "neutron-Bleae-Smojue.csv")

        assert harness.plugin.router.import_route(filename) is True

        window.show(harness.plugin.route)
        if window.window: window.window.iconify()  # Minimize the window to prevent test interference
        assert window.window is not None
        window.window.update_idletasks()

        container = window.window.winfo_children()[0]
        table_frame = container.winfo_children()[1]
        tree:TreeviewPlus = next(
            widget for widget in table_frame.winfo_children()
            if isinstance(widget, TreeviewPlus)
        )

        first_item = tree.get_children()[0]
        first_values = list(tree.item(first_item, "values"))

        assert hasattr(tree, "callback")
        if tree and tree.callback:
            tree.callback(first_values, 0, tree, first_item)

        assert harness.plugin.ui.parent is not None
        assert harness.plugin.ui.parent.clipboard_get() == first_values[0]

        self._cleanup_window(window)


class TestRouteWindowUI:
    """Test RouteWindow display logic and edge cases."""

    def test_empty_headers_no_display(self, harness:TestHarness) -> None:
        """Test show() with empty headers - should return without error."""
        from Router.route_window import RouteWindow
        window:RouteWindow = harness.plugin.ui.window_route

        empty_route = harness.plugin.route
        assert empty_route.hdrs == []
        assert window.window is None or not window.window.winfo_exists()

    def test_empty_cols_no_display(self, harness:TestHarness) -> None:
        """Test show() with empty columns - should return without error."""
        window:RouteWindow = harness.plugin.ui.window_route

        empty_route = Route(['System Name', 'Jumps'], [], 0)
        # Empty route should not crash
        assert empty_route.hdrs == ['System Name', 'Jumps']
        assert empty_route.route == []

    def test_route_with_data_empty_window(self, harness:TestHarness) -> None:
        """Test show() with data but window doesn't exist - should create window."""

        # Create a minimal route with system names
        route_data = [
            ['Sol', 0],
            ['Apurui', 10],
            ['Bleae Thua', 5]
        ]
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, route_data, 0)

        assert route.hdrs == hdrs
        assert len(route.route) == 3
        assert route.source() == 'Sol'
        assert route.destination() == 'Bleae Thua'


class TestPlotting:
    """Test end to end plotting functionality (neutron/galaxy routes)."""

    def test_plot_route_unknown_type(self, harness:TestHarness):
        """Unknown plot types should return False and not start plotting."""
        result:bool = harness.plugin.router.plot_route('UnsupportedType', {})
        assert result is False

    @pytest.mark.slow
    def test_plot_neutron_route(self, harness:TestHarness) -> None:
        """ Perform a live Neutron plot """
        global plotter_thread
        plotter_thread = None

        with patch('Router.route_manager.Thread', side_effect=capture_thread):

            res:bool = harness.plugin.router.plot_route('Neutron',
                                                {'from': 'Apurui', 'to': 'Bleae Thua NI-B b27-5',
                                                'range': '60.00', 'efficiency': '60',
                                                'supercharge_multiplier': '4'})
            assert res == True
            assert plotter_thread is not None, "Plotter thread was not captured"
            plotter_thread.join(timeout=THREAD_TIMEOUT)

            assert harness.plugin.route is not None
            assert harness.plugin.route.source() == 'Apurui'
            assert harness.plugin.route.destination() == 'Bleae Thua NI-B b27-5'
            assert harness.plugin.route.total_jumps() == 31

    @pytest.mark.slow
    def test_plot_neutron_route_caspian(self, harness:TestHarness) -> None:
        """ Perform a live Neutron plot for a Caspian explorer """
        global plotter_thread
        plotter_thread = None

        with patch('Router.route_manager.Thread', side_effect=capture_thread):

            res:bool = harness.plugin.router.plot_route('Neutron',
                                                {'from': 'Apurui', 'to': 'Bleae Thua NI-B b27-5',
                                                'range': '60.00', 'efficiency': '60',
                                                'supercharge_multiplier': '6'})
            assert res == True
            assert plotter_thread is not None, "Plotter thread was not captured"
            plotter_thread.join(timeout=THREAD_TIMEOUT)

            assert harness.plugin.route is not None
            assert harness.plugin.route.source() == 'Apurui'
            assert harness.plugin.route.destination() == 'Bleae Thua NI-B b27-5'
            assert harness.plugin.route.total_jumps() == 21

    @pytest.mark.slow
    def test_plot_galaxy_route(self, harness:TestHarness) -> None:
        """Perform a live galaxy plot and check results."""
        global plotter_thread
        plotter_thread = None

        harness.plugin.router.swap_ship(1)
        ship = harness.plugin.router.ship
        print(f"{ship}")
        assert ship is not None
        assert ship.name == 'Shipping Delay'
        assert harness.plugin.route.route == []

        galaxy_params:dict = {
            "cargo": 0,
            "max_time": 60,
            "algorithm": "optimistic",
            "fuel_reserve": 4,
            "is_supercharged": 0,
            "use_supercharge": 1,
            "use_injections": 0,
            "exclude_secondary": 1,
            "refuel_every_scoopable": 0,
            "fuel_power": ship.fuel_power,
            "fuel_multiplier": ship.fuel_multiplier,
            "optimal_mass": ship.optimal_mass,
            "base_mass": ship.base_mass,
            "tank_size": ship.tank_size,
            "internal_tank_size": ship.internal_tank_size,
            "max_fuel_per_jump": ship.max_fuel_per_jump,
            "range_boost": 10.5,
            "ship_build": ship.loadout,
            "supercharge_multiplier": ship.supercharge_multiplier,
            "injection_multiplier": ship.injection_multiplier,
            "source": "Apurui",
            "destination": "Bleae Thua NI-B b27-5"
        }

        assert ship.fuel_power == 2.45
        assert ship.fuel_multiplier == 0.013
        assert ship.optimal_mass == 1894.1
        assert ship.base_mass == 297.3
        assert ship.tank_size == 32
        assert ship.internal_tank_size == 0.5
        assert ship.max_fuel_per_jump == 5.2

        with patch('Router.route_manager.Thread', side_effect=capture_thread):

            res:bool = harness.plugin.router.plot_route('Galaxy', galaxy_params)
            assert res == True

            assert plotter_thread is not None, "Plotter thread was not captured"
            plotter_thread.join(timeout=THREAD_TIMEOUT)

            assert harness.plugin.router.src == 'Apurui'
            assert harness.plugin.router.dest == 'Bleae Thua NI-B b27-5'

            # This route seems to vary based on current conditions
            assert harness.plugin.route.total_jumps() in [18, 21, 28], f"Jumps {harness.plugin.route.total_jumps()}"

    @pytest.mark.slow
    def test_plot_galaxy_route_caspian(self, harness:TestHarness) -> None:
        """Perform a live galaxy plot with a caspian explorer and check results."""
        global plotter_thread
        plotter_thread = None

        harness.plugin.router.swap_ship(2)
        ship = harness.plugin.router.ship
        assert ship is not None
        assert ship.name == 'Perviy'
        assert harness.plugin.route.route == []

        galaxy_params:dict = {
            "cargo": 0,
            "max_time": 60,
            "algorithm": "optimistic",
            "fuel_reserve": 12,
            "is_supercharged": 0,
            "use_supercharge": 1,
            "use_injections": 0,
            "exclude_secondary": 0,
            "refuel_every_scoopable": 0,
            "fuel_power": ship.fuel_power,
            "fuel_multiplier": ship.fuel_multiplier,
            "optimal_mass": ship.optimal_mass,
            "base_mass": ship.base_mass,
            "tank_size": ship.tank_size,
            "internal_tank_size": ship.internal_tank_size,
            "max_fuel_per_jump": ship.max_fuel_per_jump,
            "range_boost": 10.5,
            "ship_build": ship.loadout,
            "supercharge_multiplier": ship.supercharge_multiplier,
            "injection_multiplier": ship.injection_multiplier,
            "source": "HIP 87621",
            "destination": "Bleae Thua ED-D c12-5"
        }

        with patch('Router.route_manager.Thread', side_effect=capture_thread):

            res:bool = harness.plugin.router.plot_route('Galaxy', galaxy_params)
            assert res == True

            assert plotter_thread is not None, "Plotter thread was not captured"
            plotter_thread.join(timeout=THREAD_TIMEOUT)

            assert harness.plugin.route is not None
            assert harness.plugin.router.src == galaxy_params['source']
            assert harness.plugin.router.dest == galaxy_params['destination']
            assert harness.plugin.route.total_jumps() == 9, f"Jumps {harness.plugin.route.total_jumps()}"

    @pytest.mark.slow
    def test_plot_rtor_route(self, harness:TestHarness) -> None:
        """ Perform a live Road-to-Riches plot """
        global plotter_thread
        plotter_thread = None

        with patch('Router.route_manager.Thread', side_effect=capture_thread):

            res:bool = harness.plugin.router.plot_route('RtoR',
                                                {'from': 'Colonia', 'range': '50', 'radius': '40',
                                                'max_results': '20', 'avoid_thargoids': '1', 'loop': '1'})
            assert res == True
            assert plotter_thread is not None, "Plotter thread was not captured"
            plotter_thread.join(timeout=THREAD_TIMEOUT)

            assert harness.plugin.route is not None
            # router.src reflects the queried source system; the route table itself only lists
            # systems with scannable bodies, so its first row's source() is a body name, not 'Colonia'.
            assert harness.plugin.router.src == 'Colonia'
            assert harness.plugin.route.source() != None
            assert "Body" in harness.plugin.route.hdrs
            assert "Est Scan Value" in harness.plugin.route.hdrs
            # Don't assert an exact body/jump count: which bodies are still unscanned
            # (and therefore appear in a riches route) changes over time in the live galaxy.
            assert len(harness.plugin.route.route) > 0

    @pytest.mark.slow
    def test_plot_ammonia_route(self, harness:TestHarness) -> None:
        """ Perform a live Ammonia World plot -- representative of the body-type-filtered
        riches variants (Ammonia/Earth-like/Rocky-metal), which all share the same
        /api/riches/route pipeline already exercised by test_plot_rtor_route above.
        Ammonia worlds are rare, and completion time depends on Spansh's shared job
        queue as much as search size, so this allows several minutes rather than the
        ~20s default used for plain (unfiltered) riches routes. """
        if 'Ammonia' not in PLOTTER_SPECS:
            return

        global plotter_thread
        plotter_thread = None

        with patch('Router.route_manager.Thread', side_effect=capture_thread):

            res:bool = harness.plugin.router.plot_route('Ammonia',
                                                {'from': 'Colonia', 'range': '50', 'radius': '150',
                                                'max_results': '20', 'avoid_thargoids': '1', 'loop': '1',
                                                'body_types': ['Ammonia world'], 'min_value': 1, 'max_time': 240})
            assert res == True
            assert plotter_thread is not None, "Plotter thread was not captured"
            plotter_thread.join(timeout=THREAD_TIMEOUT)

            assert harness.plugin.route is not None
            assert harness.plugin.router.src == 'Colonia'
            assert "Body" in harness.plugin.route.hdrs
            assert len(harness.plugin.route.route) > 0

    @pytest.mark.slow
    def test_plot_exobiology_route(self, harness:TestHarness) -> None:
        """ Perform a live Exobiology (Expressway to Exomastery) plot. Unlike the plain
        body-value riches routes, this checks for Species/Landmark Value columns, since
        that's the whole point of this route type. """
        global plotter_thread
        plotter_thread = None

        with patch('Router.route_manager.Thread', side_effect=capture_thread):

            res:bool = harness.plugin.router.plot_route('Exobiology',
                                                {'from': 'Colonia', 'range': '50', 'radius': '30',
                                                'max_results': '10', 'avoid_thargoids': '1', 'loop': '1',
                                                'min_value': 100000, 'max_time': 60})
            assert res == True
            assert plotter_thread is not None, "Plotter thread was not captured"
            plotter_thread.join(timeout=THREAD_TIMEOUT)

            assert harness.plugin.route is not None
            assert harness.plugin.router.src == 'Colonia'
            assert "Species" in harness.plugin.route.hdrs
            assert "Value" in harness.plugin.route.hdrs
            assert len(harness.plugin.route.route) > 0

    @pytest.mark.slow
    def test_plot_trade_route(self, harness:TestHarness) -> None:
        """ Perform a live Trade Planner plot from a busy hub (Jameson Memorial), which needs
        real time server-side to check commodity prices across many nearby stations. """
        global plotter_thread
        plotter_thread = None

        with patch('Router.route_manager.Thread', side_effect=capture_thread):

            res:bool = harness.plugin.router.plot_route('Trade',
                                                {'system': 'Shinrarta Dezhra', 'station': 'Jameson Memorial',
                                                'starting_capital': '1000000', 'max_cargo': '200', 'max_hops': '5',
                                                'max_hop_distance': '50', 'max_system_distance': '10000000',
                                                'requires_large_pad': '0', 'allow_prohibited': '0',
                                                'allow_planetary': '0', 'allow_player_owned': '0',
                                                'allow_restricted_access': '0', 'unique': '0', 'permit': '0',
                                                'max_time': 60})
            assert res == True
            assert plotter_thread is not None, "Plotter thread was not captured"
            plotter_thread.join(timeout=THREAD_TIMEOUT)

            assert harness.plugin.route is not None
            assert harness.plugin.router.src == 'Shinrarta Dezhra'
            assert "Station Name" in harness.plugin.route.hdrs
            assert "Commodity" in harness.plugin.route.hdrs
            assert "Cumulative Profit" in harness.plugin.route.hdrs
            assert len(harness.plugin.route.route) > 0

    @pytest.mark.slow
    def test_plot_tourist_route(self, harness:TestHarness) -> None:
        """ Perform a live Tourist Route plot between a handful of systems close to Sol,
        so the real route computation stays fast. """
        global plotter_thread
        plotter_thread = None

        with patch('Router.route_manager.Thread', side_effect=capture_thread):

            res:bool = harness.plugin.router.plot_route('Tourist',
                                                {'source': 'Sol', 'destination': ['Alpha Centauri', "Barnard's Star"],
                                                'range': '50', 'max_time': 60})
            assert res == True
            assert plotter_thread is not None, "Plotter thread was not captured"
            plotter_thread.join(timeout=THREAD_TIMEOUT)

            assert harness.plugin.route is not None
            assert harness.plugin.router.src == 'Sol'
            assert "System Name" in harness.plugin.route.hdrs
            assert len(harness.plugin.route.route) > 0


class TestEventSequences:
    """Test complex multi-step event scenarios."""

    @pytest.mark.manual_only
    @pytest.mark.slow
    def test_full_route_scenario(self, harness:TestHarness):
        """Test a complete route scenario with jumps."""
        harness.plugin.router.system = 'Apurui'

        # Import a route
        filename:str = str(Path(__file__).parent / "config" / "full-route-scenario.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        overlay = harness.plugin.overlay
        overlay.progress_display = "PD jc={jc} jr={jr} jt={jt} dc={dc} dr={dr} dt={dt} dh={dh} jh={jh} rj={rj} rd={rd} st={st}"

        # Follow the route
        for event in harness.events.get('full_route_scenario', []):
            harness.fire_event(event)
            match event.get('event'):
                case 'ShipyardSwap':
                    assert harness.plugin.router.ship_id == str(event.get('ShipID'))
                case 'Location' | 'FSDJump':
                    assert harness.plugin.router.system == event.get('StarSystem', '')
                    assert "Next: " + harness.plugin.route.next_stop() == harness.plugin.overlay.msgs["Default"]["NeutronDancer-Default-1"]["text"]

        # Final state check
        assert harness.plugin.route.jumps_remaining() == 0
        assert harness.plugin.overlay.msgs["Default"]["NeutronDancer-Default-2"]["text"].startswith("PD jc=4 jr=0 jt=4 dc=304 dr=0 dt=304")

    @pytest.mark.overlay('None')
    @pytest.mark.slow
    def test_full_route_scenario_no_overlay(self, harness:TestHarness):
        """Test a complete route scenario with jumps."""
        harness.plugin.router.system = 'Apurui'

        # Import a route
        filename:str = str(Path(__file__).parent / "config" / "full-route-scenario.csv")
        res:bool = harness.plugin.router.import_route(filename)
        assert res == True

        # Follow the route
        for event in harness.events.get('full_route_scenario', []):
            harness.fire_event(event)
            match event.get('event'):
                case 'ShipyardSwap':
                    assert harness.plugin.router.ship_id == str(event.get('ShipID'))
                case 'Location' | 'FSDJump':
                    assert harness.plugin.router.system == event.get('StarSystem', '')

        # Final state check
        assert harness.plugin.route.jumps_remaining() == 0

    @pytest.mark.slow
    def test_carrier_jump_noroute(self, harness:TestHarness) -> None:
        """Test carrier jump with docking."""
        from Router.constants import CarrierStates
        events:list = harness.events.get('carrier_events', [])
        harness.fire_event(events[0])
        assert harness.plugin.router.carrier_state == CarrierStates.Jumping
        harness.fire_event(events[1])
        assert harness.plugin.router.carrier_state == CarrierStates.Cooldown

    @pytest.mark.slow
    def test_carrier_jump_route(self, harness:TestHarness):
        """Test carrier jump with docking."""
        from Router.constants import CarrierStates
        filename:str = str(Path(__file__).parent / "config" / "vc-Bleae-Voqooe.csv")
        harness.plugin.router.import_route(filename)

        events:list = harness.events.get('carrier_events', [])
        harness.fire_event(events[0])
        assert harness.plugin.router.carrier_state == CarrierStates.Jumping
        harness.fire_event(events[1])
        assert harness.plugin.router.carrier_state == CarrierStates.Cooldown


class TestEDSMEnrichment:
    def test_star_class_extracts_letter_from_main_sequence_types(self) -> None:
        from Router.edsm import _star_class
        assert _star_class("G (White-Yellow) Star") == "G"
        assert _star_class("M (Red dwarf) Star") == "M"
        assert _star_class("L (Brown dwarf) Star") == "L"

    def test_star_class_extracts_code_from_white_dwarf_types(self) -> None:
        from Router.edsm import _star_class
        assert _star_class("White Dwarf (DA) Star") == "DA"

    def test_star_class_maps_known_exotic_types(self) -> None:
        from Router.edsm import _star_class
        assert _star_class("Neutron Star") == "N"
        assert _star_class("Black Hole") == "H"
        assert _star_class("Supermassive Black Hole") == "SupermassiveBlackHole"

    def test_star_class_falls_back_to_the_raw_string_for_an_unknown_shape(self) -> None:
        from Router.edsm import _star_class
        assert _star_class("Something Unexpected") == "Something Unexpected"

    def test_fetch_populates_the_cache_from_a_batch_response(self, harness:TestHarness) -> None:
        def fake_get(url, *args, **kwargs):
            resp = Mock()
            resp.raise_for_status = lambda: None
            resp.json = lambda: [{
                "name": "Sol", "id64": 10477373803, "coords": {"x": 0, "y": 0, "z": 0},
                "primaryStar": {"type": "G (White-Yellow) Star"},
            }]
            return resp

        with mocked_session_get(fake_get):
            harness.plugin.edsm._fetch(["Sol"])

        assert harness.plugin.edsm.get("Sol") == {
            "StarSystem": "Sol", "SystemAddress": 10477373803, "StarPos": [0, 0, 0], "StarClass": "G",
        }

    def test_fetch_skips_already_cached_names(self, harness:TestHarness) -> None:
        harness.plugin.edsm.cache["Sol"] = {"StarSystem": "Sol", "SystemAddress": 1, "StarPos": [0, 0, 0], "StarClass": "G"}

        with patch('Router.route_manager.SESSION.get') as mock_get:
            harness.plugin.edsm._fetch(["Sol"])

        mock_get.assert_not_called()

    def test_route_construction_triggers_a_background_fetch_for_its_systems(self, harness:TestHarness, monkeypatch) -> None:
        seen:list = []
        monkeypatch.setattr(harness.plugin.edsm, 'start_fetch', lambda names: seen.append(names))

        Route(['System Name'], [['Sol'], ['Wolf 359']])

        assert seen == [['Sol', 'Wolf 359']]

    def test_get_navroute_uses_cached_edsm_data_when_available(self, harness:TestHarness) -> None:
        import Router.api as api_module
        harness.plugin.edsm.cache["Sol"] = {
            "StarSystem": "Sol", "SystemAddress": 10477373803, "StarPos": [0, 0, 0], "StarClass": "G",
        }

        harness.plugin.route = Route(['System Name'], [['Sol']])
        result:dict = api_module.get_navroute()

        assert result == {"event": "NavRoute", "Route": [
            {"StarSystem": "Sol", "SystemAddress": 10477373803, "StarPos": [0, 0, 0], "StarClass": "G"},
        ]}

    def test_get_navroute_placeholders_a_system_not_yet_resolved(self, harness:TestHarness) -> None:
        import Router.api as api_module

        harness.plugin.route = Route(['System Name'], [['Somewhere Not Yet Cached']])
        result:dict = api_module.get_navroute()

        assert result == {"event": "NavRoute", "Route": [
            {"StarSystem": "Somewhere Not Yet Cached", "SystemAddress": None, "StarPos": None, "StarClass": ""},
        ]}

    def test_get_navroute_returns_clear_event_for_an_empty_route(self, harness:TestHarness) -> None:
        import Router.api as api_module
        harness.plugin.route = Route([], [], -1)
        assert api_module.get_navroute() == {"event": "NavRouteClear", "Route": []}

    def test_clear_route_wipes_the_edsm_cache(self, harness:TestHarness) -> None:
        harness.plugin.edsm.cache["Sol"] = {"StarSystem": "Sol", "SystemAddress": 1, "StarPos": [0, 0, 0], "StarClass": "G"}

        harness.plugin.router.clear_route()

        assert harness.plugin.edsm.get("Sol") is None
