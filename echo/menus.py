"""Title, help, forge, upgrade, end and pause screens."""

import math
import random

import pygame

from . import story
from .base import Screen
from .cinematics import big, blit_center, draw_fraying_thread, draw_town
from .consts import BASE_THREADS, GHOST_COLORS, MAX_FLOOR, PERKS, THREADS_PER_FLOOR, UPGRADES
from .score import GRADE_COLORS
from .theme import (GOLD, TORCH, Particles, add_glow, draw_echo, draw_glow_text, draw_heart,
                    draw_hourglass, draw_lamplighter, draw_panel, draw_rule, draw_sconce, ease_out, echo_sprite,
                    flicker, scale_color, text_surface, vertical_gradient)
from .widgets import ACCENT, BAD, DIM, ECHO, GOOD, TEXT, WARN, draw_text, draw_wrapped, tint, wrap_text

CX = 480
W, H = 960, 660
STONE_BTN = (54, 46, 50)
DANGER_BTN = (110, 44, 44)


def _center_button_rect(y, w=300, h=44):
    return (CX - w // 2, y, w, h)


def draw_backdrop(surf, t, glow_y=150):
    """Dark stone with two sconces burning either side of the title."""
    surf.blit(vertical_gradient((W, H), (20, 15, 22), (8, 6, 10)), (0, 0))
    for i, x in enumerate((170, W - 170)):
        add_glow(surf, (x, glow_y), int(190 * flicker(t, i, 0.05)), (110, 60, 24))
        img = big(lambda s, cx, cy, i=i: draw_sconce(s, cx, cy - 2, True, t, i), 20, 4)
        blit_center(surf, img, (x, glow_y + 16))


class _Embers:
    def __init__(self):
        self.p = Particles(240)
        self.rng = random.Random(9)

    def update(self, dt, sources):
        for x, y in sources:
            if self.rng.random() < dt * 10:
                self.p.emit(x + self.rng.uniform(-6, 6), y, TORCH, n=1, speed=14, life=2.2, size=1,
                            gravity=-16, angle=-math.pi / 2, spread=0.9, rng=self.rng)
        self.p.update(dt)


class TitleScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.t = 0.0
        self.embers = _Embers()
        self.add(_center_button_rect(226), "New Run  (N)", app.start_new_run, tag="new",
                 key=(pygame.K_n, pygame.K_RETURN, pygame.K_KP_ENTER))
        self.add(_center_button_rect(278), "The Story  (S)", app.show_story, tag="story", key=pygame.K_s)
        self.add(_center_button_rect(330), "Echo Forge  (F)", app.show_forge, tag="forge", key=pygame.K_f)
        self.add(_center_button_rect(382), "How to Play  (H)", app.show_help, tag="help", key=pygame.K_h)
        self.add(_center_button_rect(434), "Quit  (Esc)", app.quit, tag="quit", key=pygame.K_ESCAPE)

    def update(self, dt):
        self.t += dt
        self.embers.update(dt, [(170, 158), (W - 170, 158)])
        return True

    def draw(self, surf):
        t = self.t
        draw_backdrop(surf, t)
        self.embers.p.draw(surf)
        draw_glow_text(surf, self.app.bold[80], "ECHO DELVE", (CX, 100), ACCENT, (150, 80, 20))
        draw_rule(surf, CX, 148, 340)
        draw_text(surf, self.app.italic[26], story.TAGLINE, (CX, 178), DIM, center=True)
        d = self.app.meta.data
        draw_text(surf, self.app.fonts[22], "Runs %d   Wins %d   Best floor %d/%d   Best score %s   Shards %d" %
                  (d["runs"], d["wins"], d["best_floor"], MAX_FLOOR, "{:,}".format(d.get("best_score", 0)), d["shards"]),
                  (CX, 508), DIM, center=True)
        self._draw_procession(surf, t)
        self.draw_buttons(surf)

    def _draw_procession(self, surf, t):
        """Aurel walks through the dark; his echoes follow in his footsteps, fainter each loop."""
        y = 590
        pygame.draw.line(surf, (40, 32, 36), (0, y + 13), (W, y + 13), 1)
        lead = (t * 38 + 560) % (W + 400) - 100
        for i in range(5, 0, -1):
            x = lead - i * 46
            if -30 < x < W + 30:
                draw_echo(surf, x, y, t, GHOST_COLORS[(i - 1) % len(GHOST_COLORS)], i, alpha=int(230 - i * 34))
        if -30 < lead < W + 30:
            add_glow(surf, (int(lead + 8), y - 2), int(70 * flicker(t, 3, 0.08)), (110, 80, 34))
            draw_lamplighter(surf, lead, y, t)


HELP_SECTIONS = [
    ("Goal", "Reach the gold stairs on each of %d floors. Numbered doors seal the way. Door N is open only "
             "while something stands on plate N (same colour and number)." % MAX_FLOOR),
    ("Echoes", "Every loop you end becomes an echo that replays your exact moves in later loops, starting from "
               "the knot at the entrance. Send loop 1 to a plate and anchor there; from loop 2 on, your echo "
               "holds the plate while you walk through the door."),
    ("Ending a loop", "Anchor (E, twice) leaves your echo standing where you are. If the turns run out you "
                      "are anchored automatically. If you die, your echo replays the loop and fades where you fell. "
                      "Each echo takes one of your echo slots (top right)."),
    ("Levers & gates", "Some ways are barred by a lettered gate. Walk into lever A to pull it: gate A flips "
                       "open (or shut, if pulled again) for the rest of the loop. Echoes pull levers on the turn "
                       "you did. Levers sit too far from their gates to pull one and still make the stairs: send "
                       "an echo, and unravel it if it pulled too late. Hover a gate to see who pulls it, and when."),
    ("Unravel (U)", "Erase any echo to free its slot; your next loop is recorded in its place. It costs one "
                    "thread. You start with %d and earn %d per floor. If your last loop ends short of the stairs "
                    "with every slot full you must unravel; with no threads left, the run ends."
     % (BASE_THREADS, THREADS_PER_FLOOR)),
    ("Score", "Every turn on a floor counts, in every loop (unravelled ones too). Par is the fewest turns for "
              "what you did. Grades run S+ (par or better) to D; S and S+ earn bonus shards."),
    ("Sconces", "Walk within two steps of a sconce to light it: it stays lit every loop and shows what moves near "
                "it. Each one raises your par by what it costs to reach, and adds to the score, so lighting every "
                "sconce on a floor at par is the best score there is."),
    ("Echoes are literal", "They repeat keystrokes, not intentions: if an enemy has moved, an echo may swing "
                           "at air. Enemies attack echoes too, and reset every loop."),
    ("Dangers", "Crawlers chase. Archers shoot along rows and columns. Brutes hit hard every other turn (a ! "
                "marks the turn they act). Spikes are up 2 turns, down 2. Wardens guard the last stairs."),
    ("Controls", "Arrows / WASD move or strike. Space waits. E anchors, U unravels, Tab shows echo paths. Click "
                 "a tile beside you to step; right-click to inspect. H help, Esc menu. Bumps cost no turn."),
]
HELP_TEXT = "\n".join("%s: %s" % s for s in HELP_SECTIONS)


class HelpScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.add((150, 596, 200, 42), "Back  (Esc)", app.pop, tag="back",          # (under the shorter column)
                 key=(pygame.K_ESCAPE, pygame.K_h, pygame.K_RETURN, pygame.K_SPACE))

    def draw(self, surf):
        surf.blit(vertical_gradient((W, H), (22, 17, 24), (10, 8, 12)), (0, 0))
        draw_glow_text(surf, self.app.bold[44], "How to Play", (CX, 34), ACCENT, (140, 80, 30))
        draw_rule(surf, CX, 62, 300)
        head, body = self.app.bold[22], self.app.fonts[18]
        col_w, gap = 420, 40
        x0 = (W - 2 * col_w - gap) // 2
        cols = [HELP_SECTIONS[:4], HELP_SECTIONS[4:]]
        for c, sections in enumerate(cols):
            x, y = x0 + c * (col_w + gap), 80
            for title, text in sections:
                draw_text(surf, head, title, (x, y), ACCENT)
                y += head.get_linesize() + 2
                y = draw_wrapped(surf, body, text, (x, y), col_w, TEXT, spacing=4) + 14
        self.draw_buttons(surf)


class ForgeScreen(Screen):
    ORDER = ["hp", "slots", "time", "atk"]

    def __init__(self, app):
        super().__init__(app)
        self.meta = app.meta
        self.t = 0.0
        for i, key in enumerate(self.ORDER):
            self.add((690, 142 + i * 92, 200, 42), "", lambda k=key: self.buy(k), tag="buy:" + key,
                     key=pygame.K_1 + i)
        self.add((CX - 100, 596, 200, 42), "Back  (Esc)", app.to_title, tag="back", key=pygame.K_ESCAPE)
        self.refresh()
        self.say("Spend shards on permanent perks. You earn them by clearing floors, and with S grades.")

    def refresh(self):
        for key in self.ORDER:
            b = self.btn("buy:" + key)
            lvl, mx = self.meta.level(key), PERKS[key][2]
            b.label = "Maxed" if lvl >= mx else "Buy  (%d shards)" % self.meta.cost(key)
            b.color = (74, 58, 44) if self.meta.can_buy(key) else (40, 34, 38)

    def buy(self, key):
        name, _, mx, _ = PERKS[key]
        if self.meta.level(key) >= mx:
            self.say("%s is already maxed." % name, WARN)
        elif not self.meta.can_buy(key):
            self.say("%s costs %d shards; you have %d." % (name, self.meta.cost(key), self.meta.data["shards"]), BAD)
        else:
            self.meta.buy(key)
            self.say("Bought %s (level %d)." % (name, self.meta.level(key)), GOOD)
        self.refresh()

    def update(self, dt):
        self.t += dt
        return True

    def draw(self, surf):
        draw_backdrop(surf, self.t, glow_y=60)
        f = self.app.fonts
        draw_glow_text(surf, self.app.bold[44], "Echo Forge", (CX, 40), ACCENT, (140, 80, 30))
        draw_text(surf, self.app.italic[22], "Shards: %d" % self.meta.data["shards"], (CX, 88), WARN, center=True)
        for i, key in enumerate(self.ORDER):
            name, desc, mx, _ = PERKS[key]
            y = 130 + i * 92
            draw_panel(surf, (70, y, 840, 80), fill=(30, 25, 30))
            draw_text(surf, self.app.bold[26], "%d. %s" % (i + 1, name), (94, y + 14), TEXT)
            draw_text(surf, f[18], desc, (94, y + 48), DIM)
            lvl = self.meta.level(key)
            for p in range(mx):                      # one sconce per level: lit once bought
                x = 460 + p * 44
                if p < lvl:
                    add_glow(surf, (x, y + 34), 34, (110, 60, 24))
                img = big(lambda s, cx, cy, p=p: draw_sconce(s, cx, cy - 2, p < lvl, self.t, p + i), 20, 2)
                blit_center(surf, img, (x, y + 42))
        draw_text(surf, f[22], self.msg, (CX, 560), self.msg_color, center=True)
        self.draw_buttons(surf)


def _upgrade_icon(surf, key, cx, cy, t):
    if key == "hp":
        draw_heart(surf, cx, cy, (230, 80, 70), 12)
    elif key == "atk":
        pygame.draw.line(surf, (210, 214, 226), (cx - 14, cy + 14), (cx + 12, cy - 12), 4)
        pygame.draw.line(surf, GOLD, (cx - 12, cy + 4), (cx - 4, cy + 12), 4)
    elif key == "slot":
        img = pygame.transform.scale(echo_sprite(ECHO), (56, 56))
        blit_center(surf, img, (cx, cy))
    elif key == "time":
        img = big(lambda s, x, y: draw_hourglass(s, x, y, GOLD), 20, 2)
        blit_center(surf, img, (cx, cy))
    elif key == "sight":
        pygame.draw.ellipse(surf, TEXT, (cx - 18, cy - 9, 36, 18), 2)
        pygame.draw.circle(surf, GOLD, (cx, cy), 6)
        pygame.draw.circle(surf, (20, 16, 20), (cx, cy), 3)
    else:
        pts = [(cx - 14, cy - 14), (cx + 14, cy - 14), (cx + 12, cy + 4), (cx, cy + 16), (cx - 12, cy + 4)]
        pygame.draw.polygon(surf, (70, 110, 150), pts)
        pygame.draw.polygon(surf, ECHO, pts, 2)


class UpgradeScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.run = app.run
        self.t = 0.0
        for i, key in enumerate(self.run.options):
            self.add((60 + i * 290, 196, 270, 250), "", lambda k=key: app.choose_upgrade(k),
                     tag="up%d" % i, key=pygame.K_1 + i, color=(40, 34, 40))

    def update(self, dt):
        self.t += dt
        return True

    def draw(self, surf):
        draw_backdrop(surf, self.t, glow_y=54)
        f = self.app.fonts
        r = self.run
        draw_glow_text(surf, self.app.bold[44], "Floor %d cleared" % r.floor_no, (CX, 42), GOOD, (40, 90, 30))
        res = r.last_result
        if res:
            line = "%s   %s points, grade %s" % (story.floor_name(r.floor_no), "{:,}".format(res.score), res.grade)
            draw_text(surf, self.app.italic[22], line, (CX, 86), GRADE_COLORS.get(res.grade, TEXT), center=True)
        gain = ("%s." % r.thread_left_text().capitalize()) if r.thread is not None else \
            "+%d thread (you have %d)." % (THREADS_PER_FLOOR, r.threads)
        draw_text(surf, f[22], "Loops used: %d.  %s  Pick one upgrade (1-3)." % (r.play.loop_no, gain),
                  (CX, 122), TEXT, center=True)
        for i, key in enumerate(r.options):
            b = self.btn("up%d" % i)
            hov = b is self.hover
            rect = b.rect.move(0, -4 if hov else 0)
            draw_panel(surf, rect, fill=(44, 36, 42) if hov else (32, 27, 32), edge=ACCENT if hov else (120, 92, 56))
            name, desc = UPGRADES[key]
            add_glow(surf, (rect.centerx, rect.y + 56), 46, (50, 36, 18))
            _upgrade_icon(surf, key, rect.centerx, rect.y + 56, self.t)
            draw_text(surf, self.app.bold[26], "%d. %s" % (i + 1, name), (rect.centerx, rect.y + 116), TEXT, center=True)
            draw_rule(surf, rect.centerx, rect.y + 140, 160)
            lines = wrap_text(f[22], desc, rect.w - 40)
            for j, ln in enumerate(lines):
                draw_text(surf, f[22], ln, (rect.centerx, rect.y + 162 + j * 22), DIM, center=True)
        thread = ("Thread %s" % r.thread.hm()) if r.thread is not None else "Threads %d" % r.threads
        draw_text(surf, f[22], "Now: HP %d   Attack %d   Echo slots %d   %s   Turns/loop +%d   Sight %d   Echo HP +%d" %
                  (r.max_hp, r.atk, r.slots, thread, r.limit_bonus, r.sight, r.ghost_hp), (CX, 500), DIM, center=True)
        draw_text(surf, self.app.italic[22], "Score so far: %s" % "{:,}".format(r.total_score), (CX, 532), ACCENT, center=True)


class EndScreen(Screen):
    """Won: Hollowmere sees the dawn. Lost: the thread snaps."""

    def __init__(self, app):
        super().__init__(app)
        self.run = app.run
        self.t = 0.0
        self.fx = Particles(300)
        self.add((CX - 150, 486, 300, 42), "New Run  (N)", app.start_new_run, tag="new",
                 key=(pygame.K_n, pygame.K_RETURN, pygame.K_KP_ENTER))
        self.add((CX - 150, 536, 300, 42), "Echo Forge  (F)", app.show_forge, tag="forge", key=pygame.K_f)
        self.add((CX - 150, 586, 300, 42), "Title  (Esc)", app.to_title, tag="title", key=pygame.K_ESCAPE)

    def update(self, dt):
        self.t += dt
        if self.run.state != "won" and 0.2 < self.t < 1.2:
            for _ in range(2):
                self.fx.emit(CX, 204, GOLD, n=1, speed=80, life=1.2, size=1, gravity=30)
        self.fx.update(dt)
        return True

    def draw(self, surf):
        r, t = self.run, self.t
        won = r.state == "won"
        if won:
            dawn = ease_out(t / 5.0)
            draw_town(surf, t, dawn, (0, 0, W, H))
            veil = pygame.Surface((W, H), pygame.SRCALPHA)
            veil.fill((10, 6, 12, 120))
            surf.blit(veil, (0, 0))
            draw_glow_text(surf, self.app.bold[80], story.ENDING_TITLE_WON, (CX, 70), (255, 226, 150), (170, 90, 30))
            y = 118
            for i, para in enumerate(story.ENDING_WON):
                a = 255 * ease_out((t - 0.8 - i * 1.6) / 1.2)
                for ln in wrap_text(self.app.italic[22], para, 760):
                    img = text_surface(self.app.italic[22], ln, TEXT, a)
                    surf.blit(img, img.get_rect(center=(CX, y)))
                    y += 24
                y += 8
        else:
            surf.blit(vertical_gradient((W, H), (16, 12, 18), (6, 5, 8)), (0, 0))
            draw_glow_text(surf, self.app.bold[80], story.ENDING_TITLE_LOST, (CX, 70), BAD, (120, 30, 30))
            k = ease_out(t / 3.0)                     # Aurel fading into an echo
            img = big(lambda s, cx, cy: draw_lamplighter(s, cx, cy + 3, t, tint=(150, 160, 170) if k > 0.5 else None),
                      30, 3)
            blit_center(surf, img, (CX, 148), 255 * (1 - 0.7 * k))
            draw_fraying_thread(surf, t, 204)
            self.fx.draw(surf)
            y = 244
            for ln in wrap_text(self.app.italic[22], story.ENDING_LOST, 760):
                img = text_surface(self.app.italic[22], ln, TEXT, 255 * ease_out((t - 0.6) / 1.2))
                surf.blit(img, img.get_rect(center=(CX, y)))
                y += 24
            draw_text(surf, self.app.fonts[22], r.reason, (CX, y + 10), DIM, center=True)
        self._draw_stats(surf, r)
        self.draw_buttons(surf)

    def _draw_stats(self, surf, r):
        box = pygame.Rect(CX - 330, 318, 660, 158)
        draw_panel(surf, box, fill=(24, 20, 26), alpha=225)
        f, b = self.app.fonts, self.app.bold
        draw_text(surf, b[26], "Score  {:,}".format(r.total_score), (CX, box.y + 24), ACCENT, center=True)
        draw_text(surf, f[22], "Floors cleared %d/%d    Shards earned %d    Seed %d" %
                  (r.cleared, MAX_FLOOR, r.shards_earned(), r.seed), (CX, box.y + 54), TEXT, center=True)
        n = max(1, len(r.scores))
        step = min(92, 600 // n)
        for i, res in enumerate(r.scores):             # one medallion per floor
            cx = CX - (n - 1) * step // 2 + i * step
            c = GRADE_COLORS.get(res.grade, TEXT)
            pygame.draw.circle(surf, scale_color(c, 0.25), (cx, box.y + 96), 20)
            pygame.draw.circle(surf, c, (cx, box.y + 96), 20, 2)
            draw_text(surf, b[22], res.grade, (cx, box.y + 96), c, center=True)
            draw_text(surf, f[16], "F%d" % res.floor, (cx, box.y + 126), DIM, center=True)
        if not r.scores:
            draw_text(surf, self.app.italic[18], "No floors cleared.", (CX, box.y + 100), DIM, center=True)
        if r.picked:
            draw_text(surf, f[18], "Upgrades: " + ", ".join(UPGRADES[k][0] for k in r.picked),
                      (CX, box.bottom - 16), DIM, center=True)


class PauseScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.parent = app.stack[-1]
        self.confirm = False
        self.add((CX - 140, 250, 280, 46), "Resume  (Esc)", app.pop, tag="resume", key=pygame.K_ESCAPE)
        self.add((CX - 140, 308, 280, 46), "How to Play  (H)", app.show_help, tag="help", key=pygame.K_h)
        self.night = app.in_night()
        self.add((CX - 140, 366, 280, 46), "Back to the Night  (A)" if self.night else "Abandon Run  (A)",
                 self.abandon, tag="abandon", key=pygame.K_a)

    def abandon(self):
        if self.night:                                  # leaving keeps Aurel's run; the night goes on
            self.app.abandon_run()
            return
        if not self.confirm:
            self.confirm = True
            self.btn("abandon").label = "Really abandon? Click again"
            self.btn("abandon").color = DANGER_BTN
            self.say("Press A or click again to end this run. Esc cancels.", WARN)
        else:
            self.app.abandon_run()

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE and self.confirm:
            self.confirm = False
            b = self.btn("abandon")
            b.label, b.color = "Abandon Run  (A)", STONE_BTN
            self.say("Abandon cancelled.")
            self.app.dirty = True
            return True
        return super().handle(ev)

    def update(self, dt):
        return self.parent.update(dt)

    def draw(self, surf):
        self.parent.draw(surf)
        tint(surf, surf.get_rect(), (4, 2, 8), 170)
        draw_panel(surf, (CX - 190, 160, 380, 320), fill=(26, 22, 28))
        draw_glow_text(surf, self.app.bold[44], "Paused", (CX, 204), ACCENT, (140, 80, 30))
        draw_text(surf, self.app.fonts[22], self.msg, (CX, 450), self.msg_color, center=True)
        self.draw_buttons(surf)
