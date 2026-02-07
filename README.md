# CactusFlash

NO WARRANTY - IF IT FAILS, TRY TO FLASH AGAIN. IF THAT DOESN'T WORK, SORRY

Apologies to those of you that grinded all day. 

Flash tool for CactusCon 14 badges. Pushes a modded `main.py` over USB-serial that:

- Sets all 15 creatures to level 255 (7.375x damage multiplier, PvP-safe)
- Unlocks all achievements including the 3 character-gated ones
- Adds all creatures to the player pack
- Sets player level/XP and win streaks to max

## Requirements

- [uv](https://docs.astral.sh/uv/) (dependencies are declared inline via PEP 723, no manual install needed)
- A CactusCon 14 badge connected via USB (CH340 serial chip)

## Platform

Developed and tested on macOS. Not tested on Linux or Windows.

## Usage

With no flags, the badge gets max stats and reboots normally:

```
uv run cactusflash.py
```

Optional flags enable extra features that get baked into the firmware at flash time:

```
uv run cactusflash.py --rainbow
uv run cactusflash.py --auto-battle
uv run cactusflash.py --rainbow --auto-battle
uv run cactusflash.py --max-stats
```

- `--rainbow` -- Badge LEDs cycle through rainbow colors continuously from boot. Purely cosmetic.
- `--auto-battle` -- Badge automatically enters and plays battles without user input. Useful for farming wins/XP unattended.
- `--max-stats` -- Set all combat stats to 99 (attack, defense, HP, etc). **Breaks PvP battles** -- the badge consensus protocol requires both badges to compute identical turn outcomes, and modified combat stats cause hash mismatches that void the battle. Use this only for auto-battle grinding or showing off stats on the character screen.

The script will:

1. Auto-detect the badge by CH340 VID:PID
2. Interrupt the running app and enter raw REPL
3. Transfer the modded `main.py` to the badge via base64 encoding
4. Reboot and verify the patch applied (checks NVS values)
5. Reboot into normal operation

## Files

- `cactusflash.py` -- Host-side script that handles serial communication and file transfer
- `modded_firmware/main.py` -- The modded MicroPython entry point that runs on the badge

## How it works

The badge runs MicroPython with a compiled application in `.mpy` bytecode files. The `main.py` file on the FFAT root is plain Python and runs at boot, so it can be replaced freely.

The modded `main.py` patches the game in two ways:

1. **`_patch_stats()`** -- Writes maxed creature levels/XP, player stats, achievements, and pack data directly to NVS (non-volatile storage) in both the `"cactuscon"` and `"write"` namespaces so values persist regardless of game state.

2. **`_patch_menu()`** -- Monkey-patches `GameUI.set_pixels_controller` to optionally start rainbow LEDs after the pixels controller is initialized.

## Tools

### mpy_disasm.py

Disassemble `.mpy` (MicroPython bytecode) files from the badge firmware dump. Wraps the official MicroPython `mpy-tool.py` with a friendlier CLI.

```
uv run tools/mpy_disasm.py dump/config.mpy
uv run tools/mpy_disasm.py hexdump dump/config.mpy
uv run tools/mpy_disasm.py batch dump/
uv run tools/mpy_disasm.py batch dump/ -o analysis/disassembly
```

Run `uv run tools/mpy_disasm.py --help` for full usage.
