"""The Tick's play screen: a clockwork tower you can turn back, with a timeline and a free preview."""

import math

import pygame

from ..base import Screen
from ..theme import (GOLD, Particles, add_glow, draw_glow_text, draw_guild_warden, draw_panel, draw_pocket_watch,
                     draw_thief, ease_out, lerp, scale_color, vertical_gradient)
from ..widgets import ACCENT, BAD, DIM, GOOD, TEXT, WARN, draw_text, draw_wrapped, tint
from . import tick as tk
from .common import Card, ChoiceCard, RulesCard

W, H = 960, 660
TOP, BOTTOM = 52, 96
MOVE_TIME = 0.12
HOLD_DELAY, HOLD_EVERY = 0.3, 0.07     # holding Q keeps rewinding
DIRKEYS = {pygame.K_UP: (0, -1), pygame.K_w: (0, -1), pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0),
           pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1), pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0)}
BRASS = (200, 160, 80)
DANGER = (230, 90, 70)

RULES = [
    ("The goal", "Get out of the Tick: the doors below are barred, so the only way is up. Reach the stair up "
                 "(X) on each floor. Near the top is the Drum Room, where the hoard is kept, and then the roof."),
    ("The tower keeps time", "Everything runs on the tower's clock, the tick: wardens walk the same rounds, gear "
                             "doors open on the same ticks, every time. Moving or waiting turns the clock on by "
                             "one."),
    ("The Regulator (Q)", "Turn the whole tower back one tick while you stay exactly where you are. Hold Q to "
                             "keep turning. Each tick costs a minute of the hoard, and the hoard lasts the whole "
                             "climb. Whatever is left at the top is yours to give away, or keep."),
    ("Looking ahead (free)", "[ and ] show the tower at other ticks without changing anything: ghost wardens "
                             "and their cones. Enter winds the tower to the tick you are looking at."),
    ("Being seen", "Being seen at any tick you pass through (even while winding back), walking into a warden, "
                   "or still being on the floor when the Quarter Bell rings: the watch snaps you and the tower back "
                   "four moves for 6 minutes. Without the minutes, the floor starts over."),
    ("The timeline", "Gold: when each door is open. Red: ticks when the tile you stand on is watched. The bell "
                     "mark is the Quarter Bell. The bright line is now."),
    ("Keys", "Arrows move.  Space waits.  Q winds back.  [ ] look at other ticks.  Enter winds to it.  "
             "R retries.  H rules.  Esc title."),
]


class TickScreen(Screen):
    def __init__(self, app, run=None, announce=True):
        super().__init__(app)
        self.run = run or tk.TickRun(app.seed)
        self.level = self.run.level
        self.sim = self.run.begin()
        self.t = 0.0
        self.prev_t = 0
        self.prev_player = self.sim.player
        self.anim = 1.0
        self.rewinding = 0.0          # visual pulse while the clock runs backwards
        self.snap = 0.0               # visual flash when the watch snaps you back
        self.hold = None              # seconds until the next automatic rewind while Q is held
        self.preview = None           # a tick you are looking at (free), or None
        self.intro = announce
        self.fx = Particles(200)
        w, h = self.level.size
        self.ts = min(W // w, (H - TOP - BOTTOM) // h, 40)
        self.ox = (W - w * self.ts) // 2
        self.oy = TOP + (H - TOP - BOTTOM - h * self.ts) // 2
        self._static = None
        self.say("", DIM)

    def center(self, p):
        return (self.ox + p[0] * self.ts + self.ts // 2, self.oy + p[1] * self.ts + self.ts // 2)

    def rect(self, p):
        return pygame.Rect(self.ox + p[0] * self.ts, self.oy + p[1] * self.ts, self.ts, self.ts)

    # ------------------------------------------------------------ acting
    def act(self, action):
        msg = self.sim.validate(action)
        if msg:
            self.say(msg, WARN)
            return False
        self.prev_t, self.prev_player = self.sim.t, self.sim.player
        ev = self.sim.step(action)
        self.run.on_step(action, ev, self.sim)
        if self.app.in_night() and self.app.campaign.check_thread() != "night":
            self.app.to_night()                       # the last day ran out
            return True
        self.anim = 0.0
        lines = []
        for e in ev:
            if e[0] == "rewind":
                self.rewinding = 1.0
                c = self.center(self.sim.player)
                self.fx.emit(c[0], c[1], GOLD, n=4, speed=40, life=0.4)
                lines.append("The tower winds back to tick %d. (%d minutes left in the hoard)" % (self.sim.t,
                                                                                               self.sim.hoard))
            elif e[0] == "watch":
                lines.append("The Regulator: a pocket watch, warm, ticking out of step with the tower. Hold Q and the "
                             "tower will turn back around you.")
                c = self.center(self.sim.player)
                self.fx.emit(c[0], c[1], GOLD, n=30, speed=70, life=0.8)
            elif e[0] == "reel":
                if self.app.in_night():
                    lines.append("An hour reel from the Guild's stores. You cut it loose, and it unspools back into "
                                 "the thread: +%d minutes, for everyone." % e[2])
                else:
                    lines.append("An hour reel from the Guild's stores: +%d minutes to the hoard." % e[2])
                c = self.center(e[1])
                self.fx.emit(c[0], c[1], GOLD, n=20, speed=50, life=0.7)
            elif e[0] == "snapback":
                self.snap = 1.0
                self.prev_t, self.prev_player = self.sim.t, self.sim.player
                why = "The Quarter Bell rings" if e[1] == -1 else "A warden's lantern finds you"
                lines.append("%s, and the watch jerks you and the whole tower four moves back. (-%d minutes)" %
                             (why, e[2]))
            elif e[0] == "caught":
                why = "The Quarter Bell rings and the wardens sweep the floor." if e[1] == -1 else \
                    "A warden's lantern finds you."
                lines.append(why + " R (or Enter) starts the floor again.")
        if lines:
            self.say("  ".join(lines), BAD if self.sim.over == "caught" or any(e[0] == "snapback" for e in ev)
                     else ACCENT)
        elif action[0] != "r":
            self.say("", DIM)
        if self.sim.over == "caught":
            if not self.run.settle(self.sim):
                if self.app.in_night():
                    self.app.campaign.tick_failed = True
                self.app.push(Card(self.app, "The hoard is spent", tk.ENDING_SPENT, "Continue  (Enter)",
                                   self.app.home, color=BAD))
        elif self.sim.over == "out":
            self._floor_done()
        return True

    def wind_to(self, tick):
        """Turn the tower back to `tick` (as far as the hoard and the wardens allow)."""
        while self.sim.t > tick and not self.sim.over:
            before = self.sim.hoard
            if not self.act(("r",)) or self.sim.hoard < before - 1:
                break

    def _floor_done(self):
        spent = self.sim.spent
        self.run.settle(self.sim)
        if self.run.state == "climbed":
            n = self.run.hoard
            body = ("The hoard is here: the drum, and every minute the Guild ever took. You kept %d of them on the "
                    "way up. What do you do with them?" % n)
            body = ("The drum holds the Guild's hoard; your watch, %s more. The Guildmaster holds out his hand for "
                    "the ledger. Open the brake and let it all run down the thread, or take his bargain: enough for "
                    "your brother to tie it, and the watch is yours." % tk.duration(n))
            if self.app.in_night():                         # the Guild has been selling it all night
                c = self.app.campaign
                n = c.hoard_at_the_top()
                body = ("The drum: %s, all the Guild has not sold tonight. Your watch: %s more. Open the brake and "
                        "all of it runs down the thread, to whoever is pulling. Or take his bargain: %s sent down for "
                        "your brother, and the Guild pays for every echo he unravels. You keep the watch; he keeps the "
                        "ledger." % (tk.duration(c.drum), tk.duration(c.tick.hoard), tk.duration(c.bargain_slack())))
            self.app.push(ChoiceCard(
                self.app, "The Drum Room", body,
                [("Open the brake", lambda: self._choose(True, n)),
                 ("Take his bargain", lambda: self._choose(False, n))], color=GOLD))
            return
        self.app.push(Card(self.app, "%s: through" % self.level.name,
                           "%s  (You spent %d minutes of the hoard here; %d remain.)" %
                           (tk.beat(self.run.index - 1), spent, self.run.hoard),
                           "Continue  (Enter)", self.next_floor, color=GOOD))

    def _choose(self, release, n):
        if self.app.in_night():
            if release:
                self.app.campaign.release_hoard()
            else:
                self.app.campaign.take_bargain()
        text = tk.ENDING_RELEASE if release else tk.ENDING_BARGAIN
        self.app.replace(self)
        suffix = "" if self.app.in_night() else "  (End of the prototype.)"
        self.app.push(Card(self.app, "The Drum Room", text + suffix, "Continue  (Enter)", self.app.home,
                           color=GOOD if release else WARN))

    def next_floor(self):
        if self.app.in_night():
            self.app.to_night()
            return
        run = self.run
        key = run.index if run.index in tk.INTERLUDES else ("last" if run.index == run.floors - 1 else None)
        self.app.tell(self.app.unseen("tick:%s" % key, tk.INTERLUDES.get(key)),
                      lambda: self.app.replace(TickScreen(self.app, run)), title="Maren")

    def restart(self):
        self.app.replace(TickScreen(self.app, self.run, announce=False))

    # ------------------------------------------------------------ input
    def handle(self, ev):
        if self.intro:
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                self.app.home()
            elif ev.type == pygame.KEYDOWN or (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1):
                self.intro = False
            return True
        if ev.type == pygame.KEYUP and ev.key in (pygame.K_q, pygame.K_BACKSPACE):
            self.hold = None
            return True
        if ev.type != pygame.KEYDOWN:
            return super().handle(ev)
        k = ev.key
        if k == pygame.K_ESCAPE:
            if self.preview is not None:
                self.preview = None
                self.say("Back to now.", DIM)
            else:
                self.app.home()
            return True
        if k == pygame.K_r or (self.sim.over == "caught" and k in (pygame.K_RETURN, pygame.K_KP_ENTER)):
            if self.run.state == "playing":
                self.restart()
            return True
        if self.sim.over:
            return True
        if k in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET, pygame.K_COMMA, pygame.K_PERIOD):
            base = self.sim.t if self.preview is None else self.preview
            step = -1 if k in (pygame.K_LEFTBRACKET, pygame.K_COMMA) else 1
            self.preview = max(0, min(tk.T_MAX, base + step))
            if self.preview == self.sim.t:
                self.preview = None
            self._describe_preview()
            return True
        if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self.preview is None:
                self.say("Look at another tick first ([ and ]); Enter winds the tower there.", DIM)
            elif self.preview > self.sim.t:
                self.say("The watch only winds back. To get to tick %d, wait." % self.preview, WARN)
            else:
                target, self.preview = self.preview, None
                self.wind_to(target)
            return True
        self.preview = None
        if k in DIRKEYS:
            self.act(("m",) + DIRKEYS[k])
        elif k == pygame.K_SPACE:
            self.act(("w",))
        elif k in (pygame.K_q, pygame.K_BACKSPACE):
            if self.act(("r",)):
                self.hold = HOLD_DELAY
        elif k == pygame.K_h:
            self.app.push(RulesCard(self.app, tk.TITLE, RULES))
        else:
            return False
        return True

    def _describe_preview(self):
        if self.preview is None:
            self.say("Back to now.", DIM)
            return
        p, t = self.sim.player, self.preview
        watched = self.sim.seen_at(p, t) is not None
        cost = max(0, self.sim.t - t)
        where = "behind" if t < self.sim.t else "ahead of"
        self.say("Looking at tick %d, %d %s now (free). Standing here then you would be %s.%s" %
                 (t, abs(self.sim.t - t), where, "SEEN" if watched else "unseen",
                  "  Enter winds there for %d minutes." % cost if t < self.sim.t else ""),
                 BAD if watched else ACCENT)

    def update(self, dt):
        self.t += dt
        self.anim = min(1.0, self.anim + dt / MOVE_TIME)
        self.rewinding = max(0.0, self.rewinding - dt * 2.5)
        self.snap = max(0.0, self.snap - dt * 1.5)
        if self.hold is not None:
            pressed = pygame.key.get_pressed()
            if self.sim.over or not (pressed[pygame.K_q] or pressed[pygame.K_BACKSPACE]):
                self.hold = None                      # let go (or a key-up went missing)
            else:
                self.hold -= dt
                if self.hold <= 0:
                    self.hold = HOLD_EVERY if self.act(("r",)) else None
        self.fx.update(dt)
        return True

    # ------------------------------------------------------------ drawing
    def _interp(self, a, b):
        k = ease_out(self.anim)
        ca, cb = self.center(a), self.center(b)
        return (int(lerp(ca[0], cb[0], k)), int(lerp(ca[1], cb[1], k)))

    def _build_static(self):
        """The tower's floor plan: dark panelled walls with brass trim, a warm parquet floor."""
        lv, ts = self.level, self.ts
        w, h = lv.size
        s = pygame.Surface((w * ts, h * ts), pygame.SRCALPHA)
        for y in range(h):
            for x in range(w):
                p = (x, y)
                r = pygame.Rect(x * ts, y * ts, ts, ts)
                if p in lv.walls:
                    open_near = any((x + dx, y + dy) not in lv.walls and 0 <= x + dx < w and 0 <= y + dy < h
                                    for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)))
                    if not open_near:
                        continue
                    pygame.draw.rect(s, (46, 30, 22), r)
                    pygame.draw.rect(s, (74, 50, 34), r.inflate(-6, -6), 1)
                    if (x, y + 1) not in lv.walls and y + 1 < h:
                        pygame.draw.line(s, BRASS, (r.x, r.bottom - 2), (r.right, r.bottom - 2), 2)
                else:
                    plank = (x + (y % 2) * 2) % 4
                    c = (124 - plank * 6, 84 - plank * 4, 50 - plank * 2)         # warm parquet
                    pygame.draw.rect(s, c, r)
                    pygame.draw.line(s, (c[0] - 26, c[1] - 20, c[2] - 12), r.topleft, r.topright)
                    if plank == 0:
                        pygame.draw.line(s, (c[0] - 26, c[1] - 20, c[2] - 12), r.topleft, r.bottomleft)
        return s

    def _draw_backdrop(self, surf):
        surf.blit(vertical_gradient((W, H), (30, 20, 14), (12, 8, 6)), (0, 0))
        for gx, gy, gr, sp in ((110, 150, 120, 0.10), (W - 120, 170, 150, -0.07), (W // 2 + 40, H - 170, 90, 0.14),
                               (200, H - 160, 70, -0.2)):
            _gear_outline(surf, (gx, gy), gr, self.t * sp + 0.05 * self.sim.t, (40, 28, 20))

    def draw(self, surf):
        sim, lv = self.sim, self.level
        shown_t = sim.t if self.preview is None else self.preview
        self._draw_backdrop(surf)
        if self._static is None:
            self._static = self._build_static()
        surf.blit(self._static, (self.ox, self.oy))
        for g in lv.guards:                                              # each warden's round, faintly
            for q in g.route[::2]:
                pygame.draw.circle(surf, (160, 120, 70), self.center(q), 1)
        cone = pygame.Surface((W, H), pygame.SRCALPHA)                  # what each warden sees
        for g in lv.guards:
            for p in sim.sight(g, shown_t):
                cone.fill((255, 196, 100, 70) if self.preview is None else (150, 200, 255, 60), self.rect(p))
        surf.blit(cone, (0, 0))
        for pos in lv.doors:
            self._draw_door(surf, pos, shown_t)
        for r in sim.reels:
            c = self.center(r)
            add_glow(surf, c, self.ts, (90, 70, 24))
            pygame.draw.circle(surf, GOLD, c, self.ts // 4, 2)
            pygame.draw.circle(surf, (120, 90, 40), c, self.ts // 8)
        if lv.watch is not None and not sim.has_watch:
            c = self.center(lv.watch)
            add_glow(surf, c, int(self.ts * 1.4), (150, 110, 40))
            draw_pocket_watch(surf, c, self.ts // 3, self.t)
        gc = self.center(lv.goal)
        add_glow(surf, gc, int(self.ts * 1.4), scale_color((150, 120, 60), 0.7 + 0.3 * math.sin(self.t * 2)))
        for k in range(4):                                               # the stair up
            pygame.draw.rect(surf, scale_color((210, 180, 120), 1 - k * 0.18),
                             (gc[0] - self.ts // 2 + 3 + k * 2, gc[1] + self.ts // 2 - 6 - k * 6, self.ts - 6 - k * 4, 5))
        scale = self.ts / 22
        for g in lv.guards:
            if self.preview is None and self.anim < 1:
                pc = self._interp(g.at(self.prev_t), g.at(sim.t))
            else:
                pc = self.center(g.at(shown_t))
            f = g.facing(shown_t)
            add_glow(surf, (pc[0] + f[0] * 8, pc[1] + f[1] * 8), int(self.ts * 1.1), (90, 64, 26))
            img = pygame.Surface((28, 32), pygame.SRCALPHA)
            draw_guild_warden(img, 14, 17, self.t, f)
            img = pygame.transform.scale(img, (int(28 * scale), int(32 * scale)))
            if self.preview is not None:
                img.set_alpha(150)
            surf.blit(img, img.get_rect(center=(pc[0], pc[1] - 2)))
        me = self._interp(self.prev_player, sim.player)
        img = pygame.Surface((28, 28), pygame.SRCALPHA)
        draw_thief(img, 14, 14, self.t, sim.has_watch)
        img = pygame.transform.scale(img, (int(28 * scale), int(28 * scale)))
        surf.blit(img, img.get_rect(center=me))
        if self.preview is not None:                                    # looking at another tick
            tint(surf, pygame.Rect(self.ox, self.oy, lv.size[0] * self.ts, lv.size[1] * self.ts), (40, 70, 120), 40)
            draw_glow_text(surf, self.app.bold[26], "Tick %d  (looking; nothing changes)" % self.preview,
                           (W // 2, self.oy - 14 if self.oy > TOP + 20 else TOP + 16), (190, 220, 255))
        if self.rewinding > 0:                                         # the world runs backwards
            veil = pygame.Surface((W, H), pygame.SRCALPHA)
            veil.fill((140, 96, 40, int(70 * self.rewinding)))
            surf.blit(veil, (0, 0))
        if self.snap > 0:
            veil = pygame.Surface((W, H), pygame.SRCALPHA)
            veil.fill((200, 60, 40, int(90 * self.snap)))
            surf.blit(veil, (0, 0))
        if sim.over == "caught":
            add_glow(surf, self.center(sim.player), 70, (170, 130, 50))
        self.fx.draw(surf)
        self._draw_hud(surf)
        self._draw_timeline(surf)
        if self.intro:
            self._draw_intro(surf)

    def _draw_intro(self, surf):
        tint(surf, surf.get_rect(), (10, 6, 4), 150)
        box = pygame.Rect(W // 2 - 320, 180, 640, 270)
        draw_panel(surf, box, fill=(30, 22, 16), edge=BRASS)
        draw_glow_text(surf, self.app.bold[32], "Floor %d of %d: %s" % (self.run.index + 1, self.run.floors,
                                                                     self.level.name), (W // 2, box.y + 40), GOLD)
        draw_wrapped(surf, self.app.italic[22], self.level.hint, (box.x + 40, box.y + 78), box.w - 80, TEXT, spacing=4)
        draw_text(surf, self.app.bold[18], "Hoard: %d minutes.   Any key to begin." % self.run.hoard,
                  (W // 2, box.bottom - 26), DIM, center=True)

    def _draw_door(self, surf, pos, t):
        r = self.rect(pos)
        c = self.level.doors[pos][0]
        opened = self.sim.door_open(pos, t)
        pygame.draw.rect(surf, (30, 20, 14), r)
        cx, cy = r.center
        ang = self.t * (3 if opened else 0.3)
        teeth = 8
        pts = []
        for k in range(teeth * 2):
            a = ang + k * math.pi / teeth
            rr = (r.w // 2 - 2) if k % 2 == 0 else (r.w // 2 - 5)
            pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
        pygame.draw.polygon(surf, BRASS if not opened else (110, 90, 50), pts, 0 if not opened else 2)
        draw_text(surf, self.app.bold[16], c, (cx, cy), (30, 20, 10) if not opened else BRASS, center=True)
        label = self.app.fonts[16].render(self.level.door_label(pos), True, (240, 220, 170))
        lr = label.get_rect(midbottom=(cx, r.y - 2))
        lr.clamp_ip(pygame.Rect(0, TOP, W, H - TOP - BOTTOM))
        pygame.draw.rect(surf, (20, 14, 10), lr.inflate(6, 2), border_radius=3)
        surf.blit(label, lr)

    def _draw_hud(self, surf):
        sim = self.sim
        surf.blit(vertical_gradient((W, TOP), (44, 30, 20), (24, 16, 10)), (0, 0))
        pygame.draw.line(surf, BRASS, (0, TOP - 1), (W, TOP - 1))
        draw_text(surf, self.app.bold[22], "The Tick", (12, 6), BRASS)
        draw_text(surf, self.app.italic[16], "Floor %d of %d: %s" % (self.run.index + 1, self.run.floors,
                                                                   self.level.name), (12, 28), DIM)
        c = (W // 2 - 40, TOP // 2)                                     # the tower clock
        pygame.draw.circle(surf, (220, 200, 160), c, 20)
        pygame.draw.circle(surf, BRASS, c, 20, 2)
        shown = lerp(self.prev_t, sim.t, ease_out(self.anim))
        a = -math.pi / 2 + shown * math.tau / 60
        pygame.draw.line(surf, (40, 28, 20), c, (c[0] + math.cos(a) * 16, c[1] + math.sin(a) * 16), 2)
        draw_text(surf, self.app.bold[22], "Tick %d" % sim.t, (c[0] + 30, 6), TEXT)
        bell = self.level.bell
        draw_text(surf, self.app.italic[16], "bell at %d" % bell if bell else "no bell on this floor",
                  (c[0] + 30, 28), DIM)
        if sim.has_watch:
            draw_text(surf, self.app.bold[22], "Hoard %d min" % sim.hoard, (W - 190, 6), GOLD if sim.hoard > 10 else BAD)
            draw_text(surf, self.app.italic[16], ("thread %s" % self.app.campaign.thread.hm()) if self.app.in_night()
                      else "Q winds back (1 min a tick)", (W - 190, 28), DIM)
        else:
            draw_text(surf, self.app.bold[18], "Take the watch (W)", (W - 190, 14), GOLD)
        surf.blit(vertical_gradient((W, BOTTOM), (24, 16, 10), (40, 28, 18)), (0, H - BOTTOM))
        pygame.draw.line(surf, BRASS, (0, H - BOTTOM), (W, H - BOTTOM))
        goal = "take the Regulator (W), then reach the stair up (X)" if (self.level.watch and not sim.has_watch) else \
            "reach the stair up (X)"
        draw_text(surf, self.app.fonts[18], "Goal: %s.   Arrows move  Space wait  Q wind back  [ ] look ahead  "
                                            "H rules" % goal, (12, H - 52), DIM)
        if self.msg:
            draw_wrapped(surf, self.app.fonts[18], self.msg, (12, H - 32), W - 24, self.msg_color, spacing=0)

    def _draw_timeline(self, surf):
        """The clock as a strip: door windows (gold), ticks when your tile is watched (red), the bell."""
        sim = self.sim
        x0, x1, y = 20, W - 20, H - BOTTOM + 10
        span = max(60, (self.level.bell or 0) + 4, sim.t + 12, (self.preview or 0) + 8)
        pygame.draw.rect(surf, (20, 14, 10), (x0, y, x1 - x0, 22), border_radius=4)

        def tx(t):
            return x0 + (x1 - x0) * t / span
        cell = max(2, (x1 - x0) / span)
        for t in range(span + 1):                                     # is where you stand watched then?
            if sim.seen_at(sim.player, t) is not None:
                pygame.draw.rect(surf, DANGER, (tx(t), y + 14, cell, 6))
        for pos in self.level.doors:
            c = self.level.doors[pos][0]
            for t in range(span + 1):
                if sim.door_open(pos, t):
                    pygame.draw.rect(surf, GOLD, (tx(t), y + 3, cell, 10))
                    if t == 0 or not sim.door_open(pos, t - 1):
                        draw_text(surf, self.app.bold[16], c, (tx(t) + 3, y - 8), GOLD)
        for t in range(0, span + 1, 10):
            pygame.draw.line(surf, (90, 70, 50), (tx(t), y + 20), (tx(t), y + 24))
        if self.level.bell:
            bx = tx(self.level.bell)
            pygame.draw.line(surf, DANGER, (bx, y - 4), (bx, y + 24), 3)
            draw_text(surf, self.app.bold[16], "bell", (bx - 30, y - 8), DANGER)
        now = tx(lerp(self.prev_t, sim.t, ease_out(self.anim)))
        pygame.draw.line(surf, (255, 240, 200), (now, y - 2), (now, y + 24), 2)
        add_glow(surf, (int(now), y + 11), 14, (90, 70, 30))
        if self.preview is not None:
            px = tx(self.preview)
            pygame.draw.line(surf, (150, 200, 255), (px, y - 4), (px, y + 26), 2)


def _gear_outline(surf, c, r, angle, color):
    teeth = max(10, r // 9)
    pts = []
    for k in range(teeth * 2):
        a = angle + k * math.pi / teeth
        rr = r if k % 2 == 0 else r * 0.86
        pts.append((c[0] + math.cos(a) * rr, c[1] + math.sin(a) * rr))
    pygame.draw.polygon(surf, color, pts, 3)
    pygame.draw.circle(surf, color, c, int(r * 0.5), 3)
    for k in range(4):
        a = angle + k * math.pi / 2
        pygame.draw.line(surf, color, (c[0] + math.cos(a) * r * 0.15, c[1] + math.sin(a) * r * 0.15),
                         (c[0] + math.cos(a) * r * 0.5, c[1] + math.sin(a) * r * 0.5), 3)

