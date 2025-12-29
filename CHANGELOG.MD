# EDMC-NeutronDancer Changelog

## v2.0.0 - 2025-12-29

## New Features
* Spansh Galaxy Plotter
* Route export to CSV
* Progress bar
* Jump and distance per hour progress statistics
* Accurate ship range calculation

# Changes
* Refactored route and ship data to support new functionality
* Modified updater to check the latest release tag instead of the version file in the master


## v1.0.0 - 2025-12-23

## Changes
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

### Bug fixes
* Fixed Linux copy to clipboard

## v0.3.1 - 2025-12-14

### Bug fixes
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

### Bug fixes
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
