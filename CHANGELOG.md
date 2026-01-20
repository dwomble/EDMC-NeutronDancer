# EDMC-NeutronDancer Changelog

## v1.6.? ???-??-??

### Changes
* Improved layout especially for dark mode
* Switched up the busy animation
* Improved handling of src & dest systems between Neutron and Galaxy plotters
* Added current system at the top of the source dropdown

### Bug Fixes
* Ensured current system is always set and saved [Issue 11](https://github.com/dwomble/EDMC-NeutronDancer/issues/11)
* Fixed runtime with changing optionmenu menu items that occurred in dark mode


## v1.6.1 2026-01-18

### Bug fixes
* Removed erroneous import statement


## v1.6.0 2026-01-16

### New Features
* Improved fleetcarrier support with jump cooldown notification
* More detailed help
* Added a refuel reminder icon

### Bug Fixes
* Fixed error with displaying booleans on imported routes [Issue 8](https://github.com/dwomble/EDMC-NeutronDancer/issues/8)
* Yet another go at Linux copy to clipboard [Issue 8](https://github.com/dwomble/EDMC-NeutronDancer/issues/8)
* Made ship menus update dynamically


## v1.5.3 - 2026-01-03

### Bug fixes
* Fixed bug with True/False vs 1/0 which confused the API.


## v1.5.2 - 2026-01-03

### Bug fixes
* Fixed typo that caused Galaxy Plotter to use the Neutron Plotter's destination


## v1.5.1 - 2025-12-31

### Bug Fixes
* Fixed galaxy router error in dark mode when ships hadn't been switched
* Addressed more dark and transparent mode craziness


## v1.5.0 - 2025-12-30

### New Features
* Spansh Galaxy Plotter [Issue #3](https://github.com/dwomble/EDMC-NeutronDancer/issues/3)
* Route export to CSV
* Progress bar [Issue #4](https://github.com/dwomble/EDMC-NeutronDancer/issues/4)
* Jump and distance per hour progress statistics
* Accurate ship range calculation

### Changes
* Modified to determine supercharge multiplier via the Caspian's v2 FSD rather than just the ship [Issue #2](https://github.com/dwomble/EDMC-NeutronDancer/issues/2)
* Refactored route and ship data to support new functionality
* Modified updater to check the latest release tag instead of the version file in the master
* Made the route window highlight the current jump location
* Switched to treeview plus for improved route window text formatting
* Added progress summary to the route window
* Modified so clicking on a system in the route window copies that system name to the clipboard
* Added tooltips for previous & next waypoint
* Added a busy view while plotting


## v1.0.0 - 2025-12-23

### Changes
* Switched to a threaded implementation for the Spansh plot calls
* Modified to support just about any CSV as long as it has a system name column
* The UI now works properly with transparent and dark modes
* Code cleanup and consistency improvements
* Modified the update checker to work asynchonrously to not delay EDMC startup


## v0.5.0 - 2025-12-18

## New Features
* Added distance remaining to the system tooltip
* Switched copy to clipboard to Tk's native for all platorms
* Improved validation and error reporting for plot entry form
* Enabled auto-updating

## Changes
* Improved plot entry data validation and error reporting


## v0.4.0 - 2025-12-15

### New Features
* Added CSV importing of various formats

### Bug Fixes
* Fixed Linux copy to clipboard

## v0.3.1 - 2025-12-14

### Bug Fixes
* Fixed the updater and version identification


## v0.3.0 - 2025-12-13

### Changes
* Manual updater implemented
* Added current system to source menu list
* Update source system after jump onboard a carrier
* Added jumps remaining to the route view


## v0.2.0 - 2025-12-12

### Changes
* Work on the autoupdater

### Bug Fixes
* Autocreation of data directory
* Clearing of placeholder text on click


## v0.1.0 – 2025-12-12

### New Features
* Support for Caspian's 6x jump multiplier

### Changes
* Largely rewritten
* UI has been updated
* Does not currently support csv import or export
* Does not currently support fleetcarrier or roadtoriches
