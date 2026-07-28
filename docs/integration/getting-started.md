## Install the Integration

1. Go to the HACS -> Custom Repositories and add this repository as a Custom Repository [See HACS Documentation for help](https://hacs.xyz/docs/faq/custom_repositories/)

2. Click the button bellow and click 'Download' to install the Integration:

    [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?repository=homeconnect_local_hass&owner=vemboy200)

3. Restart Home Assistant.

## Prerequisites

To use this integration, you must first create a Home Connect account and connect your appliances.

## Supported Devices

Any Home Connect device that 
1. Allows a local connection (not all do) (View trouble shooting for more info to make sure your device supports a local connection)
2. On the same local network as your Home Assistant instance

### Supported Device Types

These devices are confirmed supported and will work well with this integration.

- Dishwashers
- Washing Machines/Dryers
- Ovens
- Cooktops/Hobs
- Refrigerators/Freezers
- Coffee Makers

**Dishwashers have the best support of any appliance type**, because BSH has pushed connectivity hardest on dishwashers out of their whole lineup:

1. Some newer models have removed physical buttons for functions like the rinse cycle, locking them behind the Home Connect app instead.
2. They _really_ want you to use Home Connect on Dishwashers. They have a card in it telling you to use Home Connect. Their manual mentions Home Connect _way_ too many times, and the "Home Connect" logo is physically engraved on ALL newer dishwasher models.
3. Every modern BSH dishwasher ships with Wi-Fi and Home Connect.

### Potentially Supported

Local connectivity is confirmed for these, but full functionality/websocket stability isn't as battle-tested as the mature categories above, treat as likely-to-work rather than guaranteed:

- **Microwaves**: Real setup attempts exist ([#211](https://github.com/chris-mc1/homeconnect_local_hass/issues/211), [#141](https://github.com/chris-mc1/homeconnect_local_hass/issues/141)) confirming local profile files and connectivity work. The reported bugs shown were about specific parsing edge cases, not a lack of local mode. Since BSH's smart microwave line is relatively new, expect more rough edges than mature categories.
- **Cookit** (Bosch's smart cooking/food-processor appliance, [product page](https://www.home-connect.com/global/smart-home-appliances/cookit)): [Issue #26](https://github.com/chris-mc1/homeconnect_local_hass/issues/26)'s debug log shows a real Cookit connecting locally over TLS websocket and passing setup, the reported error was a downstream parsing bug, fixed in version 1.0.3. Only the one confirmed report found, so broader reliability is unknown.

### Potentially Unsupported

- **Air conditioners**: No evidence either way. The Home Connect protocol/API schema theoretically includes an air-conditioner appliance type, but the actual Bosch/Siemens smart AC products on the market (5000i/3000i series) are controlled through a completely separate app and backend called **HomeCom Easy**, unrelated to Home Connect. No confirmed Home-Connect-branded AC product has been found to test against, so this is neither confirmed working nor confirmed broken.
- **Robot vacuums**: There is conflicting evidence. [Issue #228](https://github.com/chris-mc1/homeconnect_local_hass/issues/228) ("Bosch Spotless Vacuum Robot cannot be added") was closed as **not planned** after a user checked the Home Connect app's own local-connection indicator (Device → Settings → Network) and found the local-network leg permanently shows as interrupted, suggesting the device requires its cloud connection to operate. But [Issue #290](https://github.com/chris-mc1/homeconnect_local_hass/issues/290) tells a murkier story. Multiple users successfully generated profile files for Bosch Spotless/Spotless Max units, and chris-mc1 pointed testers at an experimental `cleaning_robot` branch, where setup got past the original parsing error to a different "unknown error" further down the pipeline. Still open, unresolved either way, possibly different sub-models behave differently, or the cloud-only finding from #228 doesn't generalize to the whole line. 

### Unsupported Devices

_None confirmed yet - see Potentially Unsupported above._

### Maintainer's note

If you have any of these devices that aren't in the "Supported Device Types" category it would be helpful to tell the integration maintainer whether they work with this integration and help add support for them.

## Setup

> [!NOTE]
> Both of these methods aren't something Home Connect has authorized for third-party use, and the endpoints involved are undocumented and could change or be locked down without notice. If that's not something you're comfortable with, dont use this integration and instead use the core [home connect integration](https://www.home-assistant.io/integrations/home_connect/).
> 
There are two ways to add an appliance. Signing in is quicker and doesn't require a separate tool.

### Option A: Sign in with Home Connect

1. Click the button below or use "Add Integration" in Home Assistant and select "Home Connect Local".

    [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=homeconnect_ws)

2. Choose "Sign in with Home Connect" and select the region your Home Connect account is registered in.
3. Open the shown URL in a browser and sign in with your Home Connect account. The page will fail to load afterward. That's expected.
4. Copy the full URL from your browser's address bar and paste it back into Home Assistant.
5. Select the Appliance you want to setup (skipped automatically if it's the only one left to add).
6. When the initial connection to the Appliance fails, you're asked to manually enter your Appliance IP-Address.
7. Repeat from Step 1 if you want to setup more than one Appliance.

### Option B: Upload Profile File

1. Use the [Home Connect Profile Downloader](https://github.com/bruestel/homeconnect-profile-downloader) to download your Appliance profiles, select "Home Assistant - Home Connect Local" as target. The downloaded ZIP-file contains each Appliance encryption Key and feature descriptions
2. Click the button below or use "Add Integration" in Home Assistant and select "Home Connect Local".

    [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=homeconnect_ws)

3. Choose "Upload Profile File" and upload the downloaded Profile file.
4. Select the Appliance you want to setup.
5. When the initial connection to the Appliance fails, your asked to manually enter your Appliance IP-Address.
6. Repeat from Step 2 if you want to setup more than one Appliances.

> [!IMPORTANT]
> Do <ins> **NOT**</ins> delete your Home Connect account after this. If you do then
> 
> - The device may disconnect itself from your Wi-Fi
> - You cannot troubleshoot if the appliance does not connect to Home Assistant
> - You cannot connect any more devices to Home Connect
>
> If you value your privacy you can instead go to the app settings an disable all the data collection stuff in the "Privacy and Legal" section of the app

### Configuration parameters

- Region: The region your Home Connect account is registered in (Option A only)
- Redirect URL: The URL from your browser's address bar after signing in and being redirected (Option A only)
- Profile file: The Profile File you've downloaded with the [Home Connect Profile Downloader](https://github.com/bruestel/homeconnect-profile-downloader) (Option B only)
- Select Appliance: Select the Appliance you want to setup
- Host / IP-Address: Manually enter your Appliance Hostname or IP-Address if auto discovery did not work

> [!TIP]
>If you want to, once you have connected the appliance to Home Assistant you can disable its cloud access.
>
> ### Through Home Assistant
>
>1. (OPTIONAL) Before starting, in the Home Connect app, make sure the bottom line (direct connection between your phone and device) is green in case if something goes wrong.
>2. In the configuration section there is a disabled entity called "Allow Cloud Connection" enable it and turn off the switch
>3. (OPTIONAL) Enable the "Cloud Connection" diagnostic entity to verify its disconnected from the cloud.
>
>If you see the "Cloud Connection" entity saying disconnected then you have succesfully disabled cloud access for your appliance.
>
>### Through Home Connect
>1. Open the Home Connect app and go to your appliance's settings.
>2. Scroll down until you get the "network" and tap the details button.
>3. (OPTIONAL) Make sure the bottom line (direct connection between your phone and device) is green in case if something goes wrong.
>4. Scroll down (again) until you see the connection to the server toggle.
>5. Turn off the toggle and ignore the scare screen (they have it there so they can continue collecting your data)
>6. Then save
>
>You'll know if you have successfully done it if you see the line between your appliance and their cloud is grayed out and disconnected.

>[!NOTE]
>Do note that your device will **not** get firmware updates once disconnected, if you want to, you can occasionally (once every 1-3 months) reenable the cloud connection for 1-2 days so the device can check for an update.
