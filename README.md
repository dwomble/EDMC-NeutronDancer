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

Currently the "do the neutron dance" button supports route creation by
1. Direct plotting from Spansh Neutron Router
2. CSV import from Spansh Galaxy Plotter, Fleetcarrier plotter, and similar formats

Once your route is plotted, and every time you reach a waypoint, the next one is automatically copied to your clipboard.

You just need to go to your Galaxy Map and paste it and click plot route.

If for some reason, your clipboard should be empty or containing other stuff that you copied yourself, just click on the **System Name** button, and the waypoint will be copied again to your clipboard.

If you close EDMC, the plugin will save your progress. The next time you run EDMC, it will start back where you stopped.

### Wayland Support

If you're using a Wayland desktop environment you can't use `xclip` so it will try to use `wl-copy`. If it can't find `wl-copy` or doesn't have permissions to use it you'll have to configure the plugin using the `EDMC_NEUTRON_DANCER_XCLIP` environment variable to use Wayland specific `wl-copy` tool before launching EDMC. For example:

```bash
export EDMC_SPANSH_ROUTER_XCLIP="/usr/bin/wl-copy"
python EDMarketConnector.py
```

For Flatpak users, you may need to:
1. Add permissions when launching EDMC: `--socket=wayland --filesystem=host-os`
2. Use another path for wl-copy: `export EDMC_NEUTRON_DANCER_XCLIP="/run/host/usr/bin/wl-copy"`


## Tips and Tricks

* The system records the source, destination, and ship field data when you complete a route.
* The source and destination fields have a right-click context menu that includes your current location and the last ten source and desination systems you've routed to.
* The distance field has a right-click context menu that lists the ships you've used on a route. Selecting the ship will fill both the distance and jump mulitplier.

## Suggestions

Let me know if you have any suggestions.

Fly dangerous! o7