# micropython
"""
CactusCon14 Badge - Main Entry Point (Modded)

Patches all 15 characters to max stats, max level/XP,
unlocks all achievement-gated characters, and adds all to player pack.
"""

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

ALL_ACHS = [
    'first_battle', 'clean_care', 'collector',
    'win_streak_3', 'loss_streak_3',
    'tough_love', 'sweet_tooth', 'temper_max',
    'focus', 'rage', 'work_play',
    'sao_unlock_hackachu', 'sao_unlock_enigmox', 'sao_unlock_glyphbat',
]

NVS_NAMESPACES = ['cactuscon', 'write']


def _patch_stats():
    log = open('/patch.log', 'w')

    # 1) Max in-memory base_stats
    try:
        from cactuscon.game.engine import characters
        reg = characters.get_character_registry()
        chars = reg.all()
        log.write('found {} chars\n'.format(len(chars)))
        for c in chars:
            c.base_stats.level = 99
            c.base_stats.hp = 255
            c.base_stats.max_hp = 255
            c.base_stats.attack = 99
            c.base_stats.defense = 99
            c.base_stats.sp_attack = 99
            c.base_stats.sp_defense = 99
            c.base_stats.speed = 99
        log.write('stats ok\n')
    except Exception as e:
        log.write('stats err: {}\n'.format(e))

    # 2-4) Write to both NVS namespaces so game finds values
    # regardless of which namespace it reads from
    from cactuscon.prefs import prefs, make_key
    for ns in NVS_NAMESPACES:
        try:
            prefs.begin(ns, True, context="patch_" + ns)
            try:
                # Creature level/XP
                for cid in ALL_CIDS:
                    prefs.set_int32(make_key("cl", cid), 99)
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

                # Pack
                prefs.set_string(make_key("pc", "chars"), ",".join(ALL_CIDS))
            finally:
                prefs.end()
            log.write(ns + ' ok\n')
        except Exception as e:
            log.write(ns + ' err: {}\n'.format(e))

    log.close()


def _patch_menu():
    from cactuscon.ui.panels.main_menu import MainMenuPanel
    _orig_create_ui = MainMenuPanel.create_ui

    def _patched_create_ui(self):
        _orig_create_ui(self)
        sub = self.ui_elements.get('subtitle')
        if sub:
            sub.set_text('hacked by ed')

    MainMenuPanel.create_ui = _patched_create_ui


def main():
    app = BadgeApplication()
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
