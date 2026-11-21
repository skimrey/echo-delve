"""Stillwater's play screen: a black cave that exists only where the spilled light is stirred."""

import math
import random

import pygame

from ..base import Screen
from ..theme import Particles, add_glow, draw_still, ease_out, lerp, scale_color, vertical_gradient
from ..widgets import ACCENT, BAD, DIM, GOOD, TEXT, WARN, draw_text, draw_wrapped
from . import stillwater as sw
from .common import Card, ChoiceCard, RulesCard

W, H = 960, 660
TOP, BOTTOM = 44, 58
STEP_TIME = 0.28          # seconds for a ripple to slide from one tile to the next on screen
BACK_STEPS = 5            # how many turns a step back undoes (the night does not give them back)
GLOW = (140, 224, 255)
DIRKEYS = {pygame.K_UP: (0, -1), pygame.K_w: (0, -1), pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0),
           pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1), pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0)}

RULES = [
    ("The goal", "Each chamber has a way on: a draught of air (the pale shaft of light), toward the break the "
                 "day made and the Spindle beyond it. Bring the Still who walk with you, find any who are "
                 "stranded, and go on (Enter) before the night runs out. The night is shared by the whole run."),
    ("The light", "The water is full of a day's spilled light. Wading stirs it: a ripple spreads about a tile per "
                  "turn and lights what it crosses. Touch the water (T) for a ripple that goes much further. "
                  "Ledges are dry and silent. Standing still (Space) makes no ripple at all."),
    ("Your wake", "Stirred light settles slowly: anything lit stays visible for a few turns. The Still follow "
                  "you only through light they can see. Go too far ahead, or through the dark, and they stop."),
    ("Float-gates", "A float-gate (A) rises when a ripple reaches its float (a). It sinks again a few turns "
                    "later, so send the wave first, then bring everyone through."),
    ("Eels", "Eels are blind: they feel ripples, including the ones your people make, and swim to where they "
             "began. Throw a pebble (F, then a direction) to draw them away. If one finds you, step back (B)."),
    ("Keys", "Arrows move.  Space waits.  T touches the water.  F throws.  Enter goes on.  B steps back %d turns, "
             "R starts the chamber over (turns spent stay spent: the night does not wait).  H rules.  Esc leaves."
     % BACK_STEPS),
]


class StillScreen(Screen):
    def __init__(self, app, run=None, chamber=None, announce=True):
        super().__init__(app)
        self.run = run or sw.StillRun(app.seed)
        self.level = chamber or self.run.chamber
        self.sim = sw.Still(self.level, self.run.light())
        self.t = 0.0
        self.anim = 1.0                 # 0..1 since the last turn: ripples slide between tiles
        self.throwing = False
        self.throw_fx = None            # (from, to, elapsed)
        self.fx = Particles(400)
        self.confirm_leave = False
        self.history = []               # the chamber before each turn, for stepping back
        self.kin_prev = {}              # where the Still stood before the last turn (they glide from there,
        self.kin_anim = 1.0             #  more slowly the dimmer the water)
        w, h = self.level.size
        self.ts = min(W // w, (H - TOP - BOTTOM) // h, 40)
        self.ox = (W - w * self.ts) // 2
        self.oy = TOP + (H - TOP - BOTTOM - h * self.ts) // 2
        self._static = None
        self.say("", DIM)
        self.intro = announce                  # the chamber's card, shown over the map until dismissed

    # ------------------------------------------------------------ geometry
    def center(self, p):
        return (self.ox + p[0] * self.ts + self.ts // 2, self.oy + p[1] * self.ts + self.ts // 2)

    def rect(self, p):
        return pygame.Rect(self.ox + p[0] * self.ts, self.oy + p[1] * self.ts, self.ts, self.ts)

    # ------------------------------------------------------------ acting
    def act(self, action):
        msg = self.sim.validate(action)
        if msg:
            self.say(msg, WARN)
            return
        if action[0] == "x" and not self.confirm_leave:
            left = self.sim.count("following") + self.sim.count("stranded")
            close = sum(1 for k in self.sim.kin if k.state == "following" and
                        max(abs(k.pos[0] - self.sim.player[0]), abs(k.pos[1] - self.sim.player[1])) <= 1)
            if left:
                self.confirm_leave = True
                self.say("%d of your people are still down here%s. Enter again to go on without them; "
                         "Space waits for them." % (left, " (%d right beside you)" % close if close else ""), WARN)
                return
        self.confirm_leave = False
        self.history.append(self.sim.clone())
        del self.history[:-60]
        self.kin_prev = {k.key: k.pos for k in self.sim.kin}
        self.kin_anim = 0.0
        ev = self.sim.step(action)
        self.anim = 0.0
        if self.run.spend(1, self.sim.light):
            self._dawn()
            return
        self._react(ev)
        if self.sim.over == "caught":
            self.say("An eel finds you in the dark. B: the Still pull you back %d turns. R (or Enter): try the "
                     "chamber again. The night does not wait." % BACK_STEPS, BAD)
        elif self.sim.over == "out":
            self._chamber_done()
        elif self.sim.player == self.level.exit and not self.sim.over:
            n = self.sim.count("following")
            self.say("The way on. %s Enter goes on." % ("Wait (Space) for the %d following you, then" % n
                                                           if n else "Everyone you found is out."), ACCENT)

    def _react(self, ev):
        lines = []
        for e in ev:
            k = e[0]
            if k == "ripple" and e[3] != "follow":
                c = self.center(e[1])
                self.fx.emit(c[0], c[1], GLOW, n=6 if e[3] == "wade" else 16, speed=30, life=0.6)
            elif k == "throw":
                self.throw_fx = [e[1], e[2], 0.0]
            elif k == "gate":
                lines.append("Float-gate %s %s." % ("ABC"[e[1]], "rises" if e[2] else "sinks back down"))
            elif k == "eel_hears":
                lines.append("Something blind turns toward a ripple.")
            elif k == "pebble":
                lines.append("You pick up a pebble.")
            elif k == "found":
                lines.append("You find one of your people in the dark. They take your hand.")
            elif k == "saved":
                lines.append("One of the Still climbs into the draught, toward the air.")
                c = self.center(self.level.exit)
                self.fx.emit(c[0], c[1], (230, 230, 210), n=14, speed=30, life=0.9, gravity=-40)
            elif k == "kin_taken":
                lines.append("An eel takes one of your people.")
                c = self.center(e[2])
                self.fx.emit(c[0], c[1], BAD, n=16, speed=40, life=0.6)
        if lines:
            self.say("  ".join(lines), TEXT)

    def _chamber_done(self):
        if self.run.index == self.run.chambers - 1 and self.run.choice is None:
            self.app.push(ChoiceCard(self.app, "The break", self._break_text(),
                                     [("Take them through", lambda: self._at_the_break("through")),
                                      ("Let them stay", lambda: self._at_the_break("stay"))], color=GOOD))
            return
        sim = self.sim
        saved, pop = sim.count("saved"), self.level.population
        self.run.finish(sim)
        if self.run.state == "done":
            night = self.app.in_night()
            if self.run.choice == "stay":
                text, title = sw.ENDING_STAY, "In the last of the light"
            else:
                lamps = not night or self.app.campaign.aurel_near()
                text = sw.ENDING_SOME if self.run.saved < self.run.total else \
                    (sw.ENDING_ALL if lamps else sw.ENDING_ALL_DARK)
                title = "Out of the dark"
            text += "  (%d of %d of the Still came to the break with you.%s)" % (
                self.run.saved, self.run.total, "" if night else " End of the prototype.")
            self.app.push(Card(self.app, title, text, "Continue  (Enter)", self.app.home, color=GOOD))
        else:
            text = "%d of the %d Still in this chamber made it up with you. The light will last about %d more " \
                   "turns." % (saved, pop, self.run.night)
            self.app.push(Card(self.app, "%s: through" % self.level.name, text, "Next chamber  (Enter)",
                               self.next_chamber, color=GOOD if saved == pop else WARN))

    def _break_text(self):
        """What Tarn can see through the break, and the choice it leaves him."""
        if self.app.in_night() and self.app.campaign.aurel_near():
            sight = ("Far down the Spindle there is a golden glow, and beside it, lamps: someone has lit the bottom "
                     "of the stair.")
        elif self.app.in_night():
            sight = ("Beyond the break the Spindle drops into the dark, and far below, nobody has lit the stair. If "
                     "no one comes down it, they will be stranded at the bottom of the world, without even the water.")
        else:
            sight = "Beyond the break the Spindle drops into the dark, toward a golden glow far below."
        return sight + " Take your people through? Or let them stay here, in the light, for as long as it lasts?"

    def _at_the_break(self, choice):
        self.run.choice = choice
        if self.app.in_night():
            self.app.campaign.still_choice = choice
        self.app.replace(self)
        self._chamber_done()

    def _dawn(self):
        self.sim.over = "caught"
        if self.app.in_night():
            self.app.campaign.check_thread()
            text = "The thread has run out. The light drains out of the water around you."
        else:
            text = sw.ENDING_DAWN + "  You brought %d of the Still up before it happened." % self.run.saved
        self.app.push(Card(self.app, "The light is gone", text, "Continue  (Enter)", self.app.home, color=BAD))

    def next_chamber(self):
        if self.app.in_night():
            self.app.to_night()
            return
        run = self.run
        key = run.index if run.index in sw.INTERLUDES else ("last" if run.index == run.chambers - 1 else None)
        self.app.tell(self.app.unseen("still:%s" % key, sw.INTERLUDES.get(key)),
                      lambda: self.app.replace(StillScreen(self.app, run)), title="Tarn")

    def step_back(self):
        """Undo the last few turns (an eel, a wrong turn). The turns already spent stay spent."""
        if self.sim.over == "out" or self.run.state != "playing":
            return
        if not self.history:
            self.say("Nothing to step back from yet.", WARN)
            return
        n = min(BACK_STEPS, len(self.history))
        self.sim = self.history[-n]
        del self.history[-n:]
        self.anim = self.kin_anim = 1.0
        self.throwing = False
        self.confirm_leave = False
        self.say("The Still pull you back: %d turn%s undone. The night does not give %s back." %
                 (n, "" if n == 1 else "s", "it" if n == 1 else "them"), ACCENT)

    def restart(self):
        self.app.replace(StillScreen(self.app, self.run, self.level, announce=False))

    # ------------------------------------------------------------ input
    def handle(self, ev):
        if self.intro:
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                self.app.home()
            elif ev.type == pygame.KEYDOWN or (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1):
                self.intro = False
            return True
        if ev.type != pygame.KEYDOWN:
            return super().handle(ev)
        k = ev.key
        if k == pygame.K_ESCAPE:
            if self.throwing:
                self.throwing = False
                self.say("You keep the pebble.", DIM)
            else:
                self.app.home()
            return True
        if k == pygame.K_r or (self.sim.over == "caught" and k in (pygame.K_RETURN, pygame.K_KP_ENTER)):
            if self.run.state == "playing":
                self.restart()
            return True
        if k in (pygame.K_b, pygame.K_BACKSPACE):
            self.step_back()
            return True
        if self.sim.over:
            return True
        if self.throwing:
            if k in DIRKEYS:
                self.throwing = False
                self.act(("f",) + DIRKEYS[k])
            return True
        if k != pygame.K_RETURN and k != pygame.K_KP_ENTER:
            self.confirm_leave = False
        if k in DIRKEYS:
            self.act(("m",) + DIRKEYS[k])
        elif k in (pygame.K_SPACE, pygame.K_PERIOD):
            self.act(("w",))
        elif k == pygame.K_t:
            self.act(("t",))
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.act(("x",))
        elif k == pygame.K_f:
            msg = self.sim.validate(("f", 1, 0))
            if msg:
                self.say(msg, WARN)
            else:
                self.throwing = True
                self.say("Throw which way? (arrows; Esc keeps the pebble)", ACCENT)
        elif k == pygame.K_h:
            self.app.push(RulesCard(self.app, sw.TITLE, RULES))
        else:
            return False
        return True

    def update(self, dt):
        self.t += dt
        self.anim = min(1.0, self.anim + dt / STEP_TIME)
        self.kin_anim = min(1.0, self.kin_anim + dt / (STEP_TIME * 1.4 * sw.minutes_per_turn(self.sim.light)))
        if self.throw_fx:
            self.throw_fx[2] += dt
            if self.throw_fx[2] > 0.3:
                self.throw_fx = None
        self.fx.update(dt)
        return True

    # ------------------------------------------------------------ drawing
    def glow_map(self, fronts_only=False):
        """How brightly each tile shines right now: ripple fronts (sliding between turns) plus the wake."""
        sim = self.sim
        out = {}
        for r in sim.ripples:
            va = (sim.turn - 1 - r.born) + self.anim
            fade = {"wade": 0.75, "follow": 0.45}.get(r.source, 1.0)
            for p, d in r.dist.items():
                x = abs(d - va)
                if x < 1.4:
                    g = (1 - x / 1.4) * (1 - d / (r.reach + 2)) * fade
                    if g > out.get(p, 0):
                        out[p] = g
        if fronts_only:
            return out
        for p, tl in sim.lit.items():
            age = sim.turn - 1 - tl + self.anim
            if 0 <= age <= sim.wake:
                g = 0.24 * (1 - age / (sim.wake + 1))      # the wake: visible to the Still until it fades
                if g > out.get(p, 0):
                    out[p] = g
        return out

    def _front_glow(self):
        lv = self.level
        w, h = lv.size
        small = pygame.Surface((w, h))
        small.fill((0, 0, 0))
        dim = self.sim.light                                  # the water dims as the night runs down
        for p, g in self.glow_map(fronts_only=True).items():
            if p in lv.water:
                small.set_at(p, scale_color(GLOW, min(1.0, g * 1.2 * dim)))
        return pygame.transform.smoothscale(small, (w * self.ts, h * self.ts))

    def _build_static(self):
        """The cave at full light: rough limestone, stone ledges, black water with a few motes."""
        lv, ts = self.level, self.ts
        w, h = lv.size
        rng = random.Random(sum(ord(c) for c in lv.name) + w * h)
        s = pygame.Surface((w * ts, h * ts))
        s.fill((0, 0, 0))
        for y in range(h):
            for x in range(w):
                p = (x, y)
                r = pygame.Rect(x * ts, y * ts, ts, ts)
                if p in lv.walls:
                    if not any((x + dx, y + dy) not in lv.walls and 0 <= x + dx < w and 0 <= y + dy < h
                               for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                        continue
                    v = rng.randint(-10, 10)
                    pygame.draw.rect(s, (96 + v, 100 + v, 104 + v), r)
                    for _ in range(3):                                  # pits and seams in the limestone
                        cx, cy = r.x + rng.randint(3, ts - 4), r.y + rng.randint(3, ts - 4)
                        pygame.draw.circle(s, (70 + v, 74 + v, 80 + v), (cx, cy), rng.randint(1, 3))
                    pygame.draw.line(s, (124, 128, 132), r.topleft, r.topright)
                elif p in lv.water:
                    pygame.draw.rect(s, (60, 120, 150), r)
                    for _ in range(2):
                        s.set_at((r.x + rng.randint(1, ts - 2), r.y + rng.randint(1, ts - 2)), (150, 210, 230))
                else:
                    v = rng.randint(-8, 8)
                    pygame.draw.rect(s, (120 + v, 116 + v, 110 + v), r)
                    pygame.draw.rect(s, (92 + v, 88 + v, 84 + v), r, 1)
        return s

    def _light(self, glow):
        sim, lv = self.sim, self.level
        w, h = lv.size
        small = pygame.Surface((w, h))
        small.fill((0, 0, 0))
        for p in sim.seen:
            g = glow.get(p, 0.0)
            if p in lv.walls:
                g = max([glow.get((p[0] + dx, p[1] + dy), 0.0) for dx, dy in sw.DIRS + sw.DIAGS]) * 0.8
            if p in lv.water:
                c = (int(40 + 215 * g), int(46 + 209 * g), int(56 + 199 * g))
            else:
                k = min(1.0, 0.16 + 0.8 * g)
                c = (int(255 * k), int(255 * k), int(255 * k))
            small.set_at(p, c)
        return pygame.transform.smoothscale(small, (w * self.ts, h * self.ts))

    def draw(self, surf):
        sim, lv = self.sim, self.level
        surf.fill((2, 3, 6))
        if self._static is None:
            self._static = self._build_static()
        glow = self.glow_map()
        ts = self.ts
        lit = self._static.copy()
        lit.blit(self._light(glow), (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        lit.blit(self._front_glow(), (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        surf.blit(lit, (self.ox, self.oy))
        self._draw_way_up(surf)
        for j, gp in enumerate(lv.gates):
            if gp in sim.seen:
                self._draw_gate(surf, j, gp)
        for j, bp in enumerate(lv.basins):
            if bp in sim.seen:
                c = self.center(bp)
                up = sim.gate_open(j)
                pygame.draw.circle(surf, (70, 78, 86) if not up else (220, 240, 250), c, ts // 3)
                pygame.draw.circle(surf, GLOW if up else (40, 48, 56), c, ts // 3, 2)
                draw_text(surf, self.app.bold[16], "abc"[j], c, (20, 24, 30) if up else (120, 130, 140), center=True)
                if up:
                    add_glow(surf, c, ts, (40, 90, 110))
        for p in sim.floor_pebbles:
            if p in sim.seen:
                pygame.draw.circle(surf, (150, 150, 150), self.center(p), 3)
        for e in sim.eels:
            if sim.eel_visible(e) or sim.over == "caught":
                self._draw_eel(surf, e)
        for k in sim.kin:
            self._draw_kin(surf, k)
        pc = self.center(sim.player)
        add_glow(surf, pc, int(ts * 1.2), (24, 32, 40))
        img = pygame.Surface((28, 28), pygame.SRCALPHA)
        draw_still(img, 14, 14, self.t, reach=self.sim.is_water(sim.player), color=(236, 240, 246))
        img = pygame.transform.scale(img, (int(28 * ts / 22), int(28 * ts / 22)))
        surf.blit(img, img.get_rect(center=pc))
        if self.throw_fx:
            a, b, el = self.throw_fx
            k = ease_out(el / 0.3)
            ca, cb = self.center(a), self.center(b)
            x, y = lerp(ca[0], cb[0], k), lerp(ca[1], cb[1], k) - math.sin(math.pi * k) * ts
            pygame.draw.circle(surf, (220, 220, 220), (int(x), int(y)), 3)
        self.fx.draw(surf)
        self._draw_hud(surf)
        if self.intro:
            self._draw_intro(surf)

    def _draw_intro(self, surf):
        from ..theme import draw_glow_text, draw_panel
        from ..widgets import tint
        tint(surf, surf.get_rect(), (2, 4, 8), 150)
        box = pygame.Rect(W // 2 - 320, 190, 640, 250)
        draw_panel(surf, box, fill=(14, 20, 28), edge=(80, 130, 160))
        n = self.run.index + 1
        draw_glow_text(surf, self.app.bold[32], "Chamber %d of %d: %s" % (n, self.run.chambers, self.level.name),
                       (W // 2, box.y + 40), GLOW)
        text = self.level.hint + "  (%d of your people here.)" % self.level.population
        draw_wrapped(surf, self.app.italic[22], text, (box.x + 40, box.y + 78), box.w - 80, TEXT, spacing=4)
        draw_text(surf, self.app.bold[18], "Any key to begin", (W // 2, box.bottom - 26), DIM, center=True)

    def _draw_way_up(self, surf):
        """The way on is always marked: a shaft of pale air you can feel before you can see it."""
        c = self.center(self.level.exit)
        k = 0.65 + 0.35 * math.sin(self.t * 2)
        add_glow(surf, c, int(self.ts * 2.2), scale_color((110, 104, 80), k))
        shaft = pygame.Surface((self.ts, c[1] - TOP), pygame.SRCALPHA)
        for y in range(shaft.get_height()):
            a = int(60 * k * (y / max(1, shaft.get_height())))
            pygame.draw.line(shaft, (230, 220, 180, a), (self.ts // 2 - 3, y), (self.ts // 2 + 3, y))
        surf.blit(shaft, (c[0] - self.ts // 2, TOP))
        draw_text(surf, self.app.bold[22], "^", (c[0], c[1] - 2), (240, 230, 190), center=True)

    def _draw_kin(self, surf, k):
        if k.state in ("saved", "lost"):
            return
        stranded = k.state == "stranded"
        if stranded and k.pos not in self.sim.seen:
            return
        c = self.center(k.pos)
        prev = self.kin_prev.get(k.key)
        if prev is not None and prev != k.pos and self.kin_anim < 1.0:
            q = ease_out(self.kin_anim)
            p0 = self.center(prev)
            c = (int(lerp(p0[0], c[0], q)), int(lerp(p0[1], c[1], q)))
        img = pygame.Surface((28, 28), pygame.SRCALPHA)
        draw_still(img, 14, 14, self.t + hash(k.key) % 7, color=(170, 178, 190) if not stranded else (120, 126, 136))
        img = pygame.transform.scale(img, (int(24 * self.ts / 22), int(24 * self.ts / 22)))
        surf.blit(img, img.get_rect(center=c))
        in_dark = stranded or not (self.sim.visible_to_kin(k.pos) or k.pos in getattr(self.sim, "_held", ()))
        if in_dark:
            draw_text(surf, self.app.bold[18], "?", (c[0] + self.ts // 3, c[1] - self.ts // 2), WARN, center=True)

    def _draw_gate(self, surf, j, p):
        r = self.rect(p)
        if self.sim.gate_open(j):
            pygame.draw.rect(surf, (90, 100, 110), (r.x, r.y, r.w, 4))
        else:
            pygame.draw.rect(surf, (60, 66, 74), r)
            for x in range(r.x + 3, r.right - 2, 5):
                pygame.draw.line(surf, (100, 108, 116), (x, r.y), (x, r.bottom - 2), 2)
        draw_text(surf, self.app.bold[16], "ABC"[j], r.center, ACCENT, center=True)

    def _draw_eel(self, surf, e):
        c = self.center(e.pos)
        ts = self.ts
        pts = [(c[0] - ts // 2 + 3 + i * 3, c[1] + math.sin(self.t * 6 + i) * 3) for i in range(ts // 3)]
        if len(pts) > 1:
            pygame.draw.lines(surf, (30, 44, 52), False, pts, 5)
            pygame.draw.lines(surf, (70, 96, 110), False, pts, 1)
        eye = (240, 90, 80) if e.target else (150, 160, 170)
        pygame.draw.circle(surf, eye, (int(pts[-1][0]), int(pts[-1][1]) - 1), 2)

    def _draw_hud(self, surf):
        sim, run = self.sim, self.run
        surf.blit(vertical_gradient((W, TOP), (16, 22, 30), (6, 8, 12)), (0, 0))
        pygame.draw.line(surf, (60, 90, 110), (0, TOP - 1), (W, TOP - 1))
        draw_text(surf, self.app.bold[22], "Stillwater", (12, 5), GLOW)
        draw_text(surf, self.app.italic[16], "Chamber %d of %d: %s" % (run.index + 1, run.chambers, self.level.name),
                  (12, 25), DIM)
        following, saved = sim.count("following"), sim.count("saved")
        draw_text(surf, self.app.bold[18], "With you %d   Saved %d   Lost %d" % (following, saved, sim.count("lost")),
                  (300, 6), TEXT)
        draw_text(surf, self.app.italic[16], "the water's light: %d%%   a turn costs %.1f%s" %
                  (round(100 * sim.light), sw.minutes_per_turn(sim.light), " min" if self.app.in_night() else ""),
                  (640, 30),
                  GLOW if sim.light > 0.75 else WARN)
        stranded = sim.count("stranded")
        draw_text(surf, self.app.italic[16], "%d still in the dark somewhere" % stranded if stranded else
                  "everyone here is found", (300, 25), WARN if stranded else DIM)
        frac = run.night / max(1, run.night_start)                # the night: how long the light will last
        bx = 640
        pygame.draw.rect(surf, (20, 28, 38), (bx, 12, 200, 16), border_radius=4)
        pygame.draw.rect(surf, GLOW if frac > 0.2 else BAD, (bx, 12, int(200 * frac), 16), border_radius=4)
        label = ("thread %s" % self.app.campaign.thread.hm()) if self.app.in_night() else "light left: %d turns" % run.night
        draw_text(surf, self.app.fonts[18], label, (bx + 100, 20), (10, 14, 20)
                  if frac > 0.5 else TEXT, center=True)
        for i in range(sim.pebbles):
            pygame.draw.circle(surf, (190, 190, 190), (862 + i * 12, 20), 4)
        surf.blit(vertical_gradient((W, BOTTOM), (6, 8, 12), (12, 16, 22)), (0, H - BOTTOM))
        draw_text(surf, self.app.fonts[18], "Goal: lead the Still to the way on (^), then go on (Enter).   Arrows move   "
                                            "Space wait   T touch   F throw   B step back   H rules",
                  (12, H - BOTTOM + 6), DIM)
        if self.msg:
            draw_wrapped(surf, self.app.fonts[18], self.msg, (12, H - BOTTOM + 26), W - 24, self.msg_color, spacing=0)
