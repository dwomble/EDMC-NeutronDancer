# Navl's Neutron Dancer

This plugin's purpose is to make neutron jumping easier by plotting a route using [Spansh](https://www.spansh.co.uk/plotter) within EDMC and automatically copying the next waypoint in that route to your clipboard.

The goal of this fork is support for the new 6x overcharge of the Caspian and a cleaner UI.


<img width="483" height="135" alt="Screenshot 2025-12-20 215912" src="https://github.com/user-attachments/assets/11c0f557-bbc4-4085-b6e3-fd6e5ec6056f" />

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

<img width="483" height="159" alt="Screenshot 2025-12-20 220012" src="https://github.com/user-attachments/assets/b3eaf1b7-a7b8-4ab1-93a0-f5f04b6685ac" />

Next click **Calculate** to query Spansh and plot your route.

### CSV Import

Click **Import** and select a comma separated file such as that exported by the various Spansh route plotters. Neutron Dancer is very flexible about CSV formats. It requires a column called "System Name" or "system" and will accept any other columns provided. If there are columns for remaining distance or number of jumps it will use those to calculate those values.

### Following the route

<img width="478" height="85" alt="Screenshot 2025-12-20 220110" src="https://github.com/user-attachments/assets/1376f752-4956-45fa-931c-6e43076d5aab" />

Once your route is plotted, and every time you reach a waypoint, the next one is automatically copied to your clipboard. In Elite Dangerous bring up the Galaxy Map, paste in the waypoint, and click **Plot route**.

If for some reason, your clipboard should be empty or contain other stuff that you copied yourself, click on the **System Name** button, and the waypoint will be copied again to your clipboard.

The **System Name** button also has a Tooltip that provides the number of jumps remaining and distance remaining if those values are known.

The **Show route** button will bring up a window showing the details of the plotted route.

<img width="795" height="390" alt="Screenshot 2025-12-20 220119" src="https://github.com/user-attachments/assets/f4a3b4d0-f578-4b8b-86b2-671cff1e45b0" />

If you close EDMC, the plugin will save your progress. The next time you run EDMC, it will continue from where you left off.

## Suggestions

Let me know if you have any suggestions.

Fly dangerous! o7


