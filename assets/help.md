## Neutron Plotter

This is the simple neutron route plotter. Enter your source and destination systems, ship range, routing efficiency, and neutron jump multiplier. A recently used list of ships and systems is available from a right click menu to simplify entry.

Next click **Calculate** to query Spansh and plot your route.

![Neutron Plotter](https://github.com/user-attachments/assets/fdc5f3f6-a904-476a-a6c6-1b7b8364ccd2)

- *Routing Efficiency* is the route directness. Increase this to reduce how far off the direct route the system will plot to get to a neutron star (An efficiency of 100 will not deviate from the direct route in order to plot from A to B and will most likely break down the journey into 20000 LY blocks).

- *Supercharge Multiplier* is the effect of Neutron boosting. For ships with the MkII FSD it is 6x for others 4x. This will also be pre-filled for your current ship.


## Galaxy Plotter

This works the same as the Neutron Plotter but Neutron Dancer must have seen the ship you're going to use (you must have switched to it) in order to calculate the details required. The options available are also more complex and using the wrong values can lead to **getting stuck** so make sure you understand them before taking a route. [*You have been warned*]{red}.

![Galaxy Plotter](https://github.com/user-attachments/assets/7eb44a7e-5233-41b8-ada5-3dd39f9fd35a)

- *Routing Algorithm* there are several algorithms available. Different algorithms may work faster, find better routes or in some cases be unable to find a route.
    1. *Fuel* Prioritises saving fuel, will not scoop fuel or supercharge. Will make the smallest jumps possible in order to preserve fuel as much as possible.
    1. *Fuel Jumps* Prioritises saving fuel, will not scoop fuel or supercharge. Will make the smallest jumps possible in order to preserve fuel as much as possible. Once it has generated a route it will then attempt to minimise the number of jumps to use the entire fuel tank. It will attempt to save only enough fuel to recharge the internal fuel tank once. If you have generated a particularly long route it is likely that you will need to recharge more than once and as such you will most likely run out of fuel.
    1. *Optimistic* Prioritises Neutron jumps. Penalises areas of the galaxy which have large gaps between neutron stars. Typically generates the fastest route with fewest total jumps.
    1. *Pessimistic* Prioritises calculation speed. Overestimates the average star distance to filter out routes. This means it calculates routes faster but the routes are typically less optimal.

**Notes**
1. In order to perform a galaxy plot the Neutron Dancer needs the full loadout of the ship you intend to use. This means you need to have switched to this ship for it to be able to plot it.

2. Due to the complexity of the galaxy plotter and the calculations involved a route plotted in the Neutron Dancer may vary *slightly* from one created through the web interface.


## Importing routes

Click **Import** and select a comma separated file such as that exported by the various Spansh route plotters.

Neutron Dancer is very flexible about CSV formats. It requires a column called "System Name" or "system" and will accept any other columns provided. If there are columns for remaining distance or number of jumps it will use those to calculate those values.


## Following routes

Once a route is plotted, and every time you reach a waypoint, the next one is automatically copied to your clipboard. In Elite Dangerous bring up the Galaxy Map, paste in the waypoint. If you're using the Neutron Plotter click **Plot route**. If using the Galaxy Plotter click **Target System**. If it's too far then use **Plot route**

If for some reason, your clipboard should be empty or contain other stuff that you copied yourself, click on the **System Name** button, and the waypoint will be copied again to your clipboard.

The progress bar has a Tooltip that provides the number of jumps remaining and distance remaining if those values are known.

The **Show** button will bring up a window showing the details of the plotted route along with stats on progress and speed.

The **Export** button will allow you to save the route as a CSV.

If you close EDMC, the plugin will save your progress. The next time you run EDMC, it will continue from where you left off.

### Fleet carrier routes

The Neutron Dancer doesn't (yet) directly plot fleet carrier routes but it can import and monitor them. When it does it functions just like for a Neutron route. It will also notify you when the jump cooldown is finished.


## Tips

* Almost every component has a tooltip to provide further information or hints on use.
* Many components have a right-click context menu with shortcuts.


## Credits

The biggest thank you must go to [CMDR Spansh](https://www.patreon.com/spansh) for the amazing [Spansh Route Planners](https://spansh.co.uk/plotter).

This code is based on the original [Spansh router](https://github.com/CMDR-Kiel42/EDMC_SpanshRouter) by CMDR Kiel42 and [Norohind's fork](https://github.com/norohind/EDMC_SpanshRouter).


## Suggestions

Let me know if you have any suggestions.

Fly dangerous! o7


