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
