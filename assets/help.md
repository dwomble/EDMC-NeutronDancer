# Guide to Navl's Neutron Dancer [v{version}](https://github.com/dwomble/EDMC-NeutronDancer/)

There are several route plotting options.

1. Galaxy Plotter
1. Neutron Plotter
1. Road to Riches
1. Expressway to Exomastery (Exobiology)
1. Trade Planner
1. Tourist Route
1. Fleet Carrier Route

You can switch between them with the **Route** dropdown at the top of the plotter frame.

## Galaxy Plotter

This works the same as the Neutron Plotter but Neutron Dancer must have seen the ship you're going to use (you must have switched to it) in order to calculate the details required. The options available are also more complex and using the wrong values can lead to **getting stuck** so make sure you understand them before taking a route.

![Galaxy Plotter](https://github.com/user-attachments/assets/7eb44a7e-5233-41b8-ada5-3dd39f9fd35a)

### Routing Algorithm

There are several algorithms available. Different algorithms may work faster, find better routes, or in some cases be unable to find a route.

1. *Fuel* Prioritises saving fuel, will not scoop fuel or supercharge. Will make the smallest jumps possible in order to preserve fuel as much as possible.

1. *Fuel Jumps* Like *Fuel* but once it has generated a route it will then attempt to minimise the number of jumps to use the entire fuel tank. It will attempt to save only enough fuel to recharge the internal fuel tank once. If you have generated a particularly long route it is likely that you will need to recharge more than once and as such you will most likely run out of fuel.

1. *Optimistic* Prioritises Neutron jumps. Penalises areas of the galaxy which have large gaps between neutron stars. **Typically generates the fastest route with fewest total jumps.**

1. *Pessimistic* Prioritises calculation speed. Overestimates the average star distance to filter out routes. This means it calculates routes faster but the routes are typically less optimal.

### Routing Options

- *Already supercharged* Is your ship already supercharged?

- *Use Supercharge* Use Neutron stars to supercharge your FSD

- *Use FSD Injections* Use FSD synthesis to boost when a Neutron star is not available

- *Exclude Secondary Stars* Prevent the system using secondary Neutron stars and scoopable stars to help with the route

- *Refuel Every Scoopable* Refuel every time you encounter a scoopable star. If this is not selected you must only refuel where the route indicates or you will go over the expected weight and be unable to make subsequent jumps.
If you don't select *exclude secondary stars* it's presumed you'll select this or you may accidentally refuel while Supercharging and go over the expected weight.

### Galaxy Route Tips

1. A fairly safe configuration is **Optimistic** algorithm, **Use Supercharge**, **Exclude Secondary Stars** options, and a few tonnes of **Fuel Reserve**.

1. In order to perform a galaxy plot Neutron Dancer needs the full loadout of the ship you intend to use. This means you need to have switched to this ship for it to be able to plot it.

1. Galaxy routes are ship and loadout specific. If you switch ship or change modules the rouote likely will not work without replotting.

1. When selecting the next system in the galaxy map you should target the system rather than plotting to it. This is because the game sometimes incorrectly calculates how far you can jump and will not allow you to plot within the galaxy map when you are jumping to your maximum range with missing fuel.

1. Jump range is very weight dependent. Only refuel where it says to do so or you may get a `Jump exceeds maximum fuel` error. If this happens you can use FSD Supercharge Overdrive to burn off the excess or follow the instructions below.

1. If you find yourself out of sync with a generated route then you should find the next refuelling stop in the route and plot to it within the galaxy map. Once you have refuelled at that refuelling stop then you can continue along the route as normal.

1. Due to the complexity of the galaxy plotter and the calculations involved a route plotted in Neutron Dancer may vary *slightly* from one created through the web interface.

## Neutron Plotter

This is the simple Spansh neutron route plotter. Enter your source and destination systems, ship range, routing efficiency, and neutron jump multiplier. A recently used list of ships and systems is available from a right click menu to simplify entry.

Next click **Calculate** to query Spansh and plot your route.

![Neutron Plotter](https://github.com/user-attachments/assets/fdc5f3f6-a904-476a-a6c6-1b7b8364ccd2)

- *Routing Efficiency* is the route directness. Increase this to reduce how far off the direct route the system will plot to get to a neutron star (An efficiency of 100 will not deviate from the direct route in order to plot from A to B and will most likely break down the journey into 20000 LY blocks).

- *Supercharge Multiplier* is the effect of Neutron boosting. For ships with the MkII FSD it is 6x for others 4x. This will also be pre-filled for your current ship.

- Click the **+** beside the source system to force the route through specific systems along the way. Each added system gets its own **-** (remove) and **+** (add another below).

## Road to Riches and Expressway to Exomastery

**Road to Riches** and **Expressway to Exomastery** (Exobiology) work the same way. Enter your source system, and optionally a destination — leave the destination blank to plot a circular tour that returns to your source. Set your ship's jump range, a search radius (how far off the direct line to look), and the maximum number of systems to include, then click **Calculate**.

![Expressway to Exomastery](https://github.com/user-attachments/assets/a577dce7-f8dd-4557-b479-ed68c02ccf00)

Common options:

- *Avoid Thargoids* Route around systems affected by a Thargoid war
- *Loop* Prefer routes that loop back on themselves rather than a straight line

They differ only in what they're actually looking for:

- **Road to Riches** looks for any valuable body along the way. *Use Mapping Value* ranks bodies by their DSS (Detailed Surface Scanner) mapping value rather than their FSS (Full Spectrum Scanner) scan value — select this if you intend to map every body rather than just scan it.

- **Expressway to Exomastery** looks for systems with valuable biological (exobiology) signals instead of body scan value. The *Minimum Landmark (Species) Value* slider filters out finds below that threshold, in millions of credits — raise it to skip low-value species and focus only on the most lucrative signals.

Both avoid populated systems, so they don't work well close to the bubble — increase your search radius if a route can't be found.

### Tips

- Road To Riches — You should decide if you want to DSS (Detailed Surface Scanner which requires you to travel to the body in system and surface map) or simply FSS (Full Spectrum Scanner from the system jump in point). FSS is faster for each system but will pay substantially less credits.

## Trade Planner

Plans a closed loop of trade hops starting and ending at a single **Source Station** (start typing to search — this is the one route type that starts from a station rather than just a system). Set your **Start Capital** and **Max Cargo** capacity, then cap the search with **Max Hops** (trade legs in the loop), **Max Dist** (jump distance per hop), **Max Arrival** (how far a station can be from its system's arrival point), and **Max Age** (ignore market prices older than this many days — leave blank for no limit).

![Trade Planner](https://github.com/user-attachments/assets/d99e0ae4-bbc9-444b-859a-6997fdf8a604)

Options:

- *Requires Large Pad* / *Allow Planetary* / *Allow Restricted Access* filter stations by landing pad size, planetary surface, and restricted (e.g. engineer base) access
- *Allow Prohibited* Allow commodities prohibited by the destination's superpower
- *Allow Player Owned* Allow player-owned fleet carriers as stops
- *Unique* Only visit each station once
- *Permit* Allow systems that require a permit

## Tourist Route

Enter a source system and add stops with the **+** beside it — each stop gets its own **-** (remove) and **+** (insert another below), just like the Neutron Plotter's via-points. Optionally set a **Final Destination** to end the tour somewhere other than back at the source. Set your ship's jump range and click **Calculate**.

![Tourist Route](https://github.com/user-attachments/assets/1d1953fa-2030-4dad-8439-8c752f1979c3)

## Fleet Carrier Router

The **Fleet Carrier Route** plotter plans a stop-by-stop journey for your carrier. Enter a source system, add stops with the **+** beside it (each stop gets its own **-**/**+**), pick your carrier type, and enter how much cargo/module space is already in use. Starting fuel is calculated automatically.

Once plotted, Neutron Dancer follows a carrier route just like a Neutron route, and will notify you when the jump cooldown is finished.

![Fleet Carrier Router](https://github.com/user-attachments/assets/9f9c507b-9ec3-42f0-8674-76030343220a)

## Importing Routes

Click **Import** and select a comma separated file such as that exported by the various Spansh route plotters. By default Neutron Dancer looks in its `routes` folder. This can be changed in the preferences.

Neutron Dancer is very flexible about CSV formats. It requires a column called "System Name" or "system" and will accept any other columns provided. If there are columns for remaining distance or number of jumps it will use those to calculate those values.

## Exporting Routes

Click **Export** and choose or enter a file to save the route in. Including the source, destination and ship name in the filename will help when later importing a route.

## Following Routes

Once a route is plotted, the next waypoint is shown on the button between the **◄**/**►** navigation buttons — click it to copy that waypoint to your clipboard. In Elite Dangerous bring up the Galaxy Map and paste in the waypoint. If you're using the Neutron Plotter click **Plot route**. If using the Galaxy Plotter click **Target System**. If it's too far then use **Plot route**.

If for some reason your clipboard is empty or contains other stuff that you copied yourself, click the waypoint button again. If it doesn't help you may be running Linux and should follow the [Linux Clipboard](https://github.com/dwomble/EDMC-NeutronDancer/tree/develop#linux-clipboard) instructions.

Hover over the waypoint button for a tooltip with further detail on the next stop (station/commodity/profit for trades, body/scan value for exploration, and so on) that doesn't fit on the button itself.

The progress bar has a tooltip that shows the number of jumps remaining and distance remaining if those values are known.

The **Show** button will bring up a window showing the details of the plotted route along with stats on progress and speed.

The **Export** button will allow you to save the route as a CSV.

If you close EDMC, the plugin will save your progress. The next time you run EDMC, it will continue from where you left off.

## Overlays

To enable overlays the [EDMC Modern Overlay](https://github.com/SweetJonnySauce/EDMCModernOverlay) which must be installed and activated. Neutron Dancer provides three frames that can be individually enabled, positioned, and configured.

1. **Default** displays the next jump in the current route and other details in the ship main window
1. **Galaxy Map** replaces the default frame when in the Galaxy Map and displays just the jump destination
1. **Carrier** displays carrier destination and jump and cooldown timers

### Overlay Frame Management

Each frame may be enabled and disabled from Neutron Dancer preferences. The text colour may also be configured here. Position, background, and border can be configured using Modern Overlay's [controller](https://github.com/SweetJonnySauce/EDMCModernOverlay/wiki/Overlay-Controller).

The *Default* frame can optionally display a progress bar and a customizable format string that accepts the following fields

- `{jc}` Jumps completed
- `{jr}` Jumps remaining
- `{jt}` Jumps total
- `{dc}` Distance to next checkpoint
- `{dr}` Distance remaining
- `{dt}` Distance total
- `{dh}` Distance traveled per hour
- `{jh}` Jumps performed per hour
- `{rj}` Jumps to next refuel star
- `{rd}` Distance to next refuel
- `{rs}` A ready-made "Refuel in N jumps" message (blank if no refuel stop is coming up)
- `{st}` Star type indicating if the next star is a refuel location or a neutron star

This customizable format only applies to Neutron/Galaxy-type routes (and refuel-aware CSV imports). For Trade, Road to Riches/Exobiology, Tourist, and Fleet Carrier routes — which have no refuel/neutron concept — the *Default* frame instead shows the same per-route detail as the waypoint tooltip (station/commodity/profit, body/scan value, and so on).

## Chat Commands

This enables management of Neutron Dancer without tabbing out of the game. Bring up a game chat window and type in `!nd` and a command. Supported commands are:

- `next` – move to the next waypoint
- `previous` (or just `prev`) – move to the previous waypoint
- `copy` – re-insert the next waypoint into the past buffer

## Hotkeys

If you install the [EDMC Hotkeys](https://github.com/SweetJonnySauce/EDMCHotkeys) plugin you can define hotkeys for the `next`, `previous`, and `copy` commands.

## Interface Tips

- Almost every component has a tooltip to provide further information or hints on use.
- Many components have a right-click context menu with shortcuts.

## Credits

The biggest thank you must go to [CMDR Spansh](https://www.patreon.com/spansh) for the amazing [Spansh Route Planners](https://spansh.co.uk/plotter).

This code is based on the original [Spansh router](https://github.com/CMDR-Kiel42/EDMC_SpanshRouter) by CMDR Kiel42 and [Norohind's fork](https://github.com/norohind/EDMC_SpanshRouter).

## Suggestions

Let me know if you have any [suggestions](https://github.com/dwomble/EDMC-NeutronDancer/issues).

Fly dangerous! o7
