# Using Real Ship Loadouts in the Test Harness

The test harness now supports loading real ship loadouts from the `loadouts.json` file, giving you realistic module configurations and ship parameters for testing.

## Overview

Instead of generating default/mock modules, the harness can now:
- Load actual ship loadout data from `loadouts.json`
- Use real module configurations with engineering modifications
- Preserve accurate ship parameters (mass, fuel capacity, range, etc.)
- Fall back to generated modules if real data isn't available

## Quick Start

### Load a Real Ship by Name
```python
harness = TestHarness()
harness.register_journal_handler(journal_entry)

# Load the Mandalay from loadouts.json
harness.loadout(ship_name="Shipping Delay")

# Or by ship type
harness.loadout(ship_type="mandalay")
```

### Load a Real Ship by ID
```python
# Load the ship with ID 92
harness.loadout(ship_id="92")
```

### Fall Back to Generated Modules
```python
# Explicitly use generated modules instead of real loadout
harness.loadout(
    ship_id="1",
    ship_type="Anaconda",
    ship_name="Explorer",
    use_real_loadout=False
)
```

## Available Loadouts

Check what ships are available in your loadouts.json:

```python
# Get list of all available loadouts
available = TestHarness.get_available_loadouts()

for ship in available:
    print(f"{ship['ShipName']} ({ship['Ship']})")
    print(f"  ID: {ship['ShipID']}")
    print(f"  Unladen Mass: {ship['UnladenMass']}t")
    print(f"  Max Jump Range: {ship['MaxJumpRange']}ly")
```

## Examples

### Example 1: Use Your Actual Ships
```python
harness = TestHarness()
harness.register_journal_handler(journal_entry)

# Load all your real ships
available = harness.get_available_loadouts()
for ship in available:
    harness.loadout(
        ship_id=str(ship['ShipID']),
        ship_type=ship['Ship'],
        ship_name=ship['ShipName']
    )
    print(f"Loaded {ship['ShipName']} - Range: {harness.router.ship.range}ly")
```

### Example 2: Test with Specific Ship
```python
# Find and load a specific ship
available = TestHarness.get_available_loadouts()
cargo_ship = next((s for s in available if 'trader' in s['ShipName'].lower()), None)

if cargo_ship:
    harness.loadout(ship_name=cargo_ship['ShipName'])
```

### Example 3: Compare Ship Performance
```python
harness = TestHarness()
harness.register_journal_handler(journal_entry)

available = harness.get_available_loadouts()

print("Ship Comparison:")
for ship in available:
    harness.loadout(
        ship_id=str(ship['ShipID']),
        ship_type=ship['Ship'],
        ship_name=ship['ShipName']
    )
    if harness.router.ship:
        print(f"\n{ship['ShipName']}")
        print(f"  Mass: {ship['UnladenMass']}t")
        print(f"  Calculated Range: {harness.router.ship.range}ly")
        print(f"  Supercharge: {harness.router.ship.supercharge_mult}x")
```

## How It Works

### Loadout Lookup

When you call `harness.loadout()`, it:

1. **Loads loadouts.json** - If not already loaded, reads the file
2. **Searches by key** - Tries to find a match by:
   - Ship name (e.g., "Shipping Delay")
   - Ship type (e.g., "mandalay")
   - Ship ID (e.g., "92")
3. **Uses real data** - If found, uses the full loadout with all modules
4. **Falls back** - If not found, generates default modules
5. **Fires event** - Sends the loadout event to the plugin

### Ship Information Extracted

When a real loadout is used, the harness preserves:
- **ShipID** - Unique ship identifier
- **Ship** - Ship model/type
- **ShipName** - Ship nickname
- **Modules** - Complete module list with engineering modifications
- **FuelCapacity** - Main and reserve fuel tanks
- **UnladenMass** - Ship dry mass
- **MaxJumpRange** - Pre-calculated max jump range

## Advantages

✅ **Realistic Testing** - Test with your actual ships
✅ **Real Modules** - Complete module configs with engineering
✅ **Accurate Physics** - Uses actual ship stats for range calculations
✅ **Performance Data** - Compare how different ships perform on routes
✅ **No Setup** - Loadouts automatically loaded from file

## Caveats

⚠️ **One Entry Per Ship** - Only the last loadout for each ship is kept
⚠️ **Static Data** - Uses whatever was in loadouts.json when harness starts
⚠️ **Module Changes** - Won't reflect recent remodeling (needs fresh loadouts.json)

## Troubleshooting

### "No ships found in loadouts.json"
The loadouts.json file is empty or doesn't exist. Add ship loadouts to the file by:
1. Loading the plugin in EDMC
2. Loading ships in-game
3. Checking the loadouts.json file is populated

### Ship not found
Make sure you're using the correct:
- **Ship name** - Must match exactly (case-sensitive)
- **Ship type** - Use the internal name (e.g., "mandalay" not "Mandalay")
- **Ship ID** - Must be a string (e.g., "92" not 92)

### Use fallback modules
If the real loadout isn't being found, explicitly use generated modules:
```python
harness.loadout(
    ship_type="Anaconda",
    use_real_loadout=False
)
```

## API Reference

### TestHarness.loadout()

```python
def loadout(
    self,
    ship_id: str = "1",
    ship_type: str = "Anaconda",
    ship_name: str = "Test Ship",
    modules: Optional[list] = None,
    fuel_capacity: Optional[dict] = None,
    unladen_mass: float = 400.0,
    engineer_mods: Optional[dict] = None,
    use_real_loadout: bool = True  # NEW
) -> None
```

**Parameters:**
- `ship_id` - Ship ID (searches loadouts.json if use_real_loadout=True)
- `ship_type` - Ship type like "mandalay", "panthermkii" (searches loadouts.json)
- `ship_name` - Ship name like "My Explorer" (searches loadouts.json)
- `modules` - Explicit modules (overrides real data if provided)
- `fuel_capacity` - Explicit fuel capacity (overrides real data)
- `unladen_mass` - Explicit mass (overrides real data)
- `engineer_mods` - Engineering modifications (unused for real loadouts)
- `use_real_loadout` - Whether to search loadouts.json (default: True)

### TestHarness.get_available_loadouts()

```python
@staticmethod
def get_available_loadouts() -> List[dict]
```

Returns a list of available ship loadouts with this structure:

```python
[
    {
        'ShipName': 'Shipping Delay',
        'Ship': 'mandalay',
        'ShipID': 92,
        'UnladenMass': 296.8,
        'MaxJumpRange': 82.85
    },
    ...
]
```

## Examples in the Test Suite

See `examples.py` for working examples:

- **example_list_loadouts()** - Lists all available ships
- **example_multiple_ships()** - Loads multiple real ships
- **example_route_planning()** - Uses real ship for route testing

Run all examples:
```bash
python examples.py
```

## Tips

💡 **List ships first** - Use `get_available_loadouts()` to see what's available
💡 **Use exact names** - Ship names are case-sensitive
💡 **Check modules** - Inspect `harness.router.ship.loadout` to see loaded modules
💡 **Real > Generated** - Real loadouts are more realistic for testing

## See Also

- [TEST_HARNESS.md](TEST_HARNESS.md) - Full API documentation
- [README_TESTS.md](README_TESTS.md) - Test harness overview
- [QUICKSTART.md](QUICKSTART.md) - Quick reference
- `examples.py` - Working code examples
