#!/usr/bin/env python3
import serial
import time

PORT = "/dev/serial/by-id/usb-WeAct_Studio_Display_FS_0.96_Inch_addec74db14d-if00"
BAUDRATES = [115200, 460800, 921600]

COMMANDS = {
    "SYSTEM_RESET": bytes([0x40, 0x0A]),
    "FREE": bytes([0x07, 0x0A]),
    "SET_BRIGHTNESS": bytes([0x03, 0xFF, 0x00, 0x00, 0x0A]),
}

def log_hex(prefix, data):
    if not data:
        print(f"{prefix}: <no data>")
    else:
        print(f"{prefix}: {' '.join(f'{b:02X}' for b in data)}")

for baud in BAUDRATES:
    print("\n" + "=" * 60)
    print(f"🔍 Testing {PORT} @ {baud} Baud")
    print("=" * 60)

    try:
        ser = serial.Serial(PORT, baud, timeout=1)
        time.sleep(1)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        for name, cmd in COMMANDS.items():
            print(f"\n➡️  Sending {name}")
            log_hex("TX", cmd)
            ser.write(cmd)
            ser.flush()
            time.sleep(0.5)

            resp = ser.read_all()
            log_hex("RX", resp)

        ser.close()

    except Exception as e:
        print(f"❌ Error opening serial port @ {baud}: {e}")
