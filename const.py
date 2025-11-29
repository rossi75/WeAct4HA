DOMAIN = "weact_display"
DEFAULT_PORT = "/dev/ttyACM0"
DEFAULT_PORT = "port: /dev/serial/by-id/usb-WeAct_Studio_Display_FS_0.96_Inch_addec74db14d-if00"
DEFAULT_BAUDRATE = 115200

IMG_PATH = None
MAX_BMP_FILES = 20
#IMG_PATH = Path(hass.config.path()) / "custom_components" / "weact_display"

#ATTR_WIDTH = "width"
#ATTR_HEIGHT = "height"
#ATTR_ORIENTATION = "orientation"
#ATTR_IMAGE_PATH = "image_path"

#ATTR_CLOCK_MODE = "clock_mode"
#CLOCK_REMOVE_HANDLE = None
#DEFAULT_CLOCK_MODE = "idle"

ORIENTATION_NAMES = {
    0: "Landscape",
    1: "Portrait",
    2: "Landscape Reverse",
    3: "Portrait Reverse"
}
