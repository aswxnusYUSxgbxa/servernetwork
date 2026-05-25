#!/usr/bin/env python3

import subprocess
import time
import os
import logging

# ==========================================
# CONFIG
# ==========================================

PRIMARY_WIFI = {
    "ssid": "homewifi",
    "password": "9961676620"
}

BACKUP_WIFI = {
    "ssid": "A",
    "password": None
}

PING_TARGET = "1.1.1.1"

CHECK_INTERVAL = 15
MAX_FAILED_PINGS = 3

LOG_FILE = "/var/log/wifi-watchdog.log"

ENABLE_SOUND = True
SOUND_FILE = "/opt/wifi-watchdog/alert.wav"

# ==========================================
# LOGGING
# ==========================================

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def log(msg):
    print(msg)
    logging.info(msg)

# ==========================================
# HELPERS
# ==========================================

def run(cmd):
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True
    )
    return result.stdout.strip()

# ==========================================
# INTERNET CHECK
# ==========================================

def internet_alive():
    response = os.system(
        f"ping -c 1 -W 3 {PING_TARGET} > /dev/null 2>&1"
    )
    return response == 0

# ==========================================
# SOUND ALERT
# ==========================================

def play_alert():
    if not ENABLE_SOUND:
        return

    if os.path.exists(SOUND_FILE):
        os.system(f'paplay "{SOUND_FILE}" &')
    else:
        print("\a")

# ==========================================
# WIFI SCAN
# ==========================================

def scan_wifi():
    output = run("nmcli -t -f SSID dev wifi")

    ssids = []

    for line in output.splitlines():
        line = line.strip()

        if line and line not in ssids:
            ssids.append(line)

    return ssids

# ==========================================
# CONNECT WIFI
# ==========================================

def connect_wifi(ssid, password=None):

    log(f"Trying to connect to {ssid}")

    if password:
        cmd = f'nmcli dev wifi connect "{ssid}" password "{password}"'
    else:
        cmd = f'nmcli dev wifi connect "{ssid}"'

    result = run(cmd)

    time.sleep(10)

    if internet_alive():
        log(f"Connected to {ssid}")
        return True

    log(f"Failed to connect to {ssid}")
    return False

# ==========================================
# NETWORK RECOVERY
# ==========================================

def restart_networkmanager():
    log("Restarting NetworkManager")

    os.system("systemctl restart NetworkManager")

    time.sleep(15)

def reset_wifi_radio():
    log("Resetting Wi-Fi radio")

    os.system("nmcli radio wifi off")
    time.sleep(5)

    os.system("nmcli radio wifi on")
    time.sleep(10)

# ==========================================
# MAIN LOGIC
# ==========================================

def recovery():

    play_alert()

    available = scan_wifi()

    log(f"Available networks: {available}")

    # ======================================
    # PRIORITY 1 -> HOMEWIFI
    # ======================================

    if PRIMARY_WIFI["ssid"] in available:

        log("Primary Wi-Fi found")

        if connect_wifi(
            PRIMARY_WIFI["ssid"],
            PRIMARY_WIFI["password"]
        ):
            return True

    # ======================================
    # PRIORITY 2 -> BACKUP WIFI
    # ======================================

    if BACKUP_WIFI["ssid"] in available:

        log("Backup Wi-Fi found")

        if connect_wifi(
            BACKUP_WIFI["ssid"],
            BACKUP_WIFI["password"]
        ):
            return True

    # ======================================
    # HARD RECOVERY
    # ======================================

    restart_networkmanager()

    if PRIMARY_WIFI["ssid"] in scan_wifi():

        if connect_wifi(
            PRIMARY_WIFI["ssid"],
            PRIMARY_WIFI["password"]
        ):
            return True

    if BACKUP_WIFI["ssid"] in scan_wifi():

        if connect_wifi(
            BACKUP_WIFI["ssid"],
            BACKUP_WIFI["password"]
        ):
            return True

    reset_wifi_radio()

    return False

# ==========================================
# WATCHDOG LOOP
# ==========================================

log("Wi-Fi Watchdog Started")

failed = 0

while True:

    # ======================================
    # INTERNET OK
    # ======================================

    if internet_alive():

        failed = 0

        available = scan_wifi()

        # ==================================
        # AUTO RETURN TO HOMEWIFI
        # ==================================

        current = run(
            "nmcli -t -f active,ssid dev wifi | egrep '^yes' | cut -d: -f2"
        )

        if (
            current == BACKUP_WIFI["ssid"]
            and PRIMARY_WIFI["ssid"] in available
        ):

            log("Primary Wi-Fi came back")

            connect_wifi(
                PRIMARY_WIFI["ssid"],
                PRIMARY_WIFI["password"]
            )

    # ======================================
    # INTERNET FAILED
    # ======================================

    else:

        failed += 1

        log(f"Internet failed ({failed})")

        if failed >= MAX_FAILED_PINGS:

            success = recovery()

            if success:
                failed = 0
                log("Recovery successful")

            else:
                log("Recovery failed")
                play_alert()

    time.sleep(CHECK_INTERVAL)
