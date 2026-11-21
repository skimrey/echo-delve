"""The look of Echo Delve: fonts, light, stone panels, particles and the procedural sprites
(the lamplighter, her echoes, the things in the Deep, torches in their sconces).

Everything is drawn with plain pygame calls and cached surfaces, so it stays CPU-cheap.
"""

import math
import os
import random

import pygame

ASSETS = os.path.join(os.path.dirname(__file__), "assets")
FONT_FILES = {"regular": "texgyrepagella-regular.otf", "bold": "texgyrepagella-bold.otf",
              "italic": "texgyrepagella-italic.otf"}
# the game asks for nominal sizes (tuned for pygame's default font); Pagella runs larger
FONT_SCALE = {16: 14, 18: 15, 22: 18, 26: 21, 32: 26, 44: 36, 80: 64}

# light
TORCH = (255, 158, 72)
LANTERN = (255, 206, 140)
GOLD = (244, 204, 112)
EMBER = (255, 120, 50)
STONE = (52, 46, 50)
BRONZE = (150, 112, 64)
BRONZE_DIM = (92, 70, 46)


def load_fonts(sizes=(16, 18, 22, 26, 32, 44, 80)):
    """{style: {nominal size: Font}}; falls back to pygame's default font if a file is missing."""
    out = {}
    for style, fname in FONT_FILES.items():
        path = os.path.join(ASSETS, "fonts", fname)
        fonts = {}
        for s in sizes:
            px = FONT_SCALE.get(s, round(s * 0.8))
            try:
                fonts[s] = pygame.font.Font(path, px)
            except (OSError, FileNotFoundError, pygame.error):
                f = pygame.font.Font(None, s)
                f.set_bold(style == "bold")
                f.set_italic(style == "italic")
                fonts[s] = f
        out[style] = fonts
    return out


# ---------------------------------------------------------------- math helpers

def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(a, b, t):
    t = clamp(t)
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def scale_color(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


def flicker(t, seed=0.0, amount=0.12):
    """A smooth pseudo-random flicker around 1.0 for torch and lantern light."""
    return 1.0 + amount * (0.55 * math.sin(t * 9.1 + seed * 3.7) + 0.3 * math.sin(t * 15.3 + seed * 1.3)
                           + 0.15 * math.sin(t * 27.7 + seed * 5.1))


# ---------------------------------------------------------------- cached light sprites

_GLOW_CACHE = {}


def glow(radius, color, falloff=2.0):
    """A radial gradient (bright centre, black edge) for additive or multiplicative light."""
    radius = max(2, int(radius) // 2 * 2)
    color = tuple(int(c) // 8 * 8 for c in color[:3])
    key = (radius, color, falloff)
    s = _GLOW_CACHE.get(key)
    if s is None:
        if len(_GLOW_CACHE) > 600:
            _GLOW_CACHE.clear()
        s = pygame.Surface((radius * 2, radius * 2))
        s.fill((0, 0, 0))
        steps = max(8, min(40, radius // 2))
        for i in range(steps, 0, -1):
            f = i / steps
            k = (1 - f) ** falloff
            pygame.draw.circle(s, scale_color(color, k), (radius, radius), int(radius * f))
        _GLOW_CACHE[key] = s
    return s


def add_glow(surf, center, radius, color, falloff=2.0):
    g = glow(radius, color, falloff)
    r = g.get_width() // 2
    surf.blit(g, (center[0] - r, center[1] - r), special_flags=pygame.BLEND_RGB_ADD)


_GRAD_CACHE = {}


def vertical_gradient(size, top, bottom):
    key = (size, top, bottom)
    s = _GRAD_CACHE.get(key)
    if s is None:
        w, h = size
        s = pygame.Surface(size)
        for y in range(h):
            pygame.draw.line(s, lerp_color(top, bottom, y / max(1, h - 1)), (0, y), (w, y))
        _GRAD_CACHE[key] = s
    return s


def alpha_blit(surf, src, pos, alpha):
    if alpha >= 255:
        surf.blit(src, pos)
    elif alpha > 0:
        src.set_alpha(int(alpha))
        surf.blit(src, pos)
        src.set_alpha(None)


def text_surface(font, text, color, alpha=255):
    img = font.render(str(text), True, color)
    if alpha < 255:
        img.set_alpha(max(0, int(alpha)))
    return img


def draw_glow_text(surf, font, text, center, color, glow_color=None, alpha=255):
    """Text with a soft warm halo (titles)."""
    gc = glow_color or scale_color(color, 0.45)
    img = text_surface(font, text, color, alpha)
    r = img.get_rect(center=center)
    halo = font.render(str(text), True, gc)
    halo.set_alpha(int(70 * alpha / 255))
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (-1, 1), (1, -1)):
        surf.blit(halo, r.move(dx, dy))
    surf.blit(img, r)
    return r


# ---------------------------------------------------------------- panels

def draw_panel(surf, rect, fill=(30, 26, 32), edge=BRONZE, radius=8, alpha=None, studs=True):
    """A dark stone panel with a bronze rim and corner studs."""
    rect = pygame.Rect(rect)
    if alpha is not None:
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (*fill, alpha), s.get_rect(), border_radius=radius)
        surf.blit(s, rect.topleft)
    else:
        pygame.draw.rect(surf, fill, rect, border_radius=radius)
    inner = rect.inflate(-6, -6)
    pygame.draw.rect(surf, scale_color(edge, 0.45), inner, 1, border_radius=max(0, radius - 3))
    pygame.draw.rect(surf, edge, rect, 2, border_radius=radius)
    if studs and rect.w > 40 and rect.h > 30:
        for cx, cy in ((rect.x + 7, rect.y + 7), (rect.right - 8, rect.y + 7),
                       (rect.x + 7, rect.bottom - 8), (rect.right - 8, rect.bottom - 8)):
            pygame.draw.circle(surf, scale_color(edge, 0.6), (cx, cy), 3)
            pygame.draw.circle(surf, scale_color(edge, 1.25), (cx - 1, cy - 1), 1)


def draw_rule(surf, center_x, y, width, color=BRONZE):
    """A decorative divider: a line with a diamond in the middle."""
    pygame.draw.line(surf, scale_color(color, 0.6), (center_x - width // 2, y), (center_x + width // 2, y), 1)
    pygame.draw.polygon(surf, color, [(center_x, y - 4), (center_x + 5, y), (center_x, y + 4), (center_x - 5, y)])


# ---------------------------------------------------------------- particles

class Particles:
    """Tiny glowing motes: embers, thread fibres, dust. p = [x, y, vx, vy, life, max_life, color, size, gravity]."""

    def __init__(self, cap=600):
        self.items = []
        self.cap = cap

    def emit(self, x, y, color, n=1, speed=40.0, life=0.8, size=2, gravity=0.0, spread=math.tau,
             angle=0.0, rng=random):
        for _ in range(n):
            if len(self.items) >= self.cap:
                return
            a = angle + (rng.random() - 0.5) * spread
            v = speed * (0.4 + 0.6 * rng.random())
            lf = life * (0.6 + 0.4 * rng.random())
            self.items.append([x, y, math.cos(a) * v, math.sin(a) * v, lf, lf, color, size, gravity])

    def toward(self, x, y, tx, ty, color, life=0.9, size=2):
        """A mote that flies from (x, y) to (tx, ty) over its life."""
        if len(self.items) < self.cap:
            self.items.append([x, y, (tx - x) / life, (ty - y) / life, life, life, color, size, 0.0])

    def update(self, dt):
        alive = []
        for p in self.items:
            p[4] -= dt
            if p[4] <= 0:
                continue
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += p[8] * dt
            alive.append(p)
        self.items = alive
        return bool(alive)

    def draw(self, surf):
        for x, y, _, _, life, mx, color, size, _ in self.items:
            k = life / mx
            c = scale_color(color, 0.35 + 0.65 * k)
            if size <= 1:
                surf.set_at((int(x), int(y)), c)
            else:
                pygame.draw.circle(surf, c, (int(x), int(y)), max(1, int(size * (0.5 + 0.5 * k))))

    def __len__(self):
        return len(self.items)


# ---------------------------------------------------------------- sprites

def draw_flame(surf, x, y, t, seed=0.0, scale=1.0, bright=1.0):
    """A flickering flame whose base sits at (x, y)."""
    f = flicker(t, seed, 0.18)
    h = 9 * scale * f
    w = 3.6 * scale
    sway = math.sin(t * 6.0 + seed) * 1.4 * scale
    outer = [(x - w, y), (x - w * 0.6, y - h * 0.5), (x + sway, y - h), (x + w * 0.6, y - h * 0.5), (x + w, y)]
    pygame.draw.polygon(surf, scale_color(EMBER, bright), outer)
    inner = [(x - w * 0.55, y), (x + sway * 0.6, y - h * 0.68), (x + w * 0.55, y)]
    pygame.draw.polygon(surf, scale_color((255, 214, 120), bright), inner)
    pygame.draw.circle(surf, scale_color((255, 246, 210), bright), (int(x), int(y - 1)), max(1, int(1.4 * scale)))


def draw_sconce(surf, x, y, lit, t, seed=0.0, scale=1.0):
    """An iron wall sconce; (x, y) is where the torch head sits."""
    iron, iron_hi = (46, 40, 44), (96, 86, 84)
    s = scale
    # wall plate and arm
    pygame.draw.rect(surf, iron, (x - 3 * s, y + 4 * s, 6 * s, 8 * s), border_radius=2)
    pygame.draw.line(surf, iron_hi, (x - 2 * s, y + 5 * s), (x - 2 * s, y + 10 * s), 1)
    pygame.draw.line(surf, iron, (x, y + 8 * s), (x, y + 2 * s), max(2, int(2 * s)))
    # cup
    pygame.draw.polygon(surf, iron, [(x - 4 * s, y), (x + 4 * s, y), (x + 2.5 * s, y + 3 * s), (x - 2.5 * s, y + 3 * s)])
    pygame.draw.line(surf, iron_hi, (x - 4 * s, y), (x + 4 * s, y), 1)
    if lit:
        draw_flame(surf, x, y, t, seed, s)
    else:
        pygame.draw.rect(surf, (30, 26, 26), (x - 2 * s, y - 3 * s, 4 * s, 3 * s))     # cold, charred stub


def draw_lamplighter(surf, cx, cy, t, scale=1.0, lantern=True, tint=None, alpha=255):
    """Aurel: a hooded lamplighter in a blue cloak, his mother's lantern held out to one side."""
    s = scale
    bob = math.sin(t * 2.2) * 0.8 * s
    cy = cy + bob
    cloak, hood, trim = (62, 88, 136), (80, 106, 156), (176, 196, 236)
    if tint:
        cloak, hood, trim = scale_color(tint, 0.45), scale_color(tint, 0.6), tint
    layer = surf
    if alpha < 255:
        layer = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    body = [(cx, cy - 9 * s), (cx + 7.5 * s, cy + 9 * s), (cx - 7.5 * s, cy + 9 * s)]
    pygame.draw.polygon(layer, cloak, body)
    pygame.draw.polygon(layer, trim, body, 1)
    pygame.draw.circle(layer, hood, (int(cx), int(cy - 5 * s)), int(5.2 * s))
    pygame.draw.circle(layer, (22, 22, 30), (int(cx), int(cy - 4.3 * s)), int(3.1 * s))
    pygame.draw.circle(layer, (250, 226, 180), (int(cx - 1.2 * s), int(cy - 4.6 * s)), max(1, int(0.6 * s)))
    pygame.draw.circle(layer, (250, 226, 180), (int(cx + 1.2 * s), int(cy - 4.6 * s)), max(1, int(0.6 * s)))
    if lantern:
        lx, ly = cx + 8 * s, cy - 2 * s + math.sin(t * 2.2 + 0.8) * 0.6 * s
        pygame.draw.line(layer, (90, 80, 70), (cx + 3 * s, cy + 1 * s), (lx, ly - 3 * s), max(1, int(s)))
        pygame.draw.rect(layer, (70, 60, 50), (lx - 2.5 * s, ly - 3 * s, 5 * s, 6.5 * s), 1)
        glow_c = scale_color(LANTERN, flicker(t, 2.0, 0.15))
        pygame.draw.rect(layer, glow_c, (lx - 1.5 * s, ly - 2 * s, 3 * s, 4.5 * s))
    if layer is not surf:
        layer.set_alpha(alpha)
        surf.blit(layer, (0, 0))


def echo_sprite(color, size=24):
    """A translucent hooded figure with a frayed hem, in the echo's colour (cached per colour)."""
    key = ("echo", color, size)
    s = _GLOW_CACHE.get(key)
    if s is None:
        s = pygame.Surface((size, size), pygame.SRCALPHA)
        c = size / 2
        k = size / 24
        body = [(c, c - 9 * k), (c + 7 * k, c + 6 * k), (c + 5 * k, c + 9 * k), (c + 2.5 * k, c + 7 * k),
                (c, c + 9.5 * k), (c - 2.5 * k, c + 7 * k), (c - 5 * k, c + 9 * k), (c - 7 * k, c + 6 * k)]
        pygame.draw.polygon(s, (*scale_color(color, 0.5), 170), body)
        pygame.draw.polygon(s, (*color, 230), body, 1)
        pygame.draw.circle(s, (*scale_color(color, 0.65), 200), (int(c), int(c - 5 * k)), int(5 * k))
        pygame.draw.circle(s, (*scale_color(color, 0.18), 220), (int(c), int(c - 4.3 * k)), int(3 * k))
        _GLOW_CACHE[key] = s
    return s


def draw_echo(surf, cx, cy, t, color, seed=0.0, alpha=255):
    img = echo_sprite(color)
    shimmer = 0.82 + 0.18 * math.sin(t * 3.1 + seed * 1.7)
    float_y = math.sin(t * 1.8 + seed) * 1.2
    img.set_alpha(int(alpha * shimmer))
    surf.blit(img, (int(cx - 12), int(cy - 12 + float_y)))
    img.set_alpha(None)


def draw_enemy(surf, kind, cx, cy, t, awake, seed=0.0, lantern_lit=False):
    if kind == "crawler":
        scuttle = math.sin(t * (12 if awake else 3) + seed) * 1.5
        for i in range(3):
            for side in (-1, 1):
                a = -0.7 + i * 0.7
                x1, y1 = cx + side * 5, cy + i * 2 - 1
                x2, y2 = cx + side * (10 + math.cos(a) * 1.5), cy + math.sin(a) * 6 + scuttle * (1 if i % 2 else -1)
                pygame.draw.line(surf, (70, 24, 30), (x1, y1), (x2, y2), 2)
        pygame.draw.ellipse(surf, (92, 30, 38), (cx - 8, cy - 6, 16, 13))
        pygame.draw.ellipse(surf, (140, 50, 56), (cx - 6, cy - 5, 10, 6))
        eye = (255, 90, 60) if awake else (150, 70, 60)
        pygame.draw.circle(surf, eye, (int(cx - 3), int(cy - 1)), 2)
        pygame.draw.circle(surf, eye, (int(cx + 3), int(cy - 1)), 2)
    elif kind == "archer":
        robe = [(cx, cy - 6), (cx + 7, cy + 9), (cx - 7, cy + 9)]
        pygame.draw.polygon(surf, (70, 52, 100), robe)
        pygame.draw.polygon(surf, (130, 100, 170), robe, 1)
        pygame.draw.circle(surf, (216, 210, 190), (int(cx), int(cy - 6)), 4)
        pygame.draw.circle(surf, (30, 20, 40), (int(cx - 1), int(cy - 6)), 1)
        pygame.draw.circle(surf, (30, 20, 40), (int(cx + 2), int(cy - 6)), 1)
        pygame.draw.arc(surf, (160, 120, 70), (cx + 2, cy - 8, 10, 16), -1.4, 1.4, 2)
        pygame.draw.line(surf, (200, 190, 170), (cx + 7, cy - 7), (cx + 7, cy + 7), 1)
    elif kind == "brute":
        pygame.draw.rect(surf, (84, 76, 72), (cx - 10, cy - 9, 20, 19), border_radius=5)
        pygame.draw.rect(surf, (120, 108, 100), (cx - 10, cy - 9, 20, 19), 2, border_radius=5)
        glow_c = (255, 140, 60) if awake else (150, 90, 50)
        pygame.draw.line(surf, glow_c, (cx - 6, cy + 2), (cx - 1, cy + 6), 1)
        pygame.draw.line(surf, glow_c, (cx + 3, cy - 2), (cx + 7, cy + 4), 1)
        pygame.draw.rect(surf, glow_c, (cx - 5, cy - 4, 3, 2))
        pygame.draw.rect(surf, glow_c, (cx + 2, cy - 4, 3, 2))
    else:   # warden: a lamplighter whose thread ran out
        body = [(cx, cy - 10), (cx + 9, cy + 10), (cx - 9, cy + 10)]
        pygame.draw.polygon(surf, (70, 76, 72), body)
        pygame.draw.polygon(surf, GOLD, body, 2)
        pygame.draw.circle(surf, (96, 102, 96), (int(cx), int(cy - 5)), 6)
        pygame.draw.circle(surf, (24, 26, 26), (int(cx), int(cy - 4)), 4)
        pygame.draw.circle(surf, (180, 230, 210), (int(cx - 1), int(cy - 4)), 1)
        pygame.draw.circle(surf, (180, 230, 210), (int(cx + 2), int(cy - 4)), 1)
        lx, ly = cx - 10, cy - 1
        pygame.draw.rect(surf, (60, 60, 60), (lx - 3, ly - 3, 6, 7), 1)
        if lantern_lit:                                                       # your mother's lantern
            pygame.draw.rect(surf, scale_color(LANTERN, flicker(t, seed, 0.15)), (lx - 2, ly - 2, 4, 5))
        else:                                                                 # a cold lantern
            pygame.draw.rect(surf, (40, 50, 50), (lx - 2, ly - 2, 4, 5))


def draw_heart(surf, cx, cy, color, size=6):
    s = size
    pygame.draw.circle(surf, color, (cx - s // 2, cy - s // 3), s // 2 + 1)
    pygame.draw.circle(surf, color, (cx + s // 2, cy - s // 3), s // 2 + 1)
    pygame.draw.polygon(surf, color, [(cx - s, cy - s // 6), (cx + s, cy - s // 6), (cx, cy + s)])


def draw_hourglass(surf, cx, cy, color):
    pygame.draw.polygon(surf, color, [(cx - 5, cy - 7), (cx + 5, cy - 7), (cx, cy)], 1)
    pygame.draw.polygon(surf, color, [(cx - 5, cy + 7), (cx + 5, cy + 7), (cx, cy)], 1)
    pygame.draw.polygon(surf, color, [(cx - 3, cy + 6), (cx + 3, cy + 6), (cx, cy + 2)])
    pygame.draw.line(surf, color, (cx - 6, cy - 7), (cx + 6, cy - 7), 2)
    pygame.draw.line(surf, color, (cx - 6, cy + 7), (cx + 6, cy + 7), 2)


def draw_flag(surf, cx, cy, color):
    pygame.draw.line(surf, color, (cx - 4, cy - 7), (cx - 4, cy + 7), 2)
    pygame.draw.polygon(surf, color, [(cx - 3, cy - 7), (cx + 6, cy - 4), (cx - 3, cy - 1)])


def draw_still(surf, cx, cy, t, reach=False, color=(206, 216, 226)):
    """One of the Still: pale, slight, long-haired, barefoot; a hand held out to touch the water."""
    bob = math.sin(t * 1.6) * 0.6
    cy = cy + bob
    body = [(cx, cy - 8), (cx + 6, cy + 9), (cx - 6, cy + 9)]
    pygame.draw.polygon(surf, scale_color(color, 0.55), body)
    pygame.draw.polygon(surf, color, body, 1)
    pygame.draw.circle(surf, color, (int(cx), int(cy - 6)), 4)
    pygame.draw.line(surf, scale_color(color, 0.75), (cx - 4, cy - 8), (cx - 5, cy + 1), 2)     # long hair
    pygame.draw.line(surf, scale_color(color, 0.75), (cx + 4, cy - 8), (cx + 5, cy + 1), 2)
    pygame.draw.circle(surf, (20, 24, 30), (int(cx - 1), int(cy - 6)), 1)                    # big dark eyes
    pygame.draw.circle(surf, (20, 24, 30), (int(cx + 2), int(cy - 6)), 1)
    if reach:
        pygame.draw.line(surf, color, (cx + 3, cy), (cx + 9, cy + 6), 2)


def draw_guild_warden(surf, cx, cy, t, facing=(1, 0), lamp=True):
    """A Guild warden of the Tick: long coat, tall hat, lantern held the way they face."""
    pygame.draw.polygon(surf, (60, 40, 34), [(cx, cy - 7), (cx + 7, cy + 10), (cx - 7, cy + 10)])
    pygame.draw.polygon(surf, (150, 112, 64), [(cx, cy - 7), (cx + 7, cy + 10), (cx - 7, cy + 10)], 1)
    pygame.draw.circle(surf, (214, 190, 160), (int(cx), int(cy - 6)), 4)
    pygame.draw.rect(surf, (30, 24, 24), (cx - 4, cy - 15, 8, 6))
    pygame.draw.line(surf, (30, 24, 24), (cx - 6, cy - 9), (cx + 6, cy - 9), 2)
    if lamp:
        lx, ly = cx + facing[0] * 8, cy + facing[1] * 8 - 1
        pygame.draw.rect(surf, scale_color(LANTERN, flicker(t, cx, 0.12)), (lx - 2, ly - 2, 4, 5))


def draw_thief(surf, cx, cy, t, watch=True):
    """Maren: a dark hooded cloak, an auburn braid, the Regulator glinting at her wrist."""
    bob = math.sin(t * 2.0) * 0.6
    cy = cy + bob
    body = [(cx, cy - 8), (cx + 7, cy + 9), (cx - 7, cy + 9)]
    pygame.draw.polygon(surf, (46, 58, 52), body)
    pygame.draw.polygon(surf, (120, 150, 130), body, 1)
    pygame.draw.circle(surf, (60, 74, 66), (int(cx), int(cy - 5)), 5)                       # hood
    pygame.draw.circle(surf, (226, 200, 176), (int(cx), int(cy - 4)), 3)                     # face
    pygame.draw.line(surf, (170, 80, 40), (cx + 3, cy - 5), (cx + 6, cy + 3), 2)             # the braid
    if watch:
        k = 0.5 + 0.5 * math.sin(t * 3.0)
        pygame.draw.circle(surf, scale_color(GOLD, 0.7 + 0.3 * k), (int(cx - 5), int(cy + 2)), 2)


def draw_pocket_watch(surf, c, r, t, backwards=False):
    """The Regulator: a gold pocket watch on a short chain."""
    cx, cy = c
    rim = max(2, r // 10)
    pygame.draw.line(surf, GOLD, (cx, cy - r), (cx + r // 2, cy - r - r // 2), max(2, rim // 2))   # the chain
    pygame.draw.rect(surf, GOLD, (cx - rim, cy - r - rim * 2, rim * 2, rim * 2))                 # the crown
    pygame.draw.circle(surf, scale_color(GOLD, 0.55), (cx, cy), r)
    pygame.draw.circle(surf, (240, 228, 196), (cx, cy), max(2, r - rim))
    pygame.draw.circle(surf, GOLD, (cx, cy), r, rim)
    a = (-1 if backwards else 1) * t * 2.0 - math.pi / 2
    pygame.draw.line(surf, (40, 30, 24), (cx, cy), (cx + math.cos(a) * (r - 3), cy + math.sin(a) * (r - 3)), 2)
    pygame.draw.line(surf, (40, 30, 24), (cx, cy), (cx + math.cos(a / 12) * (r - 5), cy + math.sin(a / 12) * (r - 5)), 2)
