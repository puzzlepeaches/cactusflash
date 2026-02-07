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


class HacksPanel:
    _app_ref = None

    def __init__(self, screen, game_ui, battle_manager, logger_level=None, memory_efficient=False):
        from cactuscon.utils import Logger
        self.logger = Logger(logger_level)
        self.tft = screen
        self.display = screen.display if screen else None
        self.game_ui = game_ui
        self.battle_manager = battle_manager
        self.memory_efficient = memory_efficient
        self.screen = None
        self.ui_elements = {}
        self.loaded = False
        self.visible = False
        self._rainbow_on = False
        self._auto_battle_on = False
        self._hue = 0
        self._color_timer = None
        self._rainbow_lbl = None
        self._auto_lbl = None

    def load(self):
        import lvgl as lv
        if self.loaded:
            return
        self.screen = lv.obj()
        self.create_ui()
        self.loaded = True

    def create_ui(self):
        import lvgl as lv
        scr = self.screen
        scr.set_style_bg_color(lv.color_black(), 0)
        scr.set_style_pad_all(0, 0)
        scr.remove_flag(lv.obj.FLAG.SCROLLABLE)

        # Title with rainbow color cycling
        title = lv.label(scr)
        title.set_text('Hacks')
        title.set_style_text_color(lv.color_hex(0x00FF00), 0)
        title.align(lv.ALIGN.TOP_MID, 0, 10)
        self.ui_elements['title'] = title

        self._hue = 0
        def _cycle_color(timer):
            self._hue = (self._hue + 5) % 360
            c = lv.color_hsv_to_rgb(self._hue, 100, 100)
            title.set_style_text_color(c, 0)
        self._color_timer = lv.timer_create(_cycle_color, 50, None)

        # Back button
        btn_back = lv.button(scr)
        btn_back.set_size(60, 30)
        btn_back.align(lv.ALIGN.TOP_RIGHT, -5, 5)
        btn_back.set_style_bg_color(lv.color_hex(0x1A1A1A), 0)
        btn_back.set_style_bg_color(lv.color_hex(0x2A2A2A), lv.STATE.PRESSED)
        btn_back.set_style_border_color(lv.color_hex(0x00FF00), 0)
        btn_back.set_style_border_width(2, 0)
        btn_back.set_style_radius(8, 0)
        lbl_back = lv.label(btn_back)
        lbl_back.set_text('Back')
        lbl_back.set_style_text_color(lv.color_hex(0x00FF00), 0)
        lbl_back.center()
        btn_back.add_event_cb(self._on_back, lv.EVENT.CLICKED, None)

        # Rainbow toggle
        btn_rainbow = lv.button(scr)
        btn_rainbow.set_size(200, 35)
        btn_rainbow.align(lv.ALIGN.TOP_MID, 0, 65)
        btn_rainbow.set_style_bg_color(lv.color_hex(0x1A1A1A), 0)
        btn_rainbow.set_style_bg_color(lv.color_hex(0x2A2A2A), lv.STATE.PRESSED)
        btn_rainbow.set_style_border_color(lv.color_hex(0x00FF00), 0)
        btn_rainbow.set_style_border_width(2, 0)
        btn_rainbow.set_style_radius(8, 0)
        self._rainbow_lbl = lv.label(btn_rainbow)
        self._rainbow_lbl.set_text('Rainbow: OFF')
        self._rainbow_lbl.set_style_text_color(lv.color_hex(0x00FF00), 0)
        self._rainbow_lbl.center()
        btn_rainbow.add_event_cb(self._on_rainbow, lv.EVENT.CLICKED, None)

        # Auto-Battle toggle
        btn_auto = lv.button(scr)
        btn_auto.set_size(200, 35)
        btn_auto.align(lv.ALIGN.TOP_MID, 0, 115)
        btn_auto.set_style_bg_color(lv.color_hex(0x1A1A1A), 0)
        btn_auto.set_style_bg_color(lv.color_hex(0x2A2A2A), lv.STATE.PRESSED)
        btn_auto.set_style_border_color(lv.color_hex(0x00FF00), 0)
        btn_auto.set_style_border_width(2, 0)
        btn_auto.set_style_radius(8, 0)
        self._auto_lbl = lv.label(btn_auto)
        self._auto_lbl.set_text('Auto-Battle: OFF')
        self._auto_lbl.set_style_text_color(lv.color_hex(0x00FF00), 0)
        self._auto_lbl.center()
        btn_auto.add_event_cb(self._on_auto_battle, lv.EVENT.CLICKED, None)

    def _on_back(self, event):
        self.game_ui.show_panel('main_menu')

    def _on_rainbow(self, event):
        self._rainbow_on = not self._rainbow_on
        pixels = getattr(self.game_ui, 'pixels', None)
        if pixels:
            if self._rainbow_on:
                pixels.start_rainbow()
                self._rainbow_lbl.set_text('Rainbow: ON')
            else:
                pixels.off()
                self._rainbow_lbl.set_text('Rainbow: OFF')

    def _on_auto_battle(self, event):
        self._auto_battle_on = not self._auto_battle_on
        app = HacksPanel._app_ref
        if app:
            app.auto_test_enabled = self._auto_battle_on
        if self._auto_battle_on:
            self._auto_lbl.set_text('Auto-Battle: ON')
        else:
            self._auto_lbl.set_text('Auto-Battle: OFF')

    def show(self):
        import lvgl as lv
        if self.screen:
            lv.screen_load(self.screen)
            self.visible = True

    def on_show(self):
        pass

    def on_hide(self):
        if self._color_timer:
            self._color_timer.delete()
            self._color_timer = None
        self.visible = False

    def on_cleanup(self):
        self.on_hide()

    def unload(self):
        self.on_hide()
        if self.screen:
            self.screen.delete()
            self.screen = None
        self.loaded = False


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

                # Pack (final-form only so evolving doesn't reset level)
                prefs.set_string(make_key("pc", "chars"), ",".join(FINAL_CIDS))
            finally:
                prefs.end()
            log.write(ns + ' ok\n')
        except Exception as e:
            log.write(ns + ' err: {}\n'.format(e))

    log.close()


def _patch_menu():
    import lvgl as lv
    from cactuscon.ui.panels.main_menu import MainMenuPanel
    _orig_create_ui = MainMenuPanel.create_ui

    def _patched_create_ui(self):
        _orig_create_ui(self)
        sub = self.ui_elements.get('subtitle')
        if sub:
            sub.set_text('hacked by ed')

        # Reposition Extras button to the left
        btn_extras = self.ui_elements.get('btn_extras')
        if btn_extras:
            btn_extras.align(lv.ALIGN.TOP_MID, -75, 165)

        # Add Hacks button on the right
        btn_hacks = self._create_menu_button('Hacks', 75, 165)
        btn_hacks.add_event_cb(self._on_hacks_clicked, lv.EVENT.CLICKED, None)
        self.ui_elements['btn_hacks'] = btn_hacks

    def _on_hacks_clicked(self, event):
        if 'hacks' not in self.game_ui.panel_classes:
            self.game_ui.register_panel('hacks', HacksPanel)
        self.game_ui.show_panel('hacks')

    MainMenuPanel.create_ui = _patched_create_ui
    MainMenuPanel._on_hacks_clicked = _on_hacks_clicked


def main():
    app = BadgeApplication()
    HacksPanel._app_ref = app
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
