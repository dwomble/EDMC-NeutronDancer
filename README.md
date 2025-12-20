# Navl's Neutron Dancer

This plugin's purpose is to make neutron jumping easier by plotting a route using [Spansh](https://www.spansh.co.uk/plotter) within EDMC and automatically copying the next waypoint in that route to your clipboard.

The goal of this fork is support for the new 6x overcharge of the Caspian and a cleaner UI.

## Installation

- Open your EDMC plugins folder - in EDMC settings, select "Plugins" tab, click the "Open" button.
- Create a folder inside the plugins folder and call it whatever you want, **NeutronDancer** for instance
- Download the latest release [here](https://github.com/dwomble/EDMC-NeutronDancer/releases/latest) and unzip it.
- Open the folder you created and put all the files and folders you extracted inside
- Restart EDMC

## Usage

By default Neutron Dancer starts in a minimized mode to be unobtrusive when not in use. To plot a route click **do the neutron dance** to open the route plotting form.

Neutron dancer supports two route creation methods:
1. Direct plotting from Spansh Neutron Router
2. CSV import from Spansh Galaxy Plotter, Fleetcarrier plotter, and similar formats

### Direct Plotting

Enter your source and destination systems, ship range, routing efficiency, and neutron jump multiplier. When you complete a route Neutron Dancer saves the source, destination, and ship details for easy entry. These are available from a right click menu to simplify entry.

Next click **Calculate** to query Spansh and plot your route.

### CSV Import

Click **Import** and select a comma separated file such as that exported by the various Spansh route plotters. Neutron Dancer is very flexible about CSV formats. It requires a column called "System Name" or "system" and will accept any other columns provided. If there are columns for remaining distance or number of jumps it will use those to calculate those values.

### Following the route

Once your route is plotted, and every time you reach a waypoint, the next one is automatically copied to your clipboard. In Elite Dangerous bring up the Galaxy Map, paste in the waypoint, and click **Plot route**.

If for some reason, your clipboard should be empty or contain other stuff that you copied yourself, click on the **System Name** button, and the waypoint will be copied again to your clipboard.

The **System Name** button also has a Tooltip that provides the number of jumps remaining and distance remaining if those values are known.

The **Show route** button will bring up a window showing the details of the plotted route.

If you close EDMC, the plugin will save your progress. The next time you run EDMC, it will start back where you stopped.

## Suggestions

Let me know if you have any suggestions.

Fly dangerous! o7
