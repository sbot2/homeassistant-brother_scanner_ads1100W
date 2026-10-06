# Brother ADS-1100W Scanner Integration

Custom Home Assistant integration to interface with the Brother ADS-1100W
via the WSD (Web Services for Devices) scan protocol. Supports multi-page
scanning from the automatic document feeder (ADF).

When a SANE/`brscan4` backend is available on the Home Assistant host, the
integration automatically uses it instead for acquisition, which enables
**duplex** (double-sided) scanning and more accurate colour/resolution options —
the device's WSD service itself does not advertise duplex. Otherwise it falls
back to WSD transparently.

## Features

- **Multi-page ADF scanning** – scans all pages in the document feeder in one run.
- **Snapshot service** – `brother_scanner.snapshot` to trigger a scan and save the
  resulting pages to disk.
- **Button entity** – a `Snapshot` button per device that triggers a scan.
- **Camera entity** – a `Last Snapshot` camera that shows the most recent scanned
  page and refreshes automatically.
- **Sensors** – scanner state, ADF (feeder) state, online status and scan
  diagnostics (total pages scanned, last scan time and page count).
- **PDF output** – combine all scanned pages into a single lossless PDF.
- **OCR (optional)** – extract text from scanned pages (requires local
  Tesseract).
- **Configurable scan settings** – color mode, resolution, duplex, output format
  and OCR can be changed per device via the options flow in the UI.
- **Automatic discovery** – finds the scanner via Zeroconf and walks you through
  configuration in the Home Assistant UI.

Scanned pages are saved under Home Assistant's `www` directory by default
(e.g. `www/scans/<ip>_<timestamp>.jpg`). If an absolute `filename` is supplied to
the service, the file is saved at that location instead. When set to PDF output,
a single `<name>.pdf` is produced; JPEG output produces one file per page.

## Installation (via HACS)

1. In Home Assistant, go to **HACS → Integrations → Custom repositories**.
2. Add this repository URL:
   `https://github.com/sbot2/homeassistant-brother_scanner_ads1100W`
   with category **Integration**.
3. Install the integration.
4. Restart Home Assistant.
5. Add the integration via the Home Assistant UI (search for **Brother ADS-1100W**).

## Configuration

This integration supports `config_flow`, so configuration is done entirely through
the UI.

On first setup the integration attempts to **auto-detect** the scanner via
Zeroconf. If the device is not found automatically, you can enter the scanner's
**IP address or hostname** manually.

## Options

After setup you can adjust the scan settings per device via
**Settings → Devices & Services → Brother ADS-1100W → Options**:

The available **color mode**, **resolution**, **duplex** and **rotation** options
are read from the device's advertised capabilities at setup, so only values the
scanner actually supports are shown. For the ADS-1100W this is:

- **Color mode** – `RGB24` (color), `Grayscale8` (grayscale) or `BlackAndWhite1`.
- **Resolution** – 100, 200 or 300 dpi.
- **Duplex mode** – `Duplex` is available only when the SANE/`brscan4` backend is
  installed (see below); otherwise only `None` (single-sided) is offered, because
  the device's WSD scan service reports `ADFSupportsDuplex=0`.
- **Output format** – `jpeg` (one file per page) or `pdf` (single PDF).
- **OCR** – enable to run OCR on scanned pages (requires Tesseract installed on
  the Home Assistant host).

## Entities

| Platform  | Entity                                        | Description                            |
|-----------|-----------------------------------------------|----------------------------------------|
| Button    | `button.<name>_snapshot`                      | Triggers a scan of the ADF             |
| Camera    | `camera.<name>_last_snapshot`                 | Shows the last scanned page            |
| Binary sensor | `binary_sensor.<name>_online`             | Whether the scanner is reachable       |
| Sensor    | `sensor.<name>_scanner_state`                 | Current scanner state (Idle, Scanning…)|
| Sensor    | `sensor.<name>_adf_state`                     | Document feeder state                  |
| Sensor    | `sensor.<name>_pages_scanned`                 | Total pages scanned since setup        |
| Sensor    | `sensor.<name>_last_scan`                     | Timestamp of the last scan             |
| Sensor    | `sensor.<name>_last_scan_pages`               | Number of pages in the last scan       |

## Services

### `brother_scanner.snapshot`

Triggers a scan and saves the resulting pages to disk. All fields except `ip`
are optional; settings that are not provided use the device's stored options.

| Field           | Required | Description                                                                |
|-----------------|----------|----------------------------------------------------------------------------|
| `ip`            | Yes      | The IP address or hostname of the scanner.                                 |
| `filename`      | No       | Path to save the file. Relative paths are placed under `www`. Defaults to `www/scans/<ip>_<timestamp>.jpg`. |
| `color_mode`    | No       | Override color mode (`RGB24`, `Grayscale8`, `BlackAndWhite1`).             |
| `resolution`    | No       | Override resolution in dpi (100, 200 or 300).                              |
| `duplex`        | No       | Override duplex mode (`None` or `Duplex`). Duplex requires the SANE/`brscan4` backend to be installed; otherwise only `None` works. |
| `output_format` | No       | Override output (`jpeg` or `pdf`).                                         |
| `ocr`           | No       | Override whether to run OCR.                                               |

## OCR

OCR is optional and only runs when the **OCR** option is enabled and
**Tesseract** is installed on the Home Assistant host. Text is written to a
`.txt` file next to each scanned image. This requires the `tesseract` binary to
be available in the system `PATH`.

## Default scan settings

These are the defaults used if not overridden per device via Options or per call
via the service (defined in `const.py`):

- Format: `exif` (JPEG)
- Input source: `ADF`
- Color mode: `RGB24`
- Content type: `Auto`
- Resolution: 200 dpi
- Duplex: `None`
- Media size: A4 (8500 × 11000 thousandths of an inch)

## Duplex scanning (SANE / brscan4 backend)

The Brother ADS-1100W **hardware** supports duplex (double-sided) scanning, and
you can already use it via Brother's Linux drivers. The integration cannot reach
that over the WSD scan path, however: the device's WSD Scan Service advertises
`ADFSupportsDuplex=0`, and it exposes **no** eSCL/AirScan endpoint (no
`_uscan._tcp` mDNS record). The only protocol that honours duplex is Brother's
proprietary one, delivered through the SANE `brother4`/`brscan4` backend.

To enable duplex, the SANE stack (`scanimage` + the Brother `brscan4` backend)
must be reachable from wherever Home Assistant runs. Once the integration finds a
Brother device via `scanimage -L` (checked automatically at setup) it switches
acquisition to SANE and exposes the `Duplex` option plus the real
colour/resolution list. When no Brother SANE device is detected, the integration
keeps using WSD automatically.

### Where to put the SANE stack depends on your installation

- **Home Assistant on a normal Linux machine** (HA Core / Docker on Debian,
  Ubuntu, etc.): install `sane-utils` + `brscan4` directly on that host.

  ```bash
  sudo apt install sane-utils
  # Download the Brother brscan4 driver for ADS-1100W and install it, then
  # register the network scanner, e.g.:
  sudo dpkg -i brscan4-*-amd64.deb
  sudo brsaneconfig4 -a name=ADS-1100W model=ADS-1100W ip=192.168.178.109
  scanimage -L   # should list the ADS-1100W
  ```

- **Home Assistant OS (HAOS), including a HAOS VM:** HAOS is an *immutable*
  operating system — you cannot `apt install` packages into it, and add-on
  containers are ephemeral (anything installed at runtime is lost on restart
  unless baked into the image). Do **not** try to install the driver inside the
  VM. Instead, run `saned` on a *different* machine that already has the Brother
  driver (e.g. your regular Linux desktop/server), and expose it to HA over
  SANE's `net:` backend:

  1. **On the host with working Brother scanning**, install + configure `saned`:
     ```bash
     sudo apt install sane-utils saned
     # allow the HA machine/VM's address in /etc/saned/saned.conf
     echo "192.168.178.0/24" | sudo tee -a /etc/sane.d/saned.conf
     sudo systemctl enable --now saned
     scanimage -L   # confirm this returns the ADS-1100W
     ```
  2. **Inside the HA add-on that runs the integration**, point SANE at the host
     so `scanimage -L` shows a `net:host:...` device. If your HA add-on image
     ships `sane-utils`, enable the backend (`#net` in `/etc/sane.d/dll.conf`)
     or build a small custom add-on with `sane-utils` + the SANE `net` backend
     baked into its image. The integration already parses `net:...` devices, so
     no code change is required.

  > TIP: the integration auto-selects the SANE path **only** when it sees a
  > Brother device in `scanimage -L`; whatever host the add-on can reach with
  > `scanimage -L` is what will be used.

### Recommended HAOS route: the SANE bridge add-on

Rather than baking `sane-utils` into a custom image for the integration's own
container, the repo ships a ready-made **SANE bridge add-on** in
[`addons/brother_sane_bridge/`](addons/brother_sane_bridge/). It runs in its own
container, dials **out** to the host's `saned` over SANE `net:`, and exposes a
tiny HTTP scan bridge (`GET /health`, `POST /scan`).

The integration then calls the bridge over HTTP
(`http://brother_sane_bridge:8661/scan`) instead of shelling out to a local
`scanimage`:

- At setup it probes the bridge's `/health`. If the add-on is running, it
  switches to **bridge mode** and every scan is proxied through it — no local
  `scanimage` or Brother driver is needed inside HA Core.
- If the bridge is not reachable, it falls back to the local `scanimage` path,
  then to WSD, exactly as before.

To use it:

1. Install the `brother_sane_bridge` add-on (add its folder as a local add-on).
2. Configure its options: `saned_host` = IP of the machine running `saned`,
   `saned_device` = the backend name that host reports (e.g.
   `brother4:net1;dev0`).
3. Start the add-on; check its log says `scanimage -L` sees the remote device.
4. The integration detects the bridge automatically on its next setup/reload.
   To point it at a *remote* host instead of the add-on slug, set the
   `sane_bridge` option in the integration's options flow to e.g.
   `http://192.168.178.50:8661`.

See the add-on [`README`](addons/brother_sane_bridge/README.md) for full setup
(host `saned` prerequisites, `saned.conf` allow-list, troubleshooting).

## Requirements

The integration installs its Python dependencies automatically via HACS:

- `aiohttp` – HTTP/SOAP communication
- `Pillow` – image handling for the camera entity and OCR
- `img2pdf` – lossless PDF generation
- `pytesseract` – OCR binding (requires a local Tesseract installation to be
  useful)
