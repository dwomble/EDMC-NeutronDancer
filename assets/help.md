# Guide to Navl's Neutron Dancer [v{version}](https://github.com/dwomble/EDMC-NeutronDancer/)

There are two Neutron route plotting options.

1. Neutron Plotter
1. Galaxy Plotter

You can switch between them with the radio buttons.

## Neutron Plotter

This is the simple Spansh neutron route plotter. Enter your source and destination systems, ship range, routing efficiency, and neutron jump multiplier. A recently used list of ships and systems is available from a right click menu to simplify entry.

Next click **Calculate** to query Spansh and plot your route.

![Neutron Plotter](https://github.com/user-attachments/assets/fdc5f3f6-a904-476a-a6c6-1b7b8364ccd2)

- *Routing Efficiency* is the route directness. Increase this to reduce how far off the direct route the system will plot to get to a neutron star (An efficiency of 100 will not deviate from the direct route in order to plot from A to B and will most likely break down the journey into 20000 LY blocks).

- *Supercharge Multiplier* is the effect of Neutron boosting. For ships with the MkII FSD it is 6x for others 4x. This will also be pre-filled for your current ship.


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

## Importing Routes

Click **Import** and select a comma separated file such as that exported by the various Spansh route plotters.

Neutron Dancer is very flexible about CSV formats. It requires a column called "System Name" or "system" and will accept any other columns provided. If there are columns for remaining distance or number of jumps it will use those to calculate those values.

## Exporting Routes

Click **Export** and choose or enter a file to save the route in. Including the source, destination and ship name in the filename will help when later importing a route.

## Following Routes

Once a route is plotted, and every time you reach a waypoint, the next one is automatically copied to your clipboard. In Elite Dangerous bring up the Galaxy Map and paste in the waypoint. If you're using the Neutron Plotter click **Plot route**. If using the Galaxy Plotter click **Target System**. If it's too far then use **Plot route**.

If for some reason your clipboard is empty or contains other stuff that you copied yourself exiting and returning to the Galaxy Map should correct it. If it doesn't you may be running Linux and should follow the [Linux Clipboard](https://github.com/dwomble/EDMC-NeutronDancer/tree/develop#linux-clipboard) instructions.

The progress bar has a tooltip that shows the number of jumps remaining and distance remaining if those values are known.

The **Show** button will bring up a window showing the details of the plotted route along with stats on progress and speed.

The **Export** button will allow you to save the route as a CSV.

If you close EDMC, the plugin will save your progress. The next time you run EDMC, it will continue from where you left off.

## Fleet Carrier Routes

Neutron Dancer doesn't (yet) directly plot fleet carrier routes but it can import and monitor them. When it does it functions just like for a Neutron route. It will also notify you when the jump cooldown is finished.

## Overlays

To enable overlays the [EDMC Modern Overlay](https://github.com/SweetJonnySauce/EDMCModernOverlay) which must be installed and activated. Neutron Dancer provides three frames that can be individually enabled, positioned, and configured.

1. **Default** displays the next jump in the current route and other details in the ship main window
1. **Galaxy Map** replaces the default frame when in the Galaxy Map and displays just the jump destination
1. **Carrier** displays carrier detination and jump and cooldown timers

### Overlay Frame Management

Each frame may be enabled and disabled from Neutron Dancer preferences. The text colour may also be configured here. Position, background, and border can be configured using Modern Overlay's [controller](https://github.com/SweetJonnySauce/EDMCModernOverlay/wiki/Overlay-Controller).

The *Default* frame can optionally display a progress bar and a customizable format string that accepts the following fields

- `{jc}` Jumps completed
- `{jr}` Jumps remaining
- `{jt}` Jumps total
- `{dc}` Distance to next checkpoint
- `{dr}` Distance remaining
- `{dt}` Distance total
- `{dh}` Distance travelled per hour
- `{jh}` Jumps performed per hour
- `{rj}` Jumps to next refuel star
- `{rd}` Distance to next refuel
- `{st}` Star type indicating if the next star is a refuel location or a neutron star

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
