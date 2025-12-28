# Navl's Neutron Dancer


![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python)
[![CodeQL](https://github.com/dwomble/EDMC-NeutronDancer/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/dwomble/EDMC-NeutronDancer/actions/workflows/github-code-scanning/codeql)
[![GitHub Latest Version](https://img.shields.io/github/v/release/dwomble/EDMC-NeutronDancer)](https://github.com/dwomble/EDMC-NeutronDancer/releases/latest)
[![Github All Releases](https://img.shields.io/github/downloads/dwomble/EDMC-NeutronDancer/total.svg)](https://github.com/dwomble/EDMC-NEutronDancer/releases/latest)

This plugin makes neutron jumping easier by plotting a route using [Spansh](https://www.spansh.co.uk/plotter) within [EDMC]() and automatically copying the next waypoint on the route to your clipboard. It can work for almost any router by importing a CSV of the jumps.

The goal of this fork is support for the new 6x overcharge of the Caspian and a cleaner UI.

<img width="429" height="87" alt="Screenshot 2025-12-27 164511" src="https://github.com/user-attachments/assets/fafd8ae6-4fc1-49e2-9afd-707c7a394984" />

## Installation

- Open your EDMC plugins folder - in EDMC settings, select "Plugins" tab, click the "Open" button.
- Create a folder inside the plugins folder and call it whatever you want, **NeutronDancer** for instance
- Download the latest release [here](https://github.com/dwomble/EDMC-NeutronDancer/releases/latest) and unzip it.
- Open the folder you created and put all the files and folders you extracted inside
- Restart EDMC

## Usage

By default Neutron Dancer starts in a minimized mode to be unobtrusive when not in use. To plot a route click **do the neutron dance** to open the route plotting form.

Neutron dancer supports two route creation methods:
1. Direct plotting from Spansh Neutron Router or Spansh Galaxy Router
2. CSV import from Spansh Galaxy Plotter, Fleetcarrier plotter, and similar formats

### Neutron Plotting

To use the Neutron Plotter, enter your source and destination systems, ship range, routing efficiency, and neutron jump multiplier. When you complete a route Neutron Dancer saves the source, destination, and ship details for easy entry. These are available from a right click menu to simplify entry.

<img width="384" height="163" alt="Screenshot 2025-12-27 164632" src="https://github.com/user-attachments/assets/fdc5f3f6-a904-476a-a6c6-1b7b8364ccd2" />

Next click **Calculate** to query Spansh and plot your route.

### Galaxy Plotting

This works the same as the Neutron Plotter but Neutron Dancer must have seen the ship you're going to use (you must have switched to it) in order to calculate the details required. The options available are also more complex and using the wrong values can lead to **getting stuck** so make sure you understand them before taking a route.

<img width="437" height="232" alt="Screenshot 2025-12-27 165549" src="https://github.com/user-attachments/assets/7eb44a7e-5233-41b8-ada5-3dd39f9fd35a" />


### CSV Import

Click **Import** and select a comma separated file such as that exported by the various Spansh route plotters. Neutron Dancer is very flexible about CSV formats. It requires a column called "System Name" or "system" and will accept any other columns provided. If there are columns for remaining distance or number of jumps it will use those to calculate those values.

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

This code is based on the original [Spansh router](https://github.com/CMDR-Kiel42/EDMC_SpanshRouter) by CMDR Kiel42 and [Norohind's fork](https://github.com/norohind/EDMC_SpanshRouter).

## Suggestions

Let me know if you have any suggestions.

Fly dangerous! o7






