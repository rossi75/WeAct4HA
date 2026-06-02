from pathlib import Path

DOMAIN = "weact_display"
MAX_BMP_FILES = 20
MAX_SVG_FILES = 100
BASE_PATH = Path(__file__).parent
IMG_PATH = BASE_PATH / "bmp"
ICON_CACHE_DIR = BASE_PATH / "icons"
MDI_BASE_URL = "https://raw.githubusercontent.com/Templarian/MaterialDesign-SVG/master/svg"
IGNORE_WEACT_FILTER = False
DEFAULT_BRIGHTNESS = 7

ORIENTATION_MAP = {
    "portrait": 0,
    "portrait reverse": 1,
    "landscape": 2,
    "landscape reverse": 3,
#   "Rotate": 5
}

ORIENTATION_MAP_INV = {v: k for k, v in ORIENTATION_MAP.items()}

CMD_SET_ORIENTATION        = 0x02
CMD_SET_BRIGHTNESS         = 0x03
CMD_FULL                   = 0x04
CMD_SET_BITMAP             = 0x05
CMD_ENABLE_HUMITURE_REPORT = 0x06
CMD_FREE                   = 0x07
CMD_SET_BITMAP_FASTLZ      = 0x15
CMD_SYSTEM_RESET           = 0x40
CMD_WHO_AM_I               = 0x81
CMD_READ_ORIENTATION       = 0x82
CMD_READ_BRIGHTNESS        = 0x83
CMD_HUMITURE_REPORT        = 0x86
CMD_READ_FIRMWARE_VERSION  = 0xC2
CMD_READ_SERIAL_NUMBER     = 0xC3

# array-table [old][new]:, see internal_struct.md for evidence
ORIENTATION_CONVERSION_MAP_060_061 = [ [0,2,3,1], [2,0,1,3], [1,3,0,2], [3,1,2,0] ]               # von 0.6.0 bis 0.6.1
ORIENTATION_CONVERSION_MAP         = [ [0,2,1,3], [2,0,3,1], [3,1,0,2], [1,3,2,0] ]               # von 0.6.2 bis ...
