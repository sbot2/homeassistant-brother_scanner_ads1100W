from datetime import timedelta

DOMAIN = "brother_scanner"
MANUFACTURER = "Brother"
MODEL = "ADS-1100W"
STORAGE_VERSION = 1
STORAGE_KEY_TEMPLATE = f"{DOMAIN}_{{entry_id}}"
SCANS_DIR = "scans"
# WSD scan settings for the ADS-1100W (ADF sheet-fed document scanner).
#
# The defaults below are only fallbacks: at setup the integration queries the
# device's <ScannerConfiguration> and uses the values it actually advertises
# (colour modes, resolutions, duplex, max size) to build the option pickers.
DEFAULT_FORMAT = "exif"
DEFAULT_INPUT_SOURCE = "ADF"
DEFAULT_COLOR_MODE = "RGB24"
DEFAULT_CONTENT_TYPE = "Auto"
# Media size in thousandths of an inch (A4)
DEFAULT_PAGE_WIDTH = 8500
DEFAULT_PAGE_HEIGHT = 11000

# Scan option keys (stored per config entry under entry.options)
CONF_COLOR_MODE = "color_mode"
CONF_RESOLUTION = "resolution"
CONF_DUPLEX = "duplex"
CONF_OUTPUT_FORMAT = "output_format"
CONF_OCR = "ocr"

# SANE bridge (optional) option keys under entry.options
CONF_SANE_BRIDGE = "sane_bridge"

# Default bridge base URL. `brother_sane_bridge` is the add-on slug, which is
# reachable from HA Core at that hostname; port 8661 is the add-on's HTTP port.
DEFAULT_SANE_BRIDGE_URL = "http://brother_sane_bridge:8661"

# Allowed values (fallbacks used when the device capability probe is
# unavailable; normally the device-reported list is used instead). Names follow
# the standard WSD color-mode tokens the ADS-1100W advertises.
COLOR_MODES = ["BlackAndWhite1", "Grayscale8", "RGB24"]
# Resolution in DPI (WSD xResolution is in DPI)
RESOLUTIONS = [100, 200, 300]
OUTPUT_FORMATS = ["jpeg", "pdf"]
DUPLEX_VALUES = ["None", "Duplex"]

# Defaults
DEFAULT_RESOLUTION = 200
DEFAULT_DUPLEX = "None"
DEFAULT_OUTPUT_FORMAT = "jpeg"
DEFAULT_OCR = False

# Tesseract executable (used when OCR is enabled)
TESSERACT_CMD = "tesseract"

# Scan services
SERVICE_SNAPSHOT = "snapshot"
SERVICE_CANCEL_SCAN = "cancel_scan"

# Image-processing scan option keys (stored per config entry under entry.options)
CONF_BRIGHTNESS = "brightness"
CONF_CONTRAST = "contrast"
CONF_DESKEW = "deskew"
CONF_ROTATION = "rotation"

# Allowed values
# WSD image-adjustment settings (ranges differ per vendor; we use -50..50)
BRIGHTNESS_RANGE = range(-50, 51)
CONTRAST_RANGE = range(-50, 51)
# WSD Rotation element values
ROTATIONS = ["None", "Rotate90", "Rotate180", "Rotate270"]

# Defaults
DEFAULT_BRIGHTNESS = 0
DEFAULT_CONTRAST = 0
DEFAULT_DESKEW = False
DEFAULT_ROTATION = "None"

# Max number of pages to retrieve in a single scan
MAX_PAGES = 10

# Update interval for sensor/online polling
SCAN_INTERVAL = timedelta(seconds=60)
