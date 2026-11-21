"""Story scenes: the intro, the per-floor victory, and the painted backdrops they share.

Illustrations are procedural and animated. Large figures are drawn at sprite size and scaled up
with nearest-neighbour, so they match the pixel look of the dungeon.
"""

import math
import random

import pygame

from . import scenery, story
from .base import Screen
from .game_screen import ghost_color
from .score import GRADE_COLORS
from .theme import (GOLD, TORCH, Particles, add_glow, draw_enemy, draw_glow_text, draw_lamplighter, draw_panel,
                    draw_rule, draw_sconce, ease_out, echo_sprite, flicker, lerp, lerp_color, scale_color,
                    text_surface, vertical_gradient)
from .widgets import ACCENT, BG, DIM, ECHO, TEXT, THREAD, draw_spool, draw_text, wrap_text

W, H = 960, 660
_STARS = [(random.Random(i).randrange(W), random.Random(i * 7 + 1).randrange(300), random.Random(i * 3).random())
          for i in range(90)]


# ---------------------------------------------------------------- pixel-art helpers

def big(draw_fn, size, factor):
    """Run draw_fn(surface, cx, cy) on a small transparent canvas, then scale it up crisply."""
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    draw_fn(s, size / 2, size / 2)
    return pygame.transform.scale(s, (size * factor, size * factor))


def blit_center(surf, img, center, alpha=255):
    r = img.get_rect(center=(int(center[0]), int(center[1])))
    if alpha < 255:
        img.set_alpha(int(alpha))
    surf.blit(img, r)
    if alpha < 255:
        img.set_alpha(None)


# ---------------------------------------------------------------- backdrops

def draw_town(surf, t, dawn=0.0, rect=None):
    """Hollowmere at night (dawn=0) or sunrise (dawn=1): rooftops, a bell tower with a stopped clock."""
    rect = pygame.Rect(rect or (0, 0, W, 400))
    top = lerp_color((8, 10, 30), (90, 110, 170), dawn)
    bottom = lerp_color((36, 26, 56), (250, 170, 100), dawn)
    surf.blit(vertical_gradient(rect.size, top, bottom), rect.topleft)
    for x, y, ph in _STARS:
        if y < rect.h - 60:
            k = (0.5 + 0.5 * math.sin(t * 2 + ph * 20)) * (1 - dawn)
            if k > 0.05:
                c = scale_color((230, 230, 255), 0.3 + 0.7 * k)
                surf.set_at((rect.x + x, rect.y + y), c)
    if dawn > 0:
        sx, sy = rect.x + int(rect.w * 0.86), rect.bottom - 60 - dawn * rect.h * 0.42
        add_glow(surf, (sx, int(sy)), int(60 + 220 * dawn), scale_color((255, 200, 120), dawn))
        pygame.draw.circle(surf, lerp_color((255, 150, 80), (255, 240, 200), dawn), (sx, int(sy)), 34)
    else:
        mx, my = rect.x + 160, rect.y + 80
        pygame.draw.circle(surf, (220, 220, 200), (mx, my), 26)
        pygame.draw.circle(surf, top, (mx + 10, my - 6), 24)
    base = rect.bottom
    roof = lerp_color((14, 12, 22), (60, 40, 50), dawn)
    rng = random.Random(4)
    x = rect.x - 20
    windows = []
    while x < rect.right:
        w = rng.randint(60, 110)
        h = rng.randint(60, 120)
        pygame.draw.rect(surf, roof, (x, base - h, w, h))
        pygame.draw.polygon(surf, roof, [(x - 6, base - h), (x + w // 2, base - h - rng.randint(24, 44)), (x + w + 6, base - h)])
        for _ in range(rng.randint(0, 2)):
            windows.append((x + rng.randint(10, w - 16), base - h + rng.randint(14, h - 24), rng.random()))
        x += w + rng.randint(-10, 4)
    tx = rect.centerx - 40
    pygame.draw.rect(surf, roof, (tx, base - 250, 80, 250))
    pygame.draw.polygon(surf, roof, [(tx - 10, base - 250), (tx + 40, base - 320), (tx + 90, base - 250)])
    clock = (tx + 40, base - 200)
    pygame.draw.circle(surf, lerp_color((60, 56, 70), (230, 210, 170), dawn), clock, 22)
    pygame.draw.circle(surf, lerp_color((30, 28, 36), (90, 70, 50), dawn), clock, 22, 2)
    hand = -math.pi / 2 + (dawn * math.tau * 0.25)
    pygame.draw.line(surf, (20, 18, 24), clock, (clock[0] + math.cos(hand) * 16, clock[1] + math.sin(hand) * 16), 3)
    pygame.draw.line(surf, (20, 18, 24), clock, (clock[0] + 10, clock[1]), 3)
    for wx, wy, ph in windows:
        c = scale_color((255, 190, 100), 0.6 + 0.4 * math.sin(t * 1.5 + ph * 9))
        pygame.draw.rect(surf, c if dawn < 0.6 else roof, (wx, wy, 6, 9))
    if dawn > 0.3:                       # the bells ring for morning
        for k in range(3):
            q = (t * 0.6 + k / 3) % 1.0
            ring = pygame.Surface((400, 400), pygame.SRCALPHA)
            pygame.draw.circle(ring, (255, 230, 170, int(150 * (1 - q) * min(1, (dawn - 0.3) * 3))), (200, 200),
                               int(30 + 170 * q), 2)
            surf.blit(ring, (tx + 40 - 200, base - 280 - 200))


def draw_loom(surf, t, tied=False, rect=None):
    rect = pygame.Rect(rect or (0, 0, W, 400))
    surf.blit(vertical_gradient(rect.size, (14, 10, 18), (34, 24, 30)), rect.topleft)
    cx, base = rect.centerx, rect.bottom - 30
    wood, wood_hi = (70, 48, 34), (110, 80, 54)
    for x in (cx - 220, cx + 200):
        pygame.draw.rect(surf, wood, (x, base - 300, 20, 300))
        pygame.draw.line(surf, wood_hi, (x + 3, base - 300), (x + 3, base), 2)
    for y in (base - 300, base - 40):
        pygame.draw.rect(surf, wood, (cx - 230, y, 460, 18))
        pygame.draw.line(surf, wood_hi, (cx - 230, y + 3), (cx + 230, y + 3), 2)
    for i in range(17):
        x = cx - 190 + i * 24
        sway = math.sin(t * 1.3 + i * 0.7) * 3
        c = scale_color(GOLD, 0.6 + 0.3 * math.sin(t * 2 + i))
        if i == 8 and not tied:
            top_end = (x + sway * 4, base - 175 + math.sin(t * 2.1) * 6)
            bot_end = (x - sway * 4, base - 115 + math.sin(t * 1.7) * 6)
            add_glow(surf, (int(top_end[0]), int(top_end[1])), 40, (160, 120, 40))
            add_glow(surf, (int(bot_end[0]), int(bot_end[1])), 40, (160, 120, 40))
            pygame.draw.line(surf, (255, 230, 150), (x, base - 282), top_end, 3)
            pygame.draw.line(surf, (255, 230, 150), (x, base - 40), bot_end, 3)
            for end, d in ((top_end, 1), (bot_end, -1)):          # frayed fibres
                for j in range(4):
                    a = math.pi / 2 * d + (j - 1.5) * 0.35 + math.sin(t * 3 + j) * 0.1
                    pygame.draw.line(surf, GOLD, end, (end[0] + math.cos(a) * 9, end[1] + math.sin(a) * 9), 1)
        else:
            pygame.draw.line(surf, c, (x, base - 282), (x + sway, base - 40), 2)
    add_glow(surf, (cx, base - 160), 260, (40, 30, 12))


def draw_wall(surf, rect, t, torches=(), lit_upto=None):
    """A brick wall with sconces (scaled pixel art)."""
    rect = pygame.Rect(rect)
    surf.blit(vertical_gradient(rect.size, (24, 18, 24), (40, 30, 34)), rect.topleft)
    rng = random.Random(2)
    for row, y in enumerate(range(rect.y, rect.bottom, 22)):
        off = 0 if row % 2 == 0 else 22
        for x in range(rect.x - off, rect.right, 44):
            v = rng.randint(-6, 6)
            pygame.draw.rect(surf, (54 + v, 42 + v, 42 + v), (x + 2, y + 2, 40, 18), border_radius=2)
    for i, (x, y) in enumerate(torches):
        lit = lit_upto is None or i < lit_upto
        if lit:
            add_glow(surf, (x, y), int(120 * flicker(t, i, 0.06)), (120, 70, 30))
        img = big(lambda s, cx, cy, lit=lit, i=i: draw_sconce(s, cx, cy - 2, lit, t, i), 20, 3)
        blit_center(surf, img, (x, y + 8))


# ---------------------------------------------------------------- the intro panels

def draw_scene(surf, key, t, rect):
    """Paint story scene `key` into rect; False if there is no such scene (a plain card is drawn)."""
    rect = pygame.Rect(rect)
    if key in PAINTED:
        scenery.draw(surf, PAINTED[key], t, rect)
    elif key == "town":
        draw_town(surf, t, 0.0, rect)
    elif key in ("loom", "loom_tied"):
        draw_loom(surf, t, key == "loom_tied", rect)
    elif key == "lamplighter":
        draw_wall(surf, rect, t, [(rect.x + 200, rect.y + 130), (rect.right - 200, rect.y + 130)])
        add_glow(surf, (rect.centerx + 40, rect.bottom - 150), int(140 * flicker(t, 1, 0.05)), (110, 80, 40))
        img = big(lambda s, cx, cy: draw_lamplighter(s, cx, cy + 4, t), 30, 7)
        blit_center(surf, img, (rect.centerx, rect.bottom - 120))
    elif key == "binding":
        surf.blit(vertical_gradient(rect.size, (16, 10, 22), (30, 18, 36)), rect.topleft)
        pygame.draw.rect(surf, (40, 32, 36), (0, rect.bottom - 60, rect.w, 60))       # the landing
        img = big(lambda s, cx, cy: draw_lamplighter(s, cx, cy + 4, t), 30, 7)
        blit_center(surf, img, (rect.centerx, rect.bottom - 120))
        k = ease_out(t / 2.5)                               # the loose end rises and winds around her
        pts = []
        for j in range(int(140 * k) + 2):
            a = j / 140 * math.tau * 3 + t * 2.5
            y = rect.bottom - 30 - j * 1.7
            r = 74 + 10 * math.sin(j / 10)
            pts.append((rect.centerx + math.cos(a) * r, y + math.sin(a) * 14))
        pygame.draw.line(surf, GOLD, (rect.x, rect.bottom - 30), pts[0], 2)
        if len(pts) > 1:
            pygame.draw.lines(surf, GOLD, False, pts, 2)
        add_glow(surf, (int(pts[-1][0]), int(pts[-1][1])), 40, (120, 90, 30))
        add_glow(surf, (rect.centerx, rect.bottom - 150), 180, (50, 40, 10))
    elif key == "echoes":
        surf.blit(vertical_gradient(rect.size, (18, 14, 24), (34, 26, 34)), rect.topleft)
        floor_y = rect.bottom - 70
        pygame.draw.rect(surf, (44, 36, 40), (0, floor_y + 40, rect.w, 30))
        knot = (rect.x + 90, floor_y + 30)                  # where she began the floor
        pygame.draw.circle(surf, THREAD, knot, 14, 2)
        walk = (t * 60) % 240
        lead_x = rect.x + 520 + walk
        lead = (lead_x, floor_y)
        heads = [knot]
        for i in range(3, 0, -1):                           # the steps she took, walking again
            x = lead_x - i * 130
            e = pygame.transform.scale(echo_sprite(ECHO if i != 2 else (190, 160, 255)), (96, 96))
            blit_center(surf, e, (x, floor_y + math.sin(t * 2 + i) * 3), 230 - i * 45)
            heads.append((x + 10, floor_y))
        heads.append((lead_x + 20, floor_y - 4))
        pygame.draw.lines(surf, scale_color(GOLD, 0.7), False, heads, 2)
        add_glow(surf, (int(lead_x + 30), floor_y - 10), 90, (90, 66, 28))
        img = big(lambda s, cx, cy: draw_lamplighter(s, cx, cy + 4, t), 30, 4)
        blit_center(surf, img, lead)
    elif key == "spool":
        surf.blit(vertical_gradient(rect.size, (14, 10, 18), (28, 20, 28)), rect.topleft)
        w = big(lambda s, cx, cy: draw_enemy(s, "warden", cx, cy, t, False, 1), 28, 5)
        blit_center(surf, w, (rect.right - 220, rect.centery + 30), 90)
        k = 1 - ((t / 6.0) % 1.0)                          # the spool runs down, and starts over
        cx, cy = rect.centerx - 160, rect.centery + 10
        pygame.draw.rect(surf, (120, 84, 50), (cx - 70, cy - 90, 140, 18), border_radius=4)
        pygame.draw.rect(surf, (120, 84, 50), (cx - 70, cy + 72, 140, 18), border_radius=4)
        pygame.draw.rect(surf, (70, 50, 34), (cx - 22, cy - 72, 44, 144))
        r = int(22 + 40 * k)
        pygame.draw.rect(surf, scale_color(GOLD, 0.8), (cx - r, cy - 66, 2 * r, 132), border_radius=10)
        for j in range(0, 132, 6):
            pygame.draw.line(surf, scale_color(GOLD, 0.55), (cx - r, cy - 66 + j), (cx + r, cy - 62 + j), 1)
        tail = [(cx + r, cy + 40)]
        for j in range(1, 30):
            tail.append((cx + r + j * 14, cy + 40 + math.sin(t * 2 + j * 0.5) * 8 * (j / 30)))
        pygame.draw.lines(surf, GOLD, False, tail, 2)
        add_glow(surf, (cx, cy), 140, (60, 44, 14))
    elif key == "wardens":
        surf.blit(vertical_gradient(rect.size, (10, 12, 14), (26, 30, 30)), rect.topleft)
        for i in range(5):                                  # walking the same steps forever
            a = t * 0.5 + i * math.tau / 5
            x = rect.centerx + math.cos(a) * 300
            y = rect.centery + 40 + math.sin(a) * 70
            mother = i == 0
            if mother:
                add_glow(surf, (int(x - 40), int(y)), 60, (110, 80, 36))
            img = big(lambda s, cx, cy, i=i, m=mother: draw_enemy(s, "warden", cx, cy, t, False, i, lantern_lit=m), 28, 4)
            blit_center(surf, img, (x, y), 230 if mother else 120 + 100 * (0.5 + 0.5 * math.sin(a)))
    elif key == "clock":
        surf.blit(vertical_gradient(rect.size, (18, 14, 12), (36, 28, 20)), rect.topleft)
        for gx, gy, gr, sp in ((rect.centerx - 250, rect.centery + 60, 70, 0.4), (rect.centerx + 260, rect.centery - 40, 90, -0.3),
                               (rect.centerx + 170, rect.centery + 120, 46, 0.7)):
            _gear(surf, (gx, gy), gr, t * sp, (86, 66, 40))
        c = (rect.centerx, rect.centery)
        add_glow(surf, c, 200, (70, 50, 20))
        pygame.draw.circle(surf, (226, 210, 170), c, 130)
        pygame.draw.circle(surf, (120, 90, 50), c, 130, 6)
        for h in range(12):
            a = h / 12 * math.tau
            pygame.draw.line(surf, (60, 44, 30), (c[0] + math.cos(a) * 112, c[1] + math.sin(a) * 112),
                             (c[0] + math.cos(a) * 124, c[1] + math.sin(a) * 124), 4)
        tick = math.floor(t) / 60 * math.tau - math.pi / 2                 # the second hand ticks
        pygame.draw.line(surf, (40, 30, 24), c, (c[0] + math.cos(-math.pi / 2 + 0.6) * 70, c[1] + math.sin(-math.pi / 2 + 0.6) * 70), 7)
        pygame.draw.line(surf, (40, 30, 24), c, (c[0] + math.cos(-math.pi / 2 - 0.15) * 100, c[1] + math.sin(-math.pi / 2 - 0.15) * 100), 4)
        pygame.draw.line(surf, (170, 50, 40), c, (c[0] + math.cos(tick) * 110, c[1] + math.sin(tick) * 110), 2)
        pygame.draw.circle(surf, (40, 30, 24), c, 8)
    elif key == "cave":
        surf.blit(vertical_gradient(rect.size, (10, 12, 16), (22, 26, 30)), rect.topleft)
        rng = random.Random(7)
        for i in range(22):                                 # stalactites
            x = rect.x + i * 46 + rng.randint(-10, 10)
            h = rng.randint(40, 140)
            pygame.draw.polygon(surf, (40, 44, 48), [(x - 18, rect.y), (x + 18, rect.y), (x + rng.randint(-4, 4), rect.y + h)])
        c = (rect.centerx, rect.centery + 60)
        for k in range(4):                                  # the stone answering a struck fork
            q = (t * 0.45 + k / 4) % 1.0
            ring = pygame.Surface((700, 400), pygame.SRCALPHA)
            pygame.draw.ellipse(ring, (150, 210, 230, int(170 * (1 - q))),
                                pygame.Rect(350 - int(340 * q), 200 - int(120 * q), int(680 * q) + 2, int(240 * q) + 2), 2)
            surf.blit(ring, (c[0] - 350, c[1] - 200))
        pygame.draw.line(surf, (200, 210, 220), (c[0] - 6, c[1] - 60), (c[0] - 6, c[1] - 10), 4)
        pygame.draw.line(surf, (200, 210, 220), (c[0] + 6, c[1] - 60), (c[0] + 6, c[1] - 10), 4)
        pygame.draw.line(surf, (200, 210, 220), (c[0] - 6, c[1] - 10), (c[0] + 6, c[1] - 10), 4)
        pygame.draw.line(surf, (150, 130, 100), (c[0], c[1] - 10), (c[0], c[1] + 30), 5)
    elif key == "descent":
        surf.blit(vertical_gradient(rect.size, (14, 10, 16), (4, 3, 6)), rect.topleft)
        add_glow(surf, (rect.centerx, rect.bottom - 20), 200, (90, 70, 20))
        n = 9
        for i in range(n):                                  # the stair, narrowing into the Deep
            k = i / n
            w = int(lerp(700, 120, k))
            y = int(lerp(rect.y + 40, rect.bottom - 40, k))
            h = int(lerp(40, 8, k))
            c = scale_color((80, 66, 62), 1 - k * 0.7)
            pygame.draw.rect(surf, c, (rect.centerx - w // 2, y, w, h))
            pygame.draw.line(surf, scale_color(c, 1.3), (rect.centerx - w // 2, y), (rect.centerx + w // 2, y))
            if i % 2 == 0 and i < n - 1:
                lit = t > 0.4 + i * 0.35
                for side in (-1, 1):
                    x = rect.centerx + side * (w // 2 + 20)
                    if lit:
                        add_glow(surf, (x, y), int(70 * (1 - k * 0.5) * flicker(t, i * side, 0.06)), (110, 64, 26))
                    f = max(1, int(3 - k * 2))
                    img = big(lambda s, cx, cy, lit=lit: draw_sconce(s, cx, cy, lit, t, i + side), 20, f)
                    blit_center(surf, img, (x, y))


    elif key in ("cave_dark", "still_folk", "pool", "pool_glow", "tarn", "wake"):
        _draw_still_scene(surf, key, t, rect)
    elif key in ("guild", "maren", "watch", "tick_halls"):
        _draw_tick_scene(surf, key, t, rect)
    else:                                                   # an unknown scene: a plain dark card
        surf.blit(vertical_gradient(rect.size, (16, 12, 18), (8, 6, 10)), rect.topleft)
        return False
    return True


PAINTED = {
    "spindle_whole": scenery.Section("whole"),
    "spindle": scenery.Section("broken"),
    "three": scenery.Section("night"),
    "stair_lit": scenery.Section("lit"),
    "ascent": scenery.Break(),
    "doorstep": scenery.Doorstep(),
    "counting_house": scenery.CountingHouse("theft"),
    "ledgers": scenery.CountingHouse("ledgers"),
    "ledger_desk": scenery.CountingHouse("desk"),
    "tick_stair": scenery.TickStair(),
    "clock_window": scenery.ClockWindow(),
    "drum": scenery.DrumRoom("shut"),
    "drum_open": scenery.DrumRoom("open"),
    "drum_master": scenery.DrumRoom("master"),
    "road": scenery.Road(),
    "rest": scenery.Rest(),
    "loom_door": scenery.LoomDoor(),
    "loom_door_still": scenery.LoomDoor("still"),
    "meeting": scenery.LoomDoor("meeting"),
    "dim": scenery.Dim(),
    "black_water": scenery.BlackWater(),
    "roofs_dawn": scenery.Roofs(True, None),
    "roofs_dust": scenery.Roofs(True, "dust"),
    "roofs_night": scenery.Roofs(False, "watch"),
    "roofs_empty": scenery.Roofs(False, None),
    "cave_dark": scenery.Pool("dark"),
    "still_folk": scenery.Pool("folk"),
    "pool_glow": scenery.Pool("glow"),
    "tarn": scenery.Pool("tarn"),
    "wake": scenery.Pool("wake"),
    "loom": scenery.LoomHall("broken"),
    "loom_tied": scenery.LoomHall("tied"),
    "guild": scenery.GuildCounter(),
    "spool": scenery.Spool(),
    "binding": scenery.Binding(),
    "descent": scenery.Descent(),
    "watch": scenery.Regulator(),
    "sunrise": scenery.Sunrise(6),
    "sunrise_few": scenery.Sunrise(3),
    "reunion": scenery.Reunion(),
    "summer": scenery.Summer(),
    "winter": scenery.Winter(),
    "coach": scenery.Coach(),
    "clerk": scenery.CountingHouse("clerk"),
    "children": scenery.Pool("children"),
    "loom_arrival": scenery.LoomHall("arrival"),
    "loom_waiting": scenery.LoomHall("waiting"),
    "tick_door": scenery.TickDoor(),
}


def _cave_backdrop(surf, rect, top=(6, 8, 12), bottom=(14, 18, 24)):
    surf.blit(vertical_gradient(rect.size, top, bottom), rect.topleft)
    rng = random.Random(7)
    for i in range(24):                                     # stalactites
        x = rect.x + i * 42 + rng.randint(-10, 10)
        h = rng.randint(30, 120)
        pygame.draw.polygon(surf, (26, 30, 34), [(x - 16, rect.y), (x + 16, rect.y), (x + rng.randint(-4, 4), rect.y + h)])


def _rings(surf, c, t, glow, count=4, size=(680, 220), speed=0.4):
    """Glowing ripples on black water (their brightness is the whole point of Stillwater)."""
    for k in range(count):
        q = (t * speed + k / count) % 1.0
        ring = pygame.Surface(size, pygame.SRCALPHA)
        w, h = max(2, int(size[0] * q)), max(2, int(size[1] * q))
        pygame.draw.ellipse(ring, (140, 220, 255, int(glow * 230 * (1 - q))),
                            pygame.Rect((size[0] - w) // 2, (size[1] - h) // 2, w, h), 2)
        surf.blit(ring, (c[0] - size[0] // 2, c[1] - size[1] // 2))


GLOW_STILL = (140, 220, 255)


def _draw_still_scene(surf, key, t, rect):
    from .theme import draw_still
    water_y = rect.bottom - 120
    _cave_backdrop(surf, rect)
    pygame.draw.rect(surf, (4, 6, 10), (rect.x, water_y, rect.w, rect.bottom - water_y))
    c = (rect.centerx, water_y + 50)
    if key == "cave_dark":
        img = big(lambda s, cx, cy: draw_still(s, cx, cy + 4, t, color=(120, 126, 134)), 24, 3)
        blit_center(surf, img, (rect.centerx, water_y - 30), 150)
        for k in range(3):                                  # a shout, swallowed by the stone
            q = (t * 0.7 + k / 3) % 1.0
            r = int(20 + 60 * q)
            ring = pygame.Surface((2 * r + 4, 2 * r + 4), pygame.SRCALPHA)
            pygame.draw.circle(ring, (200, 200, 200, int(90 * (1 - q) ** 3)), (r + 2, r + 2), r, 1)
            surf.blit(ring, (rect.centerx + 20 - r, water_y - 50 - r))
    elif key == "still_folk":
        _rings(surf, c, t, 0.25)
        for i, x in enumerate((-260, -150, 150, 260)):      # the Still, around the water's edge
            img = big(lambda s, cx, cy, i=i: draw_still(s, cx, cy + 4, t + i, reach=True), 24, 4)
            blit_center(surf, img, (rect.centerx + x, water_y - 30))
    elif key == "pool":
        _rings(surf, c, t, 0.18)
        add_glow(surf, (rect.centerx, rect.y + 10), 220, (40, 42, 44))      # grey light from above
        img = big(lambda s, cx, cy: draw_still(s, cx, cy + 4, t, reach=True), 24, 5)
        blit_center(surf, img, (rect.centerx - 200, water_y - 40))
    elif key == "pool_glow":
        _rings(surf, c, t, 1.0, count=6, size=(900, 260), speed=0.3)
        add_glow(surf, c, 300, (20, 60, 80))
        for i, x in enumerate((-320, 300)):
            img = big(lambda s, cx, cy, i=i: draw_still(s, cx, cy + 4, t + i, reach=True), 24, 4)
            blit_center(surf, img, (rect.centerx + x, water_y - 30))
    elif key == "wake":
        x = rect.x + 160 + (t * 50) % (rect.w - 240)
        for i in range(18):                                 # the glowing wake, fading behind
            px = x - i * 22
            if px < rect.x:
                break
            k = 1 - i / 18
            pygame.draw.ellipse(surf, scale_color(GLOW_STILL, k), (px - 18, water_y + 40 - 5, 36, 10), 2)
        for f in (1, 2):
            fx = x - f * 110
            if fx > rect.x + 20:
                img = big(lambda s, cx, cy, f=f: draw_still(s, cx, cy + 4, t + f, color=(170, 178, 190)), 24, 3)
                blit_center(surf, img, (fx, water_y + 20))
        img = big(lambda s, cx, cy: draw_still(s, cx, cy + 4, t, reach=True), 24, 4)
        blit_center(surf, img, (x + 10, water_y + 10))
    elif key == "tarn":
        _rings(surf, c, t, 1.0, count=5, size=(960, 280), speed=0.5)
        add_glow(surf, c, 200, (20, 60, 80))
        img = big(lambda s, cx, cy: draw_still(s, cx, cy + 4, t, reach=True), 24, 7)
        blit_center(surf, img, (rect.centerx - 40, water_y - 60))


def _draw_tick_scene(surf, key, t, rect):
    from .theme import draw_guild_warden, draw_pocket_watch, draw_thief
    surf.blit(vertical_gradient(rect.size, (30, 20, 14), (14, 10, 8)), rect.topleft)
    for gx, gy, gr, sp in ((rect.x + 120, rect.y + 120, 90, 0.3), (rect.right - 140, rect.y + 90, 70, -0.4),
                           (rect.right - 60, rect.bottom - 80, 50, 0.6)):
        _gear(surf, (gx, gy), gr, t * sp, (64, 46, 28))
    if key == "guild":
        c = (rect.centerx, rect.centery - 10)                 # the drum, wound thick with the lost day
        pygame.draw.rect(surf, (110, 80, 40), (c[0] - 150, c[1] - 70, 300, 140), border_radius=12)
        for i in range(26):
            y = c[1] - 62 + i * 5
            pygame.draw.line(surf, scale_color(GOLD, 0.6 + 0.4 * math.sin(t * 2 + i * 0.5)), (c[0] - 140, y),
                             (c[0] + 140, y + 2), 2)
        add_glow(surf, c, 220, (90, 70, 20))
        for i, x in enumerate((-260, 260)):                   # Guildmasters, keeping it
            img = big(lambda s, cx, cy, i=i: draw_guild_warden(s, cx, cy + 4, t, (1 if x < 0 else -1, 0)), 28, 5)
            blit_center(surf, img, (c[0] + x, rect.bottom - 120))
    elif key == "maren":
        add_glow(surf, (rect.centerx, rect.centery), 200, (70, 50, 24))
        img = big(lambda s, cx, cy: draw_thief(s, cx, cy + 4, t, watch=False), 24, 7)
        blit_center(surf, img, (rect.centerx - 150, rect.bottom - 130))
        img = big(lambda s, cx, cy: draw_lamplighter(s, cx, cy + 4, t, lantern=False), 30, 6)
        blit_center(surf, img, (rect.centerx + 170, rect.bottom - 130), 200)
        k = ease_out((t % 4.0) / 2.5)                          # the lantern, passing from her hands to his
        lx = lerp(rect.centerx - 95, rect.centerx + 120, k)
        add_glow(surf, (int(lx), rect.bottom - 150), 60, (120, 90, 40))
        lamp = big(lambda s, cx, cy: draw_sconce(s, cx, cy, True, t), 20, 3)
        blit_center(surf, lamp, (lx, rect.bottom - 150))
    elif key == "watch":
        c = (rect.centerx, rect.centery)
        add_glow(surf, c, 240, (90, 70, 24))
        draw_pocket_watch(surf, c, 130, t, backwards=True)
        img = big(lambda s, cx, cy: draw_thief(s, cx, cy + 4, t), 24, 4)
        blit_center(surf, img, (rect.centerx + 260, rect.bottom - 80))
    elif key == "tick_halls":
        pygame.draw.rect(surf, (44, 30, 22), (rect.x, rect.bottom - 110, rect.w, 110))
        for i in range(3):
            x = rect.x + ((t * 60 + i * 330) % (rect.w + 120)) - 60
            add_glow(surf, (int(x + 30), rect.bottom - 120), 80, (100, 70, 30))
            img = big(lambda s, cx, cy: draw_guild_warden(s, cx, cy + 4, t, (1, 0)), 28, 4)
            blit_center(surf, img, (x, rect.bottom - 120))


def _gear(surf, c, r, angle, color):
    teeth = max(8, r // 8)
    pts = []
    for k in range(teeth * 2):
        a = angle + k * math.pi / teeth
        rr = r if k % 2 == 0 else r * 0.82
        pts.append((c[0] + math.cos(a) * rr, c[1] + math.sin(a) * rr))
    pygame.draw.polygon(surf, color, pts)
    pygame.draw.circle(surf, scale_color(color, 0.6), c, int(r * 0.55))
    pygame.draw.circle(surf, scale_color(color, 1.3), c, int(r * 0.2))


class IntroScreen(Screen):
    """The story so far, as illustrated panels (Echo Delve's by default). Enter/Space/click: finish
    the line, then next. Left/Backspace: back. Esc: skip."""

    TYPE_SPEED = 60.0          # characters per second

    def __init__(self, app, on_done, panels=None, title=None):
        super().__init__(app)
        self.on_done = on_done
        self.panels = panels or story.INTRO
        self.title = title                                   # whose chapter this is, if anyone's
        scenery.prewarm([PAINTED[p[0]] for p in self.panels if p[0] in PAINTED])
        self.i = 0
        self.t = 0.0
        self.add((W - 220, H - 56, 200, 40), "Next  (Enter)", self.advance, tag="next")
        self.add((20, H - 56, 160, 40), "Skip  (Esc)", self.finish, tag="skip")

    @property
    def scene(self):
        return self.panels[self.i]

    def typed(self):
        return int(self.t * self.TYPE_SPEED)

    def line_done(self):
        return self.typed() >= len(self.scene[1])

    def advance(self):
        if not self.line_done():
            self.t = len(self.scene[1]) / self.TYPE_SPEED + 0.01
            return
        if self.i + 1 >= len(self.panels):
            self.finish()
            return
        self.i += 1
        self.t = 0.0
        self.btn("next").label = "Begin  (Enter)" if self.i == len(self.panels) - 1 else "Next  (Enter)"

    def back(self):
        if self.i > 0:
            self.i -= 1
            self.t = 99.0
            self.btn("next").label = "Next  (Enter)"

    def finish(self):
        self.on_done()

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.finish()
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_RIGHT, pygame.K_d):
                self.advance()
            elif ev.key in (pygame.K_LEFT, pygame.K_BACKSPACE, pygame.K_a):
                self.back()
            else:
                return False
            self.app.dirty = True
            return True
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.button_at(ev.pos) is None:
            self.advance()
            self.app.dirty = True
            return True
        return super().handle(ev)

    def update(self, dt):
        self.t += dt
        return True

    def draw(self, surf):
        surf.fill(BG)
        art = pygame.Rect(0, 0, W, 440)
        key, text = self.scene
        draw_scene(surf, key, self.t, art)
        fade = pygame.Surface((W, 44), pygame.SRCALPHA)
        for y in range(44):
            pygame.draw.line(fade, (*BG, int(255 * y / 44)), (0, y), (W, y))
        surf.blit(fade, (0, art.bottom - 44))
        if self.title:                                     # whose chapter: quietly, in the corner
            draw_text(surf, self.app.italic[22], self.title, (28, 18), (214, 184, 130))
            pygame.draw.line(surf, (150, 120, 80), (28, 46), (28 + self.app.italic[22].size(self.title)[0], 46))
        if self.t < 0.5:                                   # fade each panel in from black
            veil = pygame.Surface((W, art.h), pygame.SRCALPHA)
            veil.fill((*BG, int(255 * (1 - self.t / 0.5))))
            surf.blit(veil, (0, 0))
        shown = text[:self.typed()]
        font = self.app.italic[26]
        lines = wrap_text(font, text, 820)
        y, used = 462, 0
        for line in lines:
            part = shown[used:used + len(line)]
            used += len(line) + 1
            if part:
                surf.blit(font.render(part, True, TEXT), (70, y))
            y += font.get_linesize() + 2
        for k in range(len(self.panels)):                  # progress pips
            c = ACCENT if k == self.i else (80, 66, 60)
            pygame.draw.circle(surf, c, (W // 2 - (len(self.panels) - 1) * 10 + k * 20, H - 36), 4)
        self.draw_buttons(surf)


# ---------------------------------------------------------------- floor victory

class VictoryScreen(Screen):
    """The stairs blaze, your echoes come apart into thread that flows back to you, and the
    floor's score is tallied. Any key or click finishes the animation; the next one continues."""

    SURGE = 1.6                 # light and echo-dissolve phase
    ROW_GAP = 0.28
    COUNT = 0.55

    def __init__(self, app, final=False):
        super().__init__(app)
        self.parent = app.stack[-1]
        self.run = app.run
        self.final = final
        self.result = self.run.last_result
        self.t = 0.0
        self.fx = Particles(900)
        self.stamped = False
        self.rows = self._rows()
        self.stamp_at = self.SURGE + 0.4 + len(self.rows) * self.ROW_GAP + self.COUNT
        self.done_at = self.stamp_at + 0.35
        self.add((W // 2 - 130, 0, 260, 40), "Continue  (Enter)", self.proceed, tag="continue")
        self._layout()
        self._release_echoes()

    def _rows(self):
        r = self.result
        pct = int(round(100 * r.par / max(1, r.spent)))
        fast = "" if not r.par_fast or r.par <= r.par_fast else "  (fastest %d)" % r.par_fast
        rows = [("Turns taken", r.spent, ""), ("Par", r.par, fast), ("Loops", r.loops, ""), ("Efficiency", pct, "%")]
        if r.lamps_total:
            rows.append(("Sconces lit", r.lamps, " of %d  (+%d)" % (r.lamps_total, r.lamp_points)))
        return rows + [("Score", r.score, "")]

    def _layout(self):
        self.panel = pygame.Rect(W // 2 - 300, 96, 600, 470)
        b = self.btn("continue")
        b.rect.w = 340 if self.final else 260
        b.rect.topleft = (W // 2 - b.rect.w // 2, self.panel.bottom - 56)

    def _release_echoes(self):
        """Every echo on the floor comes apart into motes that stream back to you."""
        sim = self.run.sim
        px, py = self.parent.tile_center(sim.player.pos)
        for g in sim.ghosts:
            gx, gy = self.parent.tile_center(g.pos)
            c = ghost_color(g.script.label)
            for k in range(26):
                self.fx.toward(gx + random.uniform(-8, 8), gy + random.uniform(-8, 8), px, py, c,
                               life=0.7 + k * 0.03, size=2)
        self.fx.emit(px, py, GOLD, n=40, speed=90, life=1.0, size=2)

    @property
    def finished(self):
        return self.t >= self.done_at

    def skip(self):
        self.t = max(self.t, self.done_at)
        self._stamp()

    def proceed(self):
        if not self.finished:
            self.skip()
            return
        self.app.after_victory()

    def _stamp(self):
        if self.stamped:
            return
        self.stamped = True
        c = GRADE_COLORS.get(self.result.grade, TEXT)
        cx, cy = self.panel.right - 110, self.panel.y + 250
        self.fx.emit(cx, cy, c, n=40, speed=140, life=0.7, size=2)

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN or (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1):
            self.proceed()
            self.app.dirty = True
            return True
        return super().handle(ev)

    def update(self, dt):
        self.t += dt
        self.parent.update(dt)
        self.parent.ghost_fade = 1.0 - ease_out(self.t / 0.9)      # the echoes come apart
        if self.t >= self.stamp_at:
            self._stamp()
        if self.t < self.SURGE:                             # sparks rising from every lit torch
            for tp in self.run.lit:
                if random.random() < dt * 8:
                    x, y = self.parent.tile_center(tp)
                    self.fx.emit(x, y, TORCH, n=1, speed=40, life=0.9, gravity=-50, angle=-math.pi / 2, spread=1.0)
        self.fx.update(dt)
        return True

    def draw(self, surf):
        self.parent.draw(surf)
        floor = self.run.floor
        ex, ey = self.parent.tile_center(floor.exit)
        surge = ease_out(self.t / self.SURGE)
        add_glow(surf, (ex, ey), int(40 + 420 * surge), scale_color((150, 110, 40), 1 - 0.5 * surge))
        for tp in self.run.lit:                             # the torches flare
            x, y = self.parent.tile_center(tp)
            add_glow(surf, (x, y), int(50 * (1 - surge * 0.5)), (120, 70, 20))
        self.fx.draw(surf)
        if self.t < self.SURGE * 0.8:
            return
        k = ease_out((self.t - self.SURGE * 0.8) / 0.5)
        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((6, 4, 10, int(160 * k)))
        surf.blit(veil, (0, 0))
        self._draw_panel(surf, k)
        self.fx.draw(surf)

    def _draw_panel(self, surf, k):
        p = self.panel.move(0, int((1 - k) * 60))
        draw_panel(surf, p, fill=(24, 20, 26))
        r, f, b, it = self.result, self.app.fonts, self.app.bold, self.app.italic
        n = r.floor
        title = "The thread is tied" if self.final else "Floor %d cleared" % n
        draw_glow_text(surf, b[44], title, (p.centerx, p.y + 42), ACCENT, (140, 80, 30), alpha=255 * k)
        sub = text_surface(it[22], story.floor_name(n), DIM, 255 * k)
        surf.blit(sub, sub.get_rect(center=(p.centerx, p.y + 78)))
        y = p.y + 98
        for line in wrap_text(it[18], story.floor_cleared(n), p.w - 80):
            img = text_surface(it[18], line, TEXT, 255 * k)
            surf.blit(img, img.get_rect(center=(p.centerx, y + 8)))
            y += it[18].get_linesize()
        draw_rule(surf, p.centerx, y + 14, 380)
        y += 34
        start = self.SURGE + 0.4
        for i, (label, value, suffix) in enumerate(self.rows):
            t0 = start + i * self.ROW_GAP
            if self.t < t0:
                break
            q = ease_out((self.t - t0) / self.COUNT)
            shown = int(round(value * q))
            is_score = label == "Score"
            font = b[26] if is_score else f[22]
            col = ACCENT if is_score else TEXT
            surf.blit(font.render(label, True, DIM if not is_score else TEXT), (p.x + 60, y))
            val = "{:,}{}".format(shown, suffix)
            img = font.render(val, True, col)
            surf.blit(img, img.get_rect(topright=(p.x + 330, y)))
            y += 30 if not is_score else 36
        self._draw_grade(surf, p)
        if self.t >= self.stamp_at:
            rewards = ["+1 thread"] if self.run.thread is None else []
            if r.bonus:
                rewards.append("+%d bonus shard%s" % (r.bonus, "" if r.bonus == 1 else "s"))
            if r.spent < r.par:
                rewards.insert(0, "Under par by %d!" % (r.par - r.spent))
            if r.lamps_total and r.lamps >= r.lamps_total:
                rewards.insert(0, "Every sconce lit")
            img = b[18].render("   ".join(rewards), True, THREAD)
            rr = img.get_rect(center=(p.centerx + 10, p.bottom - 78))
            surf.blit(img, rr)
            draw_spool(surf, (rr.x - 12, rr.centery), THREAD)
        if self.finished:
            self.btn("continue").rect.y = p.bottom - 56
            self.btn("continue").label = "Continue  (Enter)" if not self.final else "Climb into the morning  (Enter)"
            self.draw_buttons(surf)

    def _draw_grade(self, surf, p):
        if self.t < self.stamp_at:
            return
        q = min(1.0, (self.t - self.stamp_at) / 0.25)
        scale = lerp(2.4, 1.0, ease_out(q))
        c = GRADE_COLORS.get(self.result.grade, TEXT)
        cx, cy = p.right - 110, p.y + 250
        rad = int(54 * scale)
        ring = pygame.Surface((rad * 2 + 4, rad * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(ring, (*scale_color(c, 0.25), int(220 * q)), (rad + 2, rad + 2), rad)
        pygame.draw.circle(ring, (*c, int(255 * q)), (rad + 2, rad + 2), rad, 3)
        surf.blit(ring, (cx - rad - 2, cy - rad - 2))
        img = self.app.bold[80].render(self.result.grade, True, c)
        if scale != 1.0:
            img = pygame.transform.smoothscale(img, (int(img.get_width() * scale), int(img.get_height() * scale)))
        img.set_alpha(int(255 * q))
        surf.blit(img, img.get_rect(center=(cx, cy + 2)))
        lab = self.app.italic[18].render("grade", True, DIM)
        surf.blit(lab, lab.get_rect(center=(cx, cy + 70)))


def draw_fraying_thread(surf, t, y, rect_w=W):
    """A golden thread that snaps in the middle and frays apart (the lost ending)."""
    gap = ease_out(t / 1.6) * 160
    sag = ease_out(t / 1.6) * 18
    for side in (-1, 1):
        pts = []
        for i in range(40):
            x = rect_w // 2 + side * (gap / 2 + i * (rect_w / 2 - gap / 2) / 39)
            yy = y + sag * (1 - i / 39) ** 2 + math.sin(t * 2 + i * 0.4) * 2
            pts.append((x, yy))
        pygame.draw.lines(surf, GOLD, False, pts, 2)
        x0, y0 = pts[0]
        for j in range(6):
            a = side * 0.3 + (j - 2.5) * 0.25
            pygame.draw.line(surf, scale_color(GOLD, 0.7), (x0, y0),
                             (x0 - side * math.cos(a) * 10, y0 + math.sin(a) * 10 + 4), 1)

