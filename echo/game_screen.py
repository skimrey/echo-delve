"""The dungeon screen: drawing, input and turn messages.

Looks: textured stone, torches in sconces that Aurel lights as he passes, his lantern and the
torches as real light, smooth movement, and small animations for the story beats (the thread
pulling you back at the end of a loop, an echo burning away when unravelled).
All animation is cosmetic: the simulation has already moved on when it plays, so input is
never blocked by it.
"""

import math
import random

import pygame

from . import story
from .base import Screen
from .consts import (ENEMIES, GHOST_COLORS, GRID_H, GRID_W, LEVER_COLORS, MAX_FLOOR, PAIR_COLORS, POTION_HEAL,
                     TILE)
from .sim import ANCHOR, LETTERS, WAIT, move
from .theme import (BRONZE, GOLD, LANTERN, TORCH, Particles, add_glow, draw_echo, draw_enemy, draw_flag, draw_flame,
                    draw_glow_text, draw_heart, draw_hourglass, draw_lamplighter, draw_sconce, draw_still, ease_in_out,
                    ease_out, flicker, lerp, scale_color, text_surface, vertical_gradient)
from .vision import visible_tiles
from .widgets import (ACCENT, BAD, BG, DIM, GOOD, TEXT, THREAD, WARN, draw_spool, draw_text,
                      draw_wrapped, wrap_text)

OY = 44                     # the map starts below the top bar
MAP_W, MAP_H = GRID_W * TILE, GRID_H * TILE
BAR_Y = OY + MAP_H          # bottom bar

KEYMAP = {
    pygame.K_UP: (0, -1), pygame.K_w: (0, -1),
    pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0),
    pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1),
    pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0),
}

AMBIENT = (122, 112, 136)     # light level away from any flame (multiplied onto the map)
MOVE_TIME = 0.11            # seconds for a one-tile slide
BANNER_TIME = 4.6


def ghost_color(label):
    return GHOST_COLORS[(label - 1) % len(GHOST_COLORS)]


def lever_color(j):
    return LEVER_COLORS[j % len(LEVER_COLORS)]


def script_path(floor, actions, start=None, limit=None):
    """Tiles an echo walks when replaying `actions` from `start` (default: the entrance).
    A preview: it follows walls and levers but not doors or enemies, which can still block an echo."""
    x, y = start or floor.start
    pts = [(x, y)]
    for a in actions[:limit]:
        if a[0] == "m":
            nx, ny = x + a[1], y + a[2]
            if not floor.is_wall(nx, ny) and (nx, ny) not in floor.lever_at:
                x, y = nx, ny
                pts.append((x, y))
    return pts


# ---------------------------------------------------------------- the stone itself

def build_static(floor):
    """Bricks, flagstones and cobbles for a floor (cached on the floor: it never changes)."""
    cached = getattr(floor, "_static_surface", None)
    if cached is not None:
        return cached
    rng = random.Random(floor.seed * 7 + floor.index * 131)
    s = pygame.Surface((MAP_W, MAP_H))
    s.fill(BG)
    walls = floor.walls
    room_at = set()
    for rm in floor.rooms:
        room_at.update(rm.tiles())

    def wall(x, y):
        return not (0 <= x < GRID_W and 0 <= y < GRID_H) or walls[y][x]

    for y in range(GRID_H):
        for x in range(GRID_W):
            r = pygame.Rect(x * TILE, y * TILE, TILE, TILE)
            if wall(x, y):
                near = any(not wall(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))
                if not near:
                    continue
                if not wall(x, y + 1):
                    _brick_face(s, r, rng)
                else:
                    base = 50 + rng.randint(-3, 3)
                    pygame.draw.rect(s, (base, base - 6, base + 4), r)
                    for (dx, dy), edge in (((-1, 0), (r.topleft, r.bottomleft)), ((1, 0), (r.topright, r.bottomright)),
                                           ((0, -1), (r.topleft, r.topright))):
                        if not wall(x + dx, y + dy):
                            pygame.draw.line(s, (104, 92, 96), edge[0], edge[1], 2)
                continue
            if (x, y) in room_at:
                v = rng.randint(-6, 6)
                base = (112 + v, 99 + v, 90 + v)
                pygame.draw.rect(s, base, r)
                pygame.draw.line(s, scale_color(base, 0.72), r.topright, r.bottomright)
                pygame.draw.line(s, scale_color(base, 0.72), r.bottomleft, r.bottomright)
                pygame.draw.line(s, scale_color(base, 1.12), (r.x + 1, r.y + 1), (r.right - 2, r.y + 1))
                roll = rng.random()
                if roll < 0.12:
                    x0, y0 = r.x + rng.randint(4, 12), r.y + rng.randint(4, 12)
                    pygame.draw.lines(s, scale_color(base, 0.6), False,
                                      [(x0, y0), (x0 + rng.randint(2, 6), y0 + rng.randint(1, 5)),
                                       (x0 + rng.randint(5, 10), y0 + rng.randint(3, 9))])
                elif roll < 0.2:
                    for _ in range(3):
                        s.set_at((r.x + rng.randint(2, 21), r.y + rng.randint(2, 21)), (70, 88, 60))
            else:
                v = rng.randint(-4, 4)
                pygame.draw.rect(s, (74 + v, 67 + v, 68 + v), r)
                for _ in range(3):
                    cx, cy = r.x + rng.randint(3, 17), r.y + rng.randint(3, 17)
                    c = 94 + rng.randint(-6, 8)
                    pygame.draw.rect(s, (c, c - 4, c - 2), (cx, cy, rng.randint(4, 7), rng.randint(3, 6)), border_radius=2)
            # soft shadow under walls
            if wall(x, y - 1):
                for k in range(5):
                    shade = pygame.Surface((TILE, 1), pygame.SRCALPHA)
                    shade.fill((0, 0, 0, 90 - k * 18))
                    s.blit(shade, (r.x, r.y + k))
            if wall(x - 1, y):
                shade = pygame.Surface((3, TILE), pygame.SRCALPHA)
                shade.fill((0, 0, 0, 50))
                s.blit(shade, r.topleft)
    # the knot: where the thread is tied, and where every loop begins
    cx, cy = floor.start[0] * TILE + TILE // 2, floor.start[1] * TILE + TILE // 2
    pygame.draw.circle(s, (86, 62, 96), (cx, cy), 10, 1)
    pygame.draw.circle(s, (120, 84, 130), (cx, cy), 6, 1)
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        pygame.draw.line(s, (100, 72, 110), (cx + math.cos(a) * 6, cy + math.sin(a) * 6),
                         (cx + math.cos(a) * 10, cy + math.sin(a) * 10))
    floor._static_surface = s
    return s


def _brick_face(s, r, rng):
    pygame.draw.rect(s, (52, 42, 46), r)
    pygame.draw.rect(s, (44, 38, 46), (r.x, r.y, r.w, 5))
    pygame.draw.line(s, (96, 84, 90), (r.x, r.y), (r.right - 1, r.y))
    row_h = 6
    for row, y in enumerate(range(r.y + 5, r.bottom, row_h)):
        off = 0 if row % 2 == 0 else 6
        for bx in range(r.x - off, r.right, 12):
            v = rng.randint(-8, 8)
            c = (112 + v, 92 + v, 86 + v)
            rect = pygame.Rect(bx + 1, y + 1, 11, row_h - 1).clip(r)
            if rect.w > 1:
                pygame.draw.rect(s, c, rect)
                pygame.draw.line(s, scale_color(c, 1.18), rect.topleft, (rect.right - 1, rect.top))


# ---------------------------------------------------------------- the screen

class GameScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.run = app.run
        self.effects = []              # [kind, data..., ttl]
        self.confirm = False
        self.show_paths = True
        self.hover_tile = None
        self.visible = set()
        self.fog = None
        self.t = 0.0
        self.particles = Particles()
        self.tweens = {}               # actor key -> [from tile, to tile, elapsed]
        self.lunges = {}               # actor key -> [dx, dy, elapsed]
        self.story_fx = None           # rewind / unravel animation
        self.ghost_fade = 1.0          # the victory scene dissolves echoes
        self.banner = BANNER_TIME
        self._still_spots = None
        self.torches = self.run.torches
        self.ignite = {}               # torch -> seconds since it was lit
        self.shown_lit = set(self.run.lit)   # sconces whose lighting has been shown
        self.door_anim = [0.0 if self.run.sim.door_open(i) else 1.0 for i in range(len(self.run.floor.doors))]
        self.gate_anim = [0.0 if self.run.sim.gate_open(j) else 1.0 for j in range(len(self.run.floor.gates))]
        self.static = build_static(self.run.floor)
        self.light = pygame.Surface((MAP_W, MAP_H))
        x = 516
        for label, w, tag, cb in (("Wait", 62, "wait", lambda: self.act(WAIT)),
                                  ("Anchor", 76, "anchor", self.request_anchor),
                                  ("Unravel", 82, "unravel", self.request_unravel),
                                  ("Paths", 66, "paths", self.toggle_paths),
                                  ("Help", 54, "help", app.show_help),
                                  ("Menu", 60, "menu", app.pause)):
            self.add((x, BAR_Y + 6, w, 30), label, cb, tag=tag)
            x += w + 7
        self.reveal()
        self.say(self.floor_hint())

    def floor_hint(self):
        f, n = self.run.floor, self.run.floor_no
        still = self.still_here()
        if still:
            return ("The Loom's hall. The Still are here: %d of them slid down the Spindle and are waiting by the "
                    "Loom, to climb home by your lamps." % self.app.campaign.still.saved)
        if f.gates and f.doors:
            return ("Floor %d. Reach the gold stairs. Doors open while something stands on their plate; "
                    "gates flip when their lever is pulled (walk into it)." % n)
        if f.gates:
            return ("Floor %d. A gate bars the way: find its lever and walk into it to pull it. It is too far "
                    "to pull and still make the stairs in one loop, so leave it to an echo." % n)
        return "Floor %d. Reach the gold stairs. Doors open while something stands on their plate." % n

    def arrival_text(self):
        """The floor's line of story (in The Long Night, the keeper's window shows whether the Still
        have already gone through the break)."""
        n = self.run.floor_no
        if n == 5 and self.app.in_night() and self.app.campaign.still.state == "done" and \
                self.app.campaign.still_choice != "stay":
            return story.STILL_GONE_ARRIVAL
        return story.floor_arrival(n)

    def still_here(self):
        """The Long Night: once Tarn has brought the Still through the break, they wait in the Loom's
        hall on Aurel's last floor (a few figures stand for all of them). Tiles near the stairs."""
        if self._still_spots is None:
            self._still_spots = []
            app = self.app
            if app.in_night() and self.run.last_floor:
                c = app.campaign
                if c.still.state == "done" and c.still.saved and c.still_choice != "stay":
                    self._still_spots = self._spots_near_exit(min(7, c.still.saved))
        return self._still_spots

    def _spots_near_exit(self, n):
        f = self.run.floor
        busy = set(f.doors) | set(f.plates) | set(f.gates) | set(f.levers) | set(f.spikes) | {f.start, f.exit}
        busy |= {(x, y) for _k, x, y in f.spawns}
        dist, frontier, out = {f.exit: 0}, [f.exit], []
        while frontier and len(out) < n:
            nxt = []
            for p in frontier:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    q = (p[0] + dx, p[1] + dy)
                    if q in dist or f.is_wall(*q) or q in f.door_at or q in f.gate_at:
                        continue
                    dist[q] = dist[p] + 1
                    nxt.append(q)
                    if dist[q] >= 2 and q not in busy and len(out) < n:
                        out.append(q)
            frontier = nxt
        return out

    # ------------------------------------------------------------ geometry
    def tile_rect(self, gx, gy):
        return pygame.Rect(gx * TILE, OY + gy * TILE, TILE, TILE)

    def tile_center(self, pos):
        r = self.tile_rect(*pos)
        return r.center

    def tile_at(self, pos):
        gx, gy = pos[0] // TILE, (pos[1] - OY) // TILE
        if 0 <= gx < GRID_W and 0 <= gy < GRID_H and pos[1] >= OY:
            return (gx, gy)
        return None

    def actor_px(self, a):
        """Where to draw an actor right now: mid-slide or mid-lunge if it just acted."""
        cx, cy = self.tile_center(a.pos)
        tw = self.tweens.get(a.key)
        if tw is not None:
            k = ease_out(tw[2] / MOVE_TIME)
            fx, fy = self.tile_center(tw[0])
            cx, cy = lerp(fx, cx, k), lerp(fy, cy, k)
        ln = self.lunges.get(a.key)
        if ln is not None:
            k = math.sin(math.pi * min(1.0, ln[2] / 0.16))
            cx, cy = cx + ln[0] * 7 * k, cy + ln[1] * 7 * k
        return int(cx), int(cy)

    # ------------------------------------------------------------ state
    def reveal(self):
        sim = self.run.sim
        self.visible = visible_tiles(sim.player.pos, self.run.sight, sim.blocks_sight) | self.run.lamp_glow()
        self.run.seen |= self.visible
        for tp in sorted(self.run.lit - self.shown_lit):      # sconces the run just lit: they flare up
            self.shown_lit.add(tp)
            self.ignite[tp] = 0.0
            cx, cy = self.tile_center(tp)
            self.particles.emit(cx, cy + 2, TORCH, n=14, speed=50, life=0.7, size=2, gravity=-40)
        self._build_fog()

    def _build_fog(self):
        fog = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
        seen, vis = self.run.seen, self.visible
        for y in range(GRID_H):
            for x in range(GRID_W):
                p = (x, y)
                if p in vis:
                    continue
                r = pygame.Rect(x * TILE, y * TILE, TILE, TILE)
                fog.fill((*BG, 255) if p not in seen else (6, 4, 10, 96), r)
        self.fog = fog

    # ------------------------------------------------------------ actions
    def act(self, action):
        if self.confirm:
            self.confirm = False
        sim = self.run.sim
        before = {a.key: a.pos for a in [sim.player] + sim.ghosts + sim.enemies}
        r = self.run.act(action)
        if r.message:
            self.say(r.message, BAD)
            return r
        self.banner = min(self.banner, 0.7)
        if self.run.sim is sim:
            for a in [sim.player] + sim.ghosts + sim.enemies:
                old = before.get(a.key)
                if old and old != a.pos and abs(old[0] - a.pos[0]) + abs(old[1] - a.pos[1]) == 1:
                    self.tweens[a.key] = [old, a.pos, 0.0]
        else:
            self.tweens.clear()
            self.lunges.clear()
        self.after(r)
        return r

    def after(self, r):
        run = self.run
        if self.app.in_night() and self.app.campaign.check_thread() != "night":
            self.app.to_night()                       # the last day ran out
            return
        self._effects_from(r.events)
        lines = self.describe(r.events)
        if r.ended:
            n = run.play.last_label
            if r.ended == "exit":
                lines.append("You reach the stairs!")
            elif r.ended == "anchor":
                lines.append("Echo %d anchored." % n)
            elif r.ended == "timeout":
                lines.append("The loop collapsed: echo %d holds where you stood." % n)
            elif r.ended == "dead":
                lines.append("You fell. Echo %d replays that loop and fades when you did." % n)
            if run.state == "playing":
                lines.append(self.loop_begins())
                self._start_rewind(r.ended)
            elif run.state == "unravel":
                lines.append("Your echo slots are full: unravel one echo to go on.")
        self.say("  ".join(lines[-4:]) if lines else "", BAD if r.ended == "dead" else TEXT)
        if run.state != "playing":
            if run.state == "unravel":
                self.reveal()
            self.app.after_act()
            return
        self.reveal()
        self.app.dirty = True

    def loop_begins(self):
        play = self.run.play
        if play.last_loop:
            return ("Loop %d begins. Every echo slot is full: this is your last loop unless you "
                    "unravel an echo (U)." % play.loop_no)
        return "Loop %d begins (next echo: %d)." % (play.loop_no, play.free_label())

    def after_unravel(self, script):
        """Called once run.unravel() has erased `script` and a fresh loop has begun."""
        run = self.run
        self.confirm = False
        self.effects = []
        self.tweens.clear()
        self.lunges.clear()
        self.reveal()
        pts = script_path(run.floor, script.actions)
        self.story_fx = dict(kind="unravel", t=0.0, dur=1.3, path=pts, color=ghost_color(script.label),
                             label=script.label, loop=run.play.loop_no)
        self.say("Echo %d unravelled (%s). %s" % (script.label, run.thread_left_text(), self.loop_begins()), ACCENT)

    def _start_rewind(self, ended):
        """The thread reels you back to the knot; the loop you played stays behind as an echo."""
        play = self.run.play
        s = play.script(play.last_label)
        if s is None:
            return
        pts = script_path(self.run.floor, s.actions)
        self.story_fx = dict(kind="rewind", t=0.0, dur=1.25, path=pts, color=ghost_color(s.label),
                             label=s.label, loop=play.loop_no, dead=ended == "dead", emitted=False)
        ex, ey = self.tile_center(pts[-1])
        self.particles.emit(ex, ey, BAD if ended == "dead" else THREAD, n=22, speed=60, life=0.8)

    def describe(self, events):
        sim = self.run.sim
        kinds = {e.key: ENEMIES[e.kind]["name"] for e in sim.enemies}

        def name(key):
            if key == "P":
                return "You"
            if key.startswith("G"):
                return "Echo " + key[1:]
            return kinds.get(key, "Enemy")

        out = []
        for e in events:
            k = e[0]
            if k == "attack":
                out.append("%s hit%s %s (-%d)." % (name(e[1]), "" if e[1] == "P" else "s",
                                                   name(e[2]).lower() if e[2] == "P" else name(e[2]), e[3]))
            elif k == "shot":
                out.append("%s shoots %s." % (name(e[1]), name(e[2]).lower() if e[2] == "P" else name(e[2])))
            elif k == "died":
                out.append("%s dies." % kinds.get(e[1], "Enemy"))
            elif k == "wake":
                out.append("%s wakes." % name(e[1]))
            elif k == "potion":
                out.append("Potion: +%d HP." % e[1])
            elif k == "door":
                out.append("Door %d %s." % (e[1] + 1, "opens" if e[2] else "closes"))
            elif k == "lever":
                c = LETTERS[e[2]]
                out.append("%s pull%s lever %s: gate %s %s." % (name(e[1]), "" if e[1] == "P" else "s", c, c,
                                                                "opens" if e[3] else "shuts"))
            elif k == "gate":
                if not any(x[0] == "lever" and x[2] == e[1] for x in events):
                    out.append("Gate %s %s." % (LETTERS[e[1]], "opens" if e[2] else "shuts"))
            elif k == "spike":
                out.append("%s hurt by spikes." % name(e[1]))
            elif k == "faded":
                out.append("Echo %s fades." % e[1][1:])
            elif k == "echo_lost":
                out.append("Echo %s is destroyed." % e[1][1:])
            elif k == "blocked":
                out.append("Echo %s is blocked!" % e[1][1:])
            elif k == "swing":
                out.append("%s swings at nothing." % name(e[1]))
        return out

    def _actor(self, key):
        sim = self.run.sim
        for a in [sim.player] + sim.ghosts + sim.enemies:
            if a.key == key:
                return a
        return None

    def _effects_from(self, events):
        for e in events:
            k = e[0]
            if k == "hurt":
                self.effects.append(["float", e[3], "-%d" % e[2], BAD if e[1][0] in "PG" else WARN, 0.7])
                cx, cy = self.tile_center(e[3])
                self.particles.emit(cx, cy, (220, 60, 50) if e[1][0] in "PG" else (250, 170, 80), n=6, speed=50, life=0.35)
            elif k == "attack":
                src = self._actor(e[1])
                if src is not None:
                    dx, dy = e[4][0] - src.x, e[4][1] - src.y
                    if abs(dx) + abs(dy) == 1:
                        self.lunges[e[1]] = [dx, dy, 0.0]
            elif k == "shot":
                self.effects.append(["line", e[3], e[4], (255, 150, 255), 0.35])
            elif k == "potion":
                self.effects.append(["float", e[2], "+%d" % e[1], GOOD, 0.8])
                cx, cy = self.tile_center(e[2])
                self.particles.emit(cx, cy, (130, 240, 140), n=12, speed=30, life=0.8, gravity=-30)
            elif k == "died":
                self.effects.append(["flash", e[-1], (255, 255, 255), 0.3])
                cx, cy = self.tile_center(e[-1])
                self.particles.emit(cx, cy, (90, 70, 80), n=14, speed=45, life=0.7, size=3)
                self.particles.emit(cx, cy, (255, 140, 60), n=6, speed=60, life=0.5)
            elif k in ("faded", "echo_lost"):
                self.effects.append(["flash", e[-1], (255, 255, 255), 0.3])
                cx, cy = self.tile_center(e[-1])
                label = int(e[1][1:]) if e[1][1:].isdigit() else 1
                self.particles.emit(cx, cy, ghost_color(label), n=16, speed=35, life=0.9, gravity=-25)
            elif k == "swing":
                self.effects.append(["flash", e[2], (200, 200, 200), 0.2])
                self.effects.append(["slash", e[2], 0.2])
            elif k == "spike":
                cx, cy = self.tile_center(e[2])
                self.particles.emit(cx, cy, (200, 60, 60), n=5, speed=40, life=0.3)
            elif k == "lever":
                cx, cy = self.tile_center(e[4])
                self.particles.emit(cx, cy - 4, lever_color(e[2]), n=10, speed=40, life=0.5)
                self.effects.append(["flash", e[4], lever_color(e[2]), 0.3])

    def request_anchor(self):
        run = self.run
        if run.state != "playing":
            return
        if not self.confirm:
            self.confirm = True
            warn = ""
            if run.play.last_loop:
                warn = ("LAST LOOP: anchoring fills your last slot, so you must then unravel an echo "
                        "(%s). " % run.unravel_cost_short() if run.can_afford_unravel() else
                        "LAST LOOP, not enough thread to unravel: anchoring ends the run! ")
            self.say(warn + "Press E (or click Anchor) again to end this loop and leave an echo here. "
                     "Anything else cancels.", WARN)
        else:
            self.confirm = False
            self.act(ANCHOR)

    def request_unravel(self):
        self.confirm = False
        problem = self.run.unravel_problem()
        if problem:
            self.say(problem, WARN)
            return
        self.app.open_unravel()

    def toggle_paths(self):
        self.show_paths = not self.show_paths
        self.say("Echo paths %s." % ("shown" if self.show_paths else "hidden"))

    def cancel_confirm(self, announce=True):
        if self.confirm:
            self.confirm = False
            if announce:
                self.say("Anchor cancelled.")
            return True
        return False

    def click_tile(self, t):
        p = self.run.sim.player.pos
        d = (t[0] - p[0], t[1] - p[1])
        if d == (0, 0):
            self.act(WAIT)
        elif abs(d[0]) + abs(d[1]) == 1:
            self.act(move(*d))
        else:
            self.say("Click a tile next to you to step or strike, or yourself to wait.", WARN)

    # ------------------------------------------------------------ input
    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            t = self.tile_at(ev.pos)
            if t != self.hover_tile:
                self.hover_tile = t
                self.app.dirty = True
            return super().handle(ev)
        if ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 1:
                b = self.button_at(ev.pos)
                if b is not None:
                    if b.tag != "anchor":
                        self.cancel_confirm(announce=False)
                    b.click()
                    self.app.dirty = True
                    return True
                t = self.tile_at(ev.pos)
                if t is not None:
                    self.click_tile(t)
                    return True
            elif ev.button == 3:
                if not self.cancel_confirm():
                    t = self.tile_at(ev.pos)
                    txt = self.describe_tile(t) if t else ""
                    self.say(txt or "Nothing to see there.")
                return True
            return False
        if ev.type == pygame.KEYDOWN:
            k = ev.key
            if k == pygame.K_ESCAPE:
                if not self.cancel_confirm():
                    self.app.pause()
                return True
            if k == pygame.K_e:
                self.request_anchor()
                return True
            if k == pygame.K_u:
                self.request_unravel()
                return True
            if self.confirm:
                self.cancel_confirm()
            if k in KEYMAP:
                self.act(move(*KEYMAP[k]))
            elif k in (pygame.K_SPACE, pygame.K_PERIOD, pygame.K_KP5):
                self.act(WAIT)
            elif k == pygame.K_TAB:
                self.toggle_paths()
            elif k == pygame.K_h:
                self.app.show_help()
            else:
                return False
            return True
        return False

    def update(self, dt):
        """Advance cosmetic animation. Always True: torches flicker, so the screen is never still."""
        self.t += dt
        for e in self.effects:
            e[-1] -= dt
        self.effects = [e for e in self.effects if e[-1] > 0]
        for key in list(self.tweens):
            self.tweens[key][2] += dt
            if self.tweens[key][2] >= MOVE_TIME:
                del self.tweens[key]
        for key in list(self.lunges):
            self.lunges[key][2] += dt
            if self.lunges[key][2] >= 0.16:
                del self.lunges[key]
        for tp in list(self.ignite):
            self.ignite[tp] += dt
            if self.ignite[tp] > 1.0:
                del self.ignite[tp]
        sim = self.run.sim
        step = dt * 6
        for i in range(len(self.door_anim)):
            target = 0.0 if sim.door_open(i) else 1.0
            cur = self.door_anim[i]
            self.door_anim[i] = min(target, cur + step) if target > cur else max(target, cur - step)
        for j in range(len(self.gate_anim)):
            target = 0.0 if sim.gate_open(j) else 1.0
            cur = self.gate_anim[j]
            self.gate_anim[j] = min(target, cur + step) if target > cur else max(target, cur - step)
        fx = self.story_fx
        if fx is not None:
            fx["t"] += dt
            self._story_particles(fx)
            if fx["t"] >= fx["dur"]:
                self.story_fx = None
        self.banner = max(0.0, self.banner - dt)
        # a few embers drift up from lit torches
        if self.torches and random.random() < dt * 6:
            lit = [tp for tp in self.torches if tp in self.run.lit]
            if lit:
                tp = random.choice(lit)
                cx, cy = self.tile_center(tp)
                self.particles.emit(cx + random.randint(-2, 2), cy - 2, (255, 150, 60), n=1, speed=10,
                                    life=1.1, size=1, gravity=-22, angle=-math.pi / 2, spread=0.8)
        self.particles.update(dt)
        return True

    def _story_particles(self, fx):
        p = fx["t"] / fx["dur"]
        pts = fx["path"]
        if fx["kind"] == "unravel":
            # the echo's route burns away from its end back to the knot, shedding fibres
            k = int(len(pts) * (1 - ease_in_out(min(1.0, p / 0.8))))
            if 0 <= k < len(pts):
                cx, cy = self.tile_center(pts[k])
                self.particles.emit(cx, cy, fx["color"], n=2, speed=30, life=0.7, gravity=-20)
        elif fx["kind"] == "rewind" and not fx.get("emitted") and p > 0.5:
            fx["emitted"] = True
            sx, sy = self.tile_center(self.run.floor.start)
            self.particles.emit(sx, sy, fx["color"], n=26, speed=55, life=0.9)

    # ------------------------------------------------------------ descriptions
    def describe_tile(self, t):
        if t is None:
            return ""
        run, sim, floor = self.run, self.run.sim, self.run.floor
        if t not in run.seen:
            return ""
        parts = []
        if t in self.visible:
            for e in sim.enemies:
                if e.alive and e.pos == t:
                    spec = ENEMIES[e.kind]
                    parts.append("%s %d/%d HP, %s. %s" % (spec["name"], e.hp, e.max_hp,
                                                          "awake" if e.awake else "asleep", story.ENEMY_LORE[e.kind]))
        if sim.player.pos == t:
            parts.append("You: %d/%d HP. %s, %s." % (sim.player.hp, sim.player.max_hp, story.HERO, story.ROLE))
        for g in sim.ghosts:
            if g.alive and g.pos == t:
                end = g.script.ending
                parts.append("Echo %d (%d HP): replays your loop %d, then %s." %
                             (g.script.label, g.hp, g.script.loop or g.script.label,
                              "stands where it ended" if end == "anchor" else "fades"))
        if t in floor.door_at:
            i = floor.door_at[t]
            parts.append("Door %d: %s. Opens while something stands on plate %d." %
                         (i + 1, "open" if sim.door_open(i) else "sealed", i + 1))
        if t in floor.plate_at:
            i = floor.plate_at[t]
            parts.append("Plate %d: %s. Holds door %d open." % (i + 1, "held" if sim.plate_held(i) else "empty", i + 1))
        if t in floor.gate_at:
            j = floor.gate_at[t]
            c = LETTERS[j]
            parts.append("Gate %s: %s. Each pull of lever %s flips it, and it stays that way for the rest of "
                         "the loop." % (c, "open" if sim.gate_open(j) else "shut", c))
            parts.extend(self._pull_schedule(j))
        if t in floor.lever_at:
            j = floor.lever_at[t]
            c = LETTERS[j]
            parts.append("Lever %s: walk into it to pull it. It flips gate %s (now %s)." %
                         (c, c, "open" if sim.gate_open(j) else "shut"))
            parts.extend(self._pull_schedule(j))
        if t == floor.exit:
            parts.append("The stairs down. Step here to finish the floor.")
        if t == floor.start:
            parts.append("The knot: where the thread is tied. Every loop begins here.")
        if t in sim.potions:
            parts.append("Potion: heals %d." % POTION_HEAL)
        if t in floor.spikes:
            parts.append("Spikes: %s now. They flip every 2 turns." %
                         ("UP (hurts)" if floor.spike_active(t, sim.turn) else "down"))
        if t in self.still_here():
            parts.append("One of the Still, pale and blinking at the Loom's light. They will climb home by your lamps.")
        if t in self.torches:
            parts.append("A sconce, %s." % ("lit by your hand. It shows what moves around it, wherever you are"
                                            if t in run.lit else "cold. Walk within two steps of it to light it"))
        return " ".join(parts)

    def _pull_schedule(self, j):
        """Which echoes pull lever j, and on which turns: the heart of a lever puzzle."""
        out = []
        for s in self.run.play.scripts:
            turns = [t for t, lv in s.pulls if lv == j]
            if turns:
                out.append("Echo %d pulls it on turn %s." % (s.label, ", ".join(str(t) for t in turns)))
        return out

    # ------------------------------------------------------------ drawing
    def draw(self, surf):
        run, sim, floor = self.run, self.run.sim, self.run.floor
        surf.fill(BG)
        surf.blit(self.static, (0, OY))
        seen, vis = run.seen, self.visible
        self._draw_features(surf, sim, floor, seen)
        self._draw_enemies(surf, sim, vis)
        self._draw_sconces(surf, seen, flames=False)
        self._apply_light(surf, sim, floor, seen)
        surf.blit(self.fog, (0, OY))
        self._draw_sconces(surf, seen, flames=True)
        if self.show_paths:
            self._draw_paths(surf, sim)
        self._draw_story_fx(surf, under=True)
        self._draw_ghosts(surf, sim)
        self._draw_still(surf, seen)
        self._draw_player(surf, sim)
        self.particles.draw(surf)
        self._draw_effects(surf)
        self._draw_story_fx(surf, under=False)
        self._draw_banner(surf)
        self._draw_hud(surf, run, sim)
        if self.app.in_night():
            self._draw_night_clock(surf)
        self._draw_lamp_count(surf)
        self._draw_tooltip(surf)
        self.draw_buttons(surf)

    def _draw_night_clock(self, surf):
        """The Long Night: what is left of the last day, shared by all three stories."""
        thread = self.app.campaign.thread
        box = pygame.Rect(960 - 176, OY + 6, 170, 26)
        pygame.draw.rect(surf, (20, 16, 22), box, border_radius=6)
        pygame.draw.rect(surf, GOLD, box, 1, border_radius=6)
        draw_text(surf, self.app.bold[18], "Thread  %s" % thread.hm(), box.center, GOLD, center=True)

    def _draw_lamp_count(self, surf):
        """How many of this floor's sconces are lit (each one is worth points, and in The Long Night
        the Still climb the stair by them)."""
        total = len(self.torches)
        if not total:
            return
        lit = len(self.run.lit)
        w = 92
        x = 960 - 6 - w - (176 if self.app.in_night() else 0)
        box = pygame.Rect(x, OY + 6, w, 26)
        pygame.draw.rect(surf, (20, 16, 22), box, border_radius=6)
        pygame.draw.rect(surf, TORCH if lit == total else (96, 80, 64), box, 1, border_radius=6)
        draw_sconce(surf, box.x + 16, box.y + 11, lit > 0, self.t, 3, 0.8)
        draw_text(surf, self.app.bold[18], "%d/%d" % (lit, total), (box.x + 54, box.centery),
                  TORCH if lit == total else TEXT, center=True)

    def _apply_light(self, surf, sim, floor, seen):
        light = self.light
        light.fill(AMBIENT)
        t = self.t
        off = (0, -OY)
        for i, tp in enumerate(self.torches):
            if tp in self.run.lit and tp in seen:
                cx, cy = self.tile_center(tp)
                boost = 1.0 + 0.8 * max(0.0, 1 - self.ignite.get(tp, 1.0) / 0.6)
                add_glow(light, (cx + off[0], cy + off[1] + 8), TILE * 4.2 * flicker(t, i, 0.06) * boost,
                         scale_color(TORCH, 0.9 * boost))
        px, py = self.actor_px(sim.player)
        add_glow(light, (px, py + off[1]), TILE * (self.run.sight + 2) * flicker(t, 7.0, 0.04), LANTERN, 1.1)
        for g in sim.ghosts:
            if g.alive:
                gx, gy = self.actor_px(g)
                add_glow(light, (gx, gy + off[1]), 30, scale_color(ghost_color(g.script.label), 0.55))
        if floor.exit in seen:
            ex, ey = self.tile_center(floor.exit)
            add_glow(light, (ex, ey + off[1]), 54 * flicker(t, 3.0, 0.05), (200, 160, 70))
        for j, lp in enumerate(floor.levers):
            if lp in seen:
                cx, cy = self.tile_center(lp)
                add_glow(light, (cx, cy + off[1]), 26 if sim.gate_flipped[j] else 16, scale_color(lever_color(j), 0.45))
        for i, pp in enumerate(floor.plates):
            if pp in seen and sim.plate_held(i):
                cx, cy = self.tile_center(pp)
                add_glow(light, (cx, cy + off[1]), 30, scale_color(PAIR_COLORS[i % len(PAIR_COLORS)], 0.7))
        surf.blit(light, (0, OY), special_flags=pygame.BLEND_RGB_MULT)

    def _draw_sconces(self, surf, seen, flames):
        for i, tp in enumerate(self.torches):
            if tp not in seen:
                continue
            r = self.tile_rect(*tp)
            x, y = r.centerx, r.y + 10
            lit = tp in self.run.lit
            if not flames:
                draw_sconce(surf, x, y, False, self.t, i)
            elif lit:
                flare = 1.0 + 0.9 * max(0.0, 1 - self.ignite.get(tp, 1.0) / 0.5)
                draw_flame(surf, x, y, self.t, i, flare)

    def _draw_features(self, surf, sim, floor, seen):
        f = self.app.bold
        for i, (x, y) in enumerate(floor.plates):
            if (x, y) not in seen:
                continue
            r = self.tile_rect(x, y).inflate(-4, -4)
            c = PAIR_COLORS[i % len(PAIR_COLORS)]
            held = sim.plate_held(i)
            pygame.draw.rect(surf, (58, 52, 54), r, border_radius=3)
            pygame.draw.rect(surf, (90, 82, 80), r, 1, border_radius=3)
            inner = r.inflate(-6, -6)
            pygame.draw.rect(surf, c if held else scale_color(c, 0.3), inner, border_radius=3)
            pygame.draw.rect(surf, c, inner, 1, border_radius=3)
            draw_text(surf, f[16], i + 1, (r.centerx, r.centery), (20, 16, 20) if held else c, center=True)
        for i, (x, y) in enumerate(floor.doors):
            if (x, y) not in seen:
                continue
            self._draw_door(surf, i, x, y, sim)
        for j, (x, y) in enumerate(floor.gates):
            if (x, y) in seen:
                self._draw_gate(surf, j, x, y)
        for j, (x, y) in enumerate(floor.levers):
            if (x, y) in seen:
                self._draw_lever(surf, j, x, y, sim)
        for pos in floor.spikes:
            if pos not in seen:
                continue
            r = self.tile_rect(*pos)
            if floor.spike_active(pos, sim.turn):
                for k in range(3):
                    cx = r.x + 5 + k * 7
                    pygame.draw.polygon(surf, (150, 150, 160), [(cx - 3, r.bottom - 4), (cx + 3, r.bottom - 4), (cx, r.y + 4)])
                    pygame.draw.line(surf, (220, 70, 60), (cx, r.y + 4), (cx, r.y + 8), 2)
            else:
                soon = floor.spike_active(pos, sim.turn + 1)
                for k in range(3):
                    c = (r.x + 6 + k * 6, r.centery + 3)
                    pygame.draw.circle(surf, (24, 20, 24), c, 2)
                    pygame.draw.circle(surf, WARN if soon else (100, 92, 96), c, 3, 1)
        for pos in sim.potions:
            if pos in seen:
                cx, cy = self.tile_center(pos)
                pygame.draw.circle(surf, (200, 50, 80), (cx, cy + 3), 6)
                pygame.draw.circle(surf, (255, 130, 150), (cx - 2, cy + 1), 2)
                pygame.draw.rect(surf, (190, 180, 170), (cx - 2, cy - 6, 4, 5))
                pygame.draw.rect(surf, (130, 90, 60), (cx - 2, cy - 8, 4, 2))
        if floor.exit in seen:
            r = self.tile_rect(*floor.exit).inflate(-2, -2)
            for k in range(4):
                c = scale_color(GOLD, 1.0 - k * 0.2)
                pygame.draw.rect(surf, c, (r.x + k * 2, r.y + k * 5, r.w - k * 4, 5))
            pygame.draw.rect(surf, (30, 22, 14), (r.x + 8, r.bottom - 4, r.w - 16, 3))
            pygame.draw.rect(surf, (120, 90, 40), r, 1)

    def _draw_door(self, surf, i, x, y, sim):
        r = self.tile_rect(x, y)
        c = PAIR_COLORS[i % len(PAIR_COLORS)]
        down = self.door_anim[i] if i < len(self.door_anim) else (0.0 if sim.door_open(i) else 1.0)
        pygame.draw.rect(surf, (26, 22, 26), r)
        pygame.draw.rect(surf, scale_color(c, 0.8), r, 2)
        bar_h = int((r.h - 4) * down)
        if bar_h > 0:
            pygame.draw.rect(surf, scale_color(c, 0.22), (r.x + 2, r.y + 2, r.w - 4, bar_h))
            for bx in range(r.x + 5, r.right - 2, 5):
                pygame.draw.line(surf, (120, 114, 118), (bx, r.y + 2), (bx, r.y + 2 + bar_h), 2)
            pygame.draw.line(surf, (150, 144, 148), (r.x + 2, r.y + 2 + bar_h), (r.right - 3, r.y + 2 + bar_h), 2)
        label = pygame.Rect(0, 0, 13, 13)
        label.center = r.center
        pygame.draw.rect(surf, (18, 14, 18), label, border_radius=3)
        draw_text(surf, self.app.bold[16], i + 1, r.center, c, center=True)

    def _draw_gate(self, surf, j, x, y):
        """A lever gate: a cross-barred grate that slides aside (doors rise; gates slide)."""
        r = self.tile_rect(x, y)
        c = lever_color(j)
        shut = self.gate_anim[j] if j < len(self.gate_anim) else 1.0
        pygame.draw.rect(surf, (24, 22, 24), r)
        pygame.draw.rect(surf, scale_color(c, 0.75), r, 2)
        w = int((r.w - 4) * shut)
        if w > 1:
            grate = pygame.Rect(r.x + 2, r.y + 2, w, r.h - 4)
            pygame.draw.rect(surf, scale_color(c, 0.18), grate)
            old_clip = surf.get_clip()
            surf.set_clip(grate)
            for k in range(-r.h, r.w, 6):        # criss-cross bars, sliding with the grate
                x0 = grate.right - r.w + 4 + k
                pygame.draw.line(surf, (128, 126, 122), (x0, grate.y), (x0 + grate.h, grate.bottom), 1)
                pygame.draw.line(surf, (128, 126, 122), (x0, grate.bottom), (x0 + grate.h, grate.y), 1)
            surf.set_clip(old_clip)
            pygame.draw.line(surf, (170, 166, 160), (grate.right - 1, grate.y), (grate.right - 1, grate.bottom - 1), 2)
        label = pygame.Rect(0, 0, 13, 13)
        label.center = r.center
        pygame.draw.rect(surf, (18, 14, 18), label, border_radius=3)
        draw_text(surf, self.app.bold[16], LETTERS[j], r.center, c, center=True)

    def _draw_lever(self, surf, j, x, y, sim):
        """A floor lever: the handle leans right while its gate is unflipped, left once flipped."""
        r = self.tile_rect(x, y)
        c = lever_color(j)
        flipped = sim.gate_flipped[j]
        pygame.draw.rect(surf, (66, 60, 62), (r.x + 4, r.bottom - 9, r.w - 8, 6), border_radius=2)
        pygame.draw.rect(surf, scale_color(c, 0.7), (r.x + 4, r.bottom - 9, r.w - 8, 6), 1, border_radius=2)
        pivot = (r.centerx, r.bottom - 8)
        a = math.radians(-55 if not flipped else -125)
        tip = (pivot[0] + math.cos(a) * 13, pivot[1] + math.sin(a) * 13)
        pygame.draw.line(surf, (160, 150, 140), pivot, tip, 3)
        pygame.draw.circle(surf, c, (int(tip[0]), int(tip[1])), 4)
        pygame.draw.circle(surf, (20, 18, 20), pivot, 3)
        draw_text(surf, self.app.bold[16], LETTERS[j], (r.x + 6, r.y + 6), c, center=True)

    def _hp_bar(self, surf, cx, top, hp, mx, w=18):
        pygame.draw.rect(surf, (40, 16, 20), (cx - w // 2, top, w, 3))
        pygame.draw.rect(surf, (230, 80, 70), (cx - w // 2, top, max(0, w * hp // max(1, mx)), 3))

    def _draw_enemies(self, surf, sim, vis):
        f = self.app.bold
        for n, e in enumerate(sim.enemies):
            if not e.alive or e.pos not in vis:
                continue
            cx, cy = self.actor_px(e)
            draw_enemy(surf, e.kind, cx, cy, self.t, e.awake, n)
            if e.awake:
                ready = {"brute": sim.turn % 2 == 0, "archer": e.cd <= 1}.get(e.kind, False)
                if ready:
                    draw_text(surf, f[22], "!", (cx + 10, cy - 15), WARN, center=True)
            else:
                zy = cy - 12 - (self.t * 6 % 6)
                draw_text(surf, self.app.italic[16], "z", (cx + 9, int(zy)), DIM, center=True)
            self._hp_bar(surf, cx, cy - 15, e.hp, e.max_hp)

    def ghost_paths(self, sim):
        out = []
        for g in sim.ghosts:
            if not g.alive:
                continue
            s = g.script
            out.append((g, script_path(sim.floor, s.actions[sim.turn:], g.pos, 90)))
        return out

    def draw_path(self, surf, pts, label, ending, width=2, color=None):
        c = color or ghost_color(label)
        if len(pts) > 1:
            line_c = c if color else tuple(v * 2 // 3 for v in c)
            pygame.draw.lines(surf, line_c, False, [self.tile_center(p) for p in pts], width)
        end = self.tile_center(pts[-1])
        if ending == "anchor":
            pygame.draw.circle(surf, c, end, 8, 2)
        else:
            pygame.draw.line(surf, c, (end[0] - 5, end[1] - 5), (end[0] + 5, end[1] + 5), 2)
            pygame.draw.line(surf, c, (end[0] - 5, end[1] + 5), (end[0] + 5, end[1] - 5), 2)

    def _draw_paths(self, surf, sim):
        for g, pts in self.ghost_paths(sim):
            self.draw_path(surf, pts, g.script.label, g.script.ending)

    def _draw_ghosts(self, surf, sim):
        f = self.app.bold
        for g in sim.ghosts:
            if not g.alive:
                continue
            cx, cy = self.actor_px(g)
            c = ghost_color(g.script.label)
            if self.ghost_fade <= 0.02:
                continue
            add_glow(surf, (cx, cy), 16, scale_color(c, 0.35 * self.ghost_fade))
            draw_echo(surf, cx, cy, self.t, c, g.script.label, alpha=int(255 * self.ghost_fade))
            if self.ghost_fade < 1.0:
                continue
            badge = (cx + 8, cy + 7)
            pygame.draw.circle(surf, (16, 14, 20), badge, 6)
            pygame.draw.circle(surf, c, badge, 6, 1)
            draw_text(surf, f[16], g.script.label, (badge[0], badge[1]), (255, 255, 255), center=True)
            self._hp_bar(surf, cx, cy - 15, g.hp, g.max_hp)

    def _draw_still(self, surf, seen):
        for i, p in enumerate(self.still_here()):
            if p not in seen:
                continue
            cx, cy = self.tile_center(p)
            add_glow(surf, (cx, cy + 2), 16, (40, 60, 80))
            draw_still(surf, cx, cy + 1, self.t + i * 0.7, reach=i % 3 == 0)

    def _draw_player(self, surf, sim):
        cx, cy = self.actor_px(sim.player)
        draw_lamplighter(surf, cx, cy, self.t)
        add_glow(surf, (cx + 8, cy - 2), 12 * flicker(self.t, 2.0, 0.1), (150, 110, 50))
        self._hp_bar(surf, cx, cy - 16, sim.player.hp, sim.player.max_hp)

    def _draw_effects(self, surf):
        f = self.app.bold
        for e in self.effects:
            kind = e[0]
            if kind == "float":
                cx, cy = self.tile_center(e[1])
                rise = int((0.8 - e[-1]) * 18)
                img = text_surface(f[22], e[2], e[3], min(255, 255 * e[-1] / 0.3))
                shadow = text_surface(f[22], e[2], (0, 0, 0), min(200, 200 * e[-1] / 0.3))
                r = img.get_rect(center=(cx, cy - 14 - rise))
                surf.blit(shadow, r.move(1, 1))
                surf.blit(img, r)
            elif kind == "line":
                a, b = self.tile_center(e[1]), self.tile_center(e[2])
                pygame.draw.line(surf, e[3], a, b, 2)
                k = 1 - e[-1] / 0.35
                head = (int(lerp(a[0], b[0], k)), int(lerp(a[1], b[1], k)))
                pygame.draw.circle(surf, (255, 230, 255), head, 3)
            elif kind == "flash":
                r = self.tile_rect(*e[1])
                pygame.draw.rect(surf, e[2], r, 2)
            elif kind == "slash":
                r = self.tile_rect(*e[1])
                k = 1 - e[-1] / 0.2
                pygame.draw.arc(surf, (240, 240, 250), r.inflate(-4, -4), 0.4 + k * 2, 2.4 + k * 2, 2)

    def _draw_story_fx(self, surf, under):
        fx = self.story_fx
        if fx is None:
            return
        p = fx["t"] / fx["dur"]
        pts = fx["path"]
        if fx["kind"] == "rewind":
            if under:
                # a veil over the map while time runs backwards
                veil = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
                a = int(80 * math.sin(math.pi * min(1.0, p)))
                veil.fill(((90, 10, 20) if fx["dead"] else (40, 20, 70)) + (a,))
                surf.blit(veil, (0, OY))
                # the thread reels in from where you stopped back to the knot
                k = max(1, int(len(pts) * (1 - ease_in_out(min(1.0, p / 0.6)))))
                seg = [self.tile_center(q) for q in pts[:k]]
                if len(seg) > 1:
                    pygame.draw.lines(surf, scale_color(THREAD, 0.6), False, seg, 4)
                    pygame.draw.lines(surf, THREAD, False, seg, 2)
                if seg:
                    pygame.draw.circle(surf, (255, 240, 255), seg[-1], 4)
                # the knot rings as the new loop begins
                if p > 0.45:
                    q = (p - 0.45) / 0.55
                    sx, sy = self.tile_center(self.run.floor.start)
                    ring = pygame.Surface((120, 120), pygame.SRCALPHA)
                    pygame.draw.circle(ring, (*THREAD, int(200 * (1 - q))), (60, 60), int(8 + 46 * ease_out(q)), 2)
                    surf.blit(ring, (sx - 60, sy - 60))
            else:
                a = 255 * math.sin(math.pi * min(1.0, p))
                draw_glow_text(surf, self.app.bold[44], "Loop %d" % fx["loop"], (MAP_W // 2, OY + 70),
                               TEXT, THREAD, alpha=a)
                sub = story.REWIND_LINE % fx["label"]
                img = text_surface(self.app.italic[22], sub, DIM, a)
                surf.blit(img, img.get_rect(center=(MAP_W // 2, OY + 104)))
        elif fx["kind"] == "unravel" and under:
            k = int(len(pts) * (1 - ease_in_out(min(1.0, p / 0.8))))
            seg = [self.tile_center(q) for q in pts[:max(1, k)]]
            if len(seg) > 1:
                pygame.draw.lines(surf, scale_color(fx["color"], 0.8), False, seg, 2)
            if 0 <= k < len(pts):
                cx, cy = self.tile_center(pts[k])
                pygame.draw.circle(surf, (255, 230, 200), (cx, cy), 3)
        elif fx["kind"] == "unravel":
            a = 255 * math.sin(math.pi * min(1.0, p))
            draw_glow_text(surf, self.app.bold[44], "Echo %d unravelled" % fx["label"], (MAP_W // 2, OY + 70),
                           TEXT, fx["color"], alpha=a)

    def _draw_banner(self, surf):
        """The floor's name and a line of story, fading in when you arrive."""
        t = BANNER_TIME - self.banner
        if self.banner <= 0:
            return
        a = min(1.0, t / 0.6) * min(1.0, self.banner / 0.7)
        if a <= 0:
            return
        n = self.run.floor_no
        back = vertical_gradient((MAP_W, 120), (8, 6, 12), (8, 6, 12))
        back.set_alpha(int(150 * a))
        surf.blit(back, (0, OY + 26))
        back.set_alpha(None)
        draw_glow_text(surf, self.app.italic[22], "Floor %d of %d" % (n, MAX_FLOOR), (MAP_W // 2, OY + 46),
                       DIM, alpha=255 * a)
        draw_glow_text(surf, self.app.bold[44], story.floor_name(n), (MAP_W // 2, OY + 80), ACCENT,
                       (140, 80, 30), alpha=255 * a)
        font = self.app.italic[22]
        lines = wrap_text(font, self.arrival_text(), MAP_W - 60)
        if len(lines) > 1:
            font = self.app.italic[18]
            lines = wrap_text(font, self.arrival_text(), MAP_W - 60)[:2]
        y = OY + 122 - (len(lines) - 1) * font.get_linesize() // 2
        for ln in lines:
            img = text_surface(font, ln, TEXT, 255 * a)
            surf.blit(img, img.get_rect(center=(MAP_W // 2, y)))
            y += font.get_linesize()

    def _draw_hud(self, surf, run, sim):
        f, b = self.app.fonts, self.app.bold
        surf.blit(vertical_gradient((960, OY), (40, 34, 40), (22, 18, 24)), (0, 0))
        pygame.draw.line(surf, BRONZE, (0, OY - 1), (960, OY - 1), 1)
        surf.blit(vertical_gradient((960, 660 - BAR_Y), (30, 25, 32), (18, 15, 20)), (0, BAR_Y))
        pygame.draw.line(surf, BRONZE, (0, BAR_Y), (960, BAR_Y), 1)
        play = run.play
        # floor
        draw_text(surf, b[22], "Floor %d/%d" % (run.floor_no, MAX_FLOOR), (10, 5), ACCENT)
        draw_text(surf, self.app.italic[16], story.floor_name(run.floor_no), (10, 25), DIM)
        # loop
        draw_text(surf, b[22], "Loop %d" % play.loop_no, (178, 5), BAD if play.last_loop else TEXT)
        draw_text(surf, self.app.italic[16], "last loop" if play.last_loop else "next echo %d" % play.free_label(),
                  (178, 25), BAD if play.last_loop else DIM)
        # turn counter
        draw_hourglass(surf, 262, 22, DIM)
        bx, bw = 274, 116
        frac = min(1.0, sim.turn / max(1, sim.limit))
        pygame.draw.rect(surf, (34, 30, 40), (bx, 13, bw, 18), border_radius=4)
        pygame.draw.rect(surf, BAD if sim.limit - sim.turn <= 10 else (120, 150, 210), (bx, 13, int(bw * frac), 18), border_radius=4)
        pygame.draw.rect(surf, (90, 80, 90), (bx, 13, bw, 18), 1, border_radius=4)
        draw_text(surf, f[18], "Turn %d/%d" % (sim.turn, sim.limit), (bx + bw // 2, 22), (255, 255, 255), center=True)
        # hp
        p = sim.player
        draw_heart(surf, 408, 22, (230, 80, 70))
        pygame.draw.rect(surf, (56, 22, 26), (418, 13, 84, 18), border_radius=4)
        pygame.draw.rect(surf, (200, 64, 60), (418, 13, int(84 * max(0, p.hp) / p.max_hp), 18), border_radius=4)
        pygame.draw.rect(surf, (110, 60, 60), (418, 13, 84, 18), 1, border_radius=4)
        draw_text(surf, f[18], "HP %d/%d" % (p.hp, p.max_hp), (460, 22), (255, 255, 255), center=True)
        # threads: the currency for unravelling echoes (in The Long Night: the shared thread itself)
        ok = run.can_afford_unravel()
        draw_spool(surf, (520, 22), THREAD if ok else (90, 80, 96))
        if run.thread is None:              # (in The Long Night the thread is the badge over the map)
            draw_text(surf, b[22], "%d" % run.threads, (530, 12), THREAD if ok else DIM)
        # score so far: every turn on this floor, against par
        spent, par = play.turns_spent, run.par_for(len(run.lit)) or 0       # (par rises with each sconce)
        draw_flag(surf, 562, 22, GOLD)
        draw_text(surf, b[18], "%d turns" % spent, (572, 6), TEXT if spent <= par else WARN)
        draw_text(surf, self.app.italic[16], "par %d" % par, (572, 25), DIM)
        # echo slots: filled slots hold an echo, empty ones are loops still to spend
        alive = {g.script.label: g for g in sim.ghosts}
        nxt = play.free_label()
        for i in range(max(play.slots, len(play.scripts))):
            label = i + 1
            r = pygame.Rect(652 + i * 33, 8, 28, 28)
            s = play.script(label)
            c = ghost_color(label)
            if s is None:
                edge = (120, 100, 80) if label == nxt else (60, 52, 56)
                pygame.draw.rect(surf, (18, 15, 20), r, border_radius=5)
                for k in range(0, 28, 6):                  # dashed: an empty slot
                    pygame.draw.line(surf, edge, (r.x + k, r.y), (r.x + min(28, k + 3), r.y))
                    pygame.draw.line(surf, edge, (r.x + k, r.bottom - 1), (r.x + min(28, k + 3), r.bottom - 1))
                    pygame.draw.line(surf, edge, (r.x, r.y + k), (r.x, r.y + min(28, k + 3)))
                    pygame.draw.line(surf, edge, (r.right - 1, r.y + k), (r.right - 1, r.y + min(28, k + 3)))
                continue
            g = alive.get(label)
            on = g is not None and g.alive
            pygame.draw.rect(surf, scale_color(c, 0.3) if on else (30, 26, 32), r, border_radius=5)
            pygame.draw.rect(surf, c if on else (80, 72, 80), r, 2, border_radius=5)
            draw_text(surf, b[22], label, (r.centerx, r.centery + 1), TEXT if on else (110, 100, 106), center=True)
        # message bar
        if self.msg:
            draw_wrapped(surf, f[18], self.msg, (10, BAR_Y + 4), 496, self.msg_color, spacing=0)
        else:
            draw_text(surf, f[18], "WASD move   Space wait   E anchor   U unravel   Tab paths   H help",
                      (10, BAR_Y + 12), DIM)

    def _draw_tooltip(self, surf):
        t = self.hover_tile
        if t is None:
            return
        txt = self.describe_tile(t)
        if not txt:
            return
        font = self.app.fonts[18]
        lines = wrap_text(font, txt, 260)
        lh = font.get_linesize()
        w = max(font.size(ln)[0] for ln in lines) + 18
        h = len(lines) * lh + 12
        r = self.tile_rect(*t)
        x = min(r.right + 6, 960 - w - 4)
        y = min(max(OY + 2, r.y - 4), BAR_Y - h - 2)
        box = pygame.Rect(x, y, w, h)
        pygame.draw.rect(surf, (20, 16, 22), box, border_radius=6)
        pygame.draw.rect(surf, BRONZE, box, 1, border_radius=6)
        for i, line in enumerate(lines):
            draw_text(surf, font, line, (x + 9, y + 6 + i * lh), TEXT)
