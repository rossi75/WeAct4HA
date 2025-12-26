from pathlib import Path

DOMAIN = "weact_display"
IMG_PATH = None
MAX_BMP_FILES = 20
MAX_SVG_FILES = 100
BASE_PATH = Path(__file__).parent
IMG_PATH = BASE_PATH / "bmp"
ICON_CACHE_DIR = BASE_PATH / "icons"
MDI_BASE_URL = "https://raw.githubusercontent.com/Templarian/MaterialDesign-SVG/master/svg"
IGNORE_WEACT_FILTER = False

ORIENTATION_MAP = {
    "Portrait": 0,
    "Portrait Reverse": 1,
    "Landscape": 2,
    "Landscape Reverse": 3,
#    "Rotate": 5
}

ORIENTATION_MAP_INV = {v: k for k, v in ORIENTATION_MAP.items()}

COMMAND_NAMES = {
    0x02: "SET_ORIENTATION",
    0x03: "SET_BRIGHTNESS",
    0x04: "FULL",
    0x05: "SET_BITMAP",
    0x06: "ENABLE_HUMITURE_REPORT",
    0x07: "FREE",
    0x40: "SYSTEM_RESET",
    0x81: "WHO_AM_I",
    0x82: "READ_ORIENTATION",
    0x83: "READ_BRIGHTNESS",
    0x86: "HUMITURE_REPORT",
    0xC2: "READ_FIRMWARE_VERSION",
    0xC3: "READ_SERIAL_NUMBER"
}
