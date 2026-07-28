The following entities are available. Which ones appear depends on the appliance type and its feature set. Not every device supports every entity listed here.

## Supported across multiple kinds of appliances

| Entity | Type | Description |
| --- | --- | --- |
| Active Program | Sensor | Currently running program |
| Operation State | Sensor | Device state (e.g. Ready, Running, Finished) |
| Remaining Program Time | Sensor | Time left in the current program |
| Program Progress | Sensor | Progress as a percentage |
| Start In | Sensor / Number | Delay before the program starts |
| Finish In | Sensor / Number | Target time until the program finishes |
| Select Program | Select | Choose a program to run, may not be writeable on laundry machines |
| Start / Abort / Pause / Resume | Button | Control the active program |
| Power State | Switch / Select | Turn the appliance on or off |
| Child Lock | Switch | Lock the physical controls |
| Remote Start Allowed | Binary Sensor | Whether remote control is enabled on the device |
| Door State | Binary Sensor / Sensor | Whether the door is open or closed |
| Program Finished | Binary Sensor | Turns on when the current cycle completes |
| Wi-Fi Signal Strength | Sensor | Device's Wi-Fi signal strength - polled hourly (see Data Updates), not pushed like everything else |
| Cloud Connection | Binary Sensor | Whether the appliance is currently connected to the Home Connect cloud |
| Allow Cloud Connection | Switch | Enable or disable the appliance's connection to the Home Connect cloud |
| Allow Consumer Insights | Switch | Enable or disable usage data collection by the Home Connect cloud |
| Synchronize Time with Server | Switch | Whether the appliance keeps its clock in sync with a time server |
| Time Format | Select | 12-hour or 24-hour clock display |
| Software Update | Update | Tracks/triggers installing an available firmware update |
| Software Download | Update | Tracks/triggers downloading an available firmware update (only on appliances that support a separate download stage) |

A few additional diagnostic entities (Local Control Active, Remote Control Active) are also available, disabled by default.

The Home Connect protocol only signals that a firmware update exists, not which version it is, so the Update entities show a generic "New Version" placeholder rather than a real version number when one is available. Also, as mentioned before, if you disabled cloud access for your appliance, or it cannot reach the Home Connect Cloud, then it cannot get new firmware updates.

Some entites are excluded from this integration on purpose, even though the Home Connect Protocol Supports it

| Entity/featureDescription | UID (hex) | Reason for exclusion |
| --- | --- | --- |
|BSH.Common.Command.ApplyFactoryReset|0229|Irreversible change|
|BSH.Common.Command.ApplyNetworkReset|022A|Also an irreversible change|
|BSH.Common.Command.DeactivateWiFi|0001|Reversible, but will prevent HA from accessing the appliance until physically activated again|

## Dishwasher

Wash program selection and options (half load, hygiene plus, extra dry, extra rinse, speed-on-demand, silence-on-demand, sanitize), FlexSpray zone configuration, rinse aid and salt level sensors, maintenance reminders (filter check, machine care, smart filter), water hardness and rinse aid dose settings, auto power off, and time light (floor projector).

## Washing Machine / Dryer

Program options including temperature, spin speed, prewash, rinse plus, gentle cycle, and hygienic steam; iDos automatic dosing (levels 1 & 2); drum light and door ring LED control (brightness and color mode); anti-wrinkle guard; maintenance reminders (drum clean, lint filter full); condensate container alert (dryer).

## Oven

Oven current and setpoint temperature, meat probe temperature and plugged-in status, heating mode selection, fast preheat, sabbath mode, convection conversion, dim display on standby, clock display (analogue/digital), night-time display dimming, sound volume, telescopic slide-out rail, and brand logo display

## Hob

- Automatic timer
  - Time (minutes) after which a zone turns off automatically
- Automatic keylock
  - Defines if keylock (childlock) is turned on automatically, manually or turned off completely
- BridgeZoneMode
  - When turning on hob this indicates if some zone (pre defined) are joined or split
- EnergyConsumptionIndication
  - Indicates if energy consumption (kWh) shall be displayed after hob is turned off
- PowerManagement
  - Maximum power drain (off or 1000W up to 9000W; 500W steps)
- BuzzerBeepLevel
  - Which signal types shall be played
- EndTimerSignalduration
  - Signal duration after timer runs out
- Ventilation level
- Those are only available if paired with a hood:
  - HoodAutomaticLightOff
    - When hob is turned off then also turn off hood light
  - HoodAutomaticLightOn
    - When hob is turned on then also turn on hood light
  - HoodAutomaticStart
    - When hob is turned on then also turn on hood fan
  - HoodAfterRun
    - When hob is turned off then also keep hood fan running (or not)

## Hood

Hood fan speed control, ambient and work lighting, automatic shutoff delay, interval ventilation, grease and carbon filter saturation sensors and one-tap reset buttons

## Coffee Maker

Bean container and amount, grind coarseness, coffee strength, temperature, brew size, shot count, milk ratio; cup warmer; maintenance countdowns for cleaning, descaling, and water filter replacement; water tank and drip tray level sensors; per-drink brew counters (coffee, espresso, milk-based drinks, and more).

## Refrigerator / Freezer

Fridge, freezer, and chiller setpoint temperatures (°C and °F); door open and door alarm binary sensors; super-freeze and super-cool modes; eco, vacation, and fresh-food modes; interior light with brightness control; water filter alert; sabbath mode duration.
