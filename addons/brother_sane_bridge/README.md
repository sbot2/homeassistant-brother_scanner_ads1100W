# Brother Scanner SANE Bridge (add-on)

A small Home Assistant **add-on** that lets the Brother Scanner integration
reach a Brother ADS-1100W via a remote `saned` and Brother's `brscan4` backend,
using SANE's `net:` protocol. This is what makes **duplex** possible when Home
Assistant runs in an immutable HAOS VM, because:

* the VM cannot persistently install Brother's proprietary driver, and
* the device's own WSD service reports `ADFSupportsDuplex=0` and exposes no
  eSCL endpoint (the usual duplex path).

## How it works

    [Host: Linux box, persistent disk]                  [HAOS VM]
     brscan4 driver -> saned (port 6566)   <--  this add-on dials OUT
                                                 scanimage -d net:<host>:<device>
                                                 -> small HTTP scan bridge (8661)
                                                       ^ integration calls it

The add-on only needs the SANE **client** (`scanimage`) plus the **`net`**
backend. It talks to the host's `saned`; it never runs `brscan4` itself. That
keeps the container small and avoids re-installing the proprietary `.deb`/`.rpm`
inside an ephemeral VM image.

* `GET /health` -> `{"ok": true, "device": "...", "listed": bool}`
* `POST /scan`  -> body `{"duplex","color_mode","resolution","source","max_pages"}`
  returns `{"pages": [base64-jpeg, ...]}`

## Host prerequisites (the Linux machine holding the driver)

1. Install SANE + the Brother driver, e.g. on Debian/Ubuntu host:

   ```bash
   sudo apt update
   sudo apt install -y sane-utils   # provides saned + scanimage
   # install the Brother brscan4 driver (from Brother's support site)
   sudo dpkg -i brscan4-*.deb
   ```

2. Register the scanner and confirm the device name the host sees:

   ```bash
   scanimage -L
   # expect a line naming the brother4 backend, e.g.:
   # device `brother4:net1;dev0' is a Brother ADS-1100W ...
   ```

3. Enable the `saned` server (it only serves; Brother's `brscan4` hands it the
   device):

   ```bash
   sudo systemctl enable --now saned
   ```

4. Allow the VM (the add-on egresses from the HA network) to connect. Add the VM
   address to `/etc/sane.d/saned.conf`:

   ```conf
   # allow the HAOS VM (adjust to your subnet)
   192.168.178.0/24
   ```

   and confirm the port is reachable from the VM:

   ```bash
   nc -vz <host-ip> 6566
   ```

## Install & configure the add-on

1. Load this folder as a local add-on in HAOS "Settings -> Add-ons" (or point a
   repository at the git checkout) and install it. It builds a local image.
2. Set the options:

   | Option               | Meaning                                | Example             |
   |----------------------|----------------------------------------|---------------------|
   | `saned_host`         | IP of the host running `saned`         | `192.168.178.101`   |
   | `saned_device`       | backend name the host reports          | `brother4:net1;dev0`|
   | `default_color_mode` | `Color` / `Gray` / `Lineart`           | `Color`             |
   | `default_resolution` | dpi                                    | `200`               |
   | `port`               | bridge HTTP port (leave default)       | `8661`              |

3. Start the add-on and read its log: it reports whether `scanimage -L` can
   see the remote device.

## Connecting the integration

The integration (`__init__.py`) normally shells out to `scanimage`, which lives
in the **HA Core** container -- a different container from this add-on. So this
add-on acts as a proxy: the integration should `POST` to
`http://brother_sane_bridge:8661/scan` (the add-on is reachable from HA Core at
its slug hostname) instead of invoking `scanimage` directly:

```python
import asyncio, base64, aiohttp

async def scan_via_bridge(url, *, duplex, color_mode, resolution, max_pages):
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{url}/scan", json={
            "duplex": duplex,
            "color_mode": color_mode,
            "resolution": resolution,
            "max_pages": max_pages,
        }) as r:
            data = await r.json()
    return [base64.b64decode(p) for p in data.get("pages", [])]
```

> If you would rather not run an add-on at all, the same `server.py` can be
> started on the host and the integration pointed at
> `http://<host>:8661/scan`. The add-on simply packages that service for the
> HAOS VM route. See the top-level README.

## Troubleshooting

* `/health` returns `listed: false`: `saned` not running on the host, the
  VM -> host port 6566 is blocked, or the VM IP is missing from `saned.conf`.
  The add-on log prints the exact `net:` string it tried; compare it with the
  host's `scanimage -L` output.
* Duplex comes out single-sided: Brother's backend needs
  `--source "ADF Duplex"`. The bridge selects that whenever `duplex: true`
  is posted.
* `scanimage` inside the add-on returns "access denied": check `saned.conf`
  host allow-list and that `saned` listens on 0.0.0.0 (see `/etc/sane.d/saned.conf`
  and `systemctl status saned`).





