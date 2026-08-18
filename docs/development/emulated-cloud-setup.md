# Idea: emulating the cloud during initial pairing, to remove the last internet dependency

**Status: unclaimed idea, not being worked on.** This is a write-up for anyone who wants to pick it up, not a roadmap item.

## The gap this would close

Today, `homeconnect_local_hass` is internet-free for everything *except* one step: getting the appliance's profile file. This currently involves either the [Home Connect Profile Downloader](https://github.com/bruestel/homeconnect-profile-downloader) or this integration's own OAuth setup path (`hc_cloud_api.py`), both of require logging into an account on the Home Connect cloud to pull that data. Once you have it, the appliance is controlled entirely over its local WebSocket, the cloud is never involved again, and you can disable the appliance's "Allow Cloud Connection" switch.

So the *only* remaining internet dependency is a one-time step during setup.

## The idea

A brand-new (or factory/network-reset) BSH appliance's very first WiFi/cloud account pairing is itself a network handshake with BSH's cloud, the appliance registers itself to a Home Connect account, and as part of that, its local encryption keys get established/reported.

If that handshake were pointed at a **local, fake cloud server** instead of BSH's real one, the same way `rethink` emulates LG's AWS backend for LG ThinQ appliances that have no local API at all, the appliance would complete pairing believing it registered to a real account, and the local keys could be captured directly from that handshake. No request would ever reach BSH's actual servers.

Combined with the fact that ongoing operation is already 100% local, this would mean **the entire appliance lifecycle, setup included, never touches BSH's cloud.** That's the appeal over the current OAuth-cloud-API approach: it removes the last "requires internet" asterisk entirely, not just for day-to-day use.

Since the web socket is the exact same regardless of whether it was setup with the fake or real cloud, this means that this integration can still cover both setup methods. It also benefits other Home Connect Local integrations like the ones for [Homey](https://homey.app/en-us/app/codes.lucasvdh.homeconnect/Home-Connect-(Local)/test/) or [OpenHab](https://www.openhab.org/addons/bindings/homeconnectdirect/).

## Why "Allow Cloud Connection" may still matter

>[!important]
> Whether this behavior will actually happen is unknown until its tested. Treat this like a theory.

Under this scheme, the appliance's own firmware believes it's legitimately registered to a Home Connect account (it doesn't know the account was fake). If its real cloud-connection toggle is left on afterward, it will periodically try to check in with BSH's *real* servers, which have no record of that registration. That mismatch is the whole scheme's exposure, BSH's servers seeing keys/credentials that don't match any real account is the one way this could get noticed or acted on. Turning "Allow Cloud Connection" off before the fake cloud is shutdown means the appliance never talks to the real cloud again, so there's nothing to notice. This may be a hard requirement of the design, not a nice-to-have.

## What's actually unknown (this is the real scope of the project)

None of the following has been reverse-engineered yet. This is not a "wire up rethink for BSH" task, it's a from-scratch protocol investigation, and the answer to the first point below could make the whole idea infeasible:

1. **TLS certificate pinning.** If the appliance validates BSH's real certificate chain during pairing and refuses to proceed against anything else, a fake local server can't complete the TLS handshake at all without getting the appliance to trust a custom root CA, which would require firmware-level access and defeats the point. This needs to be tested empirically (MITM proxy, e.g. `mitmproxy`, in front of a factory/network-reset appliance's first-time setup) before anything else here is worth building. If BSH pins certs strictly, this whole approach is likely dead on arrival.
2. **What hostname(s)/endpoints the appliance is hardcoded to contact** during initial pairing, and how it resolves them — needed to know what a local fake server needs to answer to, and how to redirect the appliance's traffic to it (local DNS interception on the network the appliance provisions over, same mechanism rethink uses for LG).
3. **The actual registration/pairing wire protocol** — request/response shapes, what triggers key generation vs. key upload, timing/retry behavior. This only comes from a live packet capture of a real pairing session.
4. **Failure modes.** If a fake response doesn't match what the appliance's firmware expects at any step, the appliance could error out, retry indefinitely, or get stuck in a half-provisioned state. Worth assuming a bricked pairing (recoverable by factory reset, but still) is a real possibility until proven otherwise, and testing on a spare/non-critical appliance if at all possible rather than a daily-driver one.

## Before making the software

Before writing any server code: capture a full packet trace (via a controlled AP running `mitmproxy` or even just `tcpdump`) of one already-owned appliance's factory/network-reset re-pairing process. That alone answers the certificate-pinning question, which determines whether the rest of this is worth attempting.

Also determine the WI-FI password, heres what I've confirmed so far
SSID: HomeConnect
Password: HomeConnect
I haven't confirmed if the password is this, but the SSID is confirmed. Seeing what the android app sends as the password to the appliance may be able to confirm it.

## Important appliances quirk.

A Home Connect Appliance is setup in a weird way. For some appliances like the Thermador T36IF905SP, pairing to WI-FI and connecting it to the app are two separate processes. But for most dishwashers like the Bosch SHE43DM5N its one process. Some appliances like the Thermador PRG486WDH has support for WPS which may just connect it to wifi but not to the app. Its unknown how or if the appliance contacts the cloud in this phase, but whats known is that it doesn't open its websocket.

Future BSH Appliances will come with matter which invovles both wifi and bluetooth. The app may have to account for a bluetooth pairing process to

## How the software would work

During the pairing process the app would be both the cloud and phone in parallel.

Draw a visual of how it would work
1. the phone connects to the appliance's hotspot, then shares the wifi credentials, then the appliance connects to the WAP
2. The appliance then negotites with the fake cloud and when/if its succesfull it sends the info to the fake cloud incloduing the stuff needed for the profile file
Note: its unknown if the appliance send the stuff needed for a profile file and then the cloud makes the profile file, or if the appliance just sends the profile file.
3. AFter that the profile is able to be downloaded to the users download folder on their computer or somewher else
Disabling cloud has two method
4.1: Phone side: The phone connects to websocket via the profile file aquired from the cloud (potentially easier since this integration does it
4.2: Cloud side: The fake cloud, already connected to the appliance sends the command instead (harder since we dont know whats sent)

```
Phone --(shares home WiFi creds via appliance's own hotspot)--> Appliance
                                                                    |
                                                                    v
                                                        Appliance joins home WAP
                                                                    |
                                                                    v
                                                    Appliance <==TLS==> Fake Cloud
                                                     (registers, reports/negotiates
                                                            local keys)
                                                                    |
                                                                    v
                                                  Fake Cloud has everything needed
                                                    for the appliance's profile
                                                                    |
                                                                    v
                                                  Profile file lands on the user's
                                                          computer
                                                                    |
                                                                    v
                                             Imported into homeconnect_local_hass
                                                                    |
                                          +-------------------------+-------------------------+
                                          |                                                   |
                                          v                                                   v
                                4.1 Phone/HA side                                    4.2 Cloud side
                          HA -> appliance's local WS                        Fake Cloud (still connected)
                         using keys from the profile                        sends disable-cloud itself
                        (what the integration does now)                       (harder — payload unknown)
                                          |                                                   |
                                          +-------------------------+-------------------------+
                                                                    |
                                                                    v
                                                    Appliance's cloud connection off
                                                                    |
                                                                    v
                                                       100% local from here on
```

## Prior art

- [rethink](https://github.com/anszom/rethink) — the LG ThinQ equivalent. Their situation is actually harder than BSH's: LG appliances have no local API at all, so rethink has to keep a fake cloud running permanently to handle ongoing control. Here, the fake cloud would only ever need to run for the few minutes of initial pairing — everything after that is already native and local.
