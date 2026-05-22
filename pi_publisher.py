#!/usr/bin/env python3
"""
DS18B20 temperature publisher.
Runs on the Raspberry Pi. Reads the sensor every second and POSTs
the reading to the laptop server over LAN.

Usage:
    python3 pi_publisher.py                       # uses LAPTOP_IP below
    python3 pi_publisher.py 192.168.1.42          # override IP from CLI
"""

import glob
import os
import sys
import time

import requests

# -------------------------------------------------------------------
# CONFIG  --  set this to your LAPTOP's LAN IP address.
# Find it on the laptop:
#   macOS / Linux : ifconfig   (or `ip a`)
#   Windows       : ipconfig
# -------------------------------------------------------------------
LAPTOP_IP = "192.168.1.179"     # <-- CHANGE ME
LAPTOP_PORT = 5000
PATIENT_ID = "PT-0427"          # shown on the dashboard
POLL_INTERVAL_SEC = 1.0

# Allow overriding the laptop IP from the command line for convenience
if len(sys.argv) > 1:
    LAPTOP_IP = sys.argv[1]

ENDPOINT = f"http://{LAPTOP_IP}:{LAPTOP_PORT}/api/temperature"

# -------------------------------------------------------------------
# DS18B20 setup (1-Wire on GPIO 4)
# -------------------------------------------------------------------
os.system("modprobe w1-gpio")
os.system("modprobe w1-therm")

BASE_DIR = "/sys/bus/w1/devices/"


def find_sensor():
    devices = glob.glob(BASE_DIR + "28*")
    if not devices:
        print("ERROR: No DS18B20 detected at /sys/bus/w1/devices/28-*")
        print("  - Check wiring: VCC->3.3V, GND->GND, DATA->GPIO4, 4.7kΩ pull-up.")
        print("  - Enable 1-Wire: `sudo raspi-config` -> Interface Options -> 1-Wire.")
        print("  - Or add `dtoverlay=w1-gpio` to /boot/config.txt and reboot.")
        sys.exit(1)
    return devices[0] + "/w1_slave"


SENSOR_FILE = find_sensor()
print(f"Sensor found: {SENSOR_FILE}")


def read_temp_c():
    """Returns temperature in Celsius, or None if read failed."""
    try:
        with open(SENSOR_FILE, "r") as f:
            lines = f.readlines()
    except OSError:
        return None

    # First line must end with 'YES' (CRC ok). Retry briefly if not.
    retries = 0
    while lines and lines[0].strip()[-3:] != "YES" and retries < 5:
        time.sleep(0.2)
        try:
            with open(SENSOR_FILE, "r") as f:
                lines = f.readlines()
        except OSError:
            return None
        retries += 1

    if not lines or len(lines) < 2:
        return None

    eq = lines[1].find("t=")
    if eq == -1:
        return None
    return float(lines[1][eq + 2:]) / 1000.0


# -------------------------------------------------------------------
# Main loop
# -------------------------------------------------------------------
print(f"Publishing to {ENDPOINT}  (patient={PATIENT_ID})")
print("Press Ctrl+C to stop.\n")

session = requests.Session()
fail_streak = 0

while True:
    try:
        temp = read_temp_c()
        if temp is None:
            print("  ! sensor read failed, retrying...")
            time.sleep(POLL_INTERVAL_SEC)
            continue

        payload = {
            "temperature_c": round(temp, 2),
            "timestamp": time.time(),
            "patient_id": PATIENT_ID,
            "sensor_id": "DS18B20-01",
        }

        try:
            r = session.post(ENDPOINT, json=payload, timeout=2)
            if r.status_code == 200:
                print(f"  {time.strftime('%H:%M:%S')}  {temp:6.2f} °C   -> 200 OK")
                fail_streak = 0
            else:
                print(f"  {time.strftime('%H:%M:%S')}  {temp:6.2f} °C   -> HTTP {r.status_code}")
        except requests.exceptions.RequestException as e:
            fail_streak += 1
            if fail_streak <= 3 or fail_streak % 10 == 0:
                print(f"  network error ({fail_streak}): {e}")

        time.sleep(POLL_INTERVAL_SEC)

    except KeyboardInterrupt:
        print("\nStopped.")
        break
