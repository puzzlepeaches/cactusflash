#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyserial"]
# ///
"""
Flash a CactusCon 14 badge with max stats.

Auto-detects any plugged-in badge (CH340 USB-serial), pushes modded main.py,
reboots, and verifies the patch applied.

Usage:
    uv run tools/flash_badge.py
"""

import argparse
import base64
import sys
import termios
import time

import serial
import serial.tools.list_ports

BAUD = 115200
CH340_VID_PID = (0x1A86, 0x7523)
DST = "/main.py"
CHUNK_SIZE = 256

MAIN_PY = """\
# micropython
\"\"\"
CactusCon14 Badge - Main Entry Point (Modded)

Patches all 15 characters to max stats, max level/XP,
unlocks all achievement-gated characters, and adds all to player pack.
\"\"\"

from cactuscon.utils import mem_info, Logger

import asyncio
from cactuscon.application import BadgeApplication
from config import BadgeConfig

config = BadgeConfig()
logger = Logger(config.LOG_LEVEL)

ALL_CIDS = [
    'hacktarchu', 'hackachu', 'hackachimon',
    'voltiny', 'voltqueen', 'voltreign',
    'cinderlet', 'cinderserp', 'cindervipe',
    'blipbat', 'glyphbat', 'runewing',
    'cipherkit', 'enigmox', 'cryptilox',
]

FINAL_CIDS = [
    'hackachimon', 'voltreign', 'cindervipe', 'runewing', 'cryptilox',
]

ALL_ACHS = [
    'first_battle', 'clean_care', 'collector',
    'win_streak_3', 'loss_streak_3',
    'tough_love', 'sweet_tooth', 'temper_max',
    'focus', 'rage', 'work_play',
    'sao_unlock_hackachu', 'sao_unlock_enigmox', 'sao_unlock_glyphbat',
]

NVS_NAMESPACES = ['cactuscon', 'write']

ENABLE_RAINBOW = False
ENABLE_AUTO_BATTLE = False
ENABLE_MAX_STATS = False


def _patch_stats():
    log = open('/patch.log', 'w')

    # 1) Patch in-memory base_stats
    try:
        from cactuscon.game.engine import characters
        reg = characters.get_character_registry()
        chars = reg.all()
        log.write('found {} chars\\n'.format(len(chars)))
        for c in chars:
            c.base_stats.level = 255
            if ENABLE_MAX_STATS:
                c.base_stats.hp = 255
                c.base_stats.max_hp = 255
                c.base_stats.attack = 99
                c.base_stats.defense = 99
                c.base_stats.sp_attack = 99
                c.base_stats.sp_defense = 99
                c.base_stats.speed = 99
        log.write('stats ok\\n')
    except Exception as e:
        log.write('stats err: {}\\n'.format(e))

    # 2-4) Write to both NVS namespaces so game finds values
    # regardless of which namespace it reads from
    from cactuscon.prefs import prefs, make_key
    for ns in NVS_NAMESPACES:
        try:
            prefs.begin(ns, True, context="patch_" + ns)
            try:
                # Creature level/XP
                for cid in ALL_CIDS:
                    prefs.set_int32(make_key("cl", cid), 255)
                    prefs.set_int32(make_key("cx", cid), 999999)

                # Player stats
                prefs.set_int32(make_key("pl", "xp"), 999999)
                prefs.set_int32(make_key("pl", "lvl"), 99)
                prefs.set_int32(make_key("pl", "win"), 999)
                prefs.set_int32(make_key("pl", "loss"), 0)

                # Station battle stats
                prefs.set_int32(make_key("st", "win"), 999)
                prefs.set_int32(make_key("st", "loss"), 0)
                prefs.set_int32(make_key("st", "ch"), 999)

                # Streaks
                prefs.set_int32("ws", 99)
                prefs.set_int32("ls", 0)
                prefs.set_int32("ccs", 99)

                # All achievements
                prefs.set_string("ach", ",".join(ALL_ACHS))

                # Pack (final-form only so evolving doesn't reset level)
                prefs.set_string(make_key("pc", "chars"), ",".join(FINAL_CIDS))
            finally:
                prefs.end()
            log.write(ns + ' ok\\n')
        except Exception as e:
            log.write(ns + ' err: {}\\n'.format(e))

    log.close()


def _patch_menu():
    from cactuscon.ui.graphics import GameUI
    _orig_set_pixels = GameUI.set_pixels_controller
    def _patched_set_pixels(self, pc):
        _orig_set_pixels(self, pc)
        if ENABLE_RAINBOW:
            pc.start_rainbow()
    GameUI.set_pixels_controller = _patched_set_pixels

    from cactuscon.ui.panels.main_menu import MainMenuPanel
    _orig_create_ui = MainMenuPanel.create_ui
    def _patched_create_ui(self):
        _orig_create_ui(self)
        sub = self.ui_elements.get('subtitle')
        if sub:
            sub.set_text('hacked by ed')
    MainMenuPanel.create_ui = _patched_create_ui

    from cactuscon.ui.panels.character import CharacterPanel
    _orig_apply = CharacterPanel._apply_character_data
    def _patched_apply(self):
        _orig_apply(self)
        xp_label = self.ui_elements.get('xp_label')
        if xp_label:
            xp_label.set_text('HACKED by ED 6/7')
    CharacterPanel._apply_character_data = _patched_apply


def main():
    app = BadgeApplication()
    if ENABLE_AUTO_BATTLE:
        app.auto_test_enabled = True
    _patch_stats()
    _patch_menu()

    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        app.cleanup()


if __name__ == "__main__":
    main()
"""


def find_badge_port():
    """Auto-detect a CactusCon badge by CH340 VID:PID."""
    ports = serial.tools.list_ports.comports()
    matches = [p for p in ports if (p.vid, p.pid) == CH340_VID_PID]
    if not matches:
        return None
    if len(matches) > 1:
        print(f"Found {len(matches)} CH340 devices:")
        for i, p in enumerate(matches):
            print(f"  [{i}] {p.device}  {p.description}")
        choice = input("Select port number: ").strip()
        return matches[int(choice)].device
    return matches[0].device


def wait_for(ser, marker, timeout=5):
    buf = b""
    end = time.time() + timeout
    while time.time() < end:
        if ser.in_waiting:
            buf += ser.read(ser.in_waiting)
            if marker in buf:
                return buf
        time.sleep(0.05)
    return buf


def interrupt_and_enter_repl(ser, retries=3):
    """Stop running app and enter raw REPL, with retries."""
    for attempt in range(retries):
        print(f"Interrupting badge app (attempt {attempt + 1})...")
        for _ in range(5):
            ser.write(b"\x03")
            time.sleep(0.1)
        time.sleep(0.5)
        ser.read(ser.in_waiting)

        print("Entering raw REPL...")
        ser.write(b"\x01")
        time.sleep(0.3)
        resp = wait_for(ser, b"raw REPL", timeout=3)
        if b"raw REPL" in resp:
            return True
        print("Didn't get raw REPL prompt, retrying...")
        time.sleep(1)

    print("WARNING: could not confirm raw REPL entry. Continuing anyway...")
    return True


def push_file(ser, data, dest):
    """Transfer file contents to badge via base64 over raw REPL."""
    b64 = base64.b64encode(data).decode("ascii")
    print(f"Pushing {len(data)} bytes ({len(b64)} b64 chars) -> {dest}")

    lines = ["import ubinascii", f"f = open('{dest}', 'wb')"]
    for i in range(0, len(b64), CHUNK_SIZE):
        lines.append(f"f.write(ubinascii.a2b_base64('{b64[i:i+CHUNK_SIZE]}'))")
    lines.append("f.close()")
    lines.append(f"print('OK wrote {dest}')")

    script = "\r\n".join(lines) + "\r\n"
    script_bytes = script.encode("utf-8")
    for i in range(0, len(script_bytes), 128):
        ser.write(script_bytes[i:i + 128])
        time.sleep(0.02)

    ser.write(b"\x04")
    time.sleep(1)
    resp = wait_for(ser, b"OK wrote", timeout=10)

    if b"OK wrote" in resp:
        print("Transfer OK.")
        return True
    print("WARNING: no confirmation received.")
    print(resp.decode("utf-8", errors="replace")[-300:])
    return False


def verify_patch(ser):
    """Reboot, wait for patch to run, then read back values."""
    # Exit raw REPL and soft reboot
    ser.write(b"\x02")
    time.sleep(0.2)
    ser.write(b"\x04")
    print("Rebooting badge... waiting 12s for patch to run...")
    time.sleep(12)

    # Re-interrupt and enter REPL
    interrupt_and_enter_repl(ser)

    # Read patch.log
    ser.read(ser.in_waiting)
    script = "\r\n".join([
        "try:",
        "    f = open('/patch.log', 'r')",
        "    d = f.read()",
        "    f.close()",
        "    print('PATCHLOG:' + d)",
        "except Exception as e:",
        "    print('PATCHLOG_ERR:' + str(e))",
    ]) + "\r\n"
    ser.write(script.encode("utf-8"))
    time.sleep(0.1)
    ser.write(b"\x04")
    time.sleep(1)
    resp = wait_for(ser, b">", timeout=5)
    text = resp.decode("utf-8", errors="replace")

    ok = True
    if "PATCHLOG:" in text:
        log_content = text.split("PATCHLOG:")[1].split(">")[0].strip()
        print(f"\n/patch.log:\n{log_content}")
        if "err" in log_content.lower():
            print("ERRORS detected in patch log!")
            ok = False
    else:
        print("Could not read patch.log")
        ok = False

    # Spot-check a few NVS values
    ser.read(ser.in_waiting)
    script = "\r\n".join([
        "from cactuscon.prefs import prefs, make_key",
        "prefs.begin('write', False, context='v')",
        "a = prefs.get_string('ach', '')",
        "pl = prefs.get_int32(make_key('pl', 'lvl'), -1)",
        "sw = prefs.get_int32(make_key('st', 'win'), -1)",
        "ws = prefs.get_int32('ws', -1)",
        "prefs.end()",
        "print('ACH_CT:' + str(len(a.split(','))))",
        "print('PL_LVL:' + str(pl))",
        "print('ST_WIN:' + str(sw))",
        "print('WS:' + str(ws))",
        "print('VDONE')",
    ]) + "\r\n"
    ser.write(script.encode("utf-8"))
    time.sleep(0.1)
    ser.write(b"\x04")
    time.sleep(1)
    resp = wait_for(ser, b"VDONE", timeout=5)
    text = resp.decode("utf-8", errors="replace")

    checks = {
        "ACH_CT": ("14", "achievements"),
        "PL_LVL": ("99", "player level"),
        "ST_WIN": ("999", "station wins"),
        "WS": ("99", "win streak"),
    }
    for key, (expected, label) in checks.items():
        if f"{key}:{expected}" in text:
            print(f"  {label}: {expected} OK")
        else:
            print(f"  {label}: MISMATCH (expected {expected})")
            ok = False

    return ok


def main():
    parser = argparse.ArgumentParser(description="Flash a CactusCon 14 badge with max stats")
    parser.add_argument("--rainbow", action="store_true", help="Enable rainbow LEDs on boot")
    parser.add_argument("--auto-battle", action="store_true", help="Enable auto-battle on boot")
    parser.add_argument("--max-stats", action="store_true",
        help="Max all combat stats to 99 (breaks PvP consensus)")
    args = parser.parse_args()

    port = find_badge_port()
    if not port:
        print("No CactusCon badge found. Is it plugged in?")
        sys.exit(1)

    print(f"Found badge on {port}")
    try:
        ser = serial.Serial(port, BAUD, timeout=1)
    except (termios.error, serial.SerialException):
        # CH340 sometimes rejects initial config; open without settings then apply
        ser = serial.Serial()
        ser.port = port
        ser.baudrate = BAUD
        ser.timeout = 1
        ser.dtr = False
        ser.rts = False
        ser.open()
    time.sleep(0.2)

    interrupt_and_enter_repl(ser)

    main_py = MAIN_PY
    if args.rainbow:
        main_py = main_py.replace("ENABLE_RAINBOW = False", "ENABLE_RAINBOW = True", 1)
    if args.auto_battle:
        main_py = main_py.replace("ENABLE_AUTO_BATTLE = False", "ENABLE_AUTO_BATTLE = True", 1)
    if args.max_stats:
        print("WARNING: --max-stats sets all combat stats to 99. This WILL break PvP")
        print("battles (consensus hash mismatch -> battle voided). Only useful for")
        print("auto-battle grinding or showing off on the character screen.")
        confirm = input("Continue? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            ser.close()
            sys.exit(0)
        main_py = main_py.replace("ENABLE_MAX_STATS = False", "ENABLE_MAX_STATS = True", 1)
    file_data = main_py.encode("utf-8")
    if not push_file(ser, file_data, DST):
        ser.close()
        sys.exit(1)

    if verify_patch(ser):
        print("\nAll checks passed. Badge is maxed out.")
    else:
        print("\nSome checks failed. Inspect badge manually.")

    # Final reboot into normal operation
    ser.write(b"\x02")
    time.sleep(0.2)
    ser.write(b"\x04")
    ser.close()
    print("Badge rebooting into normal operation.")


if __name__ == "__main__":
    main()
