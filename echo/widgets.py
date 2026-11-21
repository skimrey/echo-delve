"""Drawing helpers and a Button widget. CPU-only: plain pygame.draw calls."""

import pygame

# Lamplit stone: near-black violet, parchment text, bronze rims, gold for light, violet for thread.
BG = (12, 10, 16)
PANEL = (26, 22, 28)
PANEL_LIGHT = (44, 38, 46)
TEXT = (238, 228, 208)
DIM = (164, 150, 134)
GOOD = (150, 216, 120)
BAD = (236, 96, 82)
WARN = (246, 192, 92)
ACCENT = (242, 200, 118)
ECHO = (140, 214, 250)
THREAD = (226, 164, 236)        # threads: what unravelling an echo costs
BRONZE = (150, 112, 64)
STONE_BTN = (54, 46, 50)


def draw_text(surf, font, text, pos, color=TEXT, center=False, right=False):
    img = font.render(str(text), True, color)
    r = img.get_rect()
    if center:
        r.center = pos
    elif right:
        r.topright = pos
    else:
        r.topleft = pos
    surf.blit(img, r)
    return r


def wrap_text(font, text, width):
    lines = []
    for para in str(text).split("\n"):
        line = ""
        for word in para.split(" "):
            trial = (line + " " + word).strip()
            if font.size(trial)[0] <= width or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def draw_wrapped(surf, font, text, pos, width, color=TEXT, spacing=3):
    x, y = pos
    for line in wrap_text(font, text, width):
        draw_text(surf, font, line, (x, y), color)
        y += font.get_height() + spacing
    return y


def draw_spool(surf, center, color):
    """A small spool of thread, the icon for threads."""
    cx, cy = center
    pygame.draw.rect(surf, color, (cx - 6, cy - 8, 12, 3), border_radius=1)
    pygame.draw.rect(surf, color, (cx - 6, cy + 5, 12, 3), border_radius=1)
    pygame.draw.rect(surf, tuple(v // 2 for v in color), (cx - 4, cy - 5, 8, 10))
    for k in range(3):
        y = cy - 4 + k * 3
        pygame.draw.line(surf, color, (cx - 4, y), (cx + 3, y + 2), 1)


def tint(surf, rect, color, alpha):
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    s.fill((*color, alpha))
    surf.blit(s, rect.topleft)


class Button:
    def __init__(self, rect, label, callback, enabled=True, color=STONE_BTN,
                 key=None, tag="", active=False):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.callback = callback
        self.enabled = enabled
        self.color = color
        self.key = key
        self.tag = tag
        self.active = active

    def click(self):
        if self.enabled and self.callback:
            self.callback()
            return True
        return False

    def draw(self, surf, font, hover=False):
        r = self.rect
        base = self.color if self.enabled else (32, 28, 32)
        if self.enabled and hover:
            base = tuple(min(255, c + 22) for c in base)
        top = tuple(min(255, c + 14) for c in base)
        pygame.draw.rect(surf, base, r, border_radius=6)
        pygame.draw.rect(surf, top, (r.x + 2, r.y + 2, r.w - 4, r.h // 2 - 1), border_radius=5)
        if self.active or (self.enabled and hover):
            pygame.draw.rect(surf, ACCENT, r, 2, border_radius=6)
        elif self.enabled:
            pygame.draw.rect(surf, BRONZE, r, 1, border_radius=6)
        else:
            pygame.draw.rect(surf, (60, 52, 50), r, 1, border_radius=6)
        color = TEXT if self.enabled else (110, 100, 96)
        img = font.render(self.label, True, color)
        surf.blit(img, img.get_rect(center=(r.centerx, r.centery + 1)))
