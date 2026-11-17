"""The dungeon screen: drawing, input and turn messages."""

import pygame

from .base import Screen
from .consts import (ENEMIES, GHOST_COLORS, GRID_H, GRID_W, MAX_FLOOR, PAIR_COLORS, TILE)
from .sim import ANCHOR, WAIT, move
from .vision import visible_tiles
from .widgets import (ACCENT, BAD, BG, DIM, GOOD, PANEL, TEXT, WARN, draw_text, draw_wrapped)

OY = 44                     # the map starts below the top bar
MAP_W, MAP_H = GRID_W * TILE, GRID_H * TILE
BAR_Y = OY + MAP_H          # bottom bar

KEYMAP = {
    pygame.K_UP: (0, -1), pygame.K_w: (0, -1),
    pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0),
    pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1),
    pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0),
}

FLOOR_A, FLOOR_B, CORRIDOR_A, CORRIDOR_B = (60, 64, 90), (55, 59, 84), (48, 51, 74), (44, 47, 68)
WALL_EDGE, WALL_FILL = (70, 76, 104), (24, 25, 36)


def ghost_color(label):
    return GHOST_COLORS[(label - 1) % len(GHOST_COLORS)]


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
        self.static = self._build_static()
        x = 556
        for label, w, tag, cb in (("Wait", 70, "wait", lambda: self.act(WAIT)),
                                  ("Anchor", 84, "anchor", self.request_anchor),
                                  ("Paths", 84, "paths", self.toggle_paths),
                                  ("Help", 56, "help", app.show_help),
                                  ("Menu", 62, "menu", app.pause)):
            self.add((x, BAR_Y + 6, w, 32), label, cb, tag=tag)
            x += w + 8
        self.reveal()
        r = self.run
        self.say("Floor %d. Reach the gold stairs. Doors open while something stands on their plate." % r.floor_no)

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

    # ------------------------------------------------------------ state
    def reveal(self):
        sim = self.run.sim
        self.visible = visible_tiles(sim.player.pos, self.run.sight, sim.blocks_sight)
        self.run.seen |= self.visible
        self._build_fog()

    def _build_static(self):
        floor = self.run.floor
        s = pygame.Surface((MAP_W, MAP_H))
        s.fill(BG)
        rooms = floor.rooms
        for y in range(GRID_H):
            for x in range(GRID_W):
                r = pygame.Rect(x * TILE, y * TILE, TILE, TILE)
                if floor.walls[y][x]:
                    near = any(0 <= x + dx < GRID_W and 0 <= y + dy < GRID_H and not floor.walls[y + dy][x + dx]
                               for dx in (-1, 0, 1) for dy in (-1, 0, 1))
                    if near:
                        pygame.draw.rect(s, WALL_FILL, r)
                        pygame.draw.rect(s, WALL_EDGE, r, 1)
                else:
                    in_room = any(rm.contains(x, y) for rm in rooms)
                    a, b = (FLOOR_A, FLOOR_B) if in_room else (CORRIDOR_A, CORRIDOR_B)
                    pygame.draw.rect(s, a if (x + y) % 2 == 0 else b, r)
        return s

    def _build_fog(self):
        fog = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
        seen, vis = self.run.seen, self.visible
        for y in range(GRID_H):
            for x in range(GRID_W):
                p = (x, y)
                if p in vis:
                    continue
                r = pygame.Rect(x * TILE, y * TILE, TILE, TILE)
                fog.fill((*BG, 255) if p not in seen else (0, 0, 0, 105), r)
        self.fog = fog

    # ------------------------------------------------------------ actions
    def act(self, action):
        if self.confirm:
            self.confirm = False
        r = self.run.act(action)
        if r.message:
            self.say(r.message, BAD)
            return r
        self.after(r)
        return r

    def after(self, r):
        run = self.run
        sim = run.sim
        self._effects_from(r.events)
        lines = self.describe(r.events)
        if r.ended:
            n = len(run.play.scripts)
            if r.ended == "exit":
                lines.append("You reach the stairs!")
            elif r.ended == "anchor":
                lines.append("Echo %d anchored." % n)
            elif r.ended == "timeout":
                lines.append("The loop collapsed: echo %d holds where you stood." % n)
            elif r.ended == "dead":
                lines.append("You fell. Echo %d replays that loop and fades when you did." % n)
            if run.state == "playing":
                lines.append("Loop %d/%d begins." % (run.play.loop_no, run.play.loops_max))
        self.say("  ".join(lines[-4:]) if lines else "", BAD if r.ended == "dead" else TEXT)
        if run.state != "playing":
            self.app.after_act()
            return
        self.reveal()
        self.app.dirty = True

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

    def _effects_from(self, events):
        for e in events:
            k = e[0]
            if k == "hurt":
                self.effects.append(["float", e[3], "-%d" % e[2], BAD if e[1][0] in "PG" else WARN, 0.7])
            elif k == "shot":
                self.effects.append(["line", e[3], e[4], (255, 120, 255), 0.35])
            elif k == "potion":
                self.effects.append(["float", e[2], "+%d" % e[1], GOOD, 0.8])
            elif k == "died" or k == "faded" or k == "echo_lost":
                self.effects.append(["flash", e[-1], (255, 255, 255), 0.3])
            elif k == "swing":
                self.effects.append(["flash", e[2], (200, 200, 200), 0.2])

    def request_anchor(self):
        run = self.run
        if run.state != "playing":
            return
        if not self.confirm:
            self.confirm = True
            last = run.play.loop_no >= run.play.loops_max
            self.say(("LAST LOOP: anchoring ends the run! " if last else "") +
                     "Press E (or click Anchor) again to end this loop and leave an echo here. "
                     "Anything else cancels.", WARN)
        else:
            self.confirm = False
            self.act(ANCHOR)

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
        if not self.effects:
            return False
        for e in self.effects:
            e[-1] -= dt
        self.effects = [e for e in self.effects if e[-1] > 0]
        return True

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
                    extra = {"crawler": "Chases you.", "archer": "Shoots along rows and columns.",
                             "brute": "Hits hard every other turn.", "warden": "Guards the stairs."}[e.kind]
                    parts.append("%s %d/%d HP, %s. %s" % (spec["name"], e.hp, e.max_hp,
                                                          "awake" if e.awake else "asleep", extra))
        if sim.player.pos == t:
            parts.append("You: %d/%d HP." % (sim.player.hp, sim.player.max_hp))
        for g in sim.ghosts:
            if g.alive and g.pos == t:
                end = g.script.ending
                parts.append("Echo %d (%d HP): replays your loop %d, then %s." %
                             (g.script.label, g.hp, g.script.label, "stands here" if end == "anchor" else "fades"))
        if t in floor.door_at:
            i = floor.door_at[t]
            parts.append("Door %d: %s. Opens while something stands on plate %d." %
                         (i + 1, "open" if sim.door_open(i) else "sealed", i + 1))
        if t in floor.plate_at:
            i = floor.plate_at[t]
            parts.append("Plate %d: %s. Holds door %d open." % (i + 1, "held" if sim.plate_held(i) else "empty", i + 1))
        if t == floor.exit:
            parts.append("The stairs down. Step here to finish the floor.")
        if t in sim.potions:
            parts.append("Potion: heals %d." % 3)
        if t in floor.spikes:
            parts.append("Spikes: %s now. They flip every 2 turns." %
                         ("UP (hurts)" if floor.spike_active(t, sim.turn) else "down"))
        return " ".join(parts)

    # ------------------------------------------------------------ drawing
    def draw(self, surf):
        run, sim, floor = self.run, self.run.sim, self.run.floor
        surf.fill(BG)
        surf.blit(self.static, (0, OY))
        seen, vis = run.seen, self.visible
        self._draw_features(surf, sim, floor, seen)
        self._draw_enemies(surf, sim, vis)
        surf.blit(self.fog, (0, OY))
        if self.show_paths:
            self._draw_paths(surf, sim)
        self._draw_ghosts(surf, sim)
        self._draw_player(surf, sim)
        self._draw_effects(surf)
        self._draw_hud(surf, run, sim)
        self._draw_tooltip(surf)
        self.draw_buttons(surf)

    def _draw_features(self, surf, sim, floor, seen):
        f = self.app.fonts
        for i, (x, y) in enumerate(floor.plates):
            if (x, y) not in seen:
                continue
            r = self.tile_rect(x, y).inflate(-6, -6)
            c = PAIR_COLORS[i % len(PAIR_COLORS)]
            held = sim.plate_held(i)
            if held:
                pygame.draw.rect(surf, c, r, border_radius=5)
                pygame.draw.rect(surf, (255, 255, 255), r, 2, border_radius=5)
            else:
                pygame.draw.rect(surf, tuple(v // 4 for v in c), r, border_radius=5)
                pygame.draw.rect(surf, c, r, 2, border_radius=5)
            draw_text(surf, f[18], i + 1, r.center, (20, 20, 30) if held else c, center=True)
        for i, (x, y) in enumerate(floor.doors):
            if (x, y) not in seen:
                continue
            r = self.tile_rect(x, y)
            c = PAIR_COLORS[i % len(PAIR_COLORS)]
            if sim.door_open(i):
                pygame.draw.rect(surf, c, r.inflate(-4, -4), 2, border_radius=4)
                draw_text(surf, f[16], i + 1, r.center, c, center=True)
            else:
                pygame.draw.rect(surf, tuple(v // 3 for v in c), r)
                pygame.draw.rect(surf, c, r, 2)
                for bx in range(r.x + 5, r.right - 2, 6):
                    pygame.draw.line(surf, c, (bx, r.y + 2), (bx, r.bottom - 3), 2)
                pygame.draw.rect(surf, (20, 20, 30), pygame.Rect(0, 0, 14, 14).move(r.x + 5, r.y + 5))
                draw_text(surf, f[18], i + 1, (r.centerx, r.centery), c, center=True)
        for pos, _ in floor.spikes.items():
            if pos not in seen:
                continue
            r = self.tile_rect(*pos)
            if floor.spike_active(pos, sim.turn):
                for k in range(3):
                    cx = r.x + 5 + k * 7
                    pygame.draw.polygon(surf, (235, 70, 70), [(cx - 3, r.bottom - 4), (cx + 3, r.bottom - 4), (cx, r.y + 4)])
            else:
                soon = floor.spike_active(pos, sim.turn + 1)
                col = WARN if soon else (90, 94, 112)
                for k in range(3):
                    pygame.draw.circle(surf, col, (r.x + 6 + k * 6, r.centery + 3), 2)
        for pos in sim.potions:
            if pos in seen:
                cx, cy = self.tile_center(pos)
                pygame.draw.circle(surf, (230, 80, 110), (cx, cy), 7)
                pygame.draw.line(surf, (255, 255, 255), (cx - 4, cy), (cx + 4, cy), 2)
                pygame.draw.line(surf, (255, 255, 255), (cx, cy - 4), (cx, cy + 4), 2)
        if floor.exit in seen:
            r = self.tile_rect(*floor.exit).inflate(-4, -4)
            pygame.draw.rect(surf, (240, 210, 90), r, border_radius=3)
            for k in range(3):
                pygame.draw.line(surf, (110, 90, 20), (r.x + 2 + k * 4, r.bottom - 3 - k * 5),
                                 (r.right - 3, r.bottom - 3 - k * 5), 2)
        sx, sy = floor.start
        pygame.draw.circle(surf, (70, 90, 120), self.tile_center((sx, sy)), 10, 1)

    def _hp_bar(self, surf, cx, top, hp, mx, w=18):
        pygame.draw.rect(surf, (40, 20, 24), (cx - w // 2, top, w, 3))
        pygame.draw.rect(surf, (230, 80, 80), (cx - w // 2, top, max(0, w * hp // max(1, mx)), 3))

    def _draw_enemies(self, surf, sim, vis):
        f = self.app.fonts
        for e in sim.enemies:
            if not e.alive or e.pos not in vis:
                continue
            cx, cy = self.tile_center(e.pos)
            if e.kind == "crawler":
                pygame.draw.circle(surf, (190, 70, 70), (cx, cy), 9)
                pygame.draw.circle(surf, (255, 220, 200), (cx - 3, cy - 2), 2)
                pygame.draw.circle(surf, (255, 220, 200), (cx + 3, cy - 2), 2)
            elif e.kind == "archer":
                pygame.draw.polygon(surf, (170, 90, 210), [(cx, cy - 10), (cx + 9, cy + 8), (cx - 9, cy + 8)])
            elif e.kind == "brute":
                pygame.draw.rect(surf, (214, 130, 60), (cx - 10, cy - 10, 20, 20), border_radius=3)
                pygame.draw.rect(surf, (90, 50, 20), (cx - 10, cy - 10, 20, 20), 2, border_radius=3)
            else:
                pygame.draw.rect(surf, (60, 50, 90), (cx - 11, cy - 11, 22, 22), border_radius=3)
                pygame.draw.rect(surf, (240, 210, 90), (cx - 11, cy - 11, 22, 22), 2, border_radius=3)
            if e.awake:
                pygame.draw.circle(surf, (255, 90, 90), (cx, cy), 12, 1)
                ready = {"brute": sim.turn % 2 == 0, "archer": e.cd <= 1}.get(e.kind, False)
                if ready:
                    draw_text(surf, f[22], "!", (cx + 9, cy - 16), WARN, center=True)
            else:
                draw_text(surf, f[16], "z", (cx + 8, cy - 12), DIM, center=True)
            self._hp_bar(surf, cx, cy - 15, e.hp, e.max_hp)

    def ghost_paths(self, sim):
        out = []
        for g in sim.ghosts:
            if not g.alive:
                continue
            x, y = g.pos
            pts = [g.pos]
            for a in g.script.actions[sim.turn:sim.turn + 90]:
                if a[0] == "m":
                    nx, ny = x + a[1], y + a[2]
                    if not sim.floor.is_wall(nx, ny):
                        x, y = nx, ny
                        pts.append((x, y))
            out.append((g, pts))
        return out

    def _draw_paths(self, surf, sim):
        for g, pts in self.ghost_paths(sim):
            c = ghost_color(g.script.label)
            if len(pts) > 1:
                pygame.draw.lines(surf, tuple(v * 2 // 3 for v in c), False, [self.tile_center(p) for p in pts], 2)
            end = self.tile_center(pts[-1])
            if g.script.ending == "anchor":
                pygame.draw.circle(surf, c, end, 8, 2)
            else:
                pygame.draw.line(surf, c, (end[0] - 5, end[1] - 5), (end[0] + 5, end[1] + 5), 2)
                pygame.draw.line(surf, c, (end[0] - 5, end[1] + 5), (end[0] + 5, end[1] - 5), 2)

    def _draw_ghosts(self, surf, sim):
        f = self.app.fonts
        for g in sim.ghosts:
            if not g.alive:
                continue
            cx, cy = self.tile_center(g.pos)
            c = ghost_color(g.script.label)
            pygame.draw.circle(surf, tuple(v // 2 for v in c), (cx, cy), 9)
            pygame.draw.circle(surf, c, (cx, cy), 9, 2)
            draw_text(surf, f[18], g.script.label, (cx, cy), (255, 255, 255), center=True)
            self._hp_bar(surf, cx, cy - 14, g.hp, g.max_hp)

    def _draw_player(self, surf, sim):
        cx, cy = self.tile_center(sim.player.pos)
        pygame.draw.circle(surf, (236, 246, 255), (cx, cy), 9)
        pygame.draw.circle(surf, (60, 160, 220), (cx, cy), 9, 2)
        pygame.draw.circle(surf, (20, 30, 50), (cx - 3, cy - 2), 1)
        pygame.draw.circle(surf, (20, 30, 50), (cx + 3, cy - 2), 1)
        self._hp_bar(surf, cx, cy - 14, sim.player.hp, sim.player.max_hp)

    def _draw_effects(self, surf):
        f = self.app.fonts
        for e in self.effects:
            kind = e[0]
            if kind == "float":
                cx, cy = self.tile_center(e[1])
                rise = int((0.8 - e[-1]) * 18)
                draw_text(surf, f[22], e[2], (cx, cy - 14 - rise), e[3], center=True)
            elif kind == "line":
                pygame.draw.line(surf, e[3], self.tile_center(e[1]), self.tile_center(e[2]), 3)
            elif kind == "flash":
                r = self.tile_rect(*e[1])
                pygame.draw.rect(surf, e[2], r, 2)

    def _draw_hud(self, surf, run, sim):
        f = self.app.fonts
        pygame.draw.rect(surf, PANEL, (0, 0, 960, OY))
        pygame.draw.rect(surf, PANEL, (0, BAR_Y, 960, 660 - BAR_Y))
        play = run.play
        draw_text(surf, f[26], "Floor %d/%d" % (run.floor_no, MAX_FLOOR), (10, 12), TEXT)
        last = play.loop_no >= play.loops_max
        draw_text(surf, f[26], "Loop %d/%d" % (play.loop_no, play.loops_max), (140, 12), BAD if last else ACCENT)
        # turn counter
        bx, bw = 262, 190
        frac = min(1.0, sim.turn / max(1, sim.limit))
        pygame.draw.rect(surf, (40, 44, 62), (bx, 14, bw, 18), border_radius=4)
        pygame.draw.rect(surf, BAD if sim.limit - sim.turn <= 10 else (110, 160, 230), (bx, 14, int(bw * frac), 18), border_radius=4)
        draw_text(surf, f[18], "Turn %d/%d" % (sim.turn, sim.limit), (bx + bw // 2, 23), (255, 255, 255), center=True)
        # hp
        p = sim.player
        pygame.draw.rect(surf, (60, 28, 34), (468, 14, 120, 18), border_radius=4)
        pygame.draw.rect(surf, (225, 80, 90), (468, 14, int(120 * max(0, p.hp) / p.max_hp), 18), border_radius=4)
        draw_text(surf, f[18], "HP %d/%d" % (p.hp, p.max_hp), (528, 23), (255, 255, 255), center=True)
        # echoes
        draw_text(surf, f[18], "Echoes", (606, 15), DIM)
        if not play.scripts:
            draw_text(surf, f[18], "none yet", (660, 15), DIM)
        alive = {g.script.label: g for g in sim.ghosts}
        for i, s in enumerate(play.scripts[:8]):
            r = pygame.Rect(660 + i * 36, 8, 30, 28)
            c = ghost_color(s.label)
            g = alive.get(s.label)
            pygame.draw.rect(surf, tuple(v // 3 for v in c) if g and g.alive else (30, 30, 40), r, border_radius=4)
            pygame.draw.rect(surf, c if g and g.alive else (80, 80, 96), r, 2, border_radius=4)
            draw_text(surf, f[22], s.label, r.center, TEXT if g and g.alive else (110, 110, 126), center=True)
        # doors summary under the echoes: which plates are held
        # message bar
        if self.msg:
            draw_wrapped(surf, f[18], self.msg, (10, BAR_Y + 4), 535, self.msg_color, spacing=1)
        else:
            draw_text(surf, f[18], "Arrows/WASD move or strike   Space wait   E anchor   Tab echo paths   H help",
                      (10, BAR_Y + 12), DIM)

    def _draw_tooltip(self, surf):
        t = self.hover_tile
        if t is None:
            return
        txt = self.describe_tile(t)
        if not txt:
            return
        font = self.app.fonts[18]
        from .widgets import wrap_text
        lines = wrap_text(font, txt, 260)
        w = max(font.size(l)[0] for l in lines) + 16
        h = len(lines) * 18 + 12
        r = self.tile_rect(*t)
        x = min(r.right + 6, 960 - w - 4)
        y = min(max(OY + 2, r.y - 4), BAR_Y - h - 2)
        pygame.draw.rect(surf, (20, 22, 32), (x, y, w, h), border_radius=6)
        pygame.draw.rect(surf, (110, 120, 160), (x, y, w, h), 1, border_radius=6)
        for i, line in enumerate(lines):
            draw_text(surf, font, line, (x + 8, y + 6 + i * 18), TEXT)
