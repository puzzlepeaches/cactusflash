# CactusFlash

Flash tool for CactusCon 14 badges. Pushes a modded `main.py` over USB-serial that:

- Maxes all 15 creature stats (level 99, 255 HP, 99 across the board)
- Unlocks all achievements including the 3 character-gated ones
- Adds all creatures to the player pack
- Sets player level/XP and win streaks to max
- Changes the main menu subtitle to "hacked by ed"

## Requirements

- Python 3.9+
- [uv](https://docs.astral.sh/uv/) (dependencies are declared inline via PEP 723)
- A CactusCon 14 badge connected via USB (CH340 serial chip)

## Usage

```
uv run cactusflash.py
```

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

2. **`_patch_menu()`** -- Monkey-patches `MainMenuPanel.create_ui` so that after the original method creates the UI, the subtitle label text is replaced with "hacked by ed".
