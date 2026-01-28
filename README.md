<img width="125" height="125" align="left" alt="neutrondancer_logo125" src="https://github.com/user-attachments/assets/53f26bf9-4db3-4199-a94e-4cebbe5ed081" />

# Navl's Neutron Dancer

![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python)
[![CodeQL](https://github.com/dwomble/EDMC-NeutronDancer/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/dwomble/EDMC-NeutronDancer/actions/workflows/github-code-scanning/codeql)
[![GitHub Latest Version](https://img.shields.io/github/v/release/dwomble/EDMC-NeutronDancer)](https://github.com/dwomble/EDMC-NeutronDancer/releases/latest)
[![Github All Releases](https://img.shields.io/github/downloads/dwomble/EDMC-NeutronDancer/total.svg)](https://github.com/dwomble/EDMC-NEutronDancer/releases/latest)

Neutron Dancer makes neutron jumping easier by plotting a route using [Spansh](https://www.spansh.co.uk/plotter) within [EDMC](https://github.com/EDCD/EDMarketConnector) and automatically copying the next waypoint on the route to your clipboard. It can work for almost any router by importing a CSV of the jumps.

The original goal of this fork was support for the new 6x overcharge of the Caspian and a cleaner UI. It has grown beyond that into a significant rewrite.

<img width="429" height="87" alt="Screenshot 2025-12-27 164511" src="https://github.com/user-attachments/assets/fafd8ae6-4fc1-49e2-9afd-707c7a394984" />

## Key Features

- Spansh **Galaxy Plotting** and **Neutron Plotting** directly from within EDMC
- CSV import supports almost any route file including Road to Riches, Expressway to Exomastery, Tourist planner, and Fleetcarrier plotter
- History tracking remembers your current waypoint as well as ships, loadouts, and destinations
- Route export makes it easy to save a route for later reuse
- Fleet carrier support includes jump cooldown tracking and notification

## Installation

- Open your EDMC plugins folder - in EDMC settings, select "Plugins" tab, click the "Open" button.
- Create a folder inside the plugins folder and call it whatever you want, **NeutronDancer** for instance
- Download the latest release [here](https://github.com/dwomble/EDMC-NeutronDancer/releases/latest) and unzip it.
- Open the folder you created and put all the files and folders you extracted inside
- Restart EDMC

## Usage

<img width="481" height="53" alt="neutron_dance" src="https://github.com/user-attachments/assets/32a2034a-06f6-4805-87c6-dab7fbddd57a" />

By default Neutron Dancer starts in a minimized mode in order to be as unobtrusive as possible when not in use. To plot a route click **do the neutron dance** to open the route plotting form.

Neutron dancer supports two route creation methods:
1. Direct plotting from Spansh Neutron Router or Spansh Galaxy Router
2. CSV import from Spansh Road to Riches, Expressway to Exomastery, Tourist planner, Fleetcarrier plotter, etc.

### Neutron Plotting

To use the Neutron Plotter, enter your source and destination systems, ship range, routing efficiency, and neutron jump multiplier. When you complete a route Neutron Dancer saves the source, destination, and ship details for easy entry. These are available from a right click menu to simplify entry.

<img width="384" height="163" alt="Screenshot 2025-12-27 164632" src="https://github.com/user-attachments/assets/fdc5f3f6-a904-476a-a6c6-1b7b8364ccd2" />

Next click **Calculate** to query Spansh and plot your route.

### Galaxy Plotting

This works the same as the Neutron Plotter but Neutron Dancer must have seen the ship you're going to use (you must have switched to it) in order to calculate the details required. The options available are also more complex and using the wrong values can lead to **getting stuck** so make sure you understand them before taking a route.

<img width="439" height="239" alt="Screenshot 2026-01-16 173246" src="https://github.com/user-attachments/assets/106097f3-c72f-4add-88c1-56d4e01a463f" />

**Note** In order to perform a galaxy plot the Neutron Dancer needs the full loadout of the ship you intend to use. This means you need to have switched to this ship for it to be able to plot it.


### CSV Import


Neutron Dancer is very flexible about CSV formats. It requires a column called "System Name" or "system" and will accept any other columns provided. If there are columns for remaining distance or number of jumps it will use those to calculate those values. If there is a column for refueling it will use that too.

To import a CSV click **Import** and select an appropriate file such as that exported by the various Spansh route plotters.


### Following the route

<img width="429" height="87" alt="Screenshot 2025-12-27 164511" src="https://github.com/user-attachments/assets/3e44b43e-919d-46f9-82ef-fdb0d1a0e19d" />

Once your route is plotted, and every time you reach a waypoint, the next one is automatically copied to your clipboard. In Elite Dangerous bring up the Galaxy Map, paste in the waypoint, and click **Plot route**.

If for some reason, your clipboard should be empty or contain other stuff that you copied yourself, click on the **System Name** button, and the waypoint will be copied again to your clipboard.

The progress bar has a Tooltip that provides the number of jumps remaining and distance remaining if those values are known.

The **Show route** button will bring up a window showing the details of the plotted route.

The **Export route** button will allow you to save the route as a CSV.

If you close EDMC, the plugin will save your progress. The next time you run EDMC, it will continue from where you left off.

## Credits

The biggest thank you must go to [CMDR Spansh](https://www.patreon.com/spansh) for the amazing [Spansh Route Planners](https://spansh.co.uk/plotter).

This code is based on the original [Spansh router](https://github.com/CMDR-Kiel42/EDMC_SpanshRouter) by CMDR Kiel42, [RadarCZ's](https://github.com/RadarCZ/EDMC_SpanshRouter), and [Norohind's](https://github.com/norohind/EDMC_SpanshRouter) forks.

## Suggestions

Please let me know if you have any suggestions or find any bugs by submitting an [issue](https://github.com/dwomble/EDMC-NeutronDancer/issues), and if you like Neutron Dancer please give it a star.

Fly dangerous! o7




