"""The Long Night's screens: title, how much thread, the hub (the night, stacked), and the epilogue."""

import math
import threading

import pygame

from . import campaign as cp
from . import ending
from .sisters import stillwater as sw
from .base import Screen
from .cinematics import draw_scene, draw_town
from .theme import (GOLD, add_glow, draw_glow_text, draw_lamplighter, draw_panel, draw_rule, draw_still, draw_thief,
                    vertical_gradient)
from .widgets import ACCENT, BAD, DIM, TEXT, THREAD, WARN, draw_text, draw_wrapped, tint, wrap_text

W, H = 960, 660
CX = W // 2
BAND_TOP, BAND_STEP = 112, 152      # the three stories' bands on the hub

RULES = [
    ("One night, one thread", "The thread is the time that is left: what the Guild has not taken. Three stories share "
                              "it. Every turn in any of them spends a minute; it lengthens only when the Guild's "
                              "hours are let go. Difficulty decides how long it starts."),
    ("Aurel (within)", "Echo Delve: go down the Deep and tie the thread. Unravelling an echo cuts 20 minutes of "
                       "it. His last floor ends the night for everyone: the new day comes, ready or not."),
    ("Maren (above)", "The Tick: get out of the Guild's tower with the stolen Regulator; the only way is up. "
                      "Winding the tower back spends the Guild's hoard, not the thread. Every hour reel she cuts "
                      "loose lengthens the thread, and in the Drum Room she can let the rest go into it, or keep it."),
    ("Tarn (in the rock)", "Stillwater: lead the Still through the break before the new day takes the light from "
                           "their water. It dims as the thread shortens; Aurel's lit sconces give some back. Anyone "
                           "still in the caves when Aurel ties the thread is lost."),
    ("Order", "The night opens with each of them once (Aurel, Maren, Tarn), each with their own story. After "
              "that, any order. Leaving a level part-way is allowed; the minutes spent stay spent."),
]


class NightTitle(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.t = 0.0
        self.add((CX - 150, 380, 300, 44), "Begin the Night  (N)", app.begin_night,
                 tag="begin", key=(pygame.K_n, pygame.K_RETURN, pygame.K_KP_ENTER))
        self.add((CX - 150, 432, 300, 44), "The Story  (S)", app.night_story, tag="story", key=pygame.K_s)
        self.add((CX - 150, 484, 300, 44), "How to Play  (H)", lambda: app.push(_rules(app)), tag="help",
                 key=pygame.K_h)
        self.add((CX - 150, 536, 300, 44), "Quit  (Esc)", app.quit, tag="quit", key=pygame.K_ESCAPE)
        if app.dev:
            self.add((CX - 150, 588, 300, 44), "Endings (dev)  (E)", app.dev_endings, tag="endings", key=pygame.K_e)

    def update(self, dt):
        self.t += dt
        return True

    def draw(self, surf):
        draw_scene(surf, "three", self.t, pygame.Rect(0, 0, W, H))
        tint(surf, surf.get_rect(), (0, 0, 0), 120)
        draw_glow_text(surf, self.app.bold[80], "THE LONG NIGHT", (CX, 140), ACCENT, (140, 80, 30))
        draw_rule(surf, CX, 190, 380)
        draw_text(surf, self.app.italic[26], "One broken day. Three people. One thread.", (CX, 220), TEXT, center=True)
        draw_text(surf, self.app.italic[18], "Aurel goes down. Maren runs. Tarn leads his people to the break. "
                                             "Every turn spends the thread.", (CX, 254), DIM, center=True)
        self.draw_buttons(surf)


def _rules(app):
    from .sisters.common import RulesCard
    return RulesCard(app, "The Long Night", RULES)


class LengthScreen(Screen):
    """How much thread is left? The night is already built, so each length is shown as real time."""

    def __init__(self, app, campaign):
        super().__init__(app)
        self.c = campaign
        self.t = 0.0
        for i, (key, name, mult, desc) in enumerate(cp.LENGTHS):
            self.add((90 + i * 270, 230, 240, 220), "", lambda k=key: app.cut_thread(campaign, k), tag="len:" + key,
                     key=pygame.K_1 + i, color=(40, 34, 40))
        self.add((CX - 100, 500, 200, 42), "Back  (Esc)", app.to_title, tag="back", key=pygame.K_ESCAPE)

    def update(self, dt):
        self.t += dt
        return True

    def draw(self, surf):
        surf.blit(vertical_gradient((W, H), (18, 14, 20), (6, 5, 8)), (0, 0))
        draw_glow_text(surf, self.app.bold[44], "How much thread is left?", (CX, 130), ACCENT)
        perfect = self.c.perfect_par
        draw_text(surf, self.app.italic[22], "A perfect night (every sconce lit, everyone home) takes %d:%02d of it, "
                                             "at the very least: the mark on each thread." % divmod(perfect, 60),
                  (CX, 176), DIM, center=True)
        draw_text(surf, self.app.italic[18], "The rest is room for the dark, for mistakes, and for going back.",
                  (CX, 200), DIM, center=True)
        longest = self.c.minutes_for(cp.LENGTHS[0][0])
        for i, (key, name, mult, desc) in enumerate(cp.LENGTHS):
            b = self.btn("len:" + key)
            hov = b is self.hover
            r = b.rect
            draw_panel(surf, r, fill=(44, 36, 42) if hov else (30, 25, 30), edge=ACCENT if hov else (120, 92, 56))
            draw_text(surf, self.app.bold[26], "%d. %s" % (i + 1, name), (r.centerx, r.y + 34), TEXT, center=True)
            minutes = self.c.minutes_for(key)
            draw_text(surf, self.app.bold[32], "%d:%02d" % divmod(minutes, 60), (r.centerx, r.y + 76), GOLD, center=True)
            spool_w = int((r.w - 60) * minutes / longest)          # the thread, drawn to length
            y = r.y + 106
            pygame.draw.line(surf, GOLD, (r.centerx - spool_w // 2, y), (r.centerx + spool_w // 2, y), 3)
            for k in range(0, spool_w - 4, 7):
                pygame.draw.line(surf, (255, 236, 170), (r.centerx - spool_w // 2 + k, y + 2),
                                 (r.centerx - spool_w // 2 + k + 4, y - 2), 1)
            mark = r.centerx - spool_w // 2 + int((r.w - 60) * perfect / longest)      # a perfect night, this far
            pygame.draw.line(surf, TEXT, (mark, y - 7), (mark, y + 7), 2)
            for j, line in enumerate(wrap_text(self.app.italic[18], desc, r.w - 30)):
                draw_text(surf, self.app.italic[18], line, (r.centerx, r.y + 136 + j * 20), DIM, center=True)
            draw_text(surf, self.app.fonts[16], "room to spare: %d:%02d" % divmod(minutes - perfect, 60),
                      (r.centerx, r.bottom - 18), (150, 136, 120), center=True)
        back = self.btn("back")                       # the cards are drawn above; only "back" is a plain button
        back.draw(surf, self.app.bold[22], hover=back is self.hover)


class LoadingScreen(Screen):
    """Builds the night in the background (every level, and the clock measured against them)."""

    def __init__(self, app, work, then):
        super().__init__(app)
        self.t = 0.0
        self.box = []
        self.then = then
        self.thread = threading.Thread(target=lambda: self.box.append(work()), daemon=True)
        self.thread.start()

    def finish_now(self):
        self.thread.join()
        self.then(self.box[0])

    def update(self, dt):
        self.t += dt
        if not self.thread.is_alive() and self.box:
            self.then(self.box[0])
        return True

    def draw(self, surf):
        surf.fill((8, 6, 10))
        c = (CX, H // 2 - 20)
        for i in range(12):
            a = self.t * 3 + i * math.tau / 12
            k = (i / 12)
            pygame.draw.circle(surf, (int(240 * k), int(200 * k), int(120 * k)),
                               (int(c[0] + math.cos(a) * 30), int(c[1] + math.sin(a) * 30)), 4)
        draw_text(surf, self.app.italic[26], "Weaving the night…", (CX, H // 2 + 40), DIM, center=True)


class NightScreen(Screen):
    """The hub: the tower above, the Deep within, the water below, and the clock over all three."""

    BANDS = [("tick", "Above", "The Tick", "Maren"), ("echo", "Within", "The Deep", "Aurel"),
             ("still", "In the rock", "The caves", "Tarn")]

    def __init__(self, app):
        super().__init__(app)
        self.c = app.campaign
        self.t = 0.0
        self.confirm_end = False
        for i, (track, *_rest) in enumerate(self.BANDS):
            self.add((W - 200, BAND_TOP + i * BAND_STEP + 50, 170, 44), "", lambda tr=track: self.play(tr),
                     tag="play:" + track,
                     key=pygame.K_1 + i)
        self.add((20, H - 50, 150, 36), "Title  (Esc)", app.to_title, tag="title", key=pygame.K_ESCAPE)
        self.refresh()
        p = self.c.prologue_next
        self.say({"echo": "The night begins with Aurel, on the first landing. Have him light the sconces as he goes "
                          "(walk close to them): later, the Still will climb home by them.",
                  "tick": "Now Maren, at the foot of the Tick.",
                  "still": "And far below, Tarn, in the dark."}.get(p, "Choose whose part of the night to play next."))

    def refresh(self):
        for i, (track, *_rest) in enumerate(self.BANDS):
            b = self.btn("play:" + track)
            ok = self.c.available(track)
            b.enabled = ok
            b.label = "Done" if self.c.finished(track) else ("Play  (%d)" % (i + 1) if ok else "Later")
            b.color = (74, 58, 44) if ok else (40, 34, 38)

    def play(self, track):
        if not self.c.available(track):
            self.say("Not yet." if not self.c.finished(track) else "That part of the night is done.", WARN)
            return
        if track == "echo" and self.c.aurel_on_last_floor and not self.confirm_end:
            self.confirm_end = True
            below = self.c.still_below()
            hoard = self.c.hoard_choice is None and not self.c.tick_failed
            self.say("This is the Loom. When Aurel ties the thread the night ends for everyone%s%s. Play it again "
                     "to go on." % (" (%d of the Still are still below)" % below if below else "",
                                    ", and Maren has not reached the drum" if hoard else ""), WARN)
            return
        self.app.play_track(track)

    def update(self, dt):
        self.t += dt
        return True

    def draw(self, surf):
        c = self.c
        surf.blit(vertical_gradient((W, H), (16, 12, 18), (6, 5, 8)), (0, 0))
        draw_glow_text(surf, self.app.bold[44], "The Long Night", (CX, 34), ACCENT, (140, 80, 30))
        frac = c.thread.minutes / max(1, c.thread.start)
        bx, bw = 210, 540                                   # the thread: time left, shortening
        pygame.draw.rect(surf, (30, 24, 20), (bx, 66, bw, 22), border_radius=6)
        pygame.draw.rect(surf, GOLD if frac > 0.25 else BAD, (bx, 66, int(bw * min(1.0, frac)), 22), border_radius=6)
        for k in range(0, int(bw * min(1.0, frac)) - 6, 9):                       # twisted strands
            pygame.draw.line(surf, (255, 236, 170), (bx + k, 82), (bx + k + 6, 70), 1)
        label = "The thread: %s left" % c.thread.hm()
        draw_text(surf, self.app.italic[16], "Tied now, it would make a day %s." % c.day_until(), (CX, 96), DIM,
                  center=True)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            draw_text(surf, self.app.bold[18], label, (CX + dx, 77 + dy), (20, 14, 10), center=True)
        draw_text(surf, self.app.bold[18], label, (CX, 77), TEXT, center=True)
        for i, band in enumerate(self.BANDS):
            self._draw_band(surf, i, *band)
        draw_text(surf, self.app.italic[18], "The thread shortens every minute and lengthens when the Guild's hours "
                                             "are let go. What is left when Aurel ties it becomes the morning.",
                  (CX, H - 80), DIM, center=True)
        if self.msg:
            draw_wrapped(surf, self.app.fonts[18], self.msg, (190, H - 44), W - 210, self.msg_color, spacing=0)
        self.draw_buttons(surf)

    def _draw_band(self, surf, i, track, where, place, who):
        c = self.c
        top = BAND_TOP + i * BAND_STEP
        r = pygame.Rect(20, top, W - 40, BAND_STEP - 8)
        colors = {"tick": ((52, 36, 24), (30, 20, 14)), "echo": ((30, 24, 36), (16, 12, 20)),
                  "still": ((12, 20, 30), (4, 8, 14))}[track]
        surf.blit(vertical_gradient(r.size, *colors), r.topleft)
        edge = GOLD if c.available(track) else (70, 60, 54)
        pygame.draw.rect(surf, edge, r, 2, border_radius=8)
        art = pygame.Rect(r.x + 10, r.y + 10, 150, r.h - 20)
        pygame.draw.rect(surf, (0, 0, 0), art, border_radius=6)
        self._draw_portrait(surf, track, art)
        x = art.right + 20
        draw_text(surf, self.app.italic[18], where.upper(), (x, r.y + 12), DIM)
        draw_text(surf, self.app.bold[26], "%s: %s" % (who, place), (x, r.y + 32), TEXT)
        done, total = c.done(track), c.total(track)
        if c.finished(track):
            status = "finished"
        else:
            status = "%d of %d done. Next: %s%s" % (done, total, c.next_level_name(track),
                                                    " (tying the thread ends the night)"
                                                    if track == "echo" and c.aurel_on_last_floor else "")
        draw_text(surf, self.app.fonts[18], status, (x, r.y + 66), TEXT)
        detail = {
            "tick": ("Her watch: %d min   The Guild's drum: %d min, selling %d an hour" %
                     (c.tick.hoard, c.drum, round(60 * c.guild_rate())) if c.hoard_choice is None else
                     {"released": "She let %d minutes of the hoard go" % c.released,
                      "bargain": "She took the Guild's bargain (the Guild pays for Aurel's unravels)"}[c.hoard_choice]),
            "echo": "Stair lit: %d%% (%d of %d sconces)   An unravel cuts %s" % (
                int(round(100 * c.stair_lit())), c.lamps_lit(), c.lamps_total, c.echo.unravel_cost_short()),
            "still": "Saved: %d   Lost: %d   Still below: %d   The water's light: %d%% (a turn costs %.1f min)" % (
                c.still.saved, c.still.lost, c.still_below(), round(100 * c.still.light()),
                sw.minutes_per_turn(c.still.light())),
        }[track]
        draw_text(surf, self.app.fonts[18], detail, (x, r.y + 92), GOLD if track != "echo" else THREAD)
        for k in range(total):                                            # progress pips
            px = x + k * 20
            pygame.draw.circle(surf, GOLD if k < done else (70, 60, 54), (px + 6, r.y + 124), 6)

    def _draw_portrait(self, surf, track, art):
        cx, cy = art.center
        if track == "tick":
            add_glow(surf, (cx, cy), 60, (90, 64, 26))
            img = pygame.Surface((24, 24), pygame.SRCALPHA)
            draw_thief(img, 12, 12, self.t)
        elif track == "echo":
            add_glow(surf, (cx + 20, cy), 60, (90, 70, 30))
            img = pygame.Surface((30, 30), pygame.SRCALPHA)
            draw_lamplighter(img, 15, 15, self.t)
        else:
            for k in range(3):
                q = (self.t * 0.5 + k / 3) % 1.0
                ring = pygame.Surface((140, 60), pygame.SRCALPHA)
                pygame.draw.ellipse(ring, (140, 220, 255, int(200 * (1 - q))),
                                    pygame.Rect(70 - int(65 * q), 30 - int(25 * q), int(130 * q) + 2, int(50 * q) + 2), 2)
                surf.blit(ring, (cx - 70, cy + 10))
            img = pygame.Surface((24, 24), pygame.SRCALPHA)
            draw_still(img, 12, 12, self.t, reach=True)
        img = pygame.transform.scale(img, (img.get_width() * 4, img.get_height() * 4))
        surf.blit(img, img.get_rect(center=(cx, cy)))


class EpilogueScreen(Screen):
    """The record of the night, over Hollowmere (at dawn, if there was one). Shows the night that was
    played, or an outcome from the Story (then there is no seed or thread to report)."""

    def __init__(self, app, outcome=None, on_done=None):
        super().__init__(app)
        self.c = app.campaign if outcome is None else None
        self.outcome = outcome if outcome is not None else self.c.outcome()
        self.t = 0.0
        self.title, self.lines = ending.epilogue(self.outcome)
        self.add((CX - 150, H - 70, 300, 44), "Title  (Enter)", on_done or app.to_title, tag="title",
                 key=(pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE))

    def update(self, dt):
        self.t += dt
        return True

    def draw(self, surf):
        morning = self.outcome.morning
        if morning:
            draw_town(surf, self.t, min(1.0, self.t / 5.0), (0, 0, W, H))
        else:
            draw_town(surf, self.t, 0.0, (0, 0, W, H))
        tint(surf, surf.get_rect(), (6, 4, 8), 150)
        draw_glow_text(surf, self.app.bold[80], self.title.upper(), (CX, 90),
                       (255, 226, 150) if morning else BAD, (170, 90, 30))
        y = 160
        for line in self.lines:
            for ln in wrap_text(self.app.italic[22], line, 760):
                draw_text(surf, self.app.italic[22], ln, (CX, y), TEXT, center=True)
                y += 26
            y += 10
        if self.c is not None:
            draw_text(surf, self.app.fonts[18], "Seed %d   %s (%s)" % (self.c.seed, dict((d[0], d[1]) for d in
                                                                                     cp.LENGTHS)[self.c.length],
                                                                                self.c.thread.hm(self.c.thread.start)),
                      (CX, H - 96), DIM, center=True)
        self.draw_buttons(surf)
