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
import json
import logging
import tkinter as tk
from tkinter import ttk
import threading
import time

import tests.edmc.requests as mock_requests
from tests.edmc import edmc_data

from Router.utils.treeviewplus import TreeviewPlus
from Router.utils import th
from Router.utils.updater import Updater, Notices

# Setup path for imports
plugin_dir:Path = Path(__file__).parent
sys.path.insert(0, str(plugin_dir))

from harness import TestHarness
from Router.route_window import RouteWindow
from Router.constants import SPANSH_ROUTE, NAME, lbls
from Router.route import Route
from Router.ship import Ship
from Router.plotters import PLOTTER_SPECS, _boxel_coords, _boxel_exists, _boxel_prefix
from Router.local.index import Index, build, galaxy_extras, VERSION
from Router.local.search import Planner
from Router.local.index import Combined
from Router.local.data import LocalData, URL

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

THREAD_TIMEOUT=66

def _respond(method:str, status:int, data) -> None:
    """ Queue one mocked Spansh response. """
    mock_requests.queue_response(method, mock_requests.MockResponse(status_code=status, json_data=data))

def _wait_plot(harness:TestHarness, timeout:float = THREAD_TIMEOUT) -> None:
    """ Wait for the route plotting worker, if it's still running. """
    for t in threading.enumerate():
        if t.name == "Neutron Dancer route plotting worker": harness.wait_for_thread(t, timeout)

def _plot(harness:TestHarness, plotter) -> tuple:
    """ Run a plotter's plot(); return the route type and params it sent to Spansh, or ('', {}) if it sent nothing. """
    before:int = len(mock_requests.calls)
    plotter.plot()
    _wait_plot(harness)
    router = harness.plugin.router
    if PLOTTER_SPECS[router.last_plot].url not in {c['url'] for c in mock_requests.calls[before:]}: return '', {}
    return router.last_plot, router.route_params[router.last_plot]

def _queue_notices(text:str) -> None:
    mock_requests.queue_response("get", mock_requests.MockResponse(status_code=200, content=text))

class TestStartup:
    """Test plugin startup behavior."""

    @pytest.mark.parametrize('harness', ['None'], indirect=True)
    def test_harness_initialization(self, harness:TestHarness) -> None:
        """ A blank slate initialises. """
        assert harness.plugin.router is not None
        assert isinstance(harness.plugin.router.shiplist, dict)

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

    @pytest.mark.live_requests
    def test_module_import(self, harness:TestHarness) -> None:
        """Test retrieving module data from Coriolis """
        harness.plugin.modules = []
        harness.plugin.router._get_module_data()
        assert len(harness.plugin.modules) == 88

class TestUpdater:
    @pytest.fixture(autouse=True)
    def _mock_network(self) -> Generator[None, None, None]:
        """ Force mocked requests, since a prior test may have left the shared mock in live mode. """
        previous:bool = mock_requests.live_requests()
        mock_requests.live_requests(False)
        yield
        mock_requests.live_requests(previous)

    def test_extra_check_in_git_checkout(self, tmp_path) -> None:
        """ The extra (data) check runs on the update schedule even where a git checkout skips the plugin update. """
        (tmp_path / ".git").mkdir()
        updater = Updater(str(tmp_path), "dwomble", "EDMC-NeutronDancer-ExtraTest")
        extra = Mock()
        with patch.object(updater, 'get_release') as release:
            updater.check_for_update("1.0.0", interval=-1, extra=extra)
            for _ in range(50):
                if extra.called: break
                time.sleep(0.02)
        assert extra.called and not release.called

class TestNotices:
    """ Cursory integration check for the fetch/parse/dismiss round-trip in this plugin's stack. """

    @pytest.fixture(autouse=True)
    def _mock_network(self) -> Generator[None, None, None]:
        """ Force mocked requests for the duration of each test, then restore the prior mode. """
        previous:bool = mock_requests.live_requests()
        mock_requests.live_requests(False)
        yield
        mock_requests.live_requests(previous)

    def test_fetch_and_dismiss_notice(self) -> None:
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
        lines = route.next_stop_details().splitlines()
        assert any('Agronomic Treatment' in l for l in lines)
        assert any('Cr/t' in l for l in lines)
        assert any('Cr' in l and 'Cr/t' not in l for l in lines)  # the running-total line

    def test_next_stop_riches(self, harness:TestHarness) -> None:
        """ Subtype/distance/scan value details for a riches-shaped route. """
        hdrs = ['System Name', 'Body', 'Body Type', 'Distance To Arrival', 'Estimated Scan Value', 'Jumps']
        route_data = [
            ['Colonia', 'Colonia 1', '', 0, 0, 0],
            ['Colonia', 'Colonia 2 a', 'High metal content world', 812.0, 42300, 1],
        ]
        route = Route(hdrs, route_data, 0)

        lines = route.next_stop_details().splitlines()

        assert any('High metal content world' in l for l in lines)
        assert any('Scan' in l for l in lines)
        assert route.next_stop_display() == 'Colonia 2 a'

    def test_display_adds_missing_system(self, harness:TestHarness) -> None:
        """ A body's own value can't be trusted to include the system name, so this must add it itself. """
        hdrs = ['System Name', 'Body', 'Species', 'Jumps']
        route = Route(hdrs, [['Deciat', 'Deciat 1', '', 0], ['Deciat', '4 a', 'Bacterium Nypoxia', 1]], 0)

        assert route.next_stop_display() == 'Deciat 4 a'

    def test_display_without_body_column(self, harness:TestHarness) -> None:
        hdrs = ['System Name', 'Jumps']
        route = Route(hdrs, [['Sol', 0], ['Apurui', 10]], 0)

        assert route.next_stop_display() == route.next_stop() == 'Apurui'

    def test_next_stop_exobiology(self, harness:TestHarness) -> None:
        """ next_stop() stays the system name; next_stop_display() carries the body instead. """
        hdrs = ['System Name', 'Body', 'Species', 'Jumps']
        route_data = [
            ['Deciat', 'Deciat 1', '', 0],
            ['Deciat', 'Deciat 4 a', 'Bacterium Nypoxia', 1],
        ]
        route = Route(hdrs, route_data, 0)

        assert route.next_stop_station() == ''
        assert route.next_stop() == 'Deciat'
        assert route.next_stop_display() == 'Deciat 4 a'
        assert any('Bacterium Nypoxia' in l for l in route.next_stop_details().splitlines())

    def test_details_lists_extra_bodies(self, harness:TestHarness) -> None:
        """ Several bodies at one system must have the detail lines call out the extra ones. """
        hdrs = ['System Name', 'Body', 'Species', 'Jumps']
        route_data = [
            ['Deciat', 'Deciat 1', '', 0],
            ['Deciat', 'Deciat 4 a', 'Bacterium Nypoxia', 1],
            ['Deciat', 'Deciat 4 b', 'Fonticulua Campestris', 0],
        ]
        route = Route(hdrs, route_data, 0)

        lines = route.next_stop_details().splitlines()

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
        """ sum_value() sums an arbitrary prefix; route_value() picks the right earned-value column. """
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
        lines = route.next_stop_details().splitlines()
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
        lines = route.next_stop_details().splitlines()
        assert any('47.3K Cr' in l for l in lines)

    def test_details_blank_no_extra_columns(self, harness:TestHarness) -> None:
        """next_stop_detail_lines() is empty for plain route types (Neutron, Tourist, etc.)."""
        hdrs = ['System Name', 'Jumps']
        route_data = [['Sol', 0], ['Apurui', 10]]
        route = Route(hdrs, route_data, 0)

        assert route.next_stop_details() == ''

    def test_tracks_refuel_or_neutron(self, harness:TestHarness) -> None:
        """Test checks refuel or neutron for appropriate route types."""
        neutron_route = Route(['System Name', 'Jumps', 'Refuel'], [['Sol', 0, 'No'], ['Apurui', 10, 'Yes']], 0)
        assert neutron_route.tracks_refuel_or_neutron() == True

        galaxy_route = Route(['System Name', 'Jumps', 'Neutron'], [['Sol', 0, 'False'], ['Apurui', 10, 'True']], 0)
        assert galaxy_route.tracks_refuel_or_neutron() == True

        trade_route = Route(['System Name', 'Station Name', 'Jumps'], [['Sol', 'A', 0], ['Apurui', 'B', 10]], 0)
        assert trade_route.tracks_refuel_or_neutron() == False

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
    """ Moving along a route via real navigation events, not by calling update_route() directly. """

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

    def test_loadout_without_id_skipped(self, harness:TestHarness) -> None:
        """ A loadout built before the ship's id is known isn't saved as a ship called "None". """
        harness.play_sequence('loadout')
        entry:dict = {**harness.plugin.router.ship.loadout, 'ShipID': None, 'ShipName': 'Nameless'}
        harness.plugin.router.add_loadout(entry)
        assert 'None' not in harness.plugin.router.shiplist and 'Nameless' not in harness.plugin.router.shiplist.values()

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
            res:bool = harness.plugin.csv.write(harness.plugin.route)
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

def _synthetic_build(folder:Path, rows:list|None = None) -> dict:
    """ Indexes from synthetic dumps: by default neutrons every 200 Ly along z, with K stars every 40 Ly. """
    import gzip
    if rows is None:
        rows = [{'id64': i, 'name': f'N{i}', 'mainStar': 'Neutron Star', 'coords': {'x': 0, 'y': 0, 'z': i * 200}} for i in range(16)]
        rows += [{'id64': 100 + i, 'name': f'S{i}', 'mainStar': 'K (Yellow-Orange) Star', 'coords': {'x': 5, 'y': 0, 'z': i * 40}}
                 for i in range(76)]

    # The galaxy dump lists each row's main star, and any (type, distance) others, as bodies; an unscanned row has none
    star = lambda kind, ls, main: {'type': 'Star', 'subType': kind, 'distanceToArrival': ls, 'mainStar': main}
    systems:list = [{'id64': r['id64'], 'name': r['name'], 'mainStar': r['mainStar'], 'coords': r['coords']} for r in rows]
    galaxy:list = [{'id64': r['id64'], 'name': r['name'], 'coords': r['coords'],
                    'bodies': [] if r.get('unscanned') else [star(r['mainStar'], 0.0, True)] + [star(k, ls, False) for k, ls in r.get('stars', [])]}
                   for r in rows]
    for name, lines in (('systems', systems), ('galaxy', galaxy)):
        with gzip.open(folder / f'{name}.json.gz', 'wt') as f:
            f.write('[\n' + ',\n'.join(json.dumps(r, separators=(',', ':')) for r in lines) + '\n]\n')
    return build(folder / 'systems.json.gz', extras=galaxy_extras(folder / 'galaxy.json.gz'))

class TestShipyardSwap:
    """Test ship swapping from shipyard."""

    def test_ship_bad_init(self, harness:TestHarness):
        """Test bad ship swap event."""
        entry:dict = {"event": "bad"}
        ship:Ship = Ship(entry)

        assert ship.loadout == {}

    def test_ship_keeps_fuel(self, harness:TestHarness):
        """ Dashboard fuel lands on the current ship, survives a save and reload, and isn't part of the loadout. """
        harness.play_sequence('loadout')
        ship:Ship = harness.plugin.router.ship
        harness.fire_dashboard_event({'Fuel': {'FuelMain': ship.tank_size - 3, 'FuelReservoir': 0.5}})
        assert ship.fuel == ship.tank_size - 3 and not ship.fuel_full

        saved:Ship = type(ship)(ship.as_dict())  # the plugin's own Ship class, which sees its loaded modules
        assert saved.fuel == ship.tank_size - 3 and 'FuelLevel' not in saved.loadout
        saved.fuel = saved.tank_size
        assert saved.fuel_full

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

    def test_saved_frame_defaults_ttl(self, harness:TestHarness) -> None:
        key:str = f"{harness.plugin.plugin_name}_Default_overlay"
        harness.config.set(key, json.dumps({"name": "Default", "x": 100, "y": 900}))

        harness.plugin.overlay._load_prefs()

        assert harness.plugin.overlay.ovfrs["Default"].ttl > 0

    def test_saved_zero_ttl_ignored(self, harness:TestHarness) -> None:
        key:str = f"{harness.plugin.plugin_name}_Default_overlay"
        harness.config.set(key, json.dumps({"name": "Default", "x": 100, "y": 900, "ttl": 0}))

        harness.plugin.overlay._load_prefs()

        assert harness.plugin.overlay.ovfrs["Default"].ttl > 0

    def test_countdown_runs_and_stops(self, harness:TestHarness) -> None:
        """ A countdown shows its remaining time each second and clears its frame once stopped. """
        ov = harness.plugin.overlay
        key:str = f"{harness.plugin.plugin_name}-Carrier-0"
        ov.display_countdown('Carrier', 'Jump in {t}', 100)

        for _ in range(30):
            if ov.msgs.get('Carrier', {}).get(key, {}).get('text', '').startswith('Jump in'): break
            time.sleep(0.1)
        assert ov.msgs['Carrier'][key]['text'].startswith('Jump in')

        worker = next(t for t in threading.enumerate() if t.name.endswith('Carrier overlay countdown worker'))
        ov.stop_countdown('Carrier')
        worker.join(2)
        assert not worker.is_alive() and ov.msgs['Carrier'][key]['text'] == ''

    def test_countdown_shows_overlay(self, harness:TestHarness) -> None:
        """Ensure carrier jump completion starts the countdown thread."""
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
        harness.config.set(f"{harness.plugin.plugin_name}_progress_display", "PD jc={jc} jr={jr} jt={jt} dc={dc} dr={dr} dt={dt} dh={dh} jh={jh} rj={rj} rd={rd} st={st}")

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
        harness.config.set(f"{harness.plugin.plugin_name}_progress_display", "PD jc={jc} jr={jr} jt={jt} dc={dc} dr={dr} dt={dt} dh={dh} jh={jh} rj={rj} rd={rd} st={st}")

        overlay.update_overlays()

        assert harness.plugin.overlay.msgs["Default"]["NeutronDancer-Default-2"]["text"] == 'PD jc=15 jr=384 jt=399 dc=286 dr=16.2K dt=16.5K dh=- jh=- rj=- rd=- st=🌀'

    def test_overlay_trade_detail_not_template(self, harness:TestHarness, monkeypatch) -> None:
        """ With no Refuel/Neutron columns, the overlay shows the route's own detail section. """
        # Short names so the "Next:" line's truncation doesn't interfere.
        hdrs = ['System Name', 'Station Name', 'Commodity', 'Amount', 'Profit', 'Jumps']
        route_data = [
            ['Sol', 'Abraham Lincoln', '', 0, 0, 0],
            ['Deciat', 'Farside', 'Gold', 200, 10617, 3],
        ]
        harness.plugin.route = Route(hdrs, route_data, 0)
        assert harness.plugin.route.tracks_refuel_or_neutron() == False

        overlay = harness.plugin.overlay
        harness.config.set(f"{harness.plugin.plugin_name}_progress_display", "PD jc={jc}")  # would be shown if this were misclassified

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
        harness.config.set(f"{harness.plugin.plugin_name}_progress_display", "invalid={unknown}")

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

class TestSpanshEnrichment:
    @pytest.mark.parametrize('subtype, cls', [("G (White-Yellow) Star", "G"), ("M (Red dwarf) Star", "M"), ("L (Brown dwarf) Star", "L"),
                                               ("White Dwarf (DA) Star", "DA"), ("Neutron Star", "N"), ("Black Hole", "H"),
                                               ("Supermassive Black Hole", "SupermassiveBlackHole"),
                                               ("Something Unexpected", "Something Unexpected")])
    def test_star_class(self, subtype:str, cls:str) -> None:
        """ Spansh's subtype text maps to a star class, falling back to the text itself. """
        from Router.spansh_data import _star_class
        assert _star_class(subtype) == cls

    def test_fetch_populates_cache(self, harness:TestHarness) -> None:
        _respond('get', 200, {"record": {"bodies": [
            {"is_main_star": True, "subtype": "G (White-Yellow) Star"},
            {"is_main_star": None, "subtype": "Rocky body"},
        ]}})
        harness.plugin.spansh._fetch({"Sol": 10477373803})

        assert harness.plugin.spansh.get("Sol") == "G"

    def test_skip_cached(self, harness:TestHarness) -> None:
        harness.plugin.spansh.cache["Sol"] = "G"

        before:int = len(mock_requests.calls)
        harness.plugin.spansh._fetch({"Sol": 1})
        assert len(mock_requests.calls) == before

    def test_star_class_from_navroute(self, harness:TestHarness) -> None:
        """ StarClass comes straight from the route's own navroute data, no fetch involved. """
        import Router.api as api_module
        navroute:dict = {"Wolf 359": {"SystemAddress": 1, "StarPos": [1, 1, 1], "StarClass": "N"}}

        harness.plugin.route = Route(['System Name'], [['Wolf 359']], navroute=navroute)
        result:list|None = api_module.get_navroute()
        assert result is not None
        assert result[0]["StarClass"] == "N"

    def test_navroute_placeholder(self, harness:TestHarness) -> None:
        import Router.api as api_module

        harness.plugin.route = Route(['System Name'], [['Somewhere Not Yet Cached']])
        result:list|None = api_module.get_navroute()
        assert result is not None

        assert result[0] == {"StarSystem": "Somewhere Not Yet Cached", "SystemAddress": None, "StarPos": None, "StarClass": ""}

    def test_navroute_clear(self, harness:TestHarness) -> None:
        import Router.api as api_module
        harness.plugin.route = Route([], [], -1)
        assert api_module.get_navroute() == None

    def test_clear_route(self, harness:TestHarness) -> None:
        harness.plugin.spansh.cache["Sol"] = "G"

        harness.plugin.router.clear_route()

        assert harness.plugin.spansh.get("Sol") is None

class TestPlotMethods:
    """Test individual plotting functions"""

    def test_plotter_success_creates_route(self, harness:TestHarness) -> None:
        """Test that _plotter successfully creates a route from Spansh response."""

        _respond('post', 202, {"job": "test-job-id"})

        _respond('get', 200, {
            "result": {
                "jumps": [
                    {"system": "System1", "distance": 20.5},
                    {"system": "System2", "distance": 19.3},
                ]
            }
        })


        params = {'from': 'Start', 'to': 'End', 'max_time': 1}
        harness.plugin.router.plot_route('Neutron', params)

        _wait_plot(harness)

        assert harness.plugin.route is not None
        assert len(harness.plugin.route.route) >= 2

        # Regression: plot_route() must persist into route_params, not a stray neutron_params attribute
        assert harness.plugin.router.route_params['Neutron'] == params
        assert not hasattr(harness.plugin.router, 'neutron_params')

    def test_plotter_derives_star_class(self, harness:TestHarness) -> None:
        """ Neutron/Scoopable route flags become a guessed StarClass, with no Spansh fetch. """

        _respond('post', 202, {"job": "test-job-id"})

        _respond('get', 200, {
            "result": {
                "jumps": [
                    {"system": "System1", "distance": 20.5, "has_neutron": True},
                    {"system": "System2", "distance": 19.3, "is_scoopable": True},
                    {"system": "System3", "distance": 18.1},
                ]
            }
        })

        harness.plugin.router.plot_route('Neutron', {'from': 'Start', 'to': 'End', 'max_time': 1})

        _wait_plot(harness)

        assert harness.plugin.route.navroute['System1']['StarClass'] == 'N'
        assert harness.plugin.route.navroute['System2']['StarClass'] == 'M'
        assert harness.plugin.route.navroute['System3']['StarClass'] == ''

    def test_indy_plot_creates_route(self, harness:TestHarness) -> None:
        """ Indy hops become route rows; a hop is a neutron when the jump after it is boosted. """

        hop:dict = {'boosted': False, 'boostSource': '', 'mainStar': 'Neutron Star'}
        _respond('get', 200, {'found': True, 'hops': [
            {**hop, 'name': 'Sol', 'jumpDist': 0, 'plainJumps': 0, 'remainingDist': 941.5, 'mainStar': 'G'},
            {**hop, 'name': 'PSR A', 'jumpDist': 407.4, 'plainJumps': 7, 'remainingDist': 534.1},
            {**hop, 'name': 'PSR B', 'jumpDist': 534.1, 'plainJumps': 6, 'remainingDist': 0, 'boosted': True}]})

        params:dict = {'start': 'Sol', 'dest': 'PSR B', 'laden': '60', 'neutron': 1, 'wd': 0, 'caspian': 0}
        harness.plugin.router.plot_route('Indy', params)
        _wait_plot(harness)

        assert mock_requests.calls[-1]['params'] == params
        route = harness.plugin.route
        assert [r[route.colind('System Name')] for r in route.route] == ['Sol', 'PSR A', 'PSR B']
        assert [r[route.colind('Jumps')] for r in route.route] == [0, 7, 6]
        assert [route.navroute[s]['StarClass'] for s in ('Sol', 'PSR A', 'PSR B')] == ['', 'N', '']

    def test_indy_autocomplete_uses_search(self, harness:TestHarness) -> None:
        """ Indy's system entries look names up in Indy's own database. """
        plotter = harness.plugin.ui.plotters['Indy']
        assert plotter.src_ac.func == plotter.dest_ac.func == harness.plugin.ui.query_indy

        _respond('get', 200, {'matches': [{'name': 'Sol', 'mainStar': 'G', 'neutron': False},
                                          {'name': 'Solati', 'mainStar': 'K', 'neutron': False}]})
        assert harness.plugin.ui.query_indy('Sol') == ['Sol', 'Solati']

    def test_plotter_success_creates_route_galaxy(self, harness:TestHarness) -> None:
        """Test that _plotter persists Galaxy params into route_params (not a stray galaxy_params attribute)."""

        _respond('post', 202, {"job": "test-job-id"})

        _respond('get', 200, {
            "result": {
                "jumps": [
                    {"system": "System1", "distance": 20.5},
                    {"system": "System2", "distance": 19.3},
                ]
            }
        })

        params = {'source': 'Start', 'destination': 'End', 'max_time': 1}
        harness.plugin.router.plot_route('Galaxy', params)

        _wait_plot(harness)

        assert harness.plugin.route is not None
        assert harness.plugin.router.route_params['Galaxy'] == params
        assert not hasattr(harness.plugin.router, 'galaxy_params')

    def test_plotter_success_creates_route_rtor(self, harness:TestHarness) -> None:
        """ Flattens nested bodies into one row each, dropping bodyless systems entirely. """

        _respond('post', 202, {"job": "test-job-id"})

        # Real shape: a bodyless system (start) followed by one with two scannable bodies.
        _respond('get', 200, {
            "result": [
                {"name": "Colonia", "jumps": 1, "bodies": []},
                {"name": "Eol Prou LW-L c8-62", "jumps": 1, "bodies": [
                    {"name": "Eol Prou LW-L c8-62 7", "subtype": "Water world", "is_terraformable": True,
                     "distance_to_arrival": 173.1, "estimated_scan_value": 301683, "estimated_mapping_value": 1096113},
                    {"name": "Eol Prou LW-L c8-107 2", "subtype": "Earth-like world", "is_terraformable": False,
                     "distance_to_arrival": 436.9, "estimated_scan_value": 301332, "estimated_mapping_value": 1094838},
                ]},
            ]
        })

        params = {'from': 'Colonia', 'range': '50', 'radius': '40', 'max_results': '20', 'max_time': 1}
        harness.plugin.router.plot_route('RtoR', params)

        _wait_plot(harness)

        assert harness.plugin.route is not None
        assert len(harness.plugin.route.route) == 3  # bodyless Colonia dropped; one row per body
        assert "Body" in harness.plugin.route.hdrs
        assert "Est Scan Value" in harness.plugin.route.hdrs
        assert harness.plugin.route.source() == 'Colonia'
        assert harness.plugin.router.route_params['RtoR'] == params

    def test_plotter_success_creates_route_ammonia(self, harness:TestHarness) -> None:
        """ The riches-shape branch must trigger for body_types-filtered variants too, not just 'RtoR'. """
        if 'Ammonia' not in PLOTTER_SPECS:
            return


        _respond('post', 202, {"job": "test-job-id"})

        _respond('get', 200, {
            "result": [
                {"name": "Eol Prou OC-K c9-5", "jumps": 1, "bodies": [
                    {"name": "Eol Prou OC-K c9-5 3", "subtype": "Ammonia world", "is_terraformable": False,
                     "distance_to_arrival": 337.9, "estimated_scan_value": 302571, "estimated_mapping_value": 1099340},
                ]},
            ]
        })

        params = {'from': 'Colonia', 'range': '50', 'radius': '40', 'max_results': '20',
                  'body_types': ['Ammonia world'], 'min_value': 1, 'max_time': 1}
        harness.plugin.router.plot_route('Ammonia', params)

        _wait_plot(harness)

        assert harness.plugin.route is not None
        assert len(harness.plugin.route.route) == 1
        assert harness.plugin.route.source() == 'Colonia'
        assert harness.plugin.router.route_params['Ammonia'] == params

    def test_plotter_success_creates_route_exobiology(self, harness:TestHarness) -> None:
        """Test that _plotter flattens an Exobiology response."""

        _respond('post', 202, {"job": "test-job-id"})

        _respond('get', 200, {
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
        })

        params = {'from': 'Colonia', 'range': '50', 'radius': '30', 'max_results': '10',
                  'min_value': 100000, 'max_time': 1}
        harness.plugin.router.plot_route('Exobiology', params)

        _wait_plot(harness)

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
        """ Each commodity-per-hop becomes its own row, keyed to the hop's destination, not source. """

        _respond('post', 202, {"job": "test-job-id"})

        _respond('get', 200, {
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
        })

        params = {'system': 'Shinrarta Dezhra', 'station': 'Jameson Memorial',
                  'starting_capital': '1000000', 'max_cargo': '200', 'max_hops': '5',
                  'max_hop_distance': '50', 'max_system_distance': '10000000', 'max_time': 1}
        harness.plugin.router.plot_route('Trade', params)

        _wait_plot(harness)

        assert harness.plugin.route is not None
        assert len(harness.plugin.route.route) == 3  # 1 commodity in hop 1 + 2 commodities in hop 2
        assert "Station Name" in harness.plugin.route.hdrs
        assert "Commodity" in harness.plugin.route.hdrs
        assert "Cumulative Profit" in harness.plugin.route.hdrs

        # Row 0 is keyed to hop 0's destination, not its source -- the starting station has no row.
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
        """ Only distance != 0 rows survive -- leg-restart bookkeeping rows are dropped. """

        _respond('post', 202, {"job": "test-job-id"})

        _respond('get', 200, {
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
        })

        params = {'source_name': 'Sol', 'source': 10477373803,
                  'destination_names': ['Deciat', 'Alpha Centauri'],
                  'destinations': [6681123623626, 1178708478315],
                  'carrier_type': 'fleet', 'capacity': 25000, 'mass': 25000,
                  'capacity_used': '0', 'calculate_starting_fuel': 1, 'max_time': 1}
        harness.plugin.router.plot_route('FleetCarrier', params)

        _wait_plot(harness)

        assert harness.plugin.route is not None
        assert len(harness.plugin.route.route) == 2  # one row per stop, not per jump entry
        row0, row1 = harness.plugin.route.route[0], harness.plugin.route.route[1]
        assert row0[harness.plugin.route.hdrs.index("System Name")] == 'Deciat'
        assert row1[harness.plugin.route.hdrs.index("System Name")] == 'Alpha Centauri'
        assert "Icy Ring" in harness.plugin.route.hdrs
        assert "Restock Tritium" in harness.plugin.route.hdrs

    def test_fc_keeps_every_hop(self, harness:TestHarness) -> None:
        """ A single-leg route with several intermediate hops must keep every hop, not just the last. """

        _respond('post', 202, {"job": "test-job-id"})

        _respond('get', 200, {
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
        })

        params = {'source': 1, 'destinations': 4, 'capacity': 25000, 'mass': 25000,
                  'capacity_used': '0', 'calculate_starting_fuel': 1, 'max_time': 1}
        harness.plugin.router.plot_route('FleetCarrier', params)

        _wait_plot(harness)

        assert harness.plugin.route is not None
        names = [row[harness.plugin.route.hdrs.index("System Name")] for row in harness.plugin.route.route]
        assert names == ['Hop One', 'Hop Two', 'Colonia']

    def test_plotter_error_response_shows_error(self, harness:TestHarness):
        """Test that _plotter handles error responses without crashing."""
        _respond('post', 500, {"error": "Server error"})
        harness.plugin.router.plot_route('Neutron', {'from': 'Start', 'to': 'End', 'max_time': 1})
        _wait_plot(harness)

    def test_neutron_plotter_calls_plot_route(self, harness:TestHarness) -> None:
        """Regression: NeutronPlotter.plot() must actually invoke Context.router.plot_route()."""
        ui = harness.plugin.ui
        neutron_fr = ui.plot_frames['Neutron']

        neutron_fr.nametowidget("source_ac").set_text("Sol", False)
        neutron_fr.nametowidget("dest_ac").set_text("Colonia", False)
        neutron_fr.nametowidget("range_entry").set_text("50", False)

        which, params = _plot(harness, ui.plotters['Neutron'])
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

        _, params = _plot(harness, plotter)
        assert params['via'] == ['Deciat']

    def test_galaxy_plotter_calls_plot_route(self, harness:TestHarness) -> None:
        """Regression: GalaxyPlotter.plot() must actually invoke Context.router.plot_route()."""
        harness.play_sequence('loadout')
        ui = harness.plugin.ui
        galaxy_fr = ui.plot_frames['Galaxy']

        galaxy_fr.nametowidget("source_ac").set_text("Sol", False)
        galaxy_fr.nametowidget("dest_ac").set_text("Colonia", False)

        which, params = _plot(harness, ui.plotters['Galaxy'])
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

        which, params = _plot(harness, ui.plotters['RtoR'])
        assert which == 'RtoR'
        assert params['from'] == 'Colonia'
        assert 'to' not in params  # destination left blank -> circular tour
        assert params['radius'] == '40'
        assert params['max_results'] == '20'
        assert 'body_types' not in params  # plain Road to Riches has no body filter

    def test_rtor_placeholder_dest_blank(self, harness:TestHarness) -> None:
        """ A dest field showing its placeholder text must still be treated as blank, not sent. """
        ui = harness.plugin.ui
        rtor_fr = ui.plot_frames['RtoR']

        rtor_fr.nametowidget("source_ac").set_text("Colonia", False)
        rtor_fr.nametowidget("range_entry").set_text("50", False)
        rtor_fr.nametowidget("radius_entry").set_text("40", False)
        rtor_fr.nametowidget("max_results_entry").set_text("20", False)
        rtor_fr.nametowidget("dest_ac").put_placeholder()  # force the placeholder-shown state

        _, params = _plot(harness, ui.plotters['RtoR'])
        assert 'to' not in params

    @pytest.mark.parametrize('route_type,expected_body_types', [
        ('Ammonia', ['Ammonia world']),
        ('EarthLike', ['Earth-like world']),
        ('RockyMetal', ['Rocky body', 'High metal content world']),
    ])
    def test_riches_filter_calls_plot(self, harness:TestHarness, route_type, expected_body_types) -> None:
        """ Each body-type-filtered riches plotter invokes plot_route with its own fixed filter. """
        if route_type not in PLOTTER_SPECS:
            return

        ui = harness.plugin.ui
        fr = ui.plot_frames[route_type]

        fr.nametowidget("source_ac").set_text("Colonia", False)
        fr.nametowidget("dest_ac").set_text("", False)
        fr.nametowidget("range_entry").set_text("50", False)
        fr.nametowidget("radius_entry").set_text("40", False)
        fr.nametowidget("max_results_entry").set_text("20", False)

        which, params = _plot(harness, ui.plotters[route_type])
        assert which == route_type
        assert params['from'] == 'Colonia'
        assert params['body_types'] == expected_body_types
        assert params['min_value'] == 1
        assert 'use_mapping_value' not in params  # these pages don't expose that option

    def test_exobiology_plotter_calls_plot_route(self, harness:TestHarness) -> None:
        """ Exobiology's Minimum Landmark Value slider must be scaled by 1,000,000 before sending. """
        ui = harness.plugin.ui
        fr = ui.plot_frames['Exobiology']

        fr.nametowidget("source_ac").set_text("Colonia", False)
        fr.nametowidget("dest_ac").set_text("", False)
        fr.nametowidget("range_entry").set_text("50", False)
        fr.nametowidget("radius_entry").set_text("30", False)
        fr.nametowidget("max_results_entry").set_text("10", False)
        fr.nametowidget("min_value_entry").set(5)  # 5 million credits

        which, params = _plot(harness, ui.plotters['Exobiology'])
        assert which == 'Exobiology'
        assert params['from'] == 'Colonia'
        assert params['min_value'] == 5000000
        assert 'body_types' not in params

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
        which, params = _plot(harness, ui.plotters['Trade'])
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
        """ Adding/removing stop rows tracks the right systems; an empty hop list is valid. """
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
        """ A blank final_destination must be omitted entirely, not sent as literal "None". """
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

        which, params = _plot(harness, plotter)
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

        _, params = _plot(harness, plotter)
        assert params['final_destination'] == 'Colonia'

    def test_tourist_no_hops_reopen(self, harness:TestHarness) -> None:
        """ With no via-stops, reopening must not iterate the destination string letter by letter. """
        ui = harness.plugin.ui
        fr = ui.plot_frames['Tourist']
        plotter = ui.plotters['Tourist']

        fr.nametowidget("source_ac").set_text("Sol", False)
        fr.nametowidget("dest_ac").set_text("Colonia", False)
        fr.nametowidget("range_entry").set_text("50", False)

        _, params = _plot(harness, plotter)
        assert params['destination'] == 'Colonia'
        assert params['destination_names'] == []

        harness.plugin.router.route_params['Tourist'] = params
        plotter.create_frame(ui.frame)
        assert plotter.hop_rows == []

    def test_fleetcarrier_plotter_calls_plot_route(self, harness:TestHarness) -> None:
        """ Sends system names directly -- no id64 resolution needed. """
        ui = harness.plugin.ui
        fr = ui.plot_frames['FleetCarrier']
        plotter = ui.plotters['FleetCarrier']

        fr.nametowidget("source_ac").set_text("Sol", False)
        fr.nametowidget("dest_ac").set_text("Alpha Centauri", False)
        plotter._add_hop_row(-1)
        plotter.hop_rows[0]['ac'].set_text("Deciat", False)
        fr.nametowidget("capacity_used_entry").set_text("500", False)

        which, params = _plot(harness, plotter)
        assert which == 'FleetCarrier'
        assert params['source'] == 'Sol'
        assert params['destination'] == 'Alpha Centauri'
        assert params['destination_names'] == ['Deciat']
        assert params['destinations'] == ['Alpha Centauri', 'Deciat']
        assert params['capacity'] == 25000
        assert params['mass'] == 25000
        assert params['capacity_used'] == 500
        assert params['calculate_starting_fuel'] == "1"

    def test_boxel_generates_numeric_route(self, harness:TestHarness) -> None:
        """ A boxel route is built locally, with no Spansh call. """
        ui = harness.plugin.ui
        fr = ui.plot_frames['Boxel']

        fr.nametowidget("boxel_ac").set_text("Voqooe NR-C d", False)
        fr.nametowidget("start_entry").set_text("12", False)
        fr.nametowidget("end_entry").set_text("15", False)

        assert _plot(harness, ui.plotters['Boxel']) == ('', {})
        assert harness.plugin.router.last_plot == 'Boxel'

        assert [row[0] for row in harness.plugin.route.route] == [
            "Voqooe NR-C d12", "Voqooe NR-C d13", "Voqooe NR-C d14", "Voqooe NR-C d15",
        ]

    def test_boxel_strips_sequence_number(self, harness:TestHarness) -> None:
        """ A full example name's trailing sequence number is stripped, not rejected. """
        ui = harness.plugin.ui
        fr = ui.plot_frames['Boxel']

        fr.nametowidget("boxel_ac").set_text("Eol Prou IT-S c4-201", False)
        fr.nametowidget("start_entry").set_text("201", False)
        fr.nametowidget("end_entry").set_text("202", False)
        ui.plotters['Boxel'].plot()

        assert [row[0] for row in harness.plugin.route.route] == ["Eol Prou IT-S c4-201", "Eol Prou IT-S c4-202"]

    def test_boxel_rejects_missing_mass_code(self, harness:TestHarness) -> None:
        """ A boxel missing its mass-code letter is rejected, not silently accepted. """
        ui = harness.plugin.ui
        fr = ui.plot_frames['Boxel']

        fr.nametowidget("boxel_ac").set_text("Voqooe NR-C", False)
        fr.nametowidget("start_entry").set_text("1", False)
        fr.nametowidget("end_entry").set_text("5", False)

        assert _plot(harness, ui.plotters['Boxel']) == ('', {})

        assert harness.plugin.route.route == []

    def test_boxel_rejects_uppercase_mass_code(self, harness:TestHarness) -> None:
        """ Mass-code letters should be lower case. """
        ui = harness.plugin.ui
        fr = ui.plot_frames['Boxel']

        fr.nametowidget("boxel_ac").set_text("Bleae Thua IW-C A", False)
        fr.nametowidget("start_entry").set_text("1", False)
        fr.nametowidget("end_entry").set_text("5", False)

        assert _plot(harness, ui.plotters['Boxel']) == ('', {})

        assert harness.plugin.route.route == []

    def test_boxel_rejects_impossible_position(self, harness:TestHarness) -> None:
        """ An impossible boxel position is rejected, not silently accepted. """
        ui = harness.plugin.ui
        fr = ui.plot_frames['Boxel']

        fr.nametowidget("boxel_ac").set_text("Bleae Thua NI-B h", False)
        fr.nametowidget("start_entry").set_text("1", False)
        fr.nametowidget("end_entry").set_text("5", False)

        assert _plot(harness, ui.plotters['Boxel']) == ('', {})

        from Router.constants import errs
        assert harness.plugin.route.route == []
        assert ui.error_lbl['text'] == errs['boxel_impossible'] # the specific message, not the generic one

class TestLocalRouting:
    """ Offline neutron routing with fuel. """

    def test_fuel_matches_journal(self, harness:TestHarness) -> None:
        """ Range reproduces the journal's MaxJumpRange; boosted fuel is distance over the multiplier. """
        harness.play_sequence('loadout')
        ship:Ship = harness.plugin.router.ship
        full:float = ship.max_fuel_per_jump - ship.internal_tank_size

        assert abs(ship.jump_range(full) - ship.loadout['MaxJumpRange']) < 0.01
        assert ship.fuel_cost(ship.jump_range(20) * 0.999, 20) == pytest.approx(ship.max_fuel_per_jump, rel=0.01)
        assert ship.fuel_cost(200, 20, charged=True) == ship.fuel_cost(200 / ship.supercharge_multiplier, 20)

    def test_route_refuels_on_way(self, harness:TestHarness, tmp_path:Path) -> None:
        """ Builds, saves and loads both indexes, then plots and fills a route that must stop to scoop. """
        for kind, idx in _synthetic_build(tmp_path).items(): idx.save(tmp_path / kind)
        neu:Index = Index.load(tmp_path / 'neutron')
        sc:Index = Index.load(tmp_path / 'kgbfoam')
        assert (len(neu), len(sc)) == (16, 76)

        harness.play_sequence('loadout')
        ship:Ship = harness.plugin.router.ship
        src, dest = (0.0, 0.0, 0.0), (0.0, 0.0, 3000.0)
        planner:Planner = Planner(neu, sc)
        steps:list = planner.plot(ship, src, dest, ship.tank_size)

        assert not [s for s in steps if s.kind == 'fail']
        assert steps[-1].name == '<dest>'
        assert any(s.refuel for s in steps)

        # A reserve raises the point at which it refuels, so there are at least as many stops
        steps = planner.plot(ship, src, dest, ship.tank_size, 0, ship.tank_size * 0.75)
        assert steps[-1].name == '<dest>'
        assert sum(s.refuel for s in steps) >= sum(s.refuel for s in planner.plot(ship, src, dest, ship.tank_size))

    def test_detours_to_refuel(self, harness:TestHarness, tmp_path:Path) -> None:
        """ Too little fuel to boost on: rewind to the neutron, scoop next door, replan back through it and boost. """
        star:dict = {'mainStar': 'K (Yellow-Orange) Star', 'coords': {'x': 5, 'y': 0, 'z': 0}}
        rows:list = [{'id64': 1, 'name': 'N0', 'mainStar': 'Neutron Star', 'coords': {'x': 0, 'y': 0, 'z': 0}},
                     {'id64': 2, 'name': 'S0', **star},
                     {'id64': 3, 'name': 'N1', 'mainStar': 'Neutron Star', 'coords': {'x': 0, 'y': 0, 'z': 250}}]
        idx:dict = _synthetic_build(tmp_path, rows)

        harness.play_sequence('loadout')
        ship:Ship = harness.plugin.router.ship
        planner:Planner = Planner(idx['neutron'], idx['kgbfoam'])
        steps:list = planner.plot(ship, (0.0, 0.0, -10.0), (0.0, 0.0, 260.0), ship.max_fuel_per_jump + 0.5)

        assert [(s.name, s.kind) for s in steps] == [('N0', 'plain'), ('S0', 'plain'), ('N0', 'plain'), ('<dest>', 'boost')]
        assert steps[1].refuel

    def test_build_flags_fuel_stops(self, tmp_path:Path) -> None:
        """ Neutrons near scoopable stars are fuel stops; secondaries count if close; unscanned ones stay. """
        at = lambda i: {'x': i * 100, 'y': 0, 'z': 0}
        rows:list = [{'id64': 1, 'name': 'Near', 'mainStar': 'Neutron Star', 'coords': at(1), 'stars': [('K (Yellow-Orange) Star', 30.0)]},
                     {'id64': 2, 'name': 'Far', 'mainStar': 'Neutron Star', 'coords': at(2), 'stars': [('K (Yellow-Orange) Star', 80.0)]},
                     {'id64': 3, 'name': 'Close', 'mainStar': 'B (Blue-White) Star', 'coords': at(3), 'stars': [('Neutron Star', 200.0)]},
                     {'id64': 4, 'name': 'Long', 'mainStar': 'M (Red dwarf) Star', 'coords': at(4), 'stars': [('Neutron Star', 400.0)]},
                     {'id64': 5, 'name': 'Hole', 'mainStar': 'Black Hole', 'coords': at(5), 'stars': [('Neutron Star', 100.0)]},
                     {'id64': 6, 'name': 'Bare', 'mainStar': 'Neutron Star', 'coords': at(6), 'unscanned': True}]
        idx:dict = _synthetic_build(tmp_path, rows)
        neu:Index = idx['neutron']
        flags:dict = {neu.name(i): neu.fuel(i) for i in range(len(neu))}
        assert flags == {'Near': True, 'Far': False, 'Close': True, 'Hole': False, 'Bare': False}
        assert sorted(idx['kgbfoam'].name(i) for i in range(len(idx['kgbfoam']))) == ['Close', 'Long']

    def test_refuels_at_fuel_stop(self, harness:TestHarness, tmp_path:Path) -> None:
        """ With no other scoopable star about, a neutron with one beside it is where the route refuels. """
        rows:list = [{'id64': i, 'name': f'N{i}', 'mainStar': 'Neutron Star', 'coords': {'x': 0, 'y': 0, 'z': i * 150}} for i in range(6)]
        rows[1]['stars'] = [('K (Yellow-Orange) Star', 10.0)]
        idx:dict = _synthetic_build(tmp_path, rows)

        harness.play_sequence('loadout')
        ship:Ship = harness.plugin.router.ship
        steps:list = Planner(idx['neutron'], idx['kgbfoam']).plot(ship, (0.0, 0.0, -10.0), (0.0, 0.0, 760.0), ship.max_fuel_per_jump + 0.5)

        assert steps[-1].name == '<dest>'
        assert [(s.name, s.kind) for s in steps if s.refuel] == [('N1', 'boost')]

    def test_tops_up_before_short(self, harness:TestHarness, tmp_path:Path) -> None:
        """ A fuel stop tops up when the fuel left won't reach the next one, saving a detour to a scoopable star later. """
        rows:list = [{'id64': i, 'name': f'N{i}', 'mainStar': 'Neutron Star', 'coords': {'x': 0, 'y': 0, 'z': i * 300}} for i in range(5)]
        rows[1]['stars'] = [('K (Yellow-Orange) Star', 10.0)]
        rows.append({'id64': 10, 'name': 'K', 'mainStar': 'K (Yellow-Orange) Star', 'coords': {'x': 20, 'y': 0, 'z': 620}})
        idx:dict = _synthetic_build(tmp_path, rows)

        # Enough to land on N1 above the refuel threshold, but not on N2
        harness.play_sequence('loadout')
        ship:Ship = harness.plugin.router.ship
        hop:float = ship.fuel_cost(300, ship.tank_size, 0, True)
        steps:list = Planner(idx['neutron'], idx['kgbfoam']).plot(ship, (0.0, 0.0, -10.0), (0.0, 0.0, 1210.0), ship.max_fuel_per_jump + 1.5 * hop)

        assert steps[-1].name == '<dest>'
        assert [s.name for s in steps if s.refuel] == ['N1']
        assert 'K' not in [s.name for s in steps]

    def test_local_data_installs(self, harness:TestHarness, tmp_path:Path) -> None:
        """ Downloads, checks and unpacks each index in the manifest, skips unchanged ones, drops retired ones, keeps a backup. """
        import hashlib, io, zipfile
        idx:dict = _synthetic_build(tmp_path)
        assets:dict = {}
        files:dict = {}
        for kind in ('neutron', 'kgbfoam', 'kgbfoam_add'):
            idx['kgbfoam' if kind == 'kgbfoam_add' else kind].save(tmp_path / 'built' / kind)
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
                for f in (tmp_path / 'built' / kind).iterdir(): z.write(f, arcname=f.name)
            assets[f'{kind}.zip'] = buf.getvalue()
            files[kind] = {'asset': f'{kind}.zip', 'sha256': hashlib.sha256(buf.getvalue()).hexdigest(), 'size': len(buf.getvalue())}

        data:LocalData = LocalData(tmp_path / 'data', tmp_path / 'backup')

        def update() -> bool:
            mock_requests.queue_response('get', mock_requests.MockResponse(json_data={'files': files}), url=f"{URL}/manifest.json")
            for name, body in assets.items():
                mock_requests.queue_response('get', mock_requests.MockResponse(content=body), url=f"{URL}/{name}")
            return data.update(lambda s: None)

        assert [update() for _ in range(2)] == [True, False]
        assert all((tmp_path / 'data' / k / 'meta.json').exists() for k in files)

        # The add-on and the base search as one, with the add-on's stars numbered after the base's
        both:Combined = Combined(Index.load(tmp_path / 'data' / 'kgbfoam'), Index.load(tmp_path / 'data' / 'kgbfoam_add'))
        assert len(both) == 2 * len(idx['kgbfoam']) and len(both.near((5.0, 0.0, 0.0), 1)) == 2

        del files['kgbfoam_add']
        assert update() and not (tmp_path / 'data' / 'kgbfoam_add').exists()

        # A changed index replaces the installed one, which becomes the single backup
        files['neutron'] = dict(files['kgbfoam'])
        assert update() and (tmp_path / 'backup' / 'neutron' / 'meta.json').exists()

        files['neutron']['sha256'] = 'bad'
        with pytest.raises(ValueError): update()

        data.delete()
        assert data.size() == 0 and not (tmp_path / 'backup').exists()

    def test_old_index_not_ready(self, harness:TestHarness, tmp_path:Path, monkeypatch) -> None:
        """ Indexes in an older format aren't ready, so the startup check downloads the current ones. """
        monkeypatch.setattr(harness.plugin, 'plugin_dir', str(tmp_path))
        for kind, idx in _synthetic_build(tmp_path).items(): idx.save(tmp_path / 'data' / kind)
        harness.config.set(f"{harness.plugin.plugin_name}_local_router", True)
        assert harness.plugin.localdata.ready()

        meta:Path = tmp_path / 'data' / 'neutron' / 'meta.json'
        meta.write_text(json.dumps({**json.loads(meta.read_text()), 'version': 2}))
        assert not harness.plugin.localdata.ready()

    def test_local_plot_makes_route(self, harness:TestHarness, tmp_path:Path, monkeypatch) -> None:
        """ The Local route type looks up the destination on Spansh and plots from the data folder's indexes. """
        monkeypatch.setattr(harness.plugin, 'plugin_dir', str(tmp_path))
        for kind, idx in _synthetic_build(tmp_path).items(): idx.save(tmp_path / 'data' / kind)
        assert not harness.plugin.localdata.ready()  # data present, but the local router is still off
        harness.config.set(f"{harness.plugin.plugin_name}_local_router", True)
        assert harness.plugin.localdata.ready()

        # Opening the Local plotter loads the indexes in the background, ready for the first plot
        harness.plugin.router.local = None
        harness.plugin.ui.show_frame('Local')
        for _ in range(250):
            if harness.plugin.router.local is not None: break
            time.sleep(0.02)
        assert harness.plugin.router.local is not None

        harness.play_sequence('loadout')
        router = harness.plugin.router
        router.system, router.star_pos, router.address, router.local = 'Sol', (0.0, 0.0, 0.0), 10477373803, None

        _respond('get', 200, {'results': [{'name': 'Far Away', 'x': 0, 'y': 0, 'z': 3000, 'id64': 999}]})
        router.plot_route('Local', {'from': 'Sol', 'to': 'far away', 'ship': router.ship_id, 'cargo': 0, 'reserve_size': 0,
                                    'fuel': router.ship.tank_size})
        _wait_plot(harness)

        route = harness.plugin.route
        names:list = [r[route.colind('System Name')] for r in route.route]
        assert (names[0], names[-1]) == ('Sol', 'Far Away')
        assert route.navroute['Sol']['StarPos'] == [0.0, 0.0, 0.0] and route.navroute['Far Away']['StarPos'] == [0, 0, 3000]
        assert all(v['StarPos'] and v['SystemAddress'] is not None for v in route.navroute.values())
        assert (route.navroute['Sol']['SystemAddress'], route.navroute['Far Away']['SystemAddress']) == (10477373803, 999)
        assert route.colind('Neutron') is not None
        assert any(r[route.colind('Refuel')] for r in route.route)

    def test_local_ship_follows_galaxy(self, harness:TestHarness) -> None:
        """ Local's ship dropdown stays in step with Galaxy's and sets cargo the same way. """
        harness.play_sequence('loadout')
        ui, router = harness.plugin.ui, harness.plugin.router
        router.cargo = 12

        ui.switch_ship(router.ship)
        assert ui.plotters['Local'].shipvar.get() == router.ship.name
        assert ui.get_item('Local', 'cargo_entry') == '12'

        other:str = next((n for n in router.shipnames() if n != router.ship.name), '')
        if not other: pytest.skip('only one ship loaded')
        ui.plotters['Local'].shipvar.set(other)
        assert ui.plotters['Galaxy'].shipvar.get() == other
        assert ui.get_item('Local', 'cargo_entry') == ui.get_item('Galaxy', 'cargo_entry') == '0'

    @pytest.mark.manual_only
    @pytest.mark.slow
    def test_real_data_routes(self, harness:TestHarness) -> None:
        """ Plots three long routes from the indexes in $ND_LOCAL_DATA or data, building them from a dump if missing. """
        import time
        folder:Path = Path(os.environ.get('ND_LOCAL_DATA', Path(__file__).parent.parent / 'data'))
        metas:list = [folder / k / 'meta.json' for k in ('neutron', 'kgbfoam')]
        current:bool = all(m.exists() and json.loads(m.read_text()).get('version') == VERSION for m in metas)
        dumps:list = [folder / f'{d}.json.gz' for d in ('systems', 'galaxy')]
        if not current and not all(d.exists() for d in dumps):
            pytest.skip(f'no v{VERSION} indexes or systems and galaxy dumps in {folder}; download the star-data-v{VERSION} release there')

        if not current:
            t:float = time.time()
            for kind, idx in build(dumps[0], extras=galaxy_extras(dumps[1])).items(): idx.save(folder / kind)
            print(f"\nbuilt indexes in {time.time() - t:.0f}s")

        neu:Index = Index.load(folder / 'neutron')
        sc:Index = Index.load(folder / 'kgbfoam')
        planner:Planner = Planner(neu, sc)
        harness.play_sequence('loadout')
        ship:Ship = harness.plugin.router.ship
        rng:float = ship.jump_range(ship.tank_size)
        print(f"\n{len(neu):,} neutrons, {len(sc):,} scoopable; {ship.name} {rng:.2f} Ly, tank {ship.tank_size} t")

        dests:dict = {'Colonia': (-9530.5, -910.28125, 19808.125), 'Sagittarius A*': (25.21875, -20.90625, 25899.96875),
                      'Beagle Point': (-1111.5625, -134.21875, 65269.75)}
        for dest, pos in dests.items():
            t = time.time()
            steps:list = planner.plot(ship, (0.0, 0.0, 0.0), pos, ship.tank_size)
            fails:list = [s.name for s in steps if s.kind == 'fail']
            print(f"{dest:15} {len(steps) - len(fails)} jumps, {sum(s.kind == 'boost' for s in steps)} boosted, "
                  f"{sum(s.refuel for s in steps)} refuels, "
                  f"{sum(a.name == c.name and b.refuel for a, b, c in zip(steps, steps[1:], steps[2:]))} detours, "
                  f"min fuel {min(s.fuel for s in steps):.1f} t, "
                  f"{time.time() - t:.1f}s {fails}")
            for s in steps[-4:] if fails else []: print(f"    {s.kind:5} {s.dist:6.1f} Ly fuel {s.fuel:5.1f}  {s.name}")
            assert not fails

        # The same plot through the Local route type, with Spansh's live lookup for the destination
        router = harness.plugin.router
        router.system, router.star_pos, router.local = 'Sol', (0.0, 0.0, 0.0), planner
        t = time.time()
        router.plot_route('Local', {'from': 'Sol', 'to': 'colonia', 'ship': router.ship_id, 'cargo': 0, 'reserve_size': 0,
                                    'fuel': router.ship.tank_size})
        _wait_plot(harness, 120)

        route = harness.plugin.route
        print(f"Local route type: {len(route.route)} rows, {route.total_jumps()} jumps, headers {route.hdrs}, {time.time() - t:.1f}s")
        assert route.route[-1][route.colind('System Name')] == 'Colonia'

class TestBoxelExistence:
    """ Boxel coords/existence/prefix, verified against two real systems' actual id64 values. """

    def test_coords_match_real_system(self) -> None:
        """ Eol Prou RS-T d3-94 -- real id64 3238296097059 decodes to box coords [9, 4, 4]. """
        assert _boxel_coords('R', 'S', 'T', 3) == (9, 4, 4)

    def test_coords_match_multi_digit_subnum(self) -> None:
        """ Vegnue WK-E d12-0 -- real id64 9303087083 decodes to box coords [10, 7, 13]. """
        assert _boxel_coords('W', 'K', 'E', 12) == (10, 7, 13)

    def test_h_code_at_origin(self) -> None:
        """ h is the whole sector -- one boxel, "AA-A", confirmed against a real system. """
        assert _boxel_exists('A', 'A', 'A', 'h', 0) is True
        assert _boxel_exists('B', 'A', 'A', 'h', 0) is False
        assert _boxel_exists('A', 'B', 'A', 'h', 0) is False
        assert _boxel_exists('A', 'A', 'B', 'h', 0) is False

    def test_g_code_matches_boxels(self) -> None:
        """ Only "AA-A g"/"BA-A g" are real boxels -- every other letter combination is empty. """
        assert _boxel_exists('A', 'A', 'A', 'g', 0) is True
        assert _boxel_exists('B', 'A', 'A', 'g', 0) is True
        assert _boxel_exists('A', 'B', 'A', 'g', 0) is False
        assert _boxel_exists('C', 'A', 'A', 'g', 0) is False

    def test_boxel_range_depends_on_code(self) -> None:
        """ The same letters can be a real boxel under one mass code and not another. """
        assert _boxel_exists('I', 'W', 'C', 'a', 0) is True
        assert _boxel_exists('I', 'W', 'C', 'h', 0) is False

    def test_prefix_accepts_h_boxel(self) -> None:
        assert _boxel_prefix("Vegnoae AA-A h") == "Vegnoae AA-A h"

    def test_prefix_rejects_impossible_boxel(self) -> None:
        assert _boxel_prefix("Bleae Thua NI-B h") is None


class TestUIFunctions:
    """ Test UI functions """

    def test_menu_has_current_system(self, harness:TestHarness) -> None:
        """ Showing a plotter puts the current system first in its source menu. """
        harness.plugin.router.system = 'Apurui'
        harness.plugin.ui.show_frame('Neutron')

        ac:th.Autocompleter|None = harness.plugin.ui.plotters['Neutron'].src_ac
        assert ac is not None
        assert ac.menu.entrycget(4, 'label') == 'Apurui' # after Cut, Copy, Paste and the separator

    def test_jump_refreshes_source_menu(self, harness:TestHarness) -> None:
        """ A system change while a plotter is showing moves the new system to the top of its source menu. """
        harness.plugin.ui.show_frame('Neutron')
        ac:th.Autocompleter|None = harness.plugin.ui.plotters['Neutron'].src_ac
        assert ac is not None
        assert ac.menu.entrycget(4, 'label') != 'Deciat'

        harness.fire_event({"timestamp": "2026-11-03T00:00:00Z", "event": "FSDJump", "StarSystem": "Deciat"})

        assert ac.menu.entrycget(4, 'label') == 'Deciat'

    def test_query_station_names(self, harness:TestHarness) -> None:
        """ Formats each typeahead result as "System / Station" for the combined input field. """
        ui = harness.plugin.ui

        _respond('get', 200, [{"system": "Shinrarta Dezhra", "name": "Jameson Memorial"}])
        assert ui.query_station_names('Jameson') == ['Shinrarta Dezhra / Jameson Memorial']

    def test_ship_menu_syncs_plotters(self, harness:TestHarness) -> None:
        """ Picking a ship from a dropdown, as Tk does it, moves the other plotters to that ship. """
        harness.play_sequence('loadout')
        cb = harness.plugin.ui.plotters['Galaxy'].shipdd.obj
        other:int = next(i for i, n in enumerate(cb['values']) if n != cb.get())
        cb.tk.call('ttk::combobox::SelectEntry', str(cb), other)
        assert harness.plugin.ui.plotters['Local'].shipvar.get() == cb['values'][other]

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
        """ The button shows system + station truncated to fit; the tooltip carries commodity/profit. """
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

    def test_update_label_waits_for_zip(self, harness:TestHarness) -> None:
        """ The update label only appears once the update zip has downloaded. """
        ui = harness.plugin.ui
        updater = harness.plugin.updater
        updater.update_available = True
        updater.install_update = True

        ui.show_plugin_update()
        assert not hasattr(ui, "update")

        updater.zip_downloaded = "update.zip"
        ui.show_plugin_update(1)
        assert ui.update.grid_info()

    def test_fetched_notice_displayed(self, harness:TestHarness) -> None:
        """ Ties the real fetch/parse path to the real UI, not just a directly-set notice. """
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

    def test_show_creates_populated_window(self, harness: TestHarness) -> None:
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

    def test_close_saves_window_geometry(self, harness: TestHarness) -> None:
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
        """ A Profit block appears for Trade routes, absent for route types with no earned-value column. """
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

    def test_show_renders_table_selection(self, harness: TestHarness) -> None:
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


class TestPlotting:
    """Test end to end plotting functionality (neutron/galaxy routes)."""

    def test_plot_route_unknown_type(self, harness:TestHarness):
        """Unknown plot types should return False and not start plotting."""
        result:bool = harness.plugin.router.plot_route('UnsupportedType', {})
        assert result is False

    @pytest.mark.slow
    def test_plot_neutron_route(self, harness:TestHarness) -> None:
        """ Perform a live Neutron plot """


        res:bool = harness.plugin.router.plot_route('Neutron',
                                            {'from': 'Apurui', 'to': 'Bleae Thua NI-B b27-5',
                                            'range': '60.00', 'efficiency': '60',
                                            'supercharge_multiplier': '4'})
        assert res == True
        _wait_plot(harness)

        assert harness.plugin.route is not None
        assert harness.plugin.route.source() == 'Apurui'
        assert harness.plugin.route.destination() == 'Bleae Thua NI-B b27-5'
        assert harness.plugin.route.total_jumps() == 31

    @pytest.mark.slow
    def test_plot_neutron_route_caspian(self, harness:TestHarness) -> None:
        """ Perform a live Neutron plot for a Caspian explorer """


        res:bool = harness.plugin.router.plot_route('Neutron',
                                            {'from': 'Apurui', 'to': 'Bleae Thua NI-B b27-5',
                                            'range': '60.00', 'efficiency': '60',
                                            'supercharge_multiplier': '6'})
        assert res == True
        _wait_plot(harness)

        assert harness.plugin.route is not None
        assert harness.plugin.route.source() == 'Apurui'
        assert harness.plugin.route.destination() == 'Bleae Thua NI-B b27-5'
        assert harness.plugin.route.total_jumps() == 21

    @pytest.mark.slow
    def test_plot_galaxy_route(self, harness:TestHarness) -> None:
        """Perform a live galaxy plot and check results."""

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


        res:bool = harness.plugin.router.plot_route('Galaxy', galaxy_params)
        assert res == True

        _wait_plot(harness)

        assert harness.plugin.router.src == 'Apurui'
        assert harness.plugin.router.dest == 'Bleae Thua NI-B b27-5'

        # This route seems to vary based on current conditions
        assert harness.plugin.route.total_jumps() in [18, 21, 28], f"Jumps {harness.plugin.route.total_jumps()}"

    @pytest.mark.slow
    def test_plot_galaxy_route_caspian(self, harness:TestHarness) -> None:
        """Perform a live galaxy plot with a caspian explorer and check results."""

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


        res:bool = harness.plugin.router.plot_route('Galaxy', galaxy_params)
        assert res == True

        _wait_plot(harness)

        assert harness.plugin.route is not None
        assert harness.plugin.router.src == galaxy_params['source']
        assert harness.plugin.router.dest == galaxy_params['destination']
        assert harness.plugin.route.total_jumps() == 9, f"Jumps {harness.plugin.route.total_jumps()}"

    @pytest.mark.slow
    def test_plot_rtor_route(self, harness:TestHarness) -> None:
        """ Perform a live Road-to-Riches plot """


        res:bool = harness.plugin.router.plot_route('RtoR',
                                            {'from': 'Colonia', 'range': '50', 'radius': '40',
                                            'max_results': '20', 'avoid_thargoids': '1', 'loop': '1'})
        assert res == True
        _wait_plot(harness)

        assert harness.plugin.route is not None
        # The route table lists bodies, not the queried system, so source() isn't 'Colonia'.
        assert harness.plugin.router.src == 'Colonia'
        assert harness.plugin.route.source() != None
        assert "Body" in harness.plugin.route.hdrs
        assert "Est Scan Value" in harness.plugin.route.hdrs
        # Not an exact count: unscanned bodies here change over time in the live galaxy.
        assert len(harness.plugin.route.route) > 0

    @pytest.mark.slow
    def test_plot_ammonia_route(self, harness:TestHarness) -> None:
        """ A live Ammonia World plot -- rare enough that it's allowed several minutes, not ~20s. """
        if 'Ammonia' not in PLOTTER_SPECS:
            return



        res:bool = harness.plugin.router.plot_route('Ammonia',
                                            {'from': 'Colonia', 'range': '50', 'radius': '150',
                                            'max_results': '20', 'avoid_thargoids': '1', 'loop': '1',
                                            'body_types': ['Ammonia world'], 'min_value': 1, 'max_time': 240})
        assert res == True
        _wait_plot(harness)

        assert harness.plugin.route is not None
        assert harness.plugin.router.src == 'Colonia'
        assert "Body" in harness.plugin.route.hdrs
        assert len(harness.plugin.route.route) > 0

    @pytest.mark.slow
    def test_plot_exobiology_route(self, harness:TestHarness) -> None:
        """ A live Exobiology plot -- checks for Species/Landmark Value columns. """


        res:bool = harness.plugin.router.plot_route('Exobiology',
                                            {'from': 'Colonia', 'range': '50', 'radius': '30',
                                            'max_results': '10', 'avoid_thargoids': '1', 'loop': '1',
                                            'min_value': 100000, 'max_time': 60})
        assert res == True
        _wait_plot(harness)

        assert harness.plugin.route is not None
        assert harness.plugin.router.src == 'Colonia'
        assert "Species" in harness.plugin.route.hdrs
        assert "Value" in harness.plugin.route.hdrs
        assert len(harness.plugin.route.route) > 0

    @pytest.mark.slow
    def test_plot_trade_route(self, harness:TestHarness) -> None:
        """ A live Trade Planner plot from a busy hub, checking commodity prices across stations. """


        res:bool = harness.plugin.router.plot_route('Trade',
                                            {'system': 'Shinrarta Dezhra', 'station': 'Jameson Memorial',
                                            'starting_capital': '1000000', 'max_cargo': '200', 'max_hops': '5',
                                            'max_hop_distance': '50', 'max_system_distance': '10000000',
                                            'requires_large_pad': '0', 'allow_prohibited': '0',
                                            'allow_planetary': '0', 'allow_player_owned': '0',
                                            'allow_restricted_access': '0', 'unique': '0', 'permit': '0',
                                            'max_time': 60})
        assert res == True
        _wait_plot(harness)

        assert harness.plugin.route is not None
        assert harness.plugin.router.src == 'Shinrarta Dezhra'
        assert "Station Name" in harness.plugin.route.hdrs
        assert "Commodity" in harness.plugin.route.hdrs
        assert "Cumulative Profit" in harness.plugin.route.hdrs
        assert len(harness.plugin.route.route) > 0

    @pytest.mark.slow
    def test_plot_tourist_route(self, harness:TestHarness) -> None:
        """ A live Tourist Route plot between nearby systems, so it stays fast. """


        res:bool = harness.plugin.router.plot_route('Tourist',
                                            {'source': 'Sol', 'destination': ['Alpha Centauri', "Barnard's Star"],
                                            'range': '50', 'max_time': 60})
        assert res == True
        _wait_plot(harness)

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
        harness.config.set(f"{harness.plugin.plugin_name}_progress_display", "PD jc={jc} jr={jr} jt={jt} dc={dc} dr={dr} dt={dt} dh={dh} jh={jh} rj={rj} rd={rd} st={st}")

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
        filename:str = str(Path(__file__).parent / "config" / "fc-Bleae-Voqooe.csv")
        harness.plugin.router.import_route(filename)

        events:list = harness.events.get('carrier_events', [])
        harness.fire_event(events[0])
        assert harness.plugin.router.carrier_state == CarrierStates.Jumping
        harness.fire_event(events[1])
        assert harness.plugin.router.carrier_state == CarrierStates.Cooldown
