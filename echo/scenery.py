"""Painted story scenes, in pixel art.

Each scene is drawn on a small canvas (a third of the screen in each direction) and scaled up
with nearest-neighbour, so its pixels match the dungeon's sprites. A scene has a static layer,
painted once and cached (textured rock, masonry, baked lamplight), an animated layer drawn each
frame on the small canvas (flames, the thread, water, people), and soft light added on top at
full resolution.
"""

import math
import random
import threading

import pygame

from .theme import GOLD, LANTERN, add_glow, flicker, lerp, lerp_color, scale_color

S = 3                                   # screen pixels per canvas pixel
LW, LH = 320, 147                       # the canvas for a 960 x 440 picture

BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def bayer(x, y):
    """Ordered-dither threshold for a pixel, in (0, 1)."""
    return (BAYER[y & 3][x & 3] + 0.5) / 16.0


# ---------------------------------------------------------------- noise and pixels

class Noise:
    """Smooth value noise over the canvas (a few octaves), values in 0..1."""

    def __init__(self, seed, w=LW, h=LH, octaves=((28, 0.5), (11, 0.3), (4, 0.2))):
        rng = random.Random(seed)
        self.w, self.h = w, h
        acc = [0.0] * (w * h)
        for cell, weight in octaves:
            sw, sh = w // cell + 2, h // cell + 2
            small = pygame.Surface((sw, sh))
            for y in range(sh):
                for x in range(sw):
                    v = rng.randrange(256)
                    small.set_at((x, y), (v, v, v))
            big = pygame.transform.smoothscale(small, (sw * cell, sh * cell))
            raw = pygame.image.tobytes(big, "RGB")
            bw = sw * cell
            for y in range(h):
                row = y * bw * 3
                base = y * w
                for x in range(w):
                    acc[base + x] += raw[row + x * 3] / 255.0 * weight
        self.v = acc

    def __call__(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.v[y * self.w + x]
        return 0.5


def shade_pick(shades, k, x, y):
    """One of `shades` (dark to light) for a value k in 0..1, dithered between neighbours."""
    n = len(shades) - 1
    f = max(0.0, min(0.9999, k)) * n
    i = int(f)
    return shades[min(n, i + (1 if f - i > bayer(x, y) else 0))]


def paint(surf, test, color_at, box=None):
    """Set every pixel in `box` (default: all) where test(x, y) holds to color_at(x, y)."""
    x0, y0, x1, y1 = box or (0, 0, surf.get_width(), surf.get_height())
    for y in range(max(0, y0), min(surf.get_height(), y1)):
        for x in range(max(0, x0), min(surf.get_width(), x1)):
            if test(x, y):
                surf.set_at((x, y), color_at(x, y))


def bake_light(surf, lights, ambient=(0.32, 0.30, 0.34), box=None, levels=7):
    """Multiply a region by lamplight: ambient plus each light (x, y, radius, (r, g, b) strength),
    falling off with distance. The result is quantised to a few steps with ordered dithering, so the
    light lands in pixel-art bands rather than a smooth blur."""
    x0, y0, x1, y1 = box or (0, 0, surf.get_width(), surf.get_height())
    w, h = x1 - x0, y1 - y0
    acc = [[list(ambient) for _ in range(w)] for _ in range(h)]
    for lx, ly, rad, col in lights:
        for y in range(max(y0, int(ly - rad)), min(y1, int(ly + rad) + 1)):
            for x in range(max(x0, int(lx - rad)), min(x1, int(lx + rad) + 1)):
                d = math.hypot(x - lx, y - ly) / rad
                if d < 1.0:
                    f = (1.0 - d) ** 2
                    a = acc[y - y0][x - x0]
                    a[0] += col[0] * f
                    a[1] += col[1] * f
                    a[2] += col[2] * f
    for y in range(y0, y1):
        row = acc[y - y0]
        for x in range(x0, x1):
            r, g, b = surf.get_at((x, y))[:3]
            d = bayer(x, y)
            k = row[x - x0]
            q = [math.floor(c * levels + d) / levels for c in k]
            surf.set_at((x, y), (min(255, int(r * q[0])), min(255, int(g * q[1])), min(255, int(b * q[2]))))


def sprite(surf, x, y, rows, palette):
    """Draw a tiny pixel sprite given as strings ('.' is transparent) with its top-left at (x, y)."""
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch != ".":
                surf.set_at((int(x) + i, int(y) + j), palette[ch])


# tiny people for the wide scenes (5-6 pixels tall), bottom-centre anchored by the helpers below
AUREL_MINI = ["..H..", ".hhh.", ".hfh.", "hhhhh.", "hhhhhl", "hhhhh.", ".h.h."]
STILL_MINI = [".p.", "ppp", "pPp", "pPp", ".P."]
MAREN_MINI = ["..c..", ".cfc.", ".cccb", "ccccc", ".ccc."]
WARDEN_MINI = [".w.", "www", "wWw", "wWwl", "www"]


def mini(surf, kind, x, y, t=0.0, phase=0.0, color=None):
    """A tiny figure standing with its feet at (x, y)."""
    bob = 1 if math.sin(t * 2.0 + phase) > 0.6 else 0
    if kind == "aurel":
        pal = {"h": (70, 96, 150), "H": (96, 120, 170), "f": (26, 26, 44), "l": LANTERN}
        sprite(surf, x - 2, y - 7 - bob, AUREL_MINI, pal)
    elif kind == "still":
        c = color or (206, 216, 226)
        sprite(surf, x - 1, y - 5 - bob, STILL_MINI, {"p": c, "P": scale_color(c, 0.6)})
    elif kind == "maren":
        sprite(surf, x - 2, y - 5 - bob, MAREN_MINI, {"c": (56, 72, 62), "f": (226, 200, 176), "b": (170, 80, 40)})
    elif kind == "warden":
        c = color or (110, 104, 96)
        sprite(surf, x - 1, y - 5, WARDEN_MINI, {"w": c, "W": scale_color(c, 0.6), "l": LANTERN})


# ---------------------------------------------------------------- shared palettes

ROCK = [(36, 32, 36), (50, 45, 47), (64, 58, 58), (80, 72, 70), (98, 88, 84)]
LIMESTONE = [(34, 38, 44), (46, 50, 56), (60, 64, 70), (76, 80, 84), (92, 96, 100)]
STONE = [(70, 62, 58), (92, 82, 76), (118, 106, 96), (140, 128, 114)]
SKY_TOP, SKY_LOW = (8, 10, 28), (48, 36, 70)
ROOF = (11, 9, 18)


def rock_fill(surf, noise, palette, box=None, test=None, darken=None, seed=0):
    """Textured rock: noise mapped onto a palette with dithering, with strata and the odd seam.
    darken(y) -> 0..1 scales the value with depth."""
    x0, y0, x1, y1 = box or (0, 0, surf.get_width(), surf.get_height())
    for y in range(y0, y1):
        dk = darken(y) if darken else 1.0
        for x in range(x0, x1):
            if test is not None and not test(x, y):
                continue
            v = noise(x, y)
            k = v * 0.85 + 0.1
            band = y + int(4 * math.sin(x / 19.0 + seed) + 3 * math.sin(x / 7.0) + 6 * noise((x * 5) % noise.w, 0))
            if band % 13 == 0 and noise((x * 7 + 31) % noise.w, (y * 3) % noise.h) > 0.52:
                k -= 0.3                                                        # strata, broken into seams
            surf.set_at((x, y), shade_pick(palette, k * dk, x, y))


def seams(surf, rng, box, color, n=8, length=(6, 16)):
    """Hairline cracks wandering through rock."""
    x0, y0, x1, y1 = box
    for _ in range(n):
        x, y = rng.randrange(x0, x1), rng.randrange(y0, y1)
        for _ in range(rng.randint(*length)):
            if x0 <= x < x1 and y0 <= y < y1:
                surf.set_at((x, y), color)
            x += rng.choice((-1, 0, 1, 1))
            y += rng.choice((0, 1, 1))


def sky(surf, h, t=0.0, seed=3, moon=(40, 9), dawn=False):
    """Night sky over the top `h` rows, with stars and a thin moon (or, at dawn, a rising sun)."""
    rng = random.Random(seed)
    top, low = ((90, 110, 170), (250, 176, 112)) if dawn else (SKY_TOP, SKY_LOW)
    for y in range(h):
        for x in range(surf.get_width()):
            k = y / max(1, h - 1)
            c = lerp_color(top, low, k + (bayer(x, y) - 0.5) * 0.12)
            surf.set_at((x, y), c)
    if dawn:
        pygame.draw.circle(surf, (255, 236, 190), (60, h - 2), 7)
        return
    for _ in range(60):
        surf.set_at((rng.randrange(surf.get_width()), rng.randrange(max(1, h - 6))), (150, 150, 180))
    if moon:
        mx, my = moon
        pygame.draw.circle(surf, (220, 218, 196), (mx, my), 4)
        pygame.draw.circle(surf, SKY_TOP, (mx + 2, my - 1), 4)


def rooftops(surf, ground, x0, x1, seed=4, color=ROOF, windows=True):
    rng = random.Random(seed)
    x = x0
    out = []
    pygame.draw.rect(surf, color, (x0, ground - 4, x1 - x0, 4))            # (no sky between the houses)
    while x < x1:
        w = rng.randint(9, 17)
        h = rng.randint(5, 11)
        pygame.draw.rect(surf, color, (x, ground - h, w, h))
        peak = rng.randint(3, 6)
        pygame.draw.polygon(surf, color, [(x - 1, ground - h), (x + w // 2, ground - h - peak), (x + w, ground - h)])
        if rng.random() < 0.5:
            pygame.draw.rect(surf, color, (x + w - 4, ground - h - peak - 2, 2, 4))          # a chimney
        if windows and rng.random() < 0.55:
            out.append((x + rng.randint(2, w - 3), ground - h + rng.randint(2, max(2, h - 3))))
        x += w + rng.randint(-2, 0)
    return out


# ---------------------------------------------------------------- scene machinery

_STATIC = {}
_LOCK = threading.Lock()
_BUILDING = {}                          # key -> Event, while a static layer is being painted


def _key(scene):
    return (type(scene).__name__, getattr(scene, "variant", None))


def static_for(scene):
    """The scene's static layer, painted on first use (or waited for, if it is being painted)."""
    key = _key(scene)
    while True:
        with _LOCK:
            done = _STATIC.get(key)
            if done is not None:
                return done
            ev = _BUILDING.get(key)
            mine = ev is None
            if mine:
                ev = _BUILDING[key] = threading.Event()
        if not mine:
            ev.wait()
            continue
        try:
            surf = pygame.Surface((LW, LH))
            scene.build(surf)
            with _LOCK:
                _STATIC[key] = surf
        finally:
            with _LOCK:
                _BUILDING.pop(key, None)
            ev.set()
        return surf


def prewarm(scenes):
    """Paint static layers in the background (an intro does this for its panels while the first
    one is being read), so turning to the next panel never stalls."""
    todo = [sc for sc in scenes if _key(sc) not in _STATIC]
    if todo:
        threading.Thread(target=lambda: [static_for(sc) for sc in todo], daemon=True).start()


class Scene:
    """A painted scene: build() paints the static canvas once; frame() draws the moving parts on
    a copy of it; glow() adds soft light at full resolution."""

    def build(self, c):
        raise NotImplementedError

    def frame(self, c, t):
        pass

    def glow(self, surf, t, ox, oy):
        pass


_SCALE = [S]                            # screen pixels per canvas pixel, for the picture being drawn


def draw(surf, scene, t, rect):
    """Paint `scene` to cover `rect` (3x for the usual 960 x 440 picture; larger rects are covered
    and cropped, keeping the picture centred)."""
    c = static_for(scene).copy()
    scene.frame(c, t)
    f = max(rect.w / LW, rect.h / LH, 1.0)
    if abs(f - S) < 0.02:
        f = S
    w, h = int(round(LW * f)), int(round(LH * f))
    img = pygame.transform.scale(c, (w, h))
    ox, oy = rect.x + (rect.w - w) // 2, rect.y + (rect.h - h) // 2
    clip = surf.get_clip()
    surf.set_clip(rect)
    surf.blit(img, (ox, oy))
    _SCALE[0] = f
    try:
        scene.glow(surf, t, ox, oy)
    finally:
        _SCALE[0] = S
        surf.set_clip(clip)


def at(ox, oy, x, y):
    """Screen position of the centre of canvas pixel (x, y)."""
    f = _SCALE[0]
    return (ox + int(x * f + f / 2), oy + int(y * f + f / 2))


def flame(c, x, y, t, seed=0.0, big=False):
    """A two- or three-pixel flame with its base at (x, y)."""
    f = flicker(t, seed, 0.25)
    c.set_at((x, y), (255, 150, 60))
    c.set_at((x, y - 1), (255, 214, 120) if f > 0.97 else (255, 180, 90))
    if big or f > 1.06:
        c.set_at((x + (1 if math.sin(t * 7 + seed) > 0 else 0), y - 2), (255, 236, 180))


def rings(c, cx, cy, t, w, h, color, count=3, speed=0.35, seed=0.0):
    """Expanding ellipses on water (drawn on the canvas, so they stay pixel-crisp)."""
    for k in range(count):
        q = (t * speed + k / count + seed) % 1.0
        rw, rh = max(2, int(w * q)), max(1, int(h * q))
        col = lerp_color(color, (0, 0, 0), q * 0.9)
        pygame.draw.ellipse(c, col, (cx - rw // 2, cy - rh // 2, rw, rh), 1)


# ---------------------------------------------------------------- the Spindle, in section

class Section(Scene):
    """The whole world in one cut through the rock: the town and the Tick above, the Guild's drum,
    the Spindle running straight down to the Loom, the lamplighters' stair switching back and forth
    beside it (the keeper's windows between, the Deep's old rooms opening off it), and the caves of
    the Still on the far side of a skin of limestone.
    variant "whole": long ago, the thread unbroken and every sconce lit.
    variant "broken": the night it snapped; Aurel on the first landing with the broken end.
    variant "night": tonight; Aurel three landings down, Maren in the Drum Room, Tarn in the water.
    variant "lit": the morning after a perfect night: the thread tied, every sconce burning, and the
    Still climbing the stair behind Aurel."""

    GROUND = 28
    SX = 206                        # the Spindle's centre
    FLIGHTS = 5
    TOP = 34                        # the first landing
    DROP = 19
    RIGHT, LEFT = 198, 134          # outer edges of the landings
    BREAK = 74

    def __init__(self, variant):
        self.variant = variant

    @property
    def broken(self):
        return self.variant in ("broken", "night")

    @property
    def hall_y(self):
        return self.TOP + self.FLIGHTS * self.DROP

    def landings(self):
        """(x0, x1, y, side) for every landing, top to bottom."""
        out = []
        for k in range(self.FLIGHTS + 1):
            y = self.TOP + k * self.DROP
            if k % 2 == 0:
                out.append((self.RIGHT - 8, self.RIGHT, y, "right"))
            else:
                out.append((self.LEFT, self.LEFT + 8, y, "left"))
        return out

    def steps(self, k):
        """The treads of flight k, (x0, x1, y), from its top landing down to the next."""
        y0 = self.TOP + k * self.DROP
        n = self.DROP // 2
        run = (self.RIGHT - self.LEFT - 16) // n
        out = []
        for i in range(n):
            y = y0 + (i + 1) * 2
            if k % 2 == 0:                                          # right to left
                x1 = self.RIGHT - 8 - i * run
                out.append((x1 - run, x1, y))
            else:
                x0 = self.LEFT + 8 + i * run
                out.append((x0, x0 + run, y))
        return out

    def sconce(self, i):
        x0, x1, y, side = self.landings()[i]
        return (x0 + 2 if side == "left" else x1 - 3), y - 8

    @property
    def holed(self):
        """The wall between the Spindle and the caves is broken open."""
        return self.variant != "whole"

    def lit(self, i):
        """Whole: the Vells kept every sconce burning. Broken: all cold, but the first landing's.
        Tonight: the ones Aurel has lit on his way down. The morning: all of them."""
        return not self.broken or i <= (2 if self.variant == "night" else 0)

    # -- painting
    def build(self, c):
        G, SX, HY = self.GROUND, self.SX, self.hall_y
        rng = random.Random(12)
        sky(c, G, dawn=self.variant == "lit")
        rock_fill(c, Noise(21), ROCK, box=(0, G, LW, LH), darken=lambda y: 1.0 - 0.35 * (y - G) / (LH - G), seed=1)
        seams(c, rng, (0, G + 4, LW, LH), (30, 27, 30), n=30)
        for _ in range(70):                                                     # grit
            x, y = rng.randrange(LW), rng.randrange(G + 3, LH)
            c.set_at((x, y), ROCK[4] if rng.random() < 0.5 else ROCK[0])
        for x in range(LW):                                                     # soil and roots
            c.set_at((x, G), (52, 40, 34))
            c.set_at((x, G + 1), (40, 31, 28) if bayer(x, G) > 0.3 else (52, 40, 34))
        for _ in range(26):
            x, y = rng.randrange(LW), G + 2
            for _ in range(rng.randint(3, 9)):
                c.set_at((x, y), (44, 34, 30))
                x += rng.choice((-1, 0, 1))
                y += 1
        self._caves(c, rng)
        self._stair(c)
        self._rooms(c, rng)
        self._hall(c)
        self._spindle(c)
        self._tick(c)
        self.town_windows = rooftops(c, G, -6, SX - 13, seed=5) + rooftops(c, G, SX + 14, LW + 6, seed=9)
        lights = []
        for i in range(len(self.landings())):
            if self.lit(i):
                x, y = self.sconce(i)
                lights.append((x, y, 30, (0.95, 0.66, 0.36)))
        for x, y in self.room_lamps:
            if not self.broken:
                lights.append((x, y, 26, (0.8, 0.56, 0.3)))
        loom = 1.0 if not self.broken else 0.6
        lights.append((SX, HY - 9, 64, (0.95 * loom, 0.72 * loom, 0.32 * loom)))
        if self.broken:
            lights.append((256, 94, 52, (0.3, 0.62, 0.78)))
            lights.append((SX + 4, self.BREAK, 24, (0.9, 0.66, 0.3)))
        lights.append((SX, 22, 14, (0.7, 0.5, 0.22)))
        bake_light(c, lights, ambient=(0.58, 0.55, 0.62), box=(0, G, LW, LH))
        if self.variant != "lit":
            for x, y in self.town_windows:
                c.set_at((x, y), (255, 190, 110))
                c.set_at((x, y + 1), (200, 130, 70))

    def _caves(self, c, rng):
        """The caves of the Still: limestone, a low roof hung with stalactites, black water."""
        cave = Noise(33, octaves=((9, 0.7), (3, 0.3)))
        self.cave = {}
        for x in range(212, 304):
            u = (x - 258) / 46.0
            top = int(62 + 12 * u * u + 5 * cave(x, 0))
            bot = int(100 - 3 * u * u - 3 * cave(x, 5))
            self.cave[x] = (top, bot)
            for y in range(top - 2, bot + 2):                               # a rind of limestone
                c.set_at((x, y), shade_pick(LIMESTONE, 0.35 + 0.5 * cave(x, y), x, y))
            for y in range(top, bot):
                if y >= 91:
                    c.set_at((x, y), (12, 22, 34) if not self.broken else lerp_color((26, 70, 96), (14, 40, 60),
                                                                                      (y - 91) / 10))
                else:
                    c.set_at((x, y), (14, 16, 22))
        for x in range(215, 302, 4):                                            # stalactites
            top = self.cave[x][0]
            n = rng.randint(2, 6)
            for j in range(n):
                w = 1 if j < n - 2 else 0
                for dx in range(-w, w + 1):
                    c.set_at((x + dx, top + j), LIMESTONE[3] if dx <= 0 else LIMESTONE[2])
        for x in range(212, 304):
            top, bot = self.cave[x]
            if bot > 91:
                c.set_at((x, 91), (44, 76, 100) if not self.broken else (130, 210, 236))
        for x in range(228, 250):                                               # a ledge for the Still
            c.set_at((x, 87), LIMESTONE[4])
            for y in range(88, 91):
                c.set_at((x, y), LIMESTONE[2] if y < 90 else LIMESTONE[1])

    def _stair(self, c):
        air = (30, 24, 26)
        for x0, x1, y, side in self.landings():
            pygame.draw.rect(c, air, (x0, y - 13, x1 - x0, 13))
        for k in range(self.FLIGHTS):
            for sx0, sx1, y in self.steps(k):
                pygame.draw.rect(c, air, (sx0, y - 15, sx1 - sx0, 15))
        pygame.draw.rect(c, air, (186, self.GROUND - 1, 12, self.TOP - self.GROUND + 1))    # the mouth
        self.windows = []                                                       # the keeper's windows
        for x0, x1, y, side in self.landings()[0:5:2]:
            wy = y - 7
            pygame.draw.rect(c, (22, 18, 20), (self.RIGHT, wy, self.SX - 2 - self.RIGHT, 4))
            pygame.draw.line(c, STONE[2], (self.RIGHT, wy - 1), (self.SX - 3, wy - 1))
            pygame.draw.line(c, STONE[0], (self.RIGHT, wy + 4), (self.SX - 3, wy + 4))
            for j in range(4):
                c.set_at((self.SX - 4, wy + j), (104, 98, 92) if j % 2 == 0 else (22, 18, 20))
            self.windows.append(wy + 2)
        for k in range(self.FLIGHTS):                                           # cut stone treads
            for sx0, sx1, y in self.steps(k):
                pygame.draw.rect(c, STONE[1], (sx0, y, sx1 - sx0, 4))
                pygame.draw.line(c, STONE[3], (sx0, y), (sx1 - 1, y))
                c.set_at((sx0 if k % 2 == 0 else sx1 - 1, y + 1), STONE[2])
                pygame.draw.line(c, STONE[0], (sx0, y + 3), (sx1 - 1, y + 3))
        for x0, x1, y, side in self.landings():
            pygame.draw.rect(c, STONE[1], (x0, y, x1 - x0, 4))
            pygame.draw.line(c, STONE[3], (x0, y), (x1 - 1, y))
            pygame.draw.line(c, STONE[0], (x0, y + 3), (x1 - 1, y + 3))
        for i in range(len(self.landings())):                                   # sconce brackets
            x, y = self.sconce(i)
            c.set_at((x, y + 1), (30, 26, 26))
            c.set_at((x, y + 2), (30, 26, 26))
            c.set_at((x - 1, y + 1), (30, 26, 26))
            c.set_at((x + 1, y + 1), (30, 26, 26))

    def _rooms(self, c, rng):
        """The Deep's old rooms, opening off the left-hand landings: a flooded chapel, an ossuary."""
        self.room_lamps = []
        air = (30, 24, 26)
        # the Flooded Chapel (off the second landing)
        y = self.TOP + self.DROP
        x0, x1 = 74, self.LEFT
        for x in range(x0, x1):
            u = (x - (x0 + x1) / 2) / ((x1 - x0) / 2)
            top = int(y - 15 + 5 * u * u)
            for yy in range(top, y):
                c.set_at((x, yy), air)
        for x in range(x0, x1):
            c.set_at((x, y), STONE[2])
            for yy in range(y + 1, y + 3):
                c.set_at((x, yy), STONE[0])
        for x in range(x0 + 2, x0 + 34):                                        # black water over the pews
            for yy in range(y - 3, y):
                c.set_at((x, yy), (16, 24, 34))
            c.set_at((x, y - 3), (40, 60, 76))
        for px in range(x0 + 6, x0 + 34, 6):
            c.set_at((px, y - 4), (66, 48, 36))
            c.set_at((px + 1, y - 4), (66, 48, 36))
        pygame.draw.line(c, (80, 70, 60), (x0 + 42, y - 1), (x0 + 42, y - 8))   # a lectern
        c.set_at((x0 + 41, y - 8), (80, 70, 60))
        c.set_at((x0 + 43, y - 8), (80, 70, 60))
        bx = (x0 + x1) // 2 + 6                                                  # the bell
        c.set_at((bx, y - 13), (60, 54, 50))
        pygame.draw.rect(c, (150, 120, 60), (bx - 1, y - 12, 3, 2))
        self.room_lamps.append((x1 - 6, y - 8))
        # the Ossuary (off the fourth landing): niches of bones
        y = self.TOP + 3 * self.DROP
        x0, x1 = 60, self.LEFT
        pygame.draw.rect(c, air, (x0, y - 12, x1 - x0, 12))
        for x in range(x0, x1):
            c.set_at((x, y), STONE[2])
            c.set_at((x, y + 1), STONE[0])
        bone = [(206, 198, 176), (176, 168, 150), (140, 132, 118)]
        for nx in range(x0 + 3, x1 - 8, 9):
            for ny in (y - 10, y - 5):
                pygame.draw.rect(c, (18, 14, 16), (nx, ny, 7, 3))
                for bx in range(nx, nx + 7):                                    # long bones, stacked
                    if rng.random() < 0.7:
                        c.set_at((bx, ny + 2), bone[rng.randrange(3)])
                if rng.random() < 0.6:                                          # and a skull, set with care
                    sx = nx + rng.randint(1, 4)
                    c.set_at((sx, ny + 1), bone[0])
                    c.set_at((sx + 1, ny + 1), bone[0])
                    c.set_at((sx, ny), bone[1])
        self.room_lamps.append((x0 + 8, y - 8))
        # a great gear of the clockwork vaults, half buried below
        gx, gy = 96, self.TOP + 5 * self.DROP - 6
        for a in range(0, 360, 3):
            r = 9 if (a // 15) % 2 == 0 else 7
            x = gx + int(math.cos(math.radians(a)) * r)
            yy = gy + int(math.sin(math.radians(a)) * r)
            c.set_at((x, yy), (96, 74, 46))
        pygame.draw.circle(c, (70, 54, 34), (gx, gy), 3)

    def _hall(self, c):
        HY = self.hall_y
        for x in range(120, 286):
            u = (x - 204) / 82.0
            top = int(HY - 21 + 9 * u * u)
            for y in range(top, HY):
                c.set_at((x, y), lerp_color((36, 26, 22), (48, 34, 26), (y - top) / 21))
        for x in range(120, 286):
            c.set_at((x, HY), STONE[3])
            for y in range(HY + 1, HY + 4):
                c.set_at((x, y), STONE[1] if (x // 6 + y) % 5 else STONE[0])
        lx = self.SX - 14                                                       # the Loom
        for px in (lx, lx + 28):
            pygame.draw.rect(c, (80, 56, 38), (px, HY - 17, 3, 17))
            c.set_at((px, HY - 17), (120, 90, 60))
        pygame.draw.rect(c, (100, 70, 46), (lx - 2, HY - 18, 33, 2))
        pygame.draw.rect(c, (100, 70, 46), (lx - 2, HY - 5, 33, 2))

    def _spindle(self, c):
        SX, G = self.SX, self.GROUND
        bottom = self.hall_y - 16
        pygame.draw.rect(c, (12, 9, 11), (SX - 2, G - 3, 5, bottom - G + 3))
        for y in range(G - 3, bottom):
            ring = y % 7 == 0
            c.set_at((SX - 3, y), (104, 96, 90) if ring else (76, 70, 66))
            c.set_at((SX + 3, y), (76, 70, 66) if ring else (50, 46, 46))
        if self.holed:                                                          # the break
            for y in range(self.BREAK - 5, self.BREAK + 6):
                w = 4 + (1 if y in (self.BREAK - 3, self.BREAK, self.BREAK + 2) else 0) - (1 if abs(y - self.BREAK) == 5 else 0)
                for x in range(SX + 3, SX + 3 + w + 2):
                    c.set_at((x, y), (12, 9, 11))
            for x, y in ((214, 90), (216, 89), (219, 90), (217, 90), (222, 90), (215, 88)):
                c.set_at((x, y), LIMESTONE[4])

    def _tick(self, c):
        SX, G = self.SX, self.GROUND
        tx, tw = SX - 12, 25
        for y in range(4, G):                                                   # the tower, in brick
            for x in range(tx, tx + tw):
                brick = (y % 3 == 0) or ((x + (y // 3) * 2) % 5 == 0)
                c.set_at((x, y), (30, 26, 40) if brick else (22, 19, 32))
        pygame.draw.polygon(c, (20, 17, 30), [(tx - 2, 4), (SX, -6), (tx + tw + 1, 4)])
        pygame.draw.circle(c, (210, 196, 160), (SX, 9), 3)                       # the clock, stopped
        c.set_at((SX, 7), (40, 30, 24))
        c.set_at((SX, 8), (40, 30, 24))
        c.set_at((SX + 1, 9), (40, 30, 24))
        pygame.draw.rect(c, (14, 10, 12), (tx + 2, 14, tw - 4, G - 14))          # the Drum Room, cut open
        pygame.draw.rect(c, (48, 36, 28), (tx + 3, 15, tw - 6, G - 16))
        pygame.draw.line(c, (70, 56, 40), (tx + 3, 21), (tx + tw - 4, 21))      # the axle
        pygame.draw.rect(c, (100, 72, 36), (tx + 6, 16, tw - 12, 11))            # the drum, wound thick
        for y in range(17, 26):
            for x in range(tx + 7, tx + tw - 7):
                lum = 1.0 - abs(y - 19.5) / 7.0
                c.set_at((x, y), lerp_color((120, 86, 40), (236, 196, 104), lum if (x + y) % 3 else lum * 0.7))
        for y in range(16, 27):                                                 # its iron cheeks
            c.set_at((tx + 5, y), (60, 50, 44))
            c.set_at((tx + 6, y), (92, 78, 66) if 17 < y < 25 else (60, 50, 44))
            c.set_at((tx + tw - 6, y), (60, 50, 44))
            c.set_at((tx + tw - 7, y), (92, 78, 66) if 17 < y < 25 else (60, 50, 44))

    # -- moving parts
    def frame(self, c, t):
        SX, G, HY = self.SX, self.GROUND, self.hall_y
        for i in range(len(self.landings())):
            if self.lit(i):
                x, y = self.sconce(i)
                flame(c, x, y, t, i)
        if not self.broken:
            for x, y in self.room_lamps:
                flame(c, x, y, t, x)
        if not self.broken:
            for y in range(G - 2, HY - 16):                                    # the whole thread, rising
                q = (y + t * 14) % 23
                c.set_at((SX, y), (255, 240, 190) if q < 1.5 else GOLD)
            for x in range(SX - 11, SX + 14, 2):                               # the warp on the Loom
                pygame.draw.line(c, scale_color(GOLD, 0.85), (x, HY - 16), (x, HY - 6))
            if self.variant == "lit":
                c.set_at((SX - 1, self.BREAK), (255, 244, 210))                 # the knot
                c.set_at((SX + 1, self.BREAK), (255, 244, 210))
                path = self.stair_path()
                for k in range(9):                                              # the Still, climbing behind him
                    q = (t * 0.035 + k * 0.06) % 1.0
                    x, y = path[int((1 - q) * (len(path) - 1))]
                    mini(c, "still", x, y, t, k)
                mini(c, "aurel", 190, self.TOP - 1, t)
                return
            for i, x in enumerate(range(231, 250, 6)):
                mini(c, "still", x, 86, t, i, color=(112, 118, 128))
            return
        # broken: the top half whipped up to the drum; its end fell out of the first keeper's window
        wy = self.windows[0]
        for y in range(G - 2, wy + 1):
            c.set_at((SX, y), GOLD)
        for x in range(self.RIGHT - 2, SX):
            c.set_at((x, wy), GOLD)
        for x, y in ((self.RIGHT - 3, wy + 1), (self.RIGHT - 4, wy + 2), (self.RIGHT - 5, wy + 3)):
            c.set_at((x, y), GOLD)
        if self.variant == "night":                         # the thread, paid out down the stair behind him
            path = [(self.RIGHT - 5, self.TOP - 1)]
            for k in range(2):
                for sx0, sx1, y in self.steps(k):
                    path.append(((sx0 + sx1) // 2, y - 1))
                x0, x1, y, side = self.landings()[k + 1]
                path.append(((x0 + x1) // 2, y - 1))
            path.append((self.RIGHT - 6, self.TOP + 2 * self.DROP - 3))
            pygame.draw.lines(c, scale_color(GOLD, 0.85), False, path)
            mini(c, "aurel", self.RIGHT - 6, self.TOP + 2 * self.DROP - 1, t)
            mini(c, "maren", self.SX - 6, self.GROUND - 2, t, 1.0)
            if (t * 0.9) % 1.0 < 0.5:
                c.set_at((self.SX - 8, self.GROUND - 4), (255, 230, 140))
        else:
            mini(c, "aurel", self.RIGHT - 6, self.TOP - 1, t)
        for y in range(self.BREAK + 3, HY - 6):                                # the lower half, slack
            x = SX + int(round(math.sin(y * 0.33 + t * 0.8) * 1.3))
            c.set_at((x, y), scale_color(GOLD, 0.8))
        for k, x in enumerate(range(SX - 9, SX + 12, 3)):                       # the Loom's warp, slack
            for y in range(HY - 16, HY - 6):
                if (y + k) % 3:
                    c.set_at((x + (1 if y > HY - 11 and k % 2 else 0), y), scale_color(GOLD, 0.5))
        c.set_at((SX, self.BREAK + 2), (255, 240, 190))                         # the frayed ends
        c.set_at((SX, wy - 1), GOLD)
        for k in range(16):                                                     # the day, pouring through
            q = (t * 0.45 + k / 16) % 1.0
            x = SX + 5 + q * 34 + math.sin(k * 2.3) * 3
            y = self.BREAK + q * q * (91 - self.BREAK)
            c.set_at((int(x), int(y)), lerp_color((255, 240, 190), (130, 210, 236), q))
        rings(c, 258, 95, t, 64, 8, (160, 236, 255), count=3, speed=0.3)
        for i, x in enumerate((233, 239, 245)):
            mini(c, "still", x, 86, t, i * 1.7)

    def stair_path(self):
        """Standing places down the whole stair, top to bottom (the mouth, treads and landings)."""
        out = []
        for k, (x0, x1, y, side) in enumerate(self.landings()):
            out.append(((x0 + x1) // 2, y - 1))
            if k < self.FLIGHTS:
                out.extend(((sx0 + sx1) // 2, yy - 1) for sx0, sx1, yy in self.steps(k))
        return out

    def glow(self, surf, t, ox, oy):
        HY = self.hall_y
        for i in range(len(self.landings())):
            if self.lit(i):
                x, y = self.sconce(i)
                add_glow(surf, at(ox, oy, x, y - 1), int(48 * flicker(t, i, 0.08)), (110, 64, 24))
        if not self.broken:
            for x, y in self.room_lamps:
                add_glow(surf, at(ox, oy, x, y - 1), int(40 * flicker(t, x, 0.08)), (100, 60, 22))
            for y in range(self.GROUND, HY - 16, 12):
                add_glow(surf, at(ox, oy, self.SX, y), 18, (64, 48, 16))
        add_glow(surf, at(ox, oy, self.SX, HY - 10), 160 if not self.broken else 100,
                 (96, 70, 24) if not self.broken else (64, 46, 16))
        add_glow(surf, at(ox, oy, self.SX, 21), 44, (90, 66, 26))
        if self.variant == "lit":
            add_glow(surf, at(ox, oy, 60, self.GROUND - 6), 200, (110, 70, 30))          # the sun, coming up
        if self.broken:
            add_glow(surf, at(ox, oy, self.SX + 5, self.BREAK), int(70 * flicker(t, 3, 0.1)), (130, 96, 30))
            add_glow(surf, at(ox, oy, 258, 95), 140, (14, 54, 74))
            ay = self.TOP + (2 * self.DROP if self.variant == "night" else 0)
            add_glow(surf, at(ox, oy, self.RIGHT - 6, ay - 5), int(44 * flicker(t, 9, 0.06)), (110, 80, 36))


# ---------------------------------------------------------------- the break, from the caves

class Break(Scene):
    """The hole the day broke, seen from the caves of the Still: jagged limestone, and through it
    the inside of the Spindle, the slack lower half of the thread, and the Loom's light welling up
    from far below. Tarn stands on the lip; one of the Still has already gone over."""

    HX, HY = 214, 58                      # the hole's centre
    LIP = 90                              # where the rubble slope meets the hole

    def __init__(self, variant="near"):
        self.variant = variant

    _mask = None

    def hole(self, x, y):
        """True inside the jagged hole."""
        if Break._mask is None:
            Break._mask = [[self._hole(i, j) for i in range(LW)] for j in range(LH)]
        return 0 <= x < LW and 0 <= y < LH and Break._mask[y][x]

    def _hole(self, x, y):
        dx, dy = (x - self.HX) / 22.0, (y - self.HY) / 32.0
        if y > self.LIP:
            return False
        a = math.atan2(dy, dx)
        r = 1.0 + 0.13 * math.sin(a * 3 + 1.0) + 0.08 * math.sin(a * 7 + 0.4) + 0.05 * math.sin(a * 13 + 2.0)
        return dx * dx + dy * dy < r * r

    def slope(self, x):
        """The top of the rubble slope that climbs out of the water to the lip of the hole."""
        if x < self.HX:
            k = max(0.0, (x - 30) / (self.HX - 30))
            return int(lerp(128, self.LIP + 1, k ** 0.8) + 2 * math.sin(x / 5.0))
        k = min(1.0, (x - self.HX) / 70)
        return int(lerp(self.LIP + 1, 124, k ** 1.3) + 2 * math.sin(x / 4.0))

    def build(self, c):
        rng = random.Random(41)
        noise = Noise(52)
        rock_fill(c, noise, LIMESTONE, darken=lambda y: 0.85 + 0.15 * y / LH, seed=2)
        seams(c, rng, (0, 0, LW, 120), (26, 28, 34), n=36, length=(5, 14))
        for x in range(LW):                                                     # the ceiling
            top = 10 + int(4 * math.sin(x / 13.0) + 3 * noise(x, 3))
            for y in range(top):
                c.set_at((x, y), shade_pick(LIMESTONE, 0.15 + 0.2 * noise(x, y), x, y))
        x = 2
        while x < LW:                                                           # stalactites
            n = rng.choice((4, 6, 8, 10, 14, 22))
            top = 10 + int(4 * math.sin(x / 13.0))
            base = rng.choice((1, 2, 2, 3))
            for j in range(n):
                w = max(0, base - (j * (base + 1)) // n)
                for dx in range(-w, w + 1):
                    c.set_at((x + dx, top + j), LIMESTONE[4] if dx < 0 else (LIMESTONE[2] if dx == 0 else LIMESTONE[1]))
            if n > 8:
                c.set_at((x, top + n), (170, 190, 200))                         # a drop, about to fall
            x += rng.randint(3, 11)
        # the hole: the inside of the Spindle, masonry courses curving round the bore
        for y in range(0, LH):
            for x in range(LW):
                if not self.hole(x, y):
                    continue
                u = (x - self.HX) / 24.0
                curve = 4 * u * u
                course = int(y + curve) % 6 == 0
                joint = (x + (int(y + curve) // 6) * 5) % 11 == 0
                depth = max(0.0, (y - (self.HY - 34)) / 64.0)
                base = lerp_color((30, 22, 22), (140, 92, 40), depth ** 1.6)
                col = lerp_color(base, (10, 8, 8), min(1.0, abs(u) ** 1.5) * 0.85)
                if course or joint:
                    col = scale_color(col, 0.72)
                c.set_at((x, y), col)
        for y in range(1, LH - 1):                                              # the broken rim
            for x in range(1, LW - 1):
                if self.hole(x, y):
                    continue
                near = [self.hole(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
                if any(near):
                    c.set_at((x, y), (170, 146, 108) if (near[0] or near[2]) else (104, 108, 112))
                elif any(self.hole(x + dx, y + dy) for dx, dy in ((2, 0), (-2, 0), (0, 2), (0, -2))):
                    c.set_at((x, y), (70, 74, 80))
        # the rubble slope, climbing out of the water to the lip
        for x in range(24, 300):
            top = self.slope(x)
            for y in range(top, LH):
                v = noise(x, y * 2 % LH)
                k = 0.3 + 0.55 * v - 0.25 * (y - top) / 30
                c.set_at((x, y), shade_pick(LIMESTONE, k, x, y))
            c.set_at((x, top), LIMESTONE[4])
        for _ in range(90):                                                     # broken blocks of the wall
            x = rng.randrange(60, 290)
            y = self.slope(x) + rng.randrange(0, 8)
            w, h = rng.randint(2, 5), rng.randint(1, 3)
            pygame.draw.rect(c, LIMESTONE[rng.choice((1, 2, 3))], (x, y, w, h))
            pygame.draw.line(c, LIMESTONE[4], (x, y), (x + w - 1, y))
        # the water, in front
        for y in range(118, LH):
            for x in range(LW):
                if y >= self.slope(x) and 24 <= x < 300:
                    continue
                k = (y - 118) / (LH - 118)
                c.set_at((x, y), lerp_color((12, 20, 30), (4, 8, 14), k + (bayer(x, y) - 0.5) * 0.15))
        bake_light(c, [(self.HX, self.HY + 24, 120, (0.8, 0.54, 0.26)), (110, 134, 80, (0.1, 0.26, 0.38)),
                       (self.HX, self.HY + 12, 44, (0.5, 0.34, 0.14))],
                   ambient=(0.34, 0.38, 0.48))
        for y in range(LH):                                                     # darker at the sides
            for x in list(range(0, 30)) + list(range(LW - 30, LW)):
                if min(x, LW - 1 - x) / 30.0 < bayer(x, y) * 0.9:
                    r, g, b = c.get_at((x, y))[:3]
                    c.set_at((x, y), (r * 2 // 3, g * 2 // 3, b * 2 // 3))

    def frame(self, c, t):
        from .theme import draw_still
        top = self.HY - 28                      # the lower half of the thread, hanging from the snap
        for y in range(top, self.LIP + 1):
            if not self.hole(self.HX + 3, y):
                continue
            x = self.HX + 3 + int(round(math.sin(y * 0.17 + t * 0.9) * 2.4 * (y - top) / 60))
            c.set_at((x, y), GOLD if (y + int(t * 10)) % 9 else (255, 240, 190))
        for j in range(4):                                                      # its frayed end
            c.set_at((self.HX + 2 + j - 1, top - 1 - (j % 2)), (255, 226, 150))
        q = (t * 0.28) % 1.0                    # one of them, over the lip, sliding toward the light
        if q < 0.55:
            y = int(self.HY - 14 + (q / 0.55) ** 2 * 44)
            if self.hole(self.HX - 9, y - 3):
                mini(c, "still", self.HX - 9, y, t, 0, color=lerp_color((206, 216, 226), (255, 206, 130), q * 1.6))
        for y in range(120, LH, 2):             # the water: the hole's light, broken into ripples
            for k in range(3):
                x = int(self.HX - 20 + math.sin(t * 1.3 + y * 0.7 + k * 2) * (5 + (y - 120) * 0.5)) + k * 3
                if 0 <= x < LW and y < self.slope(x) and (x + y) % 2 == 0:
                    c.set_at((x, y), (150, 110, 56))
        rings(c, 86, 136, t, 70, 10, (140, 220, 250), count=3, speed=0.32)
        # the Still on the slope, and Tarn at the lip, reaching in
        for i, x in enumerate((120, 146, 170)):
            draw_still(c, x, self.slope(x) - 9, t + i * 1.3, color=lerp_color((150, 160, 172), (206, 216, 226), i / 2))
        draw_still(c, self.HX - 22, self.LIP - 8, t, reach=True)

    def glow(self, surf, t, ox, oy):
        add_glow(surf, at(ox, oy, self.HX, self.HY + 24), int(210 * flicker(t, 1, 0.03)), (70, 46, 16))
        add_glow(surf, at(ox, oy, self.HX + 3, self.HY - 28), 36, (120, 96, 40))
        add_glow(surf, at(ox, oy, 86, 136), 120, (10, 34, 48))


# ---------------------------------------------------------------- people, larger

def figure(c, fn, x, y, factor=2, size=32, alpha=255, tint=None):
    """Draw one of the theme's sprites (fn(surface, cx, cy)) scaled `factor` times onto the canvas,
    with its feet at about (x, y)."""
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    fn(s, size / 2, size / 2)
    if tint is not None:
        s.fill(tint + (255,), special_flags=pygame.BLEND_RGBA_MULT)
    img = pygame.transform.scale(s, (size * factor, size * factor))
    if alpha < 255:
        img.set_alpha(int(alpha))
    c.blit(img, (int(x - size * factor / 2), int(y - size * factor / 2 - 9 * factor)))


def cobbles(c, box, light=(44, 46, 58), dark=(24, 24, 32), seed=0):
    x0, y0, x1, y1 = box
    rng = random.Random(seed)
    for y in range(y0, y1):
        row = (y - y0) // 3
        for x in range(x0, x1):
            off = (row * 4) % 7
            edge = (y - y0) % 3 == 0 or (x + off) % 7 == 0
            k = (y - y0) / max(1, y1 - y0)
            c.set_at((x, y), dark if edge else lerp_color(light, scale_color(light, 0.8), k + rng.random() * 0.2))


def planks(c, box, base=(58, 40, 30), vertical=True, width=6, seed=0):
    x0, y0, x1, y1 = box
    rng = random.Random(seed)
    tones = [scale_color(base, 0.85 + 0.3 * rng.random()) for _ in range(64)]
    for y in range(y0, y1):
        for x in range(x0, x1):
            i = (x - x0) // width if vertical else (y - y0) // width
            gap = ((x - x0) % width == 0) if vertical else ((y - y0) % width == 0)
            grain = ((y * 3 + x) % 9 == 0) if vertical else ((x * 3 + y) % 11 == 0)
            col = scale_color(tones[i % 64], 0.55) if gap else (scale_color(tones[i % 64], 0.9) if grain else tones[i % 64])
            c.set_at((x, y), col)


def gear(c, cx, cy, r, angle, color, teeth=None, spokes=5):
    """A brass gear in pixels: square-cut teeth, a rim, spokes between windows, a hub; lit from
    the upper left."""
    teeth = teeth or max(8, int(r * 0.55))
    hi, lo, dark = scale_color(color, 1.35), scale_color(color, 0.7), scale_color(color, 0.45)
    pts = []
    for k in range(teeth):                                       # square teeth: four corners each
        a0 = angle + k * math.tau / teeth
        for da, rr in ((-0.28, r * 0.84), (-0.18, r), (0.18, r), (0.28, r * 0.84)):
            a = a0 + da * math.tau / teeth
            pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    pygame.draw.polygon(c, lo, pts)
    pygame.draw.circle(c, color, (int(cx), int(cy)), max(1, int(r * 0.84)))
    pygame.draw.circle(c, dark, (int(cx), int(cy)), max(1, int(r * 0.68)))          # the windows
    for k in range(spokes):
        a = angle + k * math.tau / spokes
        x1, y1 = cx + math.cos(a) * r * 0.7, cy + math.sin(a) * r * 0.7
        pygame.draw.line(c, color, (cx, cy), (x1, y1), max(1, int(r / 9)))
    pygame.draw.circle(c, color, (int(cx), int(cy)), max(1, int(r * 0.26)))          # the hub
    pygame.draw.circle(c, dark, (int(cx), int(cy)), max(1, int(r * 0.1)))
    if r >= 8:                                                                          # a gleam on the rim
        pygame.draw.arc(c, hi, (cx - r * 0.84, cy - r * 0.84, r * 1.68, r * 1.68), 1.9, 2.9, 1)
        pygame.draw.arc(c, hi, (cx - r * 0.26, cy - r * 0.26, r * 0.52, r * 0.52), 1.9, 2.9, 1)


# ---------------------------------------------------------------- the doorstep

class Doorstep(Scene):
    """The Vells' door, the night their mother did not come back. Aurel on the step with her
    lantern; Maren walking away down the street, into the dark."""

    def build(self, c):
        sky(c, 112, seed=7, moon=(260, 16))
        rooftops(c, 76, -4, LW + 4, seed=11, color=(24, 20, 36))
        pygame.draw.rect(c, (24, 20, 36), (0, 76, LW, 10))
        tx = 236                                                                # the Tick, far off
        pygame.draw.rect(c, (16, 13, 24), (tx, 18, 14, 52))
        pygame.draw.polygon(c, (16, 13, 24), [(tx - 2, 18), (tx + 7, 8), (tx + 16, 18)])
        pygame.draw.circle(c, (150, 140, 116), (tx + 7, 26), 3)
        self.windows = rooftops(c, 84, 110, LW + 6, seed=13, color=(14, 12, 22))
        pygame.draw.rect(c, (14, 12, 22), (110, 84, LW, 30))
        cobbles(c, (0, 112, LW, LH), seed=2)
        # the Vells' house: old stone, a timber lintel, the door standing open
        for y in range(20, 112):
            for x in range(0, 124):
                row = y // 5
                joint = y % 5 == 0 or (x + (row % 2) * 4) % 9 == 0
                c.set_at((x, y), (36, 34, 42) if joint else shade_pick([(52, 50, 60), (60, 58, 68), (68, 64, 74)],
                                                                         0.5 + 0.4 * math.sin(x * 0.7 + y * 1.3), x, y))
        pygame.draw.polygon(c, (22, 18, 26), [(-4, 22), (66, 0), (136, 22)])
        pygame.draw.rect(c, (60, 42, 30), (44, 60, 34, 4))                      # lintel
        pygame.draw.rect(c, (70, 52, 36), (48, 64, 26, 46))                     # the doorway, lit within
        for y in range(64, 110):
            for x in range(48, 74):
                c.set_at((x, y), lerp_color((120, 84, 46), (70, 46, 28), (y - 64) / 46 + (bayer(x, y) - 0.5) * 0.1))
        pygame.draw.rect(c, (44, 30, 24), (74, 64, 7, 46))                      # the door, swung open
        pygame.draw.line(c, (70, 50, 36), (75, 65), (75, 108))
        pygame.draw.rect(c, (80, 74, 78), (42, 108, 38, 4))                     # the step
        pygame.draw.line(c, (110, 104, 106), (42, 108), (79, 108))
        pygame.draw.rect(c, (150, 108, 60), (92, 74, 16, 14))                   # a lit window
        pygame.draw.line(c, (40, 30, 26), (100, 74), (100, 87))
        pygame.draw.line(c, (40, 30, 26), (92, 80), (107, 80))
        pygame.draw.rect(c, (40, 30, 26), (91, 73, 18, 16), 1)
        pygame.draw.line(c, (40, 34, 34), (60, 52), (60, 57))                   # the lamplighters' bracket,
        pygame.draw.line(c, (40, 34, 34), (56, 52), (64, 52))                   # empty now
        bake_light(c, [(61, 92, 70, (0.8, 0.56, 0.3)), (100, 82, 24, (0.5, 0.34, 0.18))],
                   ambient=(0.5, 0.52, 0.66), box=(0, 20, LW, LH))
        for x, y in self.windows:
            c.set_at((x, y), (230, 170, 96))

    def frame(self, c, t):
        from .theme import draw_lamplighter, draw_thief
        k = min(1.0, t / 7.0)
        mx = lerp(150, 296, k)
        figure(c, lambda s, x, y: draw_thief(s, x, y, t, watch=False), mx, 130, factor=2,
               alpha=255 * (1 - k * 0.75), tint=(170, 170, 200))
        figure(c, lambda s, x, y: draw_lamplighter(s, x, y, t), 64, 108, factor=2)

    def glow(self, surf, t, ox, oy):
        add_glow(surf, at(ox, oy, 61, 90), 170, (70, 46, 20))
        add_glow(surf, at(ox, oy, 76, 95), int(70 * flicker(t, 2, 0.06)), (110, 80, 36))


# ---------------------------------------------------------------- the Counting House

class CountingHouse(Scene):
    """Past midnight in the Guild's Counting House: panelling, ledgers, a long-case clock, a tall
    window full of moon, the green-shaded lamp, and on the Guildmaster's desk, the Regulator.
    variant "theft": Maren takes it. variant "ledgers": the Guildmaster, doing the arithmetic.
    variant "desk": a clerk's desk later that night, the watch gone, a ledger left open under the lamp.
    variant "clerk": months before: Maren at a clerk's desk, the Guildmaster winding the tower back."""

    WATCH = (206, 95)

    def __init__(self, variant="theft"):
        self.variant = variant

    def build(self, c):
        planks(c, (0, 0, LW, 100), base=(52, 38, 30), width=7, seed=3)
        for x in range(0, LW, 40):                                              # wainscot panels
            pygame.draw.rect(c, (40, 28, 22), (x + 3, 64, 34, 30), 1)
            pygame.draw.line(c, (80, 60, 44), (x + 4, 65), (x + 35, 65))
        pygame.draw.rect(c, (74, 54, 38), (0, 60, LW, 3))                       # chair rail
        planks(c, (0, 100, LW, LH), base=(64, 44, 30), vertical=False, width=4, seed=5)
        # the tall window, and the town asleep below it
        wx0, wx1, wy0, wy1 = 24, 76, 10, 92
        for y in range(wy0, wy1):
            for x in range(wx0, wx1):
                u = (x - (wx0 + wx1) / 2) / ((wx1 - wx0) / 2)
                if y < wy0 + 14 and (y - wy0 - 14) ** 2 / 196 + u * u > 1:
                    continue
                c.set_at((x, y), lerp_color((20, 24, 52), (52, 46, 80), (y - wy0) / (wy1 - wy0)))
        pygame.draw.circle(c, (226, 224, 200), (62, 26), 5)
        self.town = rooftops(c, wy1, wx0, wx1, seed=17, color=(16, 14, 26))
        for y in range(wy0, wy1):                                               # mullions and frame
            for x in range(wx0 - 2, wx1 + 2):
                inside = wx0 <= x < wx1 and not (y < wy0 + 14 and (y - wy0 - 14) ** 2 / 196 +
                                                  ((x - (wx0 + wx1) / 2) / ((wx1 - wx0) / 2)) ** 2 > 1)
                if not inside:
                    continue
                if x in (wx0, wx1 - 1, (wx0 + wx1) // 2) or (y - wy0) % 16 == 15:
                    c.set_at((x, y), (30, 22, 18))
        pygame.draw.rect(c, (86, 64, 46), (wx0 - 4, wy1, wx1 - wx0 + 8, 3))      # sill
        # a long-case clock, its pendulum swinging behind glass
        cx0 = 96
        pygame.draw.rect(c, (46, 30, 22), (cx0, 30, 18, 74))
        pygame.draw.rect(c, (70, 48, 34), (cx0 + 1, 31, 16, 72), 1)
        pygame.draw.circle(c, (200, 186, 150), (cx0 + 9, 42), 6)
        pygame.draw.circle(c, (90, 70, 50), (cx0 + 9, 42), 6, 1)
        pygame.draw.rect(c, (24, 16, 14), (cx0 + 4, 52, 10, 40))
        # shelves of ledgers
        rng = random.Random(8)
        for sy in (22, 40, 58, 76):
            pygame.draw.rect(c, (70, 50, 34), (262, sy + 14, 56, 2))
            x = 264
            while x < 316:
                w = rng.randint(2, 4)
                h = rng.randint(9, 13)
                col = rng.choice([(110, 40, 34), (60, 70, 40), (50, 56, 90), (120, 90, 50), (80, 30, 40)])
                pygame.draw.rect(c, col, (x, sy + 14 - h, w, h))
                c.set_at((x, sy + 14 - h + 2), (200, 170, 90))
                x += w + (1 if rng.random() < 0.3 else 0)
        # the Guildmaster's desk
        pygame.draw.rect(c, (70, 46, 30), (150, 100, 104, 3))
        pygame.draw.rect(c, (54, 36, 24), (154, 103, 96, 24))
        for dx in (158, 208):
            pygame.draw.rect(c, (44, 30, 20), (dx, 107, 38, 8), 1)
            c.set_at((dx + 19, 111), (180, 150, 80))
        pygame.draw.rect(c, (40, 26, 18), (156, 127, 6, 14))
        pygame.draw.rect(c, (40, 26, 18), (242, 127, 6, 14))
        for i, (lx, col) in enumerate(((160, (120, 44, 36)), (164, (60, 70, 44)), (168, (116, 90, 50)))):
            pygame.draw.rect(c, col, (lx - 2, 92 - i * 3, 18, 3))               # a stack of ledgers
            pygame.draw.line(c, (210, 200, 170), (lx - 1, 93 - i * 3), (lx + 14, 93 - i * 3))
        pygame.draw.rect(c, (26, 24, 30), (188, 95, 4, 5))                      # inkwell and quill
        pygame.draw.line(c, (220, 220, 210), (190, 95), (194, 86))
        pygame.draw.rect(c, (60, 50, 36), (228, 94, 3, 6))                      # the green-shaded lamp
        pygame.draw.polygon(c, (40, 96, 60), [(222, 88), (237, 88), (234, 83), (225, 83)])
        pygame.draw.line(c, (80, 150, 100), (225, 83), (234, 83))
        pygame.draw.rect(c, (50, 40, 30), (224, 99, 12, 1))
        bake_light(c, [(229, 92, 80, (0.95, 0.78, 0.46)), (50, 112, 70, (0.34, 0.38, 0.56)),
                       (60, 60, 44, (0.3, 0.32, 0.46))], ambient=(0.46, 0.43, 0.50))
        for x, y in self.town:
            c.set_at((x, y), (230, 170, 96))

    def taken(self, t):
        """How far the watch has travelled from the desk to Maren's hand (0..1)."""
        if self.variant != "theft":
            return 0.0
        k = min(1.0, max(0.0, (t - 1.2) / 1.0))
        return k * k * (3 - 2 * k)

    def frame(self, c, t):
        from .theme import draw_guild_warden, draw_thief
        a = math.sin(t * 2.2) * 0.45                                           # the pendulum
        px, py = 105 + math.sin(a) * 12, 54 + math.cos(a) * 30
        pygame.draw.line(c, (150, 120, 60), (105, 54), (px, py))
        pygame.draw.circle(c, (200, 160, 80), (int(px), int(py)), 2)
        if self.variant == "clerk":
            wind = t * 1.6                                                      # the pendulum swings backwards
            a = -math.sin(wind) * 0.45
            px, py = 105 + math.sin(a) * 12, 54 + math.cos(a) * 30
            pygame.draw.line(c, (150, 120, 60), (105, 54), (px, py))
            pygame.draw.circle(c, (200, 160, 80), (int(px), int(py)), 2)
            pygame.draw.rect(c, (64, 44, 30), (116, 104, 30, 3))                 # her desk, and her ledger
            pygame.draw.rect(c, (50, 34, 24), (118, 107, 26, 20))
            pygame.draw.rect(c, (226, 216, 190), (122, 100, 14, 4))
            figure(c, lambda s, x, y: draw_thief(s, x, y, t * 0.5, watch=False), 136, 124, factor=2)
            figure(c, lambda s, x, y: draw_guild_warden(s, x, y, t, (-1, 0), lamp=False), 250, 128, factor=2)
            gx, gy = 236, 92                                                    # the watch, held up
            pygame.draw.circle(c, (210, 170, 80), (gx, gy), 3)
            pygame.draw.circle(c, (240, 232, 206), (gx, gy), 2)
            for k in range(3):                                                  # the tower, turning back
                q = (t * 0.6 + k / 3) % 1.0
                r = int(3 + q * 40)
                pygame.draw.circle(c, lerp_color((230, 200, 120), (52, 38, 30), q), (gx, gy), r, 1)
            return
        if self.variant == "desk":                                              # the ledger, open
            pygame.draw.polygon(c, (236, 226, 200), [(196, 97), (208, 95), (208, 99), (196, 100)])
            pygame.draw.polygon(c, (226, 216, 190), [(208, 95), (220, 97), (220, 100), (208, 99)])
            for k in range(3):
                pygame.draw.line(c, (120, 106, 90), (198, 97 + k), (206, 96 + k))
                pygame.draw.line(c, (120, 106, 90), (210, 96 + k), (218, 97 + k))
            for k in range(8):
                q = (t * 0.05 + k / 8) % 1.0
                c.set_at((int(40 + k * 6 + math.sin(t + k) * 4), int(40 + q * 70)), (120, 124, 150))
            return
        k = self.taken(t)                                                       # the Regulator, taken
        wx, wy = int(lerp(self.WATCH[0], 150, k)), int(lerp(self.WATCH[1], 104, k) - math.sin(k * math.pi) * 8)
        if k > 0:
            pygame.draw.rect(c, (60, 44, 30), (self.WATCH[0] - 3, self.WATCH[1] + 2, 7, 1))   # where it lay
        pygame.draw.circle(c, (190, 150, 70), (wx, wy), 3)
        pygame.draw.circle(c, (236, 226, 196), (wx, wy), 2)
        c.set_at((wx, wy - 4), GOLD)
        pygame.draw.line(c, (190, 150, 70), (wx + 2, wy - 2), (wx + 7, wy))
        if (t * 0.8) % 1.0 < 0.15:
            c.set_at((wx + 1, wy - 1), (255, 255, 240))
            c.set_at((wx + 2, wy - 3), (255, 255, 220))
        for k in range(8):                                                      # dust in the moonlight
            q = (t * 0.05 + k / 8) % 1.0
            c.set_at((int(40 + k * 6 + math.sin(t + k) * 4), int(40 + q * 70)), (120, 124, 150))
        if self.variant == "theft":
            figure(c, lambda s, x, y: draw_thief(s, x, y, t, watch=False), 140, 126, factor=2)
        else:                                                                   # the Guildmaster, counting
            figure(c, lambda s, x, y: draw_guild_warden(s, x, y, t, (-1, 0), lamp=False), 272, 128, factor=2)
            if (t * 1.5) % 2 < 1:
                c.set_at((192, 86), (240, 240, 230))                            # the quill, scratching

    def glow(self, surf, t, ox, oy):
        add_glow(surf, at(ox, oy, 229, 92), int(120 * flicker(t, 5, 0.04)), (80, 70, 30))
        if self.variant == "clerk":
            add_glow(surf, at(ox, oy, 236, 92), int(40 + 10 * math.sin(t * 3)), (110, 90, 30))
            add_glow(surf, at(ox, oy, 50, 60), 150, (18, 22, 40))
            return
        if self.variant == "desk":
            add_glow(surf, at(ox, oy, 208, 97), 40, (90, 80, 50))
            add_glow(surf, at(ox, oy, 50, 60), 150, (18, 22, 40))
            return
        k = self.taken(t)
        x, y = lerp(self.WATCH[0], 150, k), lerp(self.WATCH[1], 104, k) - math.sin(k * math.pi) * 8
        add_glow(surf, at(ox, oy, x, y), int(26 + 10 * math.sin(t * 3)), (110, 90, 30))
        add_glow(surf, at(ox, oy, 50, 60), 150, (18, 22, 40))


# ---------------------------------------------------------------- the Tick, inside

def brick_wall(c, dark=(30, 20, 16), a=(48, 32, 24), b=(66, 44, 32), box=None):
    x0, y0, x1, y1 = box or (0, 0, LW, LH)
    for y in range(y0, y1):
        for x in range(x0, x1):
            row = y // 4
            joint = y % 4 == 0 or (x + (row % 2) * 5) % 10 == 0
            k = 0.5 + 0.3 * math.sin(x * 0.13 + y * 0.07) + (bayer(x, y) - 0.5) * 0.3
            c.set_at((x, y), dark if joint else lerp_color(a, b, k))


class TickStair(Scene):
    """Inside the Tick: the alarm bell swinging at the top, gears turning in the walls, a wooden
    stair switching up the tower, and far below, the wardens' lanterns, climbing."""

    X0, X1 = 70, 250
    FLIGHTS = 5

    def flight(self, k):
        """(x, y) of each tread of flight k (0 = the lowest), and which way it climbs."""
        y = LH - 6 - k * 28
        out = []
        for i in range(12):
            x = self.X0 + i * 15 if k % 2 == 0 else self.X1 - (i + 1) * 15
            out.append((x, y - i * 2))
        return out

    def build(self, c):
        brick_wall(c, dark=(26, 17, 14), a=(40, 27, 21), b=(56, 38, 28))
        for x in (22, 298):                                                     # chains
            for y in range(0, LH, 2):
                c.set_at((x, y), (96, 86, 74) if y % 4 else (62, 56, 50))
        bake_light(c, [(160, 10, 100, (0.6, 0.46, 0.26)), (120, 140, 80, (0.7, 0.5, 0.25))],
                   ambient=(0.56, 0.48, 0.46))

    def stair(self, c):
        for k in range(self.FLIGHTS):
            treads = self.flight(k)
            (xa, ya), (xb, yb) = treads[0], treads[-1]
            xb += 15 if k % 2 == 0 else 0
            xa += 0 if k % 2 == 0 else 15
            pygame.draw.line(c, (40, 28, 20), (xa, ya + 4), (xb, yb + 4), 3)      # the stringer, in shadow
            for x, y in treads:
                pygame.draw.rect(c, (104, 74, 48), (x, y, 15, 3))
                pygame.draw.line(c, (150, 112, 72), (x, y), (x + 14, y))
                pygame.draw.line(c, (62, 44, 30), (x, y + 2), (x + 14, y + 2))
            for i in range(0, 12, 3):                                           # posts and the handrail
                x, y = treads[i]
                pygame.draw.line(c, (78, 56, 38), (x + 2, y - 1), (x + 2, y - 9))
            pygame.draw.line(c, (120, 88, 56), (treads[0][0] + 2, treads[0][1] - 9),
                             (treads[-1][0] + 2, treads[-1][1] - 9))
            lx = self.X1 if k % 2 == 0 else self.X0 - 12                        # the landing
            pygame.draw.rect(c, (104, 74, 48), (lx, treads[-1][1] - 2, 12, 3))
            pygame.draw.line(c, (150, 112, 72), (lx, treads[-1][1] - 2), (lx + 11, treads[-1][1] - 2))

    def frame(self, c, t):
        from .theme import draw_thief
        for gx, gy, r, sp, col in ((40, 44, 28, 0.25, (86, 64, 40)), (286, 78, 36, -0.19, (78, 58, 36)),
                                   (252, 20, 15, 0.45, (96, 74, 46)), (120, 112, 20, -0.3, (70, 52, 34))):
            gear(c, gx, gy, r, t * sp, col)
            pygame.draw.circle(c, scale_color(col, 1.35), (gx, gy), r, 1)
        a = math.sin(t * 3.0) * 0.35                                           # the alarm bell
        bx, by = 160 + math.sin(a) * 4, 12
        pygame.draw.line(c, (70, 60, 50), (160, 0), (bx, by - 4))
        pygame.draw.polygon(c, (170, 130, 60), [(bx - 6, by + 6), (bx + 6, by + 6), (bx + 3, by - 4), (bx - 3, by - 4)])
        pygame.draw.line(c, (230, 190, 110), (bx - 4, by + 5), (bx - 2, by - 3))
        pygame.draw.line(c, (100, 74, 40), (bx - 6, by + 6), (bx + 6, by + 6))
        for k in range(3):                                                      # the sound of it
            q = (t * 1.2 + k / 3) % 1.0
            pygame.draw.arc(c, lerp_color((210, 176, 110), (50, 34, 26), q),
                            (bx - 8 - q * 44, by - 6 - q * 22, 16 + q * 88, 20 + q * 44), math.pi * 1.05,
                            math.pi * 1.95, 1)
        self.stair(c)
        low = self.flight(0)                                                    # the wardens, climbing
        for i in range(3):
            step = int(min(11, max(0, t * 0.9 - i * 1.5)))
            x, y = low[max(0, step - i * 2)]
            mini(c, "warden", x + 7, y, t, i)
        x, y = self.flight(3)[7]
        figure(c, lambda s, px, py: draw_thief(s, px, py, t), x + 7, y, factor=1)

    def glow(self, surf, t, ox, oy):
        low = self.flight(0)
        for i in range(3):
            step = int(min(11, max(0, t * 0.9 - i * 1.5)))
            x, y = low[max(0, step - i * 2)]
            add_glow(surf, at(ox, oy, x + 9, y - 3), int(44 * flicker(t, i, 0.1)), (120, 84, 30))
        add_glow(surf, at(ox, oy, 160, 14), 90, (60, 44, 20))


# ---------------------------------------------------------------- the clock face, from behind

class ClockWindow(Scene):
    """The back of one of the Tick's great clock faces: a round window of glass over Hollowmere,
    the hands in silhouette. Far off, at the mouth of the Deep, one sconce is burning again."""

    C, R = (150, 70), 62
    DEEP = (196, 99)

    def inside(self, x, y, pad=0):
        cx, cy = self.C
        return (x - cx) ** 2 + (y - cy) ** 2 < (self.R - pad) ** 2

    def build(self, c):
        cx, cy = self.C
        brick_wall(c, dark=(20, 14, 14), a=(32, 22, 19), b=(40, 28, 23))
        rng = random.Random(23)
        for y in range(LH):                                                     # through the glass: sky,
            for x in range(LW):                                                 # the hill, the town
                if not self.inside(x, y):
                    continue
                hill = int(94 + 6 * math.sin((x - 40) / 16.0) - max(0, 14 - abs(x - self.DEEP[0]) * 0.45))
                if y >= hill:
                    col = lerp_color((30, 26, 40), (20, 18, 30), (y - hill) / 30)
                else:
                    col = lerp_color((12, 14, 36), (58, 42, 76), (y - (cy - self.R)) / (hill - (cy - self.R)) +
                                     (bayer(x, y) - 0.5) * 0.1)
                c.set_at((x, y), col)
        for _ in range(50):
            x, y = rng.randrange(cx - 55, cx + 55), rng.randrange(cy - 58, cy + 10)
            if self.inside(x, y, 4):
                c.set_at((x, y), (150, 150, 184))
        dx, dy = self.DEEP                                                      # the mouth of the Deep
        pygame.draw.ellipse(c, (6, 5, 8), (dx - 5, dy - 5, 10, 10))
        pygame.draw.rect(c, (6, 5, 8), (dx - 5, dy, 10, 5))
        pygame.draw.arc(c, (60, 54, 60), (dx - 6, dy - 6, 12, 12), 0, math.pi, 1)
        town = pygame.Surface((LW, LH), pygame.SRCALPHA)
        self.town = rooftops(town, 124, cx - self.R, cx + self.R, seed=31, color=(12, 10, 20))
        pygame.draw.rect(town, (12, 10, 20), (0, 124, LW, 20))
        for y in range(LH):
            for x in range(LW):
                if self.inside(x, y) and town.get_at((x, y))[3]:
                    c.set_at((x, y), (12, 10, 20))
        self.town = [p for p in self.town if self.inside(*p, pad=3)]
        for r in (self.R, self.R + 1, self.R + 2):                              # the face's iron
            pygame.draw.circle(c, (66, 50, 36), (cx, cy), r, 1)
        for h in range(12):
            a = h / 12 * math.tau
            pygame.draw.line(c, (58, 44, 32), (cx + math.cos(a) * (self.R - 7), cy + math.sin(a) * (self.R - 7)),
                             (cx + math.cos(a) * self.R, cy + math.sin(a) * self.R), 2 if h % 3 == 0 else 1)
        pygame.draw.circle(c, (58, 44, 32), (cx, cy), 20, 1)
        for a in (0.3, 0.3 + math.pi / 3, 0.3 + 2 * math.pi / 3):
            pygame.draw.line(c, (46, 34, 26), (cx + math.cos(a) * self.R, cy + math.sin(a) * self.R),
                             (cx - math.cos(a) * self.R, cy - math.sin(a) * self.R))
        pygame.draw.line(c, (24, 16, 12), (cx, cy), (cx - 12, cy - 46), 3)       # the hands, stopped
        pygame.draw.line(c, (24, 16, 12), (cx, cy), (cx + 30, cy + 12), 4)
        pygame.draw.circle(c, (24, 16, 12), (cx, cy), 4)
        bake_light(c, [(cx, cy, 100, (0.35, 0.34, 0.5))], ambient=(0.72, 0.64, 0.64))
        for x, y in self.town:
            c.set_at((x, y), (230, 170, 96))

    def frame(self, c, t):
        from .theme import draw_thief
        x, y = self.DEEP                                                        # the first sconce, lit again
        flame(c, x + 3, y + 1, t, 4)
        figure(c, lambda s, px, py: draw_thief(s, px, py, t, watch=True), 262, 150, factor=3, tint=(52, 46, 54))

    def glow(self, surf, t, ox, oy):
        x, y = self.DEEP
        add_glow(surf, at(ox, oy, x + 3, y), int(26 * flicker(t, 4, 0.15)), (160, 100, 40))


# ---------------------------------------------------------------- the Drum Room

class DrumRoom(Scene):
    """The top of the Tick: the great drum wound with the last day, seen a little from one end,
    the thread running off it down through the floor, the brake. variant "open": the brake is off,
    the drum is turning, and the hoard is pouring down the thread."""

    X0, X1, Y0, Y1 = 110, 250, 36, 98             # the drum's wound body
    FACE = (100, 67, 36)                           # its near end: a spoked iron wheel (x, y, radius)

    def __init__(self, variant="shut"):
        self.variant = variant
        self._bodies = {}

    def body(self, phase):
        """The wound thread, as a surface, for one of five winding phases."""
        img = self._bodies.get(phase)
        if img is None:
            w, h = self.X1 - self.X0, self.Y1 - self.Y0
            img = pygame.Surface((w, h))
            for y in range(h):
                lum = (1.0 - abs(y - h / 2) / (h / 2)) ** 0.6
                for x in range(w):
                    coil = (y + x // 9 + phase) % 3 == 0
                    base = lerp_color((104, 68, 26), (252, 218, 128), lum)
                    img.set_at((x, y), scale_color(base, 0.72) if coil else base)
            self._bodies[phase] = img
        return img

    def build(self, c):
        brick_wall(c, dark=(28, 18, 14), a=(44, 30, 22), b=(58, 40, 30))
        for x in range(-20, LW, 44):                                            # rafters
            pygame.draw.polygon(c, (58, 40, 28), [(x, 0), (x + 44, 0), (x + 22, 16)])
            pygame.draw.line(c, (84, 60, 40), (x, 0), (x + 22, 16))
        pygame.draw.rect(c, (72, 52, 36), (0, 0, LW, 4))
        planks(c, (0, 120, LW, LH), base=(72, 52, 36), vertical=False, width=4, seed=9)
        pygame.draw.ellipse(c, (6, 4, 4), (173, 119, 14, 5))                    # where the thread goes down
        tx = 262                                                                # the far trestle
        pygame.draw.polygon(c, (70, 50, 34), [(tx - 14, 120), (tx, 64), (tx + 14, 120)])
        pygame.draw.polygon(c, (46, 34, 24), [(tx - 9, 120), (tx, 76), (tx + 9, 120)])
        pygame.draw.rect(c, (70, 60, 54), (self.X1 - 4, 64, 22, 5))             # the axle
        pygame.draw.rect(c, (36, 30, 28), (292, 74, 6, 46))                     # the brake
        pygame.draw.line(c, (120, 110, 100), (295, 76), (312, 48), 3)
        pygame.draw.circle(c, (170, 60, 40), (312, 48), 3)
        bake_light(c, [(180, 66, 130, (0.8, 0.6, 0.3))], ambient=(0.48, 0.42, 0.42))

    def frame(self, c, t):
        from .theme import draw_thief
        opened = self.variant == "open"
        spin = t * (5.0 if opened else 0.0)
        turn = t * (0.6 if opened else 0.05)                                     # the works that drive the drum
        gear(c, 30, 36, 26, turn, (90, 68, 42))
        gear(c, 62, 14, 12, -turn * 26 / 12 + 0.3, (100, 76, 48))
        gear(c, 300, 22, 20, -turn * 1.3, (86, 64, 40))
        c.blit(self.body(int(spin) % 3), (self.X0, self.Y0))
        pygame.draw.ellipse(c, (80, 66, 56), (self.X1 - 4, self.Y0 - 4, 8, self.Y1 - self.Y0 + 8))
        fx, fy, fr = self.FACE                                                  # the near end, spoked
        pygame.draw.circle(c, (58, 48, 42), (fx, fy), fr)
        pygame.draw.circle(c, (96, 82, 70), (fx, fy), fr, 2)
        pygame.draw.circle(c, (40, 32, 28), (fx, fy), fr - 6, 1)
        for k in range(6):
            a = spin * 0.25 + k * math.pi / 3
            pygame.draw.line(c, (84, 72, 62), (fx, fy), (fx + math.cos(a) * (fr - 3), fy + math.sin(a) * (fr - 3)), 2)
        pygame.draw.circle(c, (120, 104, 88), (fx, fy), 5)
        pygame.draw.circle(c, (60, 50, 44), (fx, fy), 2)
        twitch = 0 if opened else int(round(math.sin(t * 9) * math.sin(t * 1.7) * 1.4))
        for y in range(self.Y1, 121):                                           # the thread, down through the floor
            c.set_at((180 + (twitch if y > 106 else 0), y), (255, 236, 170))
        if opened:
            for k in range(34):
                q = (t * 0.9 + k / 34) % 1.0
                x = 180 + math.sin(k * 3.1) * (2 + 16 * (1 - q))
                y = self.Y1 + q * (121 - self.Y1)
                c.set_at((int(x), int(y)), lerp_color((255, 240, 190), (210, 150, 60), q))
        if self.variant == "master":                                             # the Guildmaster, by the brake
            from .theme import draw_guild_warden
            figure(c, lambda s, x, y: draw_guild_warden(s, x, y, t, (-1, 0), lamp=False), 282, 141, factor=2)
            figure(c, lambda s, x, y: draw_thief(s, x, y, t), 196, 141, factor=2)
        else:
            figure(c, lambda s, x, y: draw_thief(s, x, y, t), 214, 141, factor=2)

    def glow(self, surf, t, ox, oy):
        k = 1.5 if self.variant == "open" else 1.0
        add_glow(surf, at(ox, oy, 180, 66), int(220 * k * flicker(t, 2, 0.02)), (66, 48, 16))
        add_glow(surf, at(ox, oy, 180, 120), int(56 * k), (110, 80, 30))


# ---------------------------------------------------------------- Aurel, resting

def draw_sitting(surf, cx, cy, t, tint=None, eyes=True):
    """Aurel (or an echo of him) sitting on a step, knees up, hood down over his eyes."""
    cloak, hood, trim = (62, 88, 136), (80, 106, 156), (176, 196, 236)
    if tint:
        cloak, hood, trim = scale_color(tint, 0.45), scale_color(tint, 0.6), tint
    breathe = 0.5 if math.sin(t * 1.4) > 0 else 0
    body = [(cx - 1, cy - 4 + breathe), (cx + 7, cy + 8), (cx - 7, cy + 8)]
    pygame.draw.polygon(surf, cloak, body)
    pygame.draw.polygon(surf, trim, body, 1)
    pygame.draw.line(surf, trim, (cx + 2, cy + 4), (cx + 8, cy + 3))                   # a knee, drawn up
    pygame.draw.circle(surf, hood, (int(cx - 1), int(cy - 3 + breathe)), 5)
    pygame.draw.circle(surf, (22, 22, 30), (int(cx - 1), int(cy - 2 + breathe)), 3)
    if eyes:
        surf.set_at((int(cx - 2), int(cy - 3 + breathe)), (250, 226, 180))
        surf.set_at((int(cx), int(cy - 3 + breathe)), (250, 226, 180))


class Rest(Scene):
    """Halfway down: Aurel sitting on a step with the lantern beside him; his echoes sitting a
    little way off, the way Maren used to when she was angry and didn't want him to know."""

    def step_y(self, x):
        return int(52 + x * 0.3)

    def build(self, c):
        rock_fill(c, Noise(61), ROCK, seed=4)
        seams(c, random.Random(5), (0, 0, LW, LH), (30, 27, 30), n=30)
        for x in range(LW):                                                     # the stair, cut into rock,
            y = self.step_y(x - x % 12)                                         # going down to the right
            for yy in range(y, LH):
                k = 0.55 - 0.4 * (yy - y) / 40
                c.set_at((x, yy), shade_pick(STONE, k + 0.15 * bayer(x, yy), x, yy))
            c.set_at((x, y), STONE[3])
            if x % 12 == 0:
                for yy in range(self.step_y(x - 12), y):
                    c.set_at((x, yy), STONE[0])
        for x in range(0, LW, 30):                                              # the handrail rope, on pins
            pygame.draw.line(c, (40, 36, 36), (x, self.step_y(x) - 24), (x, self.step_y(x) - 18))
        pygame.draw.line(c, (84, 70, 54), (0, self.step_y(0) - 23), (LW, self.step_y(LW) - 23))
        sx = 56                                                                  # a sconce above, lit
        pygame.draw.line(c, (30, 26, 26), (sx, self.step_y(sx) - 32), (sx, self.step_y(sx) - 29))
        bake_light(c, [(118, 100, 100, (1.0, 0.7, 0.36)), (sx, self.step_y(sx) - 35, 40, (0.7, 0.46, 0.22))],
                   ambient=(0.28, 0.26, 0.32))

    def frame(self, c, t):
        from .game_screen import ghost_color
        sx = 56
        flame(c, sx, self.step_y(sx) - 33, t, 1)
        for i, x in enumerate((196, 232, 268)):                                # his echoes, keeping their distance
            y = self.step_y(x - x % 12)
            col = ghost_color(i + 1)
            layer = pygame.Surface((32, 32), pygame.SRCALPHA)
            draw_sitting(layer, 16, 16, t + i * 2.1, tint=col, eyes=False)
            layer = pygame.transform.scale(layer, (64, 64))
            layer.set_alpha(90 + 30 * i)
            c.blit(layer, (x - 32, y - 50))
        x = 110                                                                 # Aurel, and the lantern beside him
        y = self.step_y(x - x % 12)
        layer = pygame.Surface((32, 32), pygame.SRCALPHA)
        draw_sitting(layer, 16, 16, t)
        c.blit(pygame.transform.scale(layer, (64, 64)), (x - 32, y - 50))
        lx, ly = x + 16, y - 4
        pygame.draw.rect(c, (70, 60, 50), (lx - 3, ly - 8, 7, 8), 1)
        pygame.draw.rect(c, scale_color(LANTERN, flicker(t, 2, 0.15)), (lx - 2, ly - 7, 5, 6))
        pygame.draw.line(c, (90, 80, 70), (lx - 2, ly - 10), (lx + 2, ly - 10))

    def glow(self, surf, t, ox, oy):
        add_glow(surf, at(ox, oy, 126, self.step_y(108) - 10), int(120 * flicker(t, 2, 0.06)), (110, 74, 30))
        add_glow(surf, at(ox, oy, 56, self.step_y(56) - 34), int(40 * flicker(t, 1, 0.08)), (110, 64, 24))


# ---------------------------------------------------------------- the door of the Loom

class LoomDoor(Scene):
    """The bottom of the stair: a great arch full of the Loom's low golden hum, and before it a
    Warden pacing, carrying Aurel's mother's lantern. variant "still": the Still who came down the
    Spindle are there too, sitting close together off to the side. variant "meeting": Aurel and the
    Still, face to face, one of them reaching out to touch his hand."""

    AX, AY, AW, AH = 190, 122, 70, 96                  # the arch: centre x, floor y, width, height

    def __init__(self, variant="door"):
        self.variant = variant

    def build(self, c):
        rock_fill(c, Noise(71), ROCK, seed=6)
        seams(c, random.Random(7), (0, 0, LW, LH), (30, 27, 30), n=24)
        ax, ay, aw, ah = self.AX, self.AY, self.AW, self.AH
        for y in range(ay - ah, ay):                                            # the hall beyond, golden
            for x in range(ax - aw // 2, ax + aw // 2):
                u = (x - ax) / (aw / 2)
                top = ay - ah + (aw / 2) * (1 - math.sqrt(max(0.0, 1 - u * u))) * 0.9
                if y < top:
                    continue
                k = (y - (ay - ah)) / ah
                c.set_at((x, y), lerp_color((110, 74, 30), (210, 160, 80), k + (bayer(x, y) - 0.5) * 0.15))
        lx = ax                                                                 # the Loom, far inside
        for px in (lx - 16, lx + 14):
            pygame.draw.rect(c, (90, 60, 34), (px, ay - 46, 3, 46))
        pygame.draw.rect(c, (110, 74, 42), (lx - 19, ay - 48, 37, 3))
        for x in range(lx - 12, lx + 13, 3):
            for y in range(ay - 44, ay - 6):
                if (y + x) % 4:
                    c.set_at((x + (1 if y > ay - 24 and x % 2 else 0), y), (240, 200, 110))
        for k in range(-1, 2, 2):                                              # the arch's stones
            for j in range(14):
                a = math.pi * (0.5 + k * 0.5 * j / 13)
                x = ax + math.cos(a) * (aw / 2 + 3) * (1 if k > 0 else 1)
                y = ay - ah + (aw / 2) * 0.9 - math.sin(a) * (aw / 2) * 0.9
                pygame.draw.rect(c, STONE[2] if j % 2 else STONE[1], (int(x) - 3, int(y) - 2, 6, 5))
        for side in (-1, 1):
            x = ax + side * (aw // 2 + 3)
            for y in range(int(ay - ah + aw * 0.45), ay):
                pygame.draw.line(c, STONE[1] if (y // 5) % 2 else STONE[2], (x - 3, y), (x + 3, y))
        for y in range(ay, LH):                                                 # flagstones
            for x in range(LW):
                joint = (y - ay) % 6 == 0 or (x + ((y - ay) // 6) * 9) % 17 == 0
                c.set_at((x, y), STONE[0] if joint else STONE[1])
        for k in range(6):                                                      # the last flight, from the left
            pygame.draw.rect(c, STONE[1], (0, ay - 30 + k * 5, 40 - k * 6, 5))
            pygame.draw.line(c, STONE[3], (0, ay - 30 + k * 5), (39 - k * 6, ay - 30 + k * 5))
        bake_light(c, [(ax, ay - 30, 150, (1.0, 0.72, 0.3))], ambient=(0.3, 0.28, 0.32))

    def frame(self, c, t):
        from .theme import draw_enemy, draw_lamplighter
        for k in range(20):                                                     # motes of gold in the doorway
            q = (t * 0.08 + k / 20) % 1.0
            x = self.AX - 30 + (k * 37) % 60 + math.sin(t + k) * 3
            y = self.AY - 4 - q * 80
            c.set_at((int(x), int(y)), (255, 236, 170))
        from .theme import draw_still
        if self.variant == "meeting":                                           # face to face, in the doorway's light
            figure(c, lambda s, x, y: draw_lamplighter(s, x, y, t), 128, self.AY + 10, factor=2)
            for i, x in enumerate((176, 200, 224, 248)):
                reach = i == 0 and (t % 5) > 1.5
                figure(c, lambda s, px, py, i=i, r=reach: draw_still(s, px, py, t + i, reach=r), x,
                       self.AY + 10 - (i % 2) * 2, factor=2)
            return
        pace = math.sin(t * 0.5)                                                # the Warden, pacing
        wx = self.AX + pace * 40
        figure(c, lambda s, x, y: draw_enemy(s, "warden", x, y, t, False, 1, lantern_lit=True), wx, self.AY + 8,
               factor=2, size=32)
        figure(c, lambda s, x, y: draw_lamplighter(s, x, y, t), 30, self.AY - 20, factor=2)
        if self.variant == "still":                                             # the Still, off to the side
            for i, x in enumerate((262, 280, 298, 271, 289)):
                figure(c, lambda s, px, py, i=i: draw_still(s, px, py, t * 0.5 + i, color=(180, 188, 200)), x,
                       self.AY + 10 + (6 if i > 2 else 0), factor=2, alpha=235)

    def glow(self, surf, t, ox, oy):
        add_glow(surf, at(ox, oy, self.AX, self.AY - 40), int(230 * flicker(t, 0, 0.02)), (80, 58, 20))
        if self.variant == "meeting":
            add_glow(surf, at(ox, oy, 146, self.AY - 4), int(80 * flicker(t, 2, 0.06)), (110, 80, 36))
            return
        pace = math.sin(t * 0.5)
        add_glow(surf, at(ox, oy, self.AX + pace * 40 + 10, self.AY - 4), int(50 * flicker(t, 4, 0.1)), (110, 80, 30))
        add_glow(surf, at(ox, oy, 48, self.AY - 26), int(60 * flicker(t, 2, 0.06)), (110, 80, 36))


# ---------------------------------------------------------------- the caves: the light thinning

def cave_room(c, seed, water_y=96, ceiling=14):
    """A wide cave: limestone, a ragged ceiling of stalactites, black water from water_y down."""
    rng = random.Random(seed)
    noise = Noise(seed)
    rock_fill(c, noise, LIMESTONE, seed=seed)
    for x in range(LW):
        top = ceiling + int(5 * math.sin(x / 13.0) + 3 * noise(x, 3))
        for y in range(top):
            c.set_at((x, y), shade_pick(LIMESTONE, 0.12 + 0.2 * noise(x, y), x, y))
    x = 2
    while x < LW:
        n = rng.choice((4, 6, 8, 10, 14, 20))
        top = ceiling + int(5 * math.sin(x / 13.0))
        base = rng.choice((1, 2, 2, 3))
        for j in range(n):
            w = max(0, base - (j * (base + 1)) // n)
            for dx in range(-w, w + 1):
                c.set_at((x + dx, top + j), LIMESTONE[4] if dx < 0 else (LIMESTONE[2] if dx == 0 else LIMESTONE[1]))
        x += rng.randint(3, 11)
    for y in range(water_y, LH):
        for x in range(LW):
            k = (y - water_y) / max(1, LH - water_y)
            c.set_at((x, y), lerp_color((10, 16, 26), (3, 6, 12), k + (bayer(x, y) - 0.5) * 0.15))
    for x in range(LW):
        c.set_at((x, water_y), (30, 44, 58))


class Dim(Scene):
    """The light thinning: Tarn at the water's edge, his rings dying close to his hand; far across
    the caves, a warm speck where the day came in."""

    def build(self, c):
        cave_room(c, 81, water_y=84)
        for x in range(0, 190):                                                 # the near ledge
            top = 112 + int(3 * math.sin(x / 6.0)) + max(0, (x - 80) // 3)
            if top >= LH:
                break
            for y in range(top, LH):
                c.set_at((x, y), shade_pick(LIMESTONE, 0.45 - 0.3 * (y - top) / 30, x, y))
            c.set_at((x, top), LIMESTONE[4])
        for y in range(56, 78):                                                 # the far crack, warm
            w = max(0, 2 - abs(y - 67) // 5)
            for x in range(250 - w, 251 + w):
                c.set_at((x, y), (150, 110, 60))
        for y in range(85, 96):                                                 # its light, on the water
            if y % 2:
                c.set_at((250 + int(math.sin(y) * 2), y), (110, 80, 46))
        bake_light(c, [(250, 68, 40, (0.7, 0.5, 0.22)), (100, 116, 70, (0.16, 0.32, 0.42))],
                   ambient=(0.4, 0.44, 0.54))

    def frame(self, c, t):
        from .theme import draw_still
        for k in range(3):                                                      # rings that die too soon
            q = (t * 0.45 + k / 3) % 1.0
            if q > 0.55:
                continue
            rw, rh = int(8 + 110 * q), int(2 + 14 * q)
            col = lerp_color((150, 220, 250), (10, 16, 26), q / 0.55)
            pygame.draw.ellipse(c, col, (112 - rw // 2, 112 - rh // 2, rw, rh), 1)
        if math.sin(t * 1.7) > -0.6:
            c.set_at((250, 66), (255, 214, 140))
        figure(c, lambda s, x, y: draw_still(s, x, y, t, reach=True), 92, 120, factor=2)
        for i, x in enumerate((36, 58)):
            figure(c, lambda s, px, py, i=i: draw_still(s, px, py, t + i, color=(150, 160, 172)), x, 122, factor=2,
                   alpha=200)

    def glow(self, surf, t, ox, oy):
        add_glow(surf, at(ox, oy, 250, 67), int(60 * flicker(t, 6, 0.05)), (110, 80, 30))
        add_glow(surf, at(ox, oy, 112, 112), int(70 * (0.7 + 0.3 * math.sin(t * 0.45 * math.tau))), (10, 30, 40))


class BlackWater(Scene):
    """After the new day came: the caves dark again, a few of the Still left standing in water
    that no longer answers."""

    def build(self, c):
        cave_room(c, 91, water_y=100)
        bake_light(c, [(160, 110, 60, (0.06, 0.1, 0.14))], ambient=(0.22, 0.24, 0.3))

    def frame(self, c, t):
        from .theme import draw_still
        q = (t * 0.2) % 1.0                                                     # one last ring, fading
        rw, rh = int(6 + 40 * q), int(2 + 6 * q)
        pygame.draw.ellipse(c, lerp_color((60, 90, 110), (8, 12, 20), q), (150 - rw // 2, 118 - rh // 2, rw, rh), 1)
        for i, x in enumerate((110, 150, 196)):
            figure(c, lambda s, px, py, i=i: draw_still(s, px, py, t * 0.3 + i, reach=i == 1, color=(90, 96, 106)),
                   x, 122, factor=2, alpha=220)


# ---------------------------------------------------------------- the endings

class Roofs(Scene):
    """The roof of the Tick, the last morning (or none): Maren on the leads by the clock face.
    variant: (dawn, holding) -- dawn True/False, holding "watch" | "dust" | None."""

    def __init__(self, dawn=True, holding=None):
        self.variant = (dawn, holding)

    def build(self, c):
        dawn = self.variant[0]
        for y in range(LH):
            for x in range(LW):
                k = y / LH + (bayer(x, y) - 0.5) * 0.08
                if dawn:
                    col = lerp_color((70, 90, 150), (250, 170, 110), k * 1.1)
                else:
                    col = lerp_color(SKY_TOP, SKY_LOW, k)
                c.set_at((x, y), col)
        if dawn:
            pygame.draw.circle(c, (255, 226, 170), (250, 118), 16)
            pygame.draw.circle(c, (255, 244, 210), (250, 118), 12)
        else:
            rng = random.Random(5)
            for _ in range(60):
                c.set_at((rng.randrange(LW), rng.randrange(90)), (150, 150, 180))
        far = (110, 80, 90) if dawn else (18, 15, 28)
        self.windows = rooftops(c, 132, -6, LW + 6, seed=21, color=far)
        pygame.draw.rect(c, far, (0, 132, LW, 15))
        near = (40, 28, 34) if dawn else (10, 8, 16)
        pygame.draw.polygon(c, near, [(0, LH), (0, 112), (150, 96), (170, 96), (170, LH)])   # the Tick's roof
        for x in range(0, 170, 6):
            pygame.draw.line(c, scale_color(near, 1.4), (x, 112 - x * 16 // 150), (x, LH))
        pygame.draw.rect(c, near, (120, 40, 46, 60))                            # the clock turret
        pygame.draw.polygon(c, near, [(116, 40), (143, 14), (170, 40)])
        pygame.draw.circle(c, (230, 214, 170) if dawn else (120, 112, 96), (143, 62), 12)
        pygame.draw.circle(c, scale_color(near, 1.6), (143, 62), 12, 1)
        if not dawn:
            for x, y in self.windows:
                c.set_at((x, y), (230, 170, 96))

    def frame(self, c, t):
        from .theme import draw_thief
        dawn, holding = self.variant
        cx, cy = 143, 62                                                        # the hands move again at dawn
        a = -math.pi / 2 + (t * 0.05 if dawn else 0.6)
        pygame.draw.line(c, (40, 30, 24), (cx, cy), (cx + math.cos(a) * 9, cy + math.sin(a) * 9), 1)
        pygame.draw.line(c, (40, 30, 24), (cx, cy), (cx + 6, cy), 1)
        tint = None if dawn else (150, 150, 190)
        figure(c, lambda s, x, y: draw_thief(s, x, y, t, watch=holding == "watch"), 88, 110, factor=2, tint=tint)
        if holding == "dust":
            for k in range(12):
                q = (t * 0.3 + k / 12) % 1.0
                c.set_at((int(78 + k % 4 + q * 40), int(94 - q * 30 + math.sin(k + t) * 2)),
                         lerp_color((240, 210, 140), (200, 170, 150), q))

    def glow(self, surf, t, ox, oy):
        dawn, holding = self.variant
        if dawn:
            add_glow(surf, at(ox, oy, 250, 118), 260, (90, 60, 30))
        if holding == "watch":
            add_glow(surf, at(ox, oy, 80, 96), int(30 + 8 * math.sin(t * 3)), (110, 90, 30))


class Sunrise(Scene):
    """The mouth of the Deep at sunrise: the Still coming up out of it behind Aurel, shading their
    eyes. variant: how many of them (the rest were lost)."""

    def __init__(self, count=6):
        self.variant = count

    def build(self, c):
        for y in range(LH):
            for x in range(LW):
                k = y / LH + (bayer(x, y) - 0.5) * 0.08
                c.set_at((x, y), lerp_color((80, 100, 160), (255, 180, 120), k * 1.2))
        pygame.draw.circle(c, (255, 230, 180), (60, 96), 20)
        pygame.draw.circle(c, (255, 246, 214), (60, 96), 15)
        self.windows = rooftops(c, 112, -6, LW + 6, seed=41, color=(120, 86, 96))
        pygame.draw.rect(c, (120, 86, 96), (0, 112, LW, 10))
        for x in range(LW):                                                     # the hillside
            top = int(118 - 26 * math.exp(-((x - 220) / 70.0) ** 2))
            for y in range(top, LH):
                c.set_at((x, y), shade_pick([(58, 46, 50), (76, 60, 60), (96, 76, 70)],
                                            0.6 - 0.3 * (y - top) / 40 + 0.2 * bayer(x, y), x, y))
        pygame.draw.ellipse(c, (14, 10, 12), (222, 88, 30, 30))                 # the mouth of the Deep
        pygame.draw.rect(c, (14, 10, 12), (222, 103, 30, 20))
        for j in range(10):
            a = math.pi * j / 9
            pygame.draw.rect(c, (120, 104, 96), (int(237 + math.cos(a) * 17) - 2, int(103 - math.sin(a) * 17) - 2, 4, 4))

    def frame(self, c, t):
        from .theme import draw_lamplighter, draw_still
        n = self.variant
        for i in range(n):                                                      # coming up, one by one
            q = min(1.0, max(0.0, t * 0.35 - i * 0.5))
            if q <= 0:
                continue
            x = 236 - q * (24 + i * 19)
            y = 122 - (1 - q) * 6
            figure(c, lambda s, px, py, i=i: draw_still(s, px, py, t + i, reach=i % 2 == 0), x, y, factor=2,
                   alpha=255 * min(1.0, q * 3))
        figure(c, lambda s, x, y: draw_lamplighter(s, x, y, t), 102, 126, factor=2)

    def glow(self, surf, t, ox, oy):
        add_glow(surf, at(ox, oy, 60, 96), 300, (110, 70, 30))


# ---------------------------------------------------------------- the caves of the Still

class Pool(Scene):
    """A cave pool of the Still. variants:
    "dark"  -- before the day broke in: stone that swallows a shout;
    "folk"  -- the Still around the water, speaking in faint ripples;
    "glow"  -- the spilled light rising in rings, and the cave seen for the first time;
    "tarn"  -- Tarn in the shallows, his rings the brightest;
    "wake"  -- Tarn wading, the others following his glowing wake;
    "children" -- the children at the water's edge, touching it again and again to see it answer."""

    WATER = 98

    def __init__(self, variant):
        self.variant = variant

    def build(self, c):
        v = self.variant
        cave_room(c, 101, water_y=self.WATER, ceiling=16)
        rng = random.Random(103)
        for cx in (22, 96, 131, 214, 276, 305):                                 # flowstone, floor to roof
            w = rng.randint(3, 6)
            for y in range(10, self.WATER):
                ww = w + int(2 * math.sin(y / 7.0 + cx))
                for x in range(cx - ww, cx + ww + 1):
                    k = 0.3 + 0.4 * (1 - abs(x - cx) / (ww + 1)) + 0.1 * bayer(x, y)
                    c.set_at((x, y), shade_pick(LIMESTONE, k, x, y))
        for x in range(LW):                                                     # ledges, sloping into the water
            top = self.ledge(x) + int(2 * math.sin(x / 5.0))
            for y in range(top, LH):
                c.set_at((x, y), shade_pick(LIMESTONE, 0.5 - 0.35 * (y - top) / 40, x, y))
            if top < LH:
                c.set_at((x, top), LIMESTONE[4])
                if top > self.WATER:
                    c.set_at((x, top - 1), (40, 60, 76))                          # where stone meets water
        lights = {"dark": [], "folk": [(160, 112, 70, (0.05, 0.12, 0.16))],
                  "children": [(160, 112, 150, (0.16, 0.4, 0.52))],
                  "glow": [(160, 112, 190, (0.25, 0.6, 0.75))], "tarn": [(160, 112, 170, (0.22, 0.55, 0.7))],
                  "wake": [(160, 112, 140, (0.12, 0.32, 0.42))]}[v]
        amb = {"dark": (0.16, 0.17, 0.2), "folk": (0.24, 0.26, 0.32)}.get(v, (0.32, 0.36, 0.44))
        bake_light(c, lights, ambient=amb)

    def ledge(self, x):
        d = min(x, LW - 1 - x)
        return self.WATER - 4 + d // 6 + max(0, d - 58)

    def frame(self, c, t):
        from .theme import draw_still
        v = self.variant
        if v == "dark":
            x, y = 80, self.ledge(80)
            for k in range(3):                                                  # a call, swallowed by the stone
                q = (t * 0.7 + k / 3) % 1.0
                r = int(4 + 30 * q)
                pygame.draw.arc(c, lerp_color((120, 120, 124), (20, 20, 24), q ** 0.5),
                                (x + 6 - r, y - 26 - r // 2, 2 * r, r), -0.9, 0.9, 1)
            figure(c, lambda s, px, py: draw_still(s, px, py, t, color=(110, 116, 124)), x, y, factor=2)
            return
        if v == "children":
            for i, x in enumerate((96, 132, 176, 214, 250)):                    # each touching the water
                phase = i * 0.37
                rings(c, x + 6, 114, t, 46, 7, (170, 240, 255), count=2, speed=0.55, seed=phase)
                dip = 1 if math.sin(t * 2.4 + i * 1.7) > 0.4 else 0
                figure(c, lambda s, px, py, i=i: draw_still(s, px, py, t + i, reach=True), x, 110 + dip, factor=1)
            for i, x in enumerate((30, 292)):                                   # the grown-ups, watching
                figure(c, lambda s, px, py, i=i: draw_still(s, px, py, t + i, color=(160, 168, 178)), x,
                       self.ledge(x), factor=2)
            return
        if v == "folk":
            rings(c, 160, 112, t, 120, 16, (40, 70, 90), count=3, speed=0.25)
            for i, x in enumerate((34, 62, 258, 286)):
                figure(c, lambda s, px, py, i=i: draw_still(s, px, py, t + i, reach=True, color=(160, 168, 178)),
                       x, self.ledge(x), factor=2)
            return
        if v in ("glow", "tarn"):
            rings(c, 160, 114, t, 300, 40, (170, 240, 255), count=5, speed=0.3)
            rings(c, 160, 114, t + 0.4, 140, 18, (200, 250, 255), count=3, speed=0.5)
            if v == "glow":
                for i, x in enumerate((40, 280)):
                    figure(c, lambda s, px, py, i=i: draw_still(s, px, py, t + i, reach=True), x, self.ledge(x),
                           factor=2)
            else:
                for i, x in enumerate((34, 290)):
                    figure(c, lambda s, px, py, i=i: draw_still(s, px, py, t + i, color=(150, 160, 172)), x,
                           self.ledge(x), factor=2, alpha=200)
                figure(c, lambda s, px, py: draw_still(s, px, py, t, reach=True), 152, 116, factor=3)
            return
        # the wake: bright behind Tarn, fading back toward the others
        head = 250 - (t * 18) % 120
        for i in range(26):
            x = int(head + i * 6)
            if x >= LW:
                break
            k = 1 - i / 26
            pygame.draw.ellipse(c, lerp_color((10, 16, 26), (170, 240, 255), k), (x - 4, 112 - 1, 9, 3), 1)
        figure(c, lambda s, px, py: draw_still(s, px, py, t, reach=True), head - 4, 116, factor=2)
        for f in (1, 2):
            figure(c, lambda s, px, py, f=f: draw_still(s, px, py, t + f, color=(170, 178, 190)), head + f * 44,
                   116, factor=2, alpha=230 - f * 40)

    def glow(self, surf, t, ox, oy):
        v = self.variant
        if v in ("glow", "tarn", "children"):
            add_glow(surf, at(ox, oy, 160, 114), int(260 * (0.9 + 0.1 * math.sin(t))), (16, 52, 70))
        elif v == "wake":
            head = 250 - (t * 18) % 120
            add_glow(surf, at(ox, oy, head + 30, 112), 160, (12, 40, 56))


# ---------------------------------------------------------------- the Loom of Hours

class LoomHall(Scene):
    """The Loom in its hall at the bottom of the Deep: pillars going back into the dark, the great
    frame, its golden warp, a day half woven, and the single thread rising out of the top.
    variant "broken": the warp slack, the thread snapped, the light low.
    variant "tied": whole again, and singing.
    variant "arrival": the Still, dropping out of the Spindle one after another, landing in a heap, and
    picking themselves up to stand and look at the Loom.
    variant "waiting": the Still sitting in the dark of the hall, waiting for someone to come down."""

    X0, X1, TOP, FLOOR = 108, 212, 30, 126

    def __init__(self, variant="broken"):
        self.variant = variant

    MOUTH = 236                               # where the Spindle comes down into the hall

    def build(self, c):
        tied = self.variant == "tied"
        for y in range(LH):                                                     # the hall's far dark
            for x in range(LW):
                c.set_at((x, y), lerp_color((16, 12, 14), (34, 26, 22), y / LH + (bayer(x, y) - 0.5) * 0.06))
        for i, px in enumerate((18, 62, 258, 302)):                             # pillars, receding
            w = 12 if i in (0, 3) else 8
            top = 0
            for y in range(top, self.FLOOR):
                for x in range(px - w // 2, px + w // 2):
                    k = 0.35 + 0.35 * (1 - abs(x - px) / (w / 2)) + 0.1 * bayer(x, y)
                    c.set_at((x, y), shade_pick(STONE, k, x, y))
            pygame.draw.rect(c, STONE[2], (px - w // 2 - 2, self.FLOOR - 5, w + 4, 5))
        for y in range(self.FLOOR, LH):                                         # flagstones
            for x in range(LW):
                joint = (y - self.FLOOR) % 5 == 0 or (x + ((y - self.FLOOR) // 5) * 11) % 23 == 0
                c.set_at((x, y), STONE[0] if joint else lerp_color(STONE[1], STONE[2], bayer(x, y) * 0.5))
        wood, hi = (86, 58, 36), (128, 90, 56)                                  # the frame
        for px in (self.X0, self.X1 - 6):
            pygame.draw.rect(c, wood, (px, self.TOP, 6, self.FLOOR - self.TOP))
            pygame.draw.line(c, hi, (px + 1, self.TOP), (px + 1, self.FLOOR - 1))
            pygame.draw.rect(c, hi, (px - 2, self.TOP - 6, 10, 6))                # carved caps
            pygame.draw.circle(c, hi, (px + 3, self.TOP - 8), 3)
        for y in (self.TOP, self.FLOOR - 34):
            pygame.draw.rect(c, wood, (self.X0 - 4, y, self.X1 - self.X0 + 8, 5))
            pygame.draw.line(c, hi, (self.X0 - 4, y + 1), (self.X1 + 3, y + 1))
        pygame.draw.rect(c, wood, (self.X0 + 6, self.FLOOR - 8, self.X1 - self.X0 - 12, 4))   # the cloth beam
        if self.variant in ("arrival", "waiting"):                              # the Spindle's mouth, above
            m = self.MOUTH
            for y in range(0, 22):                                              # a chute of old masonry
                pygame.draw.line(c, STONE[1] if y % 5 else STONE[0], (m - 14, y), (m - 11, y))
                pygame.draw.line(c, STONE[1] if y % 5 else STONE[0], (m + 10, y), (m + 13, y))
                pygame.draw.line(c, (6, 5, 6), (m - 10, y), (m + 9, y))
            pygame.draw.rect(c, STONE[2], (m - 15, 21, 30, 3))
            pygame.draw.line(c, STONE[3], (m - 15, 21), (m + 14, 21))
        dark = self.variant == "waiting"
        light = (0.9, 0.7, 0.35) if tied else ((0.3, 0.22, 0.12) if dark else (0.5, 0.38, 0.2))
        bake_light(c, [((self.X0 + self.X1) // 2, 70, 150, light)],
                   ambient=(0.26, 0.24, 0.28) if dark else (0.42, 0.38, 0.38))

    def frame(self, c, t):
        tied = self.variant == "tied"
        cx = (self.X0 + self.X1) // 2
        top, low = self.TOP + 5, self.FLOOR - 34
        for i, x in enumerate(range(self.X0 + 10, self.X1 - 8, 4)):             # the warp
            if tied:
                col = lerp_color(GOLD, (255, 244, 200), 0.5 + 0.5 * math.sin(t * 3 + i * 0.6))
                pygame.draw.line(c, col, (x, top), (x, low))
            else:
                for y in range(top, low):
                    sag = int(math.sin((y - top) / (low - top) * math.pi) * (2 + (i % 3)))
                    if (y + i) % 3:
                        c.set_at((x + sag, y), scale_color(GOLD, 0.55))
        for y in range(low + 5, self.FLOOR - 8):                                # a day, half woven
            for x in range(self.X0 + 8, self.X1 - 6):
                weave = (x + y) % 2 == 0
                base = (230, 190, 100) if tied else (150, 120, 64)
                c.set_at((x, y), base if weave else scale_color(base, 0.8))
        if tied:                                                                # the thread, rising whole
            for y in range(0, self.TOP):
                q = (y + t * 20) % 14
                c.set_at((cx, y), (255, 244, 200) if q < 1.5 else GOLD)
            for k in range(18):
                q = (t * 0.12 + k / 18) % 1.0
                c.set_at((int(self.X0 + (k * 29) % (self.X1 - self.X0)), int(self.FLOOR - 10 - q * 110)),
                         (255, 236, 170))
        else:                                                                   # snapped: two frayed ends
            for y in range(0, 12):
                c.set_at((cx + int(math.sin(y * 0.5 + t) * 1), y), scale_color(GOLD, 0.7))
            for y in range(self.TOP - 12, self.TOP):
                c.set_at((cx + int(math.sin(y * 0.4 + t * 0.8) * 2), y), scale_color(GOLD, 0.7))
            for j in range(3):
                c.set_at((cx - 1 + j, 12 + j % 2), (255, 220, 140))
                c.set_at((cx - 1 + j, self.TOP - 13 - j % 2), (255, 220, 140))
        if self.variant == "arrival":
            self._arrivals(c, t)
        elif self.variant == "waiting":
            from .theme import draw_still
            for i, x in enumerate(range(226, 310, 13)):                         # sitting close, in the dark
                figure(c, lambda s, px, py, i=i: draw_still(s, px, py, t * 0.4 + i, color=(120, 126, 136)),
                       x, self.FLOOR + 1 + (i % 2) * 4, factor=2, alpha=220)

    def _arrivals(self, c, t):
        """Six of the Still, one after another out of the Spindle: a fall, a heap, a scramble, a gaze."""
        from .theme import draw_still
        land = [(0, 0), (-6, -5), (5, -9), (-2, -13), (7, -4), (-8, -10)]
        for i in range(6):
            t0 = 0.4 + i * 0.5
            if t < t0:
                continue
            dx, dy = land[i]
            hx, hy = self.MOUTH + dx, self.FLOOR + dy                            # where they land, on the heap
            fall = min(1.0, (t - t0) / 0.45)
            up = 3.6 + i * 0.25                                                 # when they pick themselves up
            gx = 226 + i * 17                                                   # where they stand, after
            if t < up:
                x, y = hx, lerp(18, hy, fall * fall)
                if fall >= 1.0:                                                 # a bounce, then lying there
                    y -= max(0.0, 3 * math.sin(min(1.0, (t - t0 - 0.45) / 0.25) * math.pi))
                angle = 0 if fall < 1.0 else (90 if i % 2 else -90)
            else:
                k = min(1.0, (t - up) / 1.1)
                x, y = lerp(hx, gx, k), lerp(hy, self.FLOOR + 1, k) - abs(math.sin(k * 9)) * 2
                angle = 0
            img = pygame.Surface((32, 32), pygame.SRCALPHA)
            draw_still(img, 16, 16, t + i, reach=t > up + 1.2 and i % 3 == 0)
            if angle:
                img = pygame.transform.rotate(img, angle)
            img = pygame.transform.scale(img, (64, 64))
            c.blit(img, (int(x - 32), int(y - 50 + (14 if angle else 0))))

    def glow(self, surf, t, ox, oy):
        cx = (self.X0 + self.X1) // 2
        if self.variant == "tied":
            add_glow(surf, at(ox, oy, cx, 70), int(300 * flicker(t, 1, 0.03)), (100, 76, 26))
            add_glow(surf, at(ox, oy, cx, 10), 80, (100, 80, 30))
        else:
            add_glow(surf, at(ox, oy, cx, 80), 180, (50, 36, 14))
            add_glow(surf, at(ox, oy, cx, 12), 30, (100, 76, 30))
            add_glow(surf, at(ox, oy, cx, self.TOP - 12), 30, (100, 76, 30))


# ---------------------------------------------------------------- the Guild of Hours, selling

class GuildCounter(Scene):
    """The Guild's counter in the Tick: behind it the drum, wound with what they took; before it,
    a queue of townsfolk with coins; a Guildmaster measuring thread into little lamps."""

    def build(self, c):
        brick_wall(c, dark=(26, 18, 14), a=(42, 29, 22), b=(56, 38, 28))
        for y in range(18, 64):                                                 # the drum behind, dim
            lum = (1 - abs(y - 41) / 23) ** 0.6
            for x in range(70, 250):
                coil = (y + x // 9) % 3 == 0
                base = lerp_color((80, 54, 22), (200, 166, 90), lum)
                c.set_at((x, y), scale_color(base, 0.75) if coil else base)
        for ex in (64, 250):
            pygame.draw.rect(c, (60, 50, 44), (ex, 14, 6, 54))
            pygame.draw.line(c, (100, 86, 74), (ex + 1, 14), (ex + 1, 67))
        planks(c, (0, 88, LW, 104), base=(86, 58, 38), vertical=True, width=8, seed=4)     # the counter
        pygame.draw.rect(c, (120, 84, 52), (0, 86, LW, 3))
        planks(c, (0, 104, LW, LH), base=(52, 38, 30), vertical=False, width=5, seed=6)
        for i, x in enumerate(range(120, 230, 16)):                             # little lamps, for sale
            pygame.draw.rect(c, (70, 60, 50), (x, 76, 7, 10), 1)
            pygame.draw.rect(c, (250, 210, 120) if i % 2 else (230, 180, 90), (x + 1, 77, 5, 8))
            pygame.draw.line(c, (90, 80, 70), (x + 1, 74), (x + 5, 74))
        bake_light(c, [(160, 44, 140, (0.75, 0.56, 0.28)), (170, 80, 60, (0.6, 0.45, 0.2))],
                   ambient=(0.44, 0.38, 0.38))

    def frame(self, c, t):
        from .theme import draw_guild_warden
        gear(c, 22, 30, 30, t * 0.12, (96, 72, 44))                             # the Tick's works, turning
        gear(c, 58, 6, 14, -t * 0.12 * 30 / 14 + 0.2, (104, 80, 50))            # (meshed with the big one)
        gear(c, 300, 34, 26, -t * 0.15, (90, 68, 42))
        gear(c, 276, 70, 12, t * 0.15 * 26 / 12, (100, 76, 48))
        a = t * 1.2                                                             # thread wound off into a lamp
        pts = [(160 + int(math.sin(a + k * 0.4) * 3), 64 + k) for k in range(12)]
        pygame.draw.lines(c, (255, 230, 150), False, pts)
        for i, x in enumerate((96, 226)):
            figure(c, lambda s, px, py, i=i: draw_guild_warden(s, px, py, t, (1 if i == 0 else -1, 0)), x, 86,
                   factor=2)
        for i in range(5):                                                      # the queue, with coins
            x = 40 + i * 58
            figure(c, lambda s, px, py, i=i: _townsfolk(s, px, py, t + i), x, LH + 4, factor=2,
                   tint=(150, 140, 150))

    def glow(self, surf, t, ox, oy):
        add_glow(surf, at(ox, oy, 160, 44), int(200 * flicker(t, 1, 0.02)), (66, 48, 16))
        for i, x in enumerate(range(120, 230, 16)):
            add_glow(surf, at(ox, oy, x + 3, 81), int(24 * flicker(t, i, 0.1)), (100, 70, 24))


def _townsfolk(surf, cx, cy, t):
    """Someone from Hollowmere, queueing in the cold: shawl, bowed head, a coin held out."""
    body = [(cx, cy - 6), (cx + 6, cy + 9), (cx - 6, cy + 9)]
    pygame.draw.polygon(surf, (70, 62, 70), body)
    pygame.draw.polygon(surf, (110, 100, 106), body, 1)
    pygame.draw.circle(surf, (86, 76, 84), (int(cx), int(cy - 5)), 4)
    if math.sin(t * 0.7) > 0:
        surf.set_at((int(cx + 5), int(cy)), (230, 200, 110))


# ---------------------------------------------------------------- what is left of the thread

class Spool(Scene):
    """What is left of the thread, on a spool on a stone floor, running out across the dark; far
    off, a Warden, who held it once."""

    def build(self, c):
        for y in range(LH):
            for x in range(LW):
                c.set_at((x, y), lerp_color((14, 10, 16), (26, 20, 24), y / LH + (bayer(x, y) - 0.5) * 0.05))
        for y in range(104, LH):                                                # the floor
            for x in range(LW):
                joint = (y - 104) % 6 == 0 or (x + ((y - 104) // 6) * 13) % 29 == 0
                k = (y - 104) / (LH - 104)
                c.set_at((x, y), scale_color(STONE[0] if joint else STONE[1], 0.5 + 0.4 * k))
        bake_light(c, [(110, 96, 90, (0.7, 0.52, 0.26))], ambient=(0.7, 0.66, 0.7))

    def frame(self, c, t):
        from .theme import draw_enemy
        k = 1 - ((t / 9.0) % 1.0)                                               # the spool runs down, and again
        cx, cy = 100, 90
        r = int(6 + 16 * k)
        pygame.draw.rect(c, (100, 70, 44), (cx - 26, cy - 30, 52, 5))          # the flanges
        pygame.draw.rect(c, (100, 70, 44), (cx - 26, cy + 20, 52, 5))
        pygame.draw.line(c, (140, 100, 64), (cx - 26, cy - 30), (cx + 25, cy - 30))
        pygame.draw.rect(c, (70, 50, 34), (cx - 5, cy - 25, 10, 45))            # the core
        for y in range(cy - 25, cy + 20):                                       # what is wound on it
            lum = 1 - abs(y - (cy - 3)) / 26
            for x in range(cx - r, cx + r):
                coil = (y + (x - cx) // 5) % 2 == 0
                base = lerp_color((150, 110, 40), (252, 220, 130), (1 - abs(x - cx) / (r + 1)) * 0.8 + lum * 0.2)
                c.set_at((x, y), scale_color(base, 0.8) if coil else base)
        pts = [(cx + r, cy + 14)]                                               # the loose end, running out
        for j in range(1, 40):
            pts.append((cx + r + j * 5, cy + 20 + j * 0.3 + math.sin(t * 1.5 + j * 0.45) * 2 * (j / 40)))
        pygame.draw.lines(c, GOLD, False, pts)
        figure(c, lambda s, px, py: draw_enemy(s, "warden", px, py, t, False, 1), 268, 120, factor=2, alpha=110)

    def glow(self, surf, t, ox, oy):
        add_glow(surf, at(ox, oy, 100, 88), 130, (70, 50, 16))


# ---------------------------------------------------------------- the binding, on the first landing

class Binding(Scene):
    """The first landing, at the mouth of the Deep: a keeper's window in the wall, the broken end
    of the thread lying where it fell out of it, and the thread finding Aurel's wrist."""

    def build(self, c):
        rock_fill(c, Noise(111), ROCK, seed=9)
        seams(c, random.Random(3), (0, 0, LW, LH), (30, 27, 30), n=30)
        for y in range(118, LH):                                                # the landing
            for x in range(LW):
                c.set_at((x, y), STONE[1] if (y - 118) % 5 and (x + (y // 5) * 7) % 19 else STONE[0])
        pygame.draw.line(c, STONE[3], (0, 118), (LW, 118))
        for k in range(8):                                                      # the stair, going down on the right
            pygame.draw.rect(c, STONE[1], (232 + k * 11, 118 + k * 4, 11, 4))
            pygame.draw.line(c, STONE[3], (232 + k * 11, 118 + k * 4), (242 + k * 11, 118 + k * 4))
        wx, wy = 60, 60                                                         # the keeper's window
        pygame.draw.rect(c, (12, 9, 10), (wx, wy, 30, 22))
        pygame.draw.rect(c, STONE[2], (wx - 3, wy - 3, 36, 3))
        pygame.draw.rect(c, STONE[2], (wx - 3, wy + 22, 36, 3))
        for bx in range(wx + 3, wx + 30, 6):
            pygame.draw.line(c, (100, 96, 92), (bx, wy), (bx, wy + 21))
        bake_light(c, [(160, 96, 110, (0.8, 0.58, 0.3)), (76, 70, 40, (0.5, 0.38, 0.18))],
                   ambient=(0.36, 0.33, 0.38))

    def frame(self, c, t):
        from .theme import draw_lamplighter
        k = min(1.0, t / 2.5)                                                   # the end rises and winds round him
        pts = [(84, 78), (88, 96), (100, 112), (118, 117)]
        for j in range(int(90 * k) + 2):
            a = j / 90 * math.tau * 3 + t * 2.2
            y = 115 - j * 0.55
            pts.append((160 + math.cos(a) * (22 - j * 0.08), y + math.sin(a) * 4))
        pygame.draw.lines(c, GOLD, False, [(int(x), int(y)) for x, y in pts])
        figure(c, lambda s, x, y: draw_lamplighter(s, x, y, t), 160, 118, factor=3)

    def glow(self, surf, t, ox, oy):
        add_glow(surf, at(ox, oy, 160, 92), int(140 * flicker(t, 2, 0.04)), (90, 64, 24))
        add_glow(surf, at(ox, oy, 84, 78), 30, (110, 86, 30))


# ---------------------------------------------------------------- the stair down

class Descent(Scene):
    """The stair down, in cutaway: flight after flight switching back into the dark, with Aurel on
    the top landing and the sconces catching one after another as he goes. Beside it, behind a
    keeper's window, the Spindle, and far below in it the slack end of the thread and the Loom's glow."""

    RUN, RISE, STEPS = 10, 3, 15
    LEFT, RIGHT = 40, 190                     # where the flights turn
    TOP = 22
    SX = 242                                  # the Spindle

    def flights(self):
        """(x0, y0, direction) for each flight, top to bottom."""
        out, y = [], self.TOP
        for k in range(3):
            d = 1 if k % 2 == 0 else -1
            out.append((self.LEFT if d > 0 else self.RIGHT, y, d))
            y += self.STEPS * self.RISE
        return out

    def treads(self, k):
        x0, y0, d = self.flights()[k]
        return [(x0 + d * i * self.RUN - (self.RUN if d < 0 else 0), y0 + (i + 1) * self.RISE) for i in range(self.STEPS)]

    def sconces(self):
        """Wall sconces, in the order he reaches them: landings and the middle of each flight."""
        out = []
        for k, (x0, y0, d) in enumerate(self.flights()):
            out.append((x0 - 6 * d, y0 - 10))
            mx, my = self.treads(k)[self.STEPS // 2]
            out.append((mx + 4, my - 14))
        return out

    def build(self, c):
        rock_fill(c, Noise(121), ROCK, darken=lambda y: 1.0 - 0.45 * y / LH, seed=3)
        seams(c, random.Random(7), (0, 0, LW, LH), (30, 27, 30), n=30)
        air = (50, 39, 36)
        for k, (x0, y0, d) in enumerate(self.flights()):                      # the stairwell, cut in the rock
            for x, y in self.treads(k):
                pygame.draw.rect(c, air, (x, y - 17, self.RUN, 17))
            pygame.draw.rect(c, air, (x0 - 26 if d > 0 else x0, y0 - 17, 26, 17))
        pygame.draw.rect(c, air, (self.RIGHT, self.TOP + 45 - 17, 26, 17))
        # the Spindle beside it, and a keeper's window through to it from the landing
        pygame.draw.rect(c, (12, 9, 11), (self.SX - 3, 0, 7, LH))
        for y in range(LH):
            c.set_at((self.SX - 4, y), (86, 78, 74) if y % 7 else (110, 100, 94))
            c.set_at((self.SX + 4, y), (56, 50, 50) if y % 7 else (80, 72, 68))
        wy = self.TOP + 45 - 9
        pygame.draw.rect(c, (20, 16, 18), (self.RIGHT + 26, wy, self.SX - 4 - self.RIGHT - 26, 5))
        for j in range(5):
            c.set_at((self.SX - 5, wy + j), (110, 104, 98) if j % 2 == 0 else (20, 16, 18))
        # the flights and landings, in cut stone: tread, riser, and the soffit underneath
        for k, (x0, y0, d) in enumerate(self.flights()):
            ts = self.treads(k)
            for x, y in ts:
                pygame.draw.rect(c, STONE[1], (x, y, self.RUN, self.RISE + 1))
                pygame.draw.line(c, STONE[3], (x, y), (x + self.RUN - 1, y))
                ex = x if d > 0 else x + self.RUN - 1
                pygame.draw.line(c, STONE[0], (ex, y), (ex, y + self.RISE))
            (xa, ya), (xb, yb) = ts[0], ts[-1]
            xa += 0 if d > 0 else self.RUN
            xb += self.RUN if d > 0 else 0
            pygame.draw.polygon(c, STONE[0], [(xa, ya + self.RISE + 1), (xb, yb + self.RISE + 1),
                                              (xb, yb + self.RISE + 5), (xa, ya + self.RISE + 5)])
        for x0, x1, y in ((self.LEFT - 26, self.LEFT, self.TOP), (self.RIGHT, self.RIGHT + 26, self.TOP + 45),
                          (self.LEFT - 26, self.LEFT, self.TOP + 90)):
            pygame.draw.rect(c, STONE[1], (x0, y, x1 - x0, 5))
            pygame.draw.line(c, STONE[3], (x0, y), (x1 - 1, y))
        for x, y in self.sconces():
            c.set_at((x, y + 1), (30, 26, 26))
            c.set_at((x, y + 2), (30, 26, 26))
        lights = [(26, self.TOP - 8, 70, (0.9, 0.66, 0.34)), (self.SX, LH, 80, (0.6, 0.44, 0.18))]
        lights += [(x, y, 44, (0.55, 0.38, 0.2)) for x, y in self.sconces()]
        bake_light(c, lights, ambient=(0.6, 0.56, 0.62))

    def lit(self, i, t):
        return t > 0.8 + i * 0.6

    def frame(self, c, t):
        from .theme import draw_lamplighter
        for y in range(0, LH):                                                  # the slack end, far below
            x = self.SX + int(round(math.sin(y * 0.2 + t * 0.7) * 1.5 * y / LH))
            c.set_at((x, y), scale_color(GOLD, 0.35 + 0.5 * y / LH))
        for i, (x, y) in enumerate(self.sconces()):
            if self.lit(i, t):
                flame(c, x, y, t, i)
        figure(c, lambda s, x, y: draw_lamplighter(s, x, y, t), self.LEFT - 14, self.TOP, factor=1)

    def glow(self, surf, t, ox, oy):
        add_glow(surf, at(ox, oy, self.SX, LH), 170, (90, 66, 22))
        add_glow(surf, at(ox, oy, self.LEFT - 10, self.TOP - 8), int(70 * flicker(t, 2, 0.06)), (110, 80, 36))
        for i, (x, y) in enumerate(self.sconces()):
            if self.lit(i, t):
                add_glow(surf, at(ox, oy, x, y), int(80 * flicker(t, i, 0.08)), (110, 64, 24))


# ---------------------------------------------------------------- the Regulator

class Regulator(Scene):
    """The watch in Maren's hand, close: running backwards, and behind it the tower's gears
    turning the wrong way round and a warden walking backwards through the dark."""

    def build(self, c):
        brick_wall(c, dark=(22, 15, 12), a=(34, 24, 18), b=(44, 30, 22))
        bake_light(c, [(160, 70, 120, (0.5, 0.38, 0.18))], ambient=(0.6, 0.52, 0.5))

    def frame(self, c, t):
        from .theme import draw_guild_warden
        for gx, gy, r, sp in ((40, 40, 30, 0.3), (286, 104, 38, -0.24), (262, 20, 16, 0.5)):
            gear(c, gx, gy, r, -t * sp, (66, 50, 32))                           # the wrong way round
        wx = 250 - (t * 6) % 80                                                 # a warden, walking backwards
        figure(c, lambda s, px, py: draw_guild_warden(s, px, py, t, (1, 0)), wx, 120, factor=2, alpha=150)
        cx, cy, r = 148, 72, 34                                                 # the Regulator
        pygame.draw.line(c, (190, 150, 70), (cx + 6, cy - r - 4), (cx + 40, cy - r - 14), 2)   # its chain
        pygame.draw.rect(c, (210, 170, 80), (cx - 3, cy - r - 6, 7, 6))
        pygame.draw.circle(c, (170, 130, 56), (cx, cy), r + 3)
        pygame.draw.circle(c, (236, 200, 110), (cx, cy), r + 3, 2)
        pygame.draw.circle(c, (240, 230, 200), (cx, cy), r - 1)
        for h in range(12):
            a = h / 12 * math.tau
            x0, y0 = cx + math.cos(a) * (r - 6), cy + math.sin(a) * (r - 6)
            pygame.draw.line(c, (70, 56, 44), (x0, y0), (cx + math.cos(a) * (r - 2), cy + math.sin(a) * (r - 2)),
                             2 if h % 3 == 0 else 1)
        a = -t * 2.0 - math.pi / 2                                              # running backwards
        pygame.draw.line(c, (40, 30, 24), (cx, cy), (cx + math.cos(a) * (r - 6), cy + math.sin(a) * (r - 6)), 1)
        b = -t * 0.17 - math.pi / 2
        pygame.draw.line(c, (40, 30, 24), (cx, cy), (cx + math.cos(b) * (r - 14), cy + math.sin(b) * (r - 14)), 2)
        pygame.draw.circle(c, (40, 30, 24), (cx, cy), 2)
        pygame.draw.arc(c, (255, 255, 240), (cx - r + 4, cy - r + 4, 2 * r - 8, 2 * r - 8), 2.2, 2.9, 1)   # a gleam
        hand = [(cx - 30, cy + 30), (cx + 30, cy + 34), (cx + 44, cy + 60), (cx - 40, cy + 64)]   # her palm
        pygame.draw.polygon(c, (206, 170, 140), hand)
        pygame.draw.polygon(c, (150, 116, 96), hand, 1)
        for k in range(4):
            fx = cx - 24 + k * 14
            pygame.draw.rect(c, (214, 180, 150), (fx, cy + 24 - (k % 2) * 2, 9, 10))
            pygame.draw.rect(c, (150, 116, 96), (fx, cy + 24 - (k % 2) * 2, 9, 10), 1)
        pygame.draw.polygon(c, (46, 58, 52), [(cx - 60, LH), (cx - 40, cy + 64), (cx + 44, cy + 60), (cx + 70, LH)])

    def glow(self, surf, t, ox, oy):
        add_glow(surf, at(ox, oy, 148, 72), int(180 * flicker(t, 3, 0.03)), (80, 62, 22))


class Reunion(Sunrise):
    """The mouth of the Deep at sunrise: Maren waiting with nothing in her hands, and Aurel holding
    out their mother's lantern. This time, she takes it."""

    def __init__(self):
        self.variant = "reunion"

    def lantern_at(self, t):
        k = min(1.0, max(0.0, (t - 2.0) / 2.2))
        k = k * k * (3 - 2 * k)
        return lerp(188, 150, k), 104 - math.sin(k * math.pi) * 4, k

    def frame(self, c, t):
        from .theme import draw_lamplighter, draw_thief
        figure(c, lambda s, x, y: draw_thief(s, x, y, t, watch=False), 132, 126, factor=2)      # waiting
        figure(c, lambda s, x, y: draw_lamplighter(s, x, y, t, lantern=False), 206, 124, factor=2)  # up out of the Deep
        x, y, k = self.lantern_at(t)
        x, y = int(x), int(y)
        pygame.draw.line(c, (90, 80, 70), (x - 2, y - 6), (x + 2, y - 6))
        pygame.draw.rect(c, (70, 60, 50), (x - 3, y - 5, 7, 8), 1)
        pygame.draw.rect(c, scale_color(LANTERN, flicker(t, 2, 0.15)), (x - 2, y - 4, 5, 6))

    def glow(self, surf, t, ox, oy):
        add_glow(surf, at(ox, oy, 60, 96), 300, (110, 70, 30))
        x, y, k = self.lantern_at(t)
        add_glow(surf, at(ox, oy, x, y), int(60 * flicker(t, 2, 0.06)), (120, 86, 36))


# ---------------------------------------------------------------- a long summer evening, long ago

class Summer(Scene):
    """Hollowmere long ago, on a summer evening that lasted until midnight: gold over the roofs,
    swallows, and the thread coming up into the Tick, where a little of the day is kept back."""

    TX = 200                                  # the Tick

    def build(self, c):
        for y in range(LH):
            for x in range(LW):
                k = y / LH + (bayer(x, y) - 0.5) * 0.07
                c.set_at((x, y), lerp_color((120, 150, 200), (255, 196, 120), k * 1.15))
        pygame.draw.circle(c, (255, 236, 180), (270, 104), 14)
        pygame.draw.circle(c, (255, 248, 220), (270, 104), 10)
        self.windows = rooftops(c, 120, -6, LW + 6, seed=61, color=(110, 76, 80))
        pygame.draw.rect(c, (110, 76, 80), (0, 120, LW, LH - 120))
        for y in range(122, LH):                                                # the street, warm
            for x in range(LW):
                if (x + (y // 3) * 4) % 9 == 0 or y % 3 == 0:
                    c.set_at((x, y), (96, 64, 66))
        tx = self.TX                                                            # the Tick
        pygame.draw.rect(c, (92, 62, 68), (tx - 12, 30, 24, 90))
        pygame.draw.polygon(c, (92, 62, 68), [(tx - 15, 30), (tx, 12), (tx + 15, 30)])
        for y in range(32, 120, 4):
            pygame.draw.line(c, (84, 56, 62), (tx - 12, y), (tx + 11, y))
        pygame.draw.circle(c, (240, 222, 180), (tx, 42), 6)
        pygame.draw.circle(c, (120, 90, 70), (tx, 42), 6, 1)
        pygame.draw.line(c, (60, 40, 36), (tx, 42), (tx, 38))
        pygame.draw.line(c, (60, 40, 36), (tx, 42), (tx + 3, 43))
        pygame.draw.rect(c, (250, 210, 130), (tx - 6, 70, 12, 10))              # the Drum Room, glowing
        pygame.draw.rect(c, (120, 80, 60), (tx - 6, 70, 12, 10), 1)

    def frame(self, c, t):
        tx = self.TX
        for y in range(80, 122):                                                # the thread, coming up into it
            c.set_at((tx, y), GOLD if (y + int(t * 12)) % 7 else (255, 244, 200))
        for k in range(5):                                                      # swallows
            q = (t * 0.08 + k * 0.21) % 1.0
            x = int(-10 + q * (LW + 20))
            y = int(40 + k * 9 + math.sin(t * 2 + k) * 5)
            up = math.sin(t * 9 + k * 2) > 0
            col = (60, 44, 50)
            c.set_at((x, y), col)
            c.set_at((x - 1, y - (1 if up else 0)), col)
            c.set_at((x + 1, y - (1 if up else 0)), col)
            c.set_at((x - 2, y - (1 if up else -1)), col)
            c.set_at((x + 2, y - (1 if up else -1)), col)

    def glow(self, surf, t, ox, oy):
        add_glow(surf, at(ox, oy, 270, 104), 260, (110, 70, 30))
        add_glow(surf, at(ox, oy, self.TX, 75), int(60 * flicker(t, 1, 0.05)), (110, 80, 30))


# ---------------------------------------------------------------- the ledgers, on the door of the Tick

class TickDoor(Scene):
    """The first morning: the great door of the Tick with the Guild's ledgers nailed to it, every hour
    kept back for generations in a careful hand, and the town reading them in the sun."""

    def build(self, c):
        for y in range(LH):                                                     # morning sky
            for x in range(LW):
                c.set_at((x, y), lerp_color((130, 170, 220), (250, 214, 160), y / LH + (bayer(x, y) - 0.5) * 0.06))
        brick_wall(c, dark=(96, 70, 60), a=(150, 110, 90), b=(176, 132, 104), box=(40, 0, 280, 118))   # the Tick
        for y in range(118, LH):                                                # the square, in sunlight
            for x in range(LW):
                joint = (y - 118) % 5 == 0 or (x + ((y - 118) // 5) * 7) % 13 == 0
                c.set_at((x, y), (150, 130, 116) if joint else (196, 172, 146))
        pygame.draw.rect(c, (96, 66, 44), (118, 36, 84, 82))                    # the great door, arched
        pygame.draw.ellipse(c, (96, 66, 44), (118, 16, 84, 44))
        pygame.draw.line(c, (70, 48, 32), (160, 24), (160, 117))
        for y in range(30, 118, 8):
            pygame.draw.line(c, (84, 58, 40), (120, y), (200, y))
        for x in (138, 182):                                                    # iron rings
            pygame.draw.circle(c, (60, 56, 56), (x, 84), 3, 1)
        self.pages = []
        rng = random.Random(17)
        for k in range(9):                                                      # the ledgers, nailed up
            px = 124 + (k % 3) * 26 + rng.randint(-2, 2)
            py = 40 + (k // 3) * 22 + rng.randint(-2, 2)
            self.pages.append((px, py))
            pygame.draw.rect(c, (236, 228, 206), (px, py, 16, 19))
            for ly in range(py + 3, py + 17, 3):
                pygame.draw.line(c, (120, 110, 100), (px + 2, ly), (px + 2 + rng.randint(6, 12), ly))
            c.set_at((px + 8, py + 1), (60, 56, 56))                              # the nail
        bake_light(c, [(260, 20, 200, (0.5, 0.42, 0.3))], ambient=(0.9, 0.88, 0.86))

    def frame(self, c, t):
        for i, (px, py) in enumerate(self.pages):                               # one page lifts in the wind
            if i == 4 and math.sin(t * 2.3) > 0.3:
                pygame.draw.polygon(c, (250, 244, 226), [(px, py + 19), (px + 16, py + 19), (px + 18, py + 14),
                                                         (px + 2, py + 14)])
        for i, x in enumerate((70, 96, 224, 250, 276)):                         # the town, reading
            figure(c, lambda s, px, py, i=i: _townsfolk(s, px, py, t * 0.5 + i), x, 150, factor=2)

    def glow(self, surf, t, ox, oy):
        add_glow(surf, at(ox, oy, 300, 10), 240, (90, 70, 40))



class Road(Scene):
    """The road out of Hollowmere at sunrise: Maren, set down by the Guild's coach, shivering, the watch
    gone grey and cold in her hand; its hours drifting back toward the town, to the Loom."""

    def build(self, c):
        for y in range(LH):
            for x in range(LW):
                k = y / LH + (bayer(x, y) - 0.5) * 0.07
                c.set_at((x, y), lerp_color((96, 120, 176), (250, 180, 120), k * 1.2))
        pygame.draw.circle(c, (255, 234, 184), (236, 78), 12)
        far = (120, 88, 100)
        rooftops(c, 84, 150, 320, seed=71, color=far)                          # Hollowmere, behind her
        pygame.draw.rect(c, far, (226, 40, 12, 44))                             # the Tick
        pygame.draw.polygon(c, far, [(224, 40), (232, 30), (240, 40)])
        for y in range(84, LH):                                                  # the fields, and the road
            for x in range(LW):
                k = (y - 84) / (LH - 84)
                c.set_at((x, y), lerp_color((120, 100, 90), (90, 74, 66), k + (bayer(x, y) - 0.5) * 0.1))
            half = 2 + (y - 84) * 0.6
            mid = 200 - (y - 84) * 1.3
            for x in range(int(mid - half), int(mid + half)):
                if 0 <= x < LW:
                    c.set_at((x, y), lerp_color((190, 160, 130), (160, 132, 108), (y - 84) / (LH - 84)))

    def frame(self, c, t):
        from .theme import draw_thief
        for k in range(14):                                                     # her hours, going home
            q = (t * 0.18 + k / 14) % 1.0
            x = int(lerp(120, 232, q) + math.sin(k * 2.1 + t) * 4)
            y = int(lerp(112, 62, q) + math.sin(k + t * 2) * 3)
            c.set_at((x, y), lerp_color((255, 226, 150), (250, 200, 150), q))
        shiver = 1 if (t * 11) % 2 < 1 and math.sin(t * 1.3) > 0.2 else 0
        figure(c, lambda s, x, y: draw_thief(s, x, y, 0.0, watch=False), 118 + shiver, 134, factor=2,
               tint=(170, 180, 210))
        pygame.draw.circle(c, (120, 124, 130), (106, 116), 3)                   # the watch: grey, and cold
        pygame.draw.circle(c, (150, 154, 160), (106, 116), 2)
        for k in range(3):                                                      # her breath, in the cold
            q = (t * 0.5 + k / 3) % 1.0
            pygame.draw.circle(c, lerp_color((220, 224, 236), (200, 170, 150), q),
                               (int(124 + q * 10), int(96 - q * 8)), 1 + int(q * 2))

    def glow(self, surf, t, ox, oy):
        add_glow(surf, at(ox, oy, 236, 78), 240, (110, 70, 30))



# ---------------------------------------------------------------- winter, long ago

class Winter(Scene):
    """Hollowmere in winter, long ago: snow on the roofs, a short grey day already going, and in every
    window a Guild lamp, bought by the lampful."""

    def houses(self, c, ground, seed, base, windows):
        """A row of houses, each its own shade, with a snowy roof, a chimney and a lit window or two."""
        rng = random.Random(seed)
        x = -6
        while x < LW + 6:
            w, h = rng.randint(12, 20), rng.randint(10, 18)
            col = scale_color(base, 0.85 + 0.3 * rng.random())
            pygame.draw.rect(c, col, (x, ground - h, w, h))
            pygame.draw.line(c, scale_color(col, 0.7), (x, ground - h), (x, ground))           # its edge
            peak = rng.randint(5, 9)
            roof = [(x - 2, ground - h), (x + w // 2, ground - h - peak), (x + w + 1, ground - h)]
            pygame.draw.polygon(c, scale_color(col, 0.75), roof)
            pygame.draw.line(c, (226, 230, 242), roof[0], roof[1], 2)                           # snow on it
            pygame.draw.line(c, (200, 206, 224), roof[1], roof[2], 2)
            if rng.random() < 0.6:                                                              # a chimney
                cx = x + w - 5
                pygame.draw.rect(c, scale_color(col, 0.6), (cx, ground - h - peak + 1, 3, peak - 1))
                pygame.draw.line(c, (226, 230, 242), (cx, ground - h - peak + 1), (cx + 2, ground - h - peak + 1))
            for _ in range(rng.randint(1, 2)):
                wx, wy = x + rng.randint(3, max(3, w - 5)), ground - h + rng.randint(3, max(3, h - 6))
                pygame.draw.rect(c, scale_color(col, 0.5), (wx - 1, wy - 1, 4, 5))
                windows.append((wx, wy))
            x += w + rng.randint(1, 3)

    def build(self, c):
        for y in range(LH):
            for x in range(LW):
                k = y / LH + (bayer(x, y) - 0.5) * 0.07
                c.set_at((x, y), lerp_color((40, 48, 74), (110, 110, 130), k))
        self.windows = []
        tx = 210                                                                 # the Tick, behind
        pygame.draw.rect(c, (44, 40, 56), (tx - 10, 34, 20, 70))
        pygame.draw.polygon(c, (44, 40, 56), [(tx - 13, 34), (tx, 18), (tx + 13, 34)])
        pygame.draw.line(c, (220, 224, 236), (tx - 13, 34), (tx, 18))
        pygame.draw.circle(c, (200, 190, 160), (tx, 44), 4)
        self.houses(c, 100, 83, (70, 62, 80), self.windows)
        self.houses(c, 128, 87, (58, 50, 66), self.windows)
        for y in range(128, LH):                                                 # the snowy street
            for x in range(LW):
                c.set_at((x, y), lerp_color((180, 186, 204), (140, 146, 168), (y - 128) / 19 + bayer(x, y) * 0.1))

    def frame(self, c, t):
        for i, (x, y) in enumerate(self.windows):                               # a Guild lamp in every window
            f = flicker(t, i, 0.1)
            c.set_at((x, y), scale_color((255, 200, 110), min(1.2, f)))
            c.set_at((x, y + 1), (200, 130, 60))
        for k in range(70):                                                     # snow
            q = (t * 0.07 + k * 0.137) % 1.0
            x = int((k * 53 + math.sin(t * 0.8 + k) * 6) % LW)
            c.set_at((x, int(q * LH)), (230, 234, 244))
        for i in range(3):                                                      # people, carrying lamps home
            x = (40 + t * 9 + i * 60) % (LW + 40) - 20
            figure(c, lambda s, px, py, i=i: _townsfolk(s, px, py, t + i), x, 146, factor=1, tint=(150, 150, 170))
            pygame.draw.rect(c, (255, 210, 120), (int(x) + 5, 137, 2, 3))

    def glow(self, surf, t, ox, oy):
        for i, (x, y) in enumerate(self.windows[::2]):
            add_glow(surf, at(ox, oy, x, y), int(18 * flicker(t, i, 0.1)), (90, 60, 24))
        add_glow(surf, at(ox, oy, 210, 44), 30, (60, 50, 30))


# ---------------------------------------------------------------- the Guild's coach

class Coach(Scene):
    """Before dawn: a Guild coach on the road out of Hollowmere, its lamps swinging, and in its window
    Maren, with the watch warm in her hand."""

    def build(self, c):
        for y in range(LH):
            for x in range(LW):
                k = y / LH + (bayer(x, y) - 0.5) * 0.07
                c.set_at((x, y), lerp_color(SKY_TOP, (60, 50, 84), k))
        rng = random.Random(91)
        for _ in range(50):
            c.set_at((rng.randrange(LW), rng.randrange(70)), (150, 150, 184))
        far = (22, 18, 32)
        rooftops(c, 96, 190, 330, seed=93, color=far)
        pygame.draw.rect(c, far, (262, 52, 12, 44))
        pygame.draw.polygon(c, far, [(260, 52), (268, 42), (276, 52)])
        for y in range(96, LH):                                                 # the moor, and the road
            for x in range(LW):
                c.set_at((x, y), lerp_color((30, 28, 40), (18, 16, 24), (y - 96) / 51 + bayer(x, y) * 0.1))
            w = 4 + (y - 96) * 0.8
            mid = 230 - (y - 96) * 1.8
            for x in range(int(mid - w), int(mid + w)):
                if 0 <= x < LW:
                    c.set_at((x, y), (52, 48, 58))

    def frame(self, c, t):
        x = 96 - (t * 4) % 40                                                   # the coach, going away from us
        y = 118
        bob = 1 if math.sin(t * 7) > 0 else 0
        pygame.draw.rect(c, (16, 12, 16), (x - 26, y - 22 + bob, 52, 24))        # the body
        pygame.draw.rect(c, (60, 46, 30), (x - 26, y - 22 + bob, 52, 24), 1)
        pygame.draw.rect(c, (120, 90, 46), (x - 20, y - 18 + bob, 14, 10))       # her window, warm
        for wx in (x - 18, x + 18):                                             # wheels
            pygame.draw.circle(c, (40, 32, 30), (int(wx), y + 4), 7, 2)
            a = t * 5
            pygame.draw.line(c, (40, 32, 30), (wx, y + 4), (wx + math.cos(a) * 6, y + 4 + math.sin(a) * 6))
        for k, lx in enumerate((x - 28, x + 27)):                              # its lamps, swinging
            ly = y - 24 + bob + int(math.sin(t * 3 + k) * 1.5)
            c.set_at((int(lx), ly), (255, 210, 120))
            c.set_at((int(lx), ly + 1), (230, 160, 80))
        for k in range(2):                                                      # the horses, in silhouette
            hx = x + 36 + k * 14
            pygame.draw.rect(c, (14, 10, 14), (hx - 6, y - 12, 12, 7))
            pygame.draw.rect(c, (14, 10, 14), (hx + 5, y - 17, 3, 7))
            for lg in (-4, 3):
                pygame.draw.line(c, (14, 10, 14), (hx + lg, y - 5), (hx + lg + (1 if math.sin(t * 9 + k) > 0 else -1),
                                                                   y + 4))
        from .theme import draw_thief
        img = pygame.Surface((32, 32), pygame.SRCALPHA)                         # Maren, in the window
        draw_thief(img, 16, 16, t, watch=True)
        c.blit(img.subsurface((8, 4, 16, 14)), (int(x) - 21, y - 22 + bob))
        self._coach_x = x

    def glow(self, surf, t, ox, oy):
        x = getattr(self, "_coach_x", 96)
        add_glow(surf, at(ox, oy, x - 13, 104), int(34 + 6 * math.sin(t * 3)), (110, 80, 30))
        for lx in (x - 28, x + 27):
            add_glow(surf, at(ox, oy, lx, 95), 24, (100, 70, 30))
