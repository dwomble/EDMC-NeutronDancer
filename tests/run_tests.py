"""
Advanced test suite for EDMC Neutron Dancer plugin using pytest.

Run with: pytest run_tests.py -v
"""

import pytest
import sys
from pathlib import Path
from typing import Optional

# Setup path for imports (tests are in tests/ subdirectory)
plugin_dir = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_dir))

# Mock config before importing Router modules
class MockConfig:
    def __init__(self):
        self.data = {}
    
    def __setitem__(self, key, value):
        self.data[key] = value
    
    def __getitem__(self, key):
        return self.data.get(key)
    
    def get(self, key, default=None):
        return self.data.get(key, default)
    
    def set(self, key, value):
        self.data[key] = value

sys.modules['config'] = type('module', (), {
    'appname': 'EDMC',
    'config': MockConfig()
})()

from test_harness import TestHarness
from load import journal_entry
from Router.context import Context

# If loadouts.json contains ships, use them for tests; otherwise fall back to defaults
AVAILABLE_LOADOUTS = TestHarness.get_available_loadouts()
if AVAILABLE_LOADOUTS and len(AVAILABLE_LOADOUTS) > 0:
    SHIP1 = AVAILABLE_LOADOUTS[0]
else:
    SHIP1 = {'ShipID': '1', 'Ship': 'Anaconda', 'ShipName': 'Anaconda'}

if AVAILABLE_LOADOUTS and len(AVAILABLE_LOADOUTS) > 1:
    SHIP2 = AVAILABLE_LOADOUTS[1]
else:
    SHIP2 = {'ShipID': '2', 'Ship': 'AspX', 'ShipName': 'AspX'}


@pytest.fixture
def harness():
    """Provide a fresh test harness for each test."""
    test_harness = TestHarness()
    test_harness.register_journal_handler(journal_entry)
    yield test_harness
    # Cleanup if needed
    Context.router = None


class TestStartup:
    """Test plugin startup behavior."""
    
    def test_startup_event(self, harness: TestHarness):
        """Test that startup event sets system correctly."""
        harness.startup("Sol")
        assert harness.router.system == "Sol"
    
    def test_startup_different_systems(self, harness: TestHarness):
        """Test startup in various systems."""
        for system in ["Sirius", "Betelgeuse", "Vega"]:
            harness2 = TestHarness()
            harness2.register_journal_handler(journal_entry)
            harness2.startup(system)
            assert harness2.router.system == system


class TestShipLoadout:
    """Test ship loadout and switching."""
    
    def test_loadout_event(self, harness: TestHarness):
        """Test loading a ship."""
        use_real = True if AVAILABLE_LOADOUTS else False
        harness.loadout(
            ship_id=str(SHIP1.get('ShipID', '1')),
            ship_type=SHIP1.get('Ship', 'Anaconda'),
            ship_name=SHIP1.get('ShipName', 'Test Ship'),
            use_real_loadout=use_real
        )
        assert harness.router.ship_id == str(SHIP1.get('ShipID', '1'))
        assert harness.router.ship is not None
        assert harness.router.ship.type == SHIP1.get('Ship', 'Anaconda')
        assert harness.router.ship.name == SHIP1.get('ShipName', 'Test Ship')
    
    def test_loadout_with_real_data(self, harness: TestHarness):
        """Test loading a ship with real loadout data."""
        available = TestHarness.get_available_loadouts()
        if available:
            ship = available[0]
            harness.loadout(
                ship_id=str(ship['ShipID']),
                ship_type=ship['Ship'],
                ship_name=ship['ShipName'],
                use_real_loadout=True
            )
            assert harness.router.ship is not None
            # Real loadout should have modules
            assert len(harness.router.router.ships[str(ship['ShipID'])].loadout.get('Modules', [])) > 0
    
    def test_multiple_ships(self, harness: TestHarness):
        """Test loading multiple different ships."""
        # Load first ship
        use_real = True if AVAILABLE_LOADOUTS else False
        harness.loadout(ship_id=str(SHIP1.get('ShipID', '1')), ship_type=SHIP1.get('Ship', 'Anaconda'), ship_name=SHIP1.get('ShipName', 'Anaconda'), use_real_loadout=use_real)
        assert harness.router.ship_id == str(SHIP1.get('ShipID', '1'))

        harness.loadout(ship_id=str(SHIP2.get('ShipID', '2')), ship_type=SHIP2.get('Ship', 'AspX'), ship_name=SHIP2.get('ShipName', 'AspX'), use_real_loadout=use_real)
        assert harness.router.ship_id == str(SHIP2.get('ShipID', '2'))

        # Ships should be stored in shipyard
        assert str(SHIP1.get('ShipID', '1')) in harness.router.ships
        assert str(SHIP2.get('ShipID', '2')) in harness.router.ships
    
    def test_ship_range_calculation(self, harness: TestHarness):
        """Test that ship range is calculated."""
        use_real = True if AVAILABLE_LOADOUTS else False
        harness.loadout(ship_id=str(SHIP1.get('ShipID', '1')), ship_type=SHIP1.get('Ship', 'Anaconda'), use_real_loadout=use_real)
        
        assert harness.router.ship is not None
        assert hasattr(harness.router.ship, 'range')
        assert harness.router.ship.range > 0


class TestJumps:
    """Test jump tracking and route management."""
    
    def test_single_jump(self, harness: TestHarness):
        """Test a single FSD jump."""
        harness.startup("Sol")
        harness.jump("Sirius", jump_distance=8.6)
        assert harness.router.system == "Sirius"
    
    def test_jump_sequence(self, harness: TestHarness):
        """Test a sequence of jumps."""
        systems = ["Sol", "Sirius", "Betelgeuse", "Vega"]
        distances = [8.6, 11.2, 19.5, 25.3]
        
        harness.startup(systems[0])
        for system, distance in zip(systems[1:], distances[1:]):
            harness.jump(system, jump_distance=distance)
            assert harness.router.system == system
    
    def test_jump_with_different_star_classes(self, harness: TestHarness):
        """Test jumps to different star classes."""
        harness.startup("Sol")
        
        star_classes = ['K', 'F', 'G', 'A', 'B', 'O']
        for i, star_class in enumerate(star_classes):
            system = f"TestSystem{i}"
            harness.jump(system, jump_distance=20.0, star_class=star_class)
            assert harness.router.system == system


class TestCargo:
    """Test cargo management."""
    
    def test_cargo_event(self, harness: TestHarness):
        """Test cargo event updates."""
        harness.cargo(count=100)
        assert harness.router.cargo == 100
        
        harness.cargo(count=50)
        assert harness.router.cargo == 50
        
        harness.cargo(count=0)
        assert harness.router.cargo == 0


class TestComplexScenarios:
    """Test complex multi-step scenarios."""
    
    def test_full_route_scenario(self, harness: TestHarness):
        """Test a complete route scenario with jumps and cargo."""
        # Setup
        harness.startup("Sol")
        use_real = True if AVAILABLE_LOADOUTS else False
        harness.loadout(ship_id=str(SHIP1.get('ShipID', '1')), ship_type=SHIP1.get('Ship', 'Anaconda'), ship_name=SHIP1.get('ShipName','Route Runner'), use_real_loadout=use_real)
        harness.cargo(0)
        
        # Simulate route
        route_systems = ["Sol", "Sirius", "Procyon", "Altair"]
        distances = [8.6, 11.4, 10.4]
        
        for i, system in enumerate(route_systems[1:], 1):
            harness.jump(system, jump_distance=distances[i-1])
            assert harness.router.system == system
        
        # Final state check
        state = harness.get_router_state()
        assert state['system'] == "Altair"
        assert state['cargo'] == 0
    
    def test_carrier_jump_scenario(self, harness: TestHarness):
        """Test carrier jump with docking."""
        harness.startup("Sol")
        harness.carrier_jump("Sirius", station="My Fleet Carrier", docked=True)
        
        assert harness.router.system == "Sirius"
        assert harness.station == "My Fleet Carrier"
    
    def test_supercruise_exit(self, harness: TestHarness):
        """Test supercruise exit event."""
        harness.startup("Sol")
        harness.supercruise_exit("Sirius", body="A", position=[0, 0, 0])
        
        # System should be updated
        assert harness.router.system == "Sirius"
    
    def test_location_event(self, harness: TestHarness):
        """Test location event."""
        harness.startup("Sol")
        harness.location("Sirius", station="Habitats", body="", planetary=False)
        
        assert harness.router.system == "Sirius"
        assert harness.station == "Habitats"


class TestShipyardSwap:
    """Test ship swapping from shipyard."""
    
    def test_swap_existing_ship(self, harness: TestHarness):
        """Test swapping to a previously loaded ship."""
        # Load multiple ships
        use_real = True if AVAILABLE_LOADOUTS else False
        harness.loadout(ship_id=str(SHIP1.get('ShipID', '1')), ship_type=SHIP1.get('Ship', 'Anaconda'), use_real_loadout=use_real)
        harness.loadout(ship_id=str(SHIP2.get('ShipID', '2')), ship_type=SHIP2.get('Ship', 'AspX'), use_real_loadout=use_real)
        
        # Swap back to first ship
        harness.shipyard_swap("1")
        assert harness.router.ship_id == "1"
        assert harness.router.ship.type == "Anaconda"
    
    def test_swap_unknown_ship(self, harness: TestHarness):
        """Test swapping to an unknown ship."""
        use_real = True if AVAILABLE_LOADOUTS else False
        harness.loadout(ship_id=str(SHIP1.get('ShipID', '1')), ship_type=SHIP1.get('Ship', 'Anaconda'), use_real_loadout=use_real)
        
        # Try to swap to unknown ship
        harness.shipyard_swap("999")
        # Should reset ship_id since ship not found
        assert harness.router.ship_id == ""


class TestStateManagement:
    """Test router state management."""
    
    def test_router_singleton(self, harness: TestHarness):
        """Test that Router is a singleton."""
        harness.startup("Sol")
        
        # Create another harness - should share same router instance
        harness2 = TestHarness()
        assert harness.router is harness2.router
    
    def test_save_load_parameters(self, harness: TestHarness):
        """Test that route parameters are saved."""
        harness.startup("Sol")
        use_real = True if AVAILABLE_LOADOUTS else False
        harness.loadout(ship_id=str(SHIP1.get('ShipID', '1')), ship_type=SHIP1.get('Ship', 'Anaconda'), use_real_loadout=use_real)
        
        state = harness.get_router_state()
        assert state['system'] == "Sol"
        assert state['ship_id'] == "1"


def test_harness_initialization():
    """Test basic harness initialization."""
    harness = TestHarness()
    assert harness.commander == "TestCommander"
    assert harness.system == "Sol"
    assert harness.router is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
