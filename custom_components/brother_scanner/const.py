from datetime import timedelta

DOMAIN = "brother_scanner"
MANUFACTURER = "Brother"
MODEL = "ADS-1100ADW"
STORAGE_VERSION = 1
STORAGE_KEY_TEMPLATE = f"{DOMAIN}_{{entry_id}}"
SCANS_DIR = "scans"
# WSD scan settings for the ADS-1100ADW (ADF sheet-fed document scanner)
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

# Allowed values
COLOR_MODES = ["RGB24", "RGB48", "Gray8", "Gray16", "BlackAndWhite1"]
# Resolution in DPI (hundreds of a mm would differ; WSD xResolution is in DPI)
RESOLUTIONS = [100, 200, 300, 400, 600]
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
