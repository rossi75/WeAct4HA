from pathlib import Path

DOMAIN = "weact_display"
IMG_PATH = None
MAX_BMP_FILES = 20
MAX_SVG_FILES = 100
BASE_PATH = Path(__file__).parent
IMG_PATH = BASE_PATH / "bmp"
ICON_CACHE_DIR = BASE_PATH / "icons"
MDI_BASE_URL = "https://raw.githubusercontent.com/Templarian/MaterialDesign-SVG/master/svg"

ORIENTATION_NAMES = {
    0: "Portrait",
    1: "Portrait Reverse",
    2: "Landscape",
    3: "Landscape Reverse",
    5: "Rotate"
}
