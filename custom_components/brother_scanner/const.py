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
COLOR_MODES = ["RGB24", "Gray8", "BlackAndWhite1"]
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

# Max number of pages to retrieve in a single scan
MAX_PAGES = 10

# Update interval for sensor/online polling, in seconds
SCAN_INTERVAL = 60
