<!--img width="125" height="125" align="left" alt="neutrondancer_logo125" src="https://github.com/user-attachments/assets/53f26bf9-4db3-4199-a94e-4cebbe5ed081" -->
<img width="125" height="125" alt="neutrondancer_logo125_white" src="https://github.com/user-attachments/assets/8d76f1ae-f59d-4063-8312-61eae76c1597" />

# Navl's Neutron Dancer

![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python)
[![CodeQL](https://github.com/dwomble/EDMC-NeutronDancer/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/dwomble/EDMC-NeutronDancer/actions/workflows/github-code-scanning/codeql)
[![GitHub Latest Version](https://img.shields.io/github/v/release/dwomble/EDMC-NeutronDancer)](https://github.com/dwomble/EDMC-NeutronDancer/releases/latest)
[![Github All Releases](https://img.shields.io/github/downloads/dwomble/EDMC-NeutronDancer/total.svg)](https://github.com/dwomble/EDMC-NEutronDancer/releases/latest)

Neutron Dancer makes neutron jumping easier by letting you plot a [Spansh](https://www.spansh.co.uk/plotter) Neutron or Galacy route directly within [EDMC](https://github.com/EDCD/EDMarketConnector); tracking progress along the route; and automatically copying the next waypoint into your clipboard. It can work for almost any router by importing a CSV of the jumps.

The original goal of this fork was support for the new 6x overcharge of the Caspian Explorer and a cleaner UI. It has grown beyond that into a significant rewrite.

<img width="429" height="87" alt="Screenshot 2025-12-27 164511" src="https://github.com/user-attachments/assets/fafd8ae6-4fc1-49e2-9afd-707c7a394984" />

## Key Features

- Use Spansh's sophisticated **Galaxy Plotter** directly from EDMC *without having to manually export, copy and paste ship builds*.
- Use Spansh's **Neutron Plotter** directly from EDMC.
- Next destination is automatically put into the paste buffer.
- Remembers your route, progress, ships, loadouts, and destinations across sessions.
- Refuel locations and Neutron stars are highlighted.
- Star name autocompletion
- CSV import supports almost any route file including Road to Riches, Expressway to Exomastery, Tourist planner, and Fleetcarrier plotter.
- Route export makes it easy to save a route for later reuse.
- Fleet carrier support includes jump countdown and cooldown tracking and cooldown notifications.
- Tracks and reports statistics including jumps and distance per hour.
- Single screen and VR support via
  - [Modern Overlay](https://github.com/SweetJonnySauce/EDMCModernOverlay) for in game display of routes and countdown timers.
  - Chat commands (`!nd next`, `!nd previous`, `!nd copy`)
  - [Hotkeys](https://github.com/SweetJonnySauce/EDMCHotkeys) for next waypoint, previous waypoint, and copy to clipboard operations.
- Full EDMC theme support

## Installation

- Download and unzip the latest `EDMC-NeutronDancer.zip` from [here](https://github.com/dwomble/EDMC-NeutronDancer/releases/latest).
- Open your EDMC plugins folder (in EDMC settings, select "Plugins" tab, click the "Open" button).
- Create a folder inside the plugins folder and call it whatever you want, **EDMC-NeutronDancer** for instance.
- Copy the unzipped files into this folder.
- Restart EDMC.

## Route Plotting

<img width="481" height="53" alt="neutron_dance" src="https://github.com/user-attachments/assets/32a2034a-06f6-4805-87c6-dab7fbddd57a" />

By default Neutron Dancer starts in a minimized mode in order to be as unobtrusive as possible when not in use. To plot a route click **do the neutron dance** to open the route plotting form.

Neutron dancer supports two direct route creation methods:

1. The sophisticated Spansh Galaxy Plotter
1. The simpler Spansh Neutron Plotter

It also supports CSV file import in a wide variety of formats

1. Road to Riches
1. Expressway to Exomastery
1. Tourist planner
1. Fleetcarrier plotter, etc.

### Galaxy Plotting

To use the Galaxy Plotter, also known as the *exact plotter*, enter your source and destination systems, select the ship and set any other options and choose `Calculate`. The Galaxy Plotter options are explained in the help window as well as at [Spansh](https://spansh.co.uk/exact-plotter).

<img width="439" height="239" alt="Screenshot 2026-01-16 173246" src="https://github.com/user-attachments/assets/106097f3-c72f-4add-88c1-56d4e01a463f" />

When you complete a route Neutron Dancer saves the source, destination, and ship details for easy entry. These are available from a right click menu to simplify entry.

**Note:** In order to perform a galaxy plot the Neutron Dancer needs the full loadout of the ship you intend to use. For Neutron Dancer to know this information you must have switched to this ship to plot a route for it.

### Neutron Plotting

This works like the Galaxy plotter but is simpler and produces less efficient routes.

<img width="384" height="163" alt="Screenshot 2025-12-27 164632" src="https://github.com/user-attachments/assets/fdc5f3f6-a904-476a-a6c6-1b7b8364ccd2" />

### Following the Route

<img width="429" height="87" alt="Screenshot 2025-12-27 164511" src="https://github.com/user-attachments/assets/3e44b43e-919d-46f9-82ef-fdb0d1a0e19d" />

Once your route is plotted, and every time you reach a waypoint, the next one is automatically copied to your clipboard when you enter the Galaxy Map. In Elite Dangerous bring up the Galaxy Map, paste in the waypoint, and click **Plot route**.

If for some reason, your clipboard should be empty or contain other stuff that you copied yourself, click on the **System Name** button, and the waypoint will be copied again to your clipboard.

The progress bar has a Tooltip that provides the number of jumps remaining and distance remaining if those values are known.

### Viewing the Route

<img width="1164" height="361" alt="route_window" src="https://github.com/user-attachments/assets/37d0080d-30bc-41f1-a992-701474b605ef" />

The **Show route** button will open a window showing progress and the details of the plotted route. The current waypoint is hightlighted and progress includes waypoints completed and remaining, distance completed and remaining, jumps and lightyears per hour. For each jump the details include waypoints, distance traveled and remaining, fuel used and remaining, tritium used and remaining, whether to refueld and whether a star is a neutron star or scoopable depending on the type of route being followed.

### CSV Import

Neutron Dancer is very flexible about CSV formats. It requires a column called "System Name" or "system" and will accept any other columns provided. If there are columns for remaining distance or number of jumps it will use those to calculate those values. If there is a column for refueling it will use that too.

### Route Export

The **Export route** button will open a file dialog allowing you to save the current route as a CSV.

### Overlays

This requires the [EDMC Modern Overlay](https://github.com/SweetJonnySauce/EDMCModernOverlay) to be installed, older overlays aren't supported.

Three overlays are available.

1. *Default* displays the next jump in the current route and other details in the ship main window
1. *Galaxy Map* replaces the default frame when in the Galaxy Map and displays just the jump destination
1. *Carrier* displays carrier jump and cooldown timers

Each can be individually enabled and frame size, color, position, background, text alignment etc. are all configurable.

<img width="410" height="122" alt="overlay" src="https://github.com/user-attachments/assets/bd492595-1cfa-4ac1-aaac-810a42e0cd4a" />

The `Default` frame can be further customized with:

- A progress bar showing route progress
- A customizable route details string that can display a wide variety of route information

<img width="777" height="56" alt="overlay_customization" src="https://github.com/user-attachments/assets/b86abb00-aba7-44e3-8006-ef32066c53de" />

### Chat Commands

This enables management of Neutron Dancer without tabbing out of the game. Simply bring up a chat window and type in `!nd` and a command. Supported commands are:

- `next` – move to the next waypoint
- `previous` (or just `prev`) – move to the previous waypoint
- `copy` – re-copy the next waypoint into the past buffer

### Hotkeys

If you install the [EDMC Hotkeys](https://github.com/SweetJonnySauce/EDMCHotkeys) plugin you can define hotkeys for the `next`, `previous` and `copy` commands.

### Saving State

If you close EDMC, the plugin will save your progress. The next time you run EDMC, it will continue from where you left off and even catch up any progress made while EDMC was inactive.

It also saves ship details and source and destination systems for easy entry.

### Linux Clipboard

This is notoriously variable and problematic. Neutron Dancer tries to find `wl-copy`, `xsel` and `xclip` based on the current session. If it doesn't find anything appropriate it runs _all_ of them that exist. If it can't find any of them it falls back to using the Tk native method.

If you have problems with waypoints not being put into the clipboard you can override all of this by setting an environment variable `EDMC_CLIPBOARD_CLI` to the command you wish to use before running EDMC. e.g.

```shell
export EDMC_CLIPBOARD_CLI="/usr/local/random/xsel --clipboard --input"
/usr/bin/python EDMarketConnector.py
```

Note, if you're running Flatpak and still having problems even with the environment variable set, check that EDMC is allowed to run the command you're referencing and allowed to follow any symlinks.

## Credits

The biggest thank you must go to [CMDR Spansh](https://www.patreon.com/spansh) for the amazing [Spansh Route Planners](https://spansh.co.uk/plotter).

This code is based on the original [Spansh router](https://github.com/CMDR-Kiel42/EDMC_SpanshRouter) by CMDR Kiel42, [RadarCZ's](https://github.com/RadarCZ/EDMC_SpanshRouter), and [Norohind's](https://github.com/norohind/EDMC_SpanshRouter) forks.

## Suggestions

Please let me know if you have any suggestions or find any bugs by submitting an [issue](https://github.com/dwomble/EDMC-NeutronDancer/issues), and if you like Neutron Dancer I don't need a coffee, I live in Seattle so I'm plenty caffeinated already, but please give it a star.

Fly dangerous! o7
