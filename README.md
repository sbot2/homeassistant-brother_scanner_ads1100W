# Brother ADS-1100ADW Scanner Integration

Custom Home Assistant integration to interface with the Brother ADS-1100ADW
via the WSD (Web Services for Devices) scan protocol. Supports multi-page
scanning from the automatic document feeder (ADF).

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
5. Add the integration via the Home Assistant UI (search for **Brother ADS-1100ADW**).

## Configuration

This integration supports `config_flow`, so configuration is done entirely through
the UI.

On first setup the integration attempts to **auto-detect** the scanner via
Zeroconf. If the device is not found automatically, you can enter the scanner's
**IP address or hostname** manually.

## Options

After setup you can adjust the scan settings per device via
**Settings → Devices & Services → Brother ADS-1100ADW → Options**:

- **Color mode** – `RGB24` (color), `Gray8` (grayscale) or `BlackAndWhite1`.
- **Resolution** – 100, 200, 300, 400 or 600 dpi.
- **Duplex mode** – `None` (single-sided) or `Duplex`.
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
| `color_mode`    | No       | Override color mode (`RGB24`, `Gray8`, `BlackAndWhite1`).                  |
| `resolution`    | No       | Override resolution in dpi (100–600).                                      |
| `duplex`        | No       | Override duplex mode (`None` or `Duplex`).                                 |
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

## Requirements

The integration installs its Python dependencies automatically via HACS:

- `aiohttp` – HTTP/SOAP communication
- `Pillow` – image handling for the camera entity and OCR
- `img2pdf` – lossless PDF generation
- `pytesseract` – OCR binding (requires a local Tesseract installation to be
  useful)
