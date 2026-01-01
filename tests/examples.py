#!/usr/bin/env python3
"""
Example usage of the Neutron Dancer test harness.

This script demonstrates various ways to use the test harness to simulate
journal events and test plugin behavior.
"""

import sys
from pathlib import Path

# Add plugin to path (go up one level from tests/)
plugin_dir = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_dir))

# Add tests to path
sys.path.insert(0, str(Path(__file__).parent))

# Mock config
class MockConfig:
    def __init__(self):
        self.data = {}
    
    def __setitem__(self, key, value):
        self.data[key] = value
    
    def __getitem__(self, key):
        return self.data.get(key)
    
    def get(self, key, default=None):
        return self.data.get(key, default)

sys.modules['config'] = type('module', (), {
    'appname': 'EDMC',
    'config': MockConfig()
})()

from test_harness import TestHarness, create_test_scenario
from load import journal_entry


def example_basic_usage():
    """Example 1: Basic harness usage."""
    print("=" * 60)
    print("EXAMPLE 1: Basic Harness Usage")
    print("=" * 60)
    
    harness = TestHarness()
    harness.register_journal_handler(journal_entry)
    
    print("\nStarting at Sol...")
    harness.startup("Sol")
    harness.print_state()
    
    print("\nLoading Anaconda...")
    harness.loadout(
        ship_id="1",
        ship_type="Anaconda",
        ship_name="Explorer"
    )
    harness.print_state()


def example_jump_sequence():
    """Example 2: Simulate a jump sequence."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Jump Sequence")
    print("=" * 60)
    
    harness = TestHarness()
    harness.register_journal_handler(journal_entry)
    
    print("\nStarting at Sol with fully loaded Anaconda...")
    harness.startup("Sol")
    harness.loadout(ship_id="1", ship_type="Anaconda", ship_name="Route Runner")
    harness.cargo(0)
    
    print("\nExecuting jump sequence:")
    jumps = [
        ("Sirius", 8.6),
        ("Altair", 11.2),
        ("Vega", 25.3),
        ("Deneb", 19.7),
        ("Betelgeuse", 24.5),
    ]
    
    for system, distance in jumps:
        print(f"\n  Jumping to {system} ({distance} ly)...")
        harness.jump(system, jump_distance=distance)
        state = harness.get_router_state()
        print(f"    Current system: {state['system']}")


def example_multiple_ships():
    """Example 3: Test multiple ships."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Multiple Ships from loadouts.json")
    print("=" * 60)
    
    harness = TestHarness()
    harness.register_journal_handler(journal_entry)
    
    # Get available loadouts
    available = harness.get_available_loadouts()
    print(f"\nFound {len(available)} ships in loadouts.json")
    
    if available:
        print("\nLoading real ships from loadouts.json...")
        for ship_info in available[:3]:  # Load first 3
            print(f"\n  Loading {ship_info['ShipName']} ({ship_info['Ship']})...")
            harness.loadout(
                ship_id=str(ship_info['ShipID']),
                ship_type=ship_info['Ship'],
                ship_name=ship_info['ShipName']
            )
            if harness.router.ship:
                print(f"    Range: {harness.router.ship.range} ly")
                print(f"    Unladen mass: {ship_info['UnladenMass']} t")
        
        print("\n\nShips in shipyard:")
        state = harness.get_router_state()
        for sid, ship_str in state['ships'].items():
            print(f"  {sid}: {ship_str}")
    else:
        print("\nNo ships found in loadouts.json - using generated ships")
        ships = [
            ("1", "Anaconda", "Explorer"),
            ("2", "AspX", "Trader"),
            ("3", "AllianceChallenger", "Fighter"),
        ]
        
        for ship_id, ship_type, ship_name in ships:
            print(f"\n  Loading {ship_name} ({ship_type})...")
            harness.loadout(ship_id=ship_id, ship_type=ship_type, ship_name=ship_name, use_real_loadout=False)
            if harness.router.ship:
                print(f"    Range: {harness.router.ship.range} ly")


def example_cargo_management():
    """Example 4: Track cargo through journey."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Cargo Management")
    print("=" * 60)
    
    harness = TestHarness()
    harness.register_journal_handler(journal_entry)
    
    print("\nStarting journey with cargo tracking...")
    harness.startup("Sol")
    harness.loadout(ship_id="1", ship_type="Python", ship_name="Trader")
    
    print("\nPicking up cargo at Sirius...")
    harness.jump("Sirius", jump_distance=8.6)
    harness.cargo(100)
    print(f"  Cargo: {harness.router.cargo} units")
    
    print("\nJumping to Procyon...")
    harness.jump("Procyon", jump_distance=11.4)
    print(f"  Cargo: {harness.router.cargo} units")
    
    print("\nDelivering cargo...")
    harness.cargo(75)
    print(f"  Cargo: {harness.router.cargo} units")


def example_route_planning():
    """Example 5: Route planning scenario."""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Route Planning Scenario with Real Loadout")
    print("=" * 60)
    
    harness = TestHarness()
    harness.register_journal_handler(journal_entry)
    
    print("\nSetting up for neutron route planning...")
    harness.startup("Colonia")
    
    # Get first available loadout for demonstration
    available = harness.get_available_loadouts()
    if available:
        ship = available[0]
        print(f"\nLoading {ship['ShipName']} ({ship['Ship']})...")
        harness.loadout(
            ship_id=str(ship['ShipID']),
            ship_type=ship['Ship'],
            ship_name=ship['ShipName']
        )
    else:
        print("\nLoading long-range explorer (generated)...")
        harness.loadout(
            ship_id="1",
            ship_type="Anaconda",
            ship_name="Neutron Dancer",
            use_real_loadout=False
        )
    
    if harness.router.ship:
        print(f"  Ship range: {harness.router.ship.range} ly")
        print(f"  Supercharge multiplier: {harness.router.ship.supercharge_mult}x")
    
    print("\nStarting neutron route from Colonia...")
    
    neutron_route = [
        ("HIP 1221", 32.0),
        ("HIP 2206", 31.5),
        ("HIP 4754", 32.1),
        ("HIP 5111", 30.8),
    ]
    
    for i, (system, distance) in enumerate(neutron_route, 1):
        print(f"\n  Jump {i}: {system} ({distance} ly)")
        harness.jump(system, jump_distance=distance)


def example_preset_scenarios():
    """Example 6: Using preset test scenarios."""
    print("\n" + "=" * 60)
    print("EXAMPLE 6: Preset Test Scenarios")
    print("=" * 60)
    
    scenarios = ['basic', 'ship_loaded', 'route_sequence']
    
    for scenario_name in scenarios:
        print(f"\nRunning '{scenario_name}' scenario...")
        harness = create_test_scenario(scenario_name)
        harness.register_journal_handler(journal_entry)
        
        state = harness.get_router_state()
        print(f"  System: {state['system']}")
        print(f"  Ship ID: {state['ship_id']}")
        print(f"  Cargo: {state['cargo']}")


def example_custom_testing():
    """Example 7: Custom test logic."""
    print("\n" + "=" * 60)
    print("EXAMPLE 7: Custom Testing")
    print("=" * 60)
    
    harness = TestHarness()
    harness.register_journal_handler(journal_entry)
    
    print("\nTesting emergency response scenario...")
    print("Ship gets damaged and needs to jump to nearest repair station")
    
    harness.startup("Sirius")
    harness.loadout(ship_id="1", ship_type="Anaconda", ship_name="Damaged Explorer")
    
    print("\n  Initial: At Sirius, hull at 50%")
    print("  Taking evasive jumps...")
    
    emergency_jumps = [
        ("Sol", 8.6),
        ("Altair", 11.2),
        ("Procyon", 11.4),
    ]
    
    for system, distance in emergency_jumps:
        print(f"  -> Emergency jump to {system}")
        harness.jump(system, jump_distance=distance)
    
    print(f"\n  Final system: {harness.router.system}")
    print("  Reached safe haven for repairs!")


def example_list_loadouts():
    """Example showing available real ship loadouts."""
    print("\n" + "=" * 60)
    print("EXAMPLE 0: Available Ship Loadouts from loadouts.json")
    print("=" * 60)
    
    available = TestHarness.get_available_loadouts()
    
    if available:
        print(f"\nFound {len(available)} ship loadouts:\n")
        for ship in available:
            print(f"  {ship['ShipName']:30} ({ship['Ship']:15})")
            print(f"    ID: {ship['ShipID']:3}  Mass: {ship['UnladenMass']:6.1f}t  Range: {ship['MaxJumpRange']:6.1f}ly")
    else:
        print("\nNo real ship loadouts found in loadouts.json")
        print("The harness will generate default ship modules for testing.")


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "Neutron Dancer Test Harness" + " " * 15 + "║")
    print("║" + " " * 20 + "Example Scenarios" + " " * 22 + "║")
    print("╚" + "=" * 58 + "╝")
    
    examples = [
        ("Available Loadouts", example_list_loadouts),
        ("Basic Usage", example_basic_usage),
        ("Jump Sequence", example_jump_sequence),
        ("Multiple Ships", example_multiple_ships),
        ("Cargo Management", example_cargo_management),
        ("Route Planning", example_route_planning),
        ("Preset Scenarios", example_preset_scenarios),
        ("Custom Testing", example_custom_testing),
    ]
    
    for i, (name, func) in enumerate(examples, 1):
        try:
            func()
        except Exception as e:
            print(f"\nError in {name}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    main()
