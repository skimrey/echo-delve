"""Drawing helpers and a Button widget. CPU-only: plain pygame.draw calls."""

import pygame

BG = (14, 15, 22)
PANEL = (26, 28, 40)
PANEL_LIGHT = (38, 41, 58)
TEXT = (232, 234, 244)
DIM = (140, 146, 170)
GOOD = (110, 220, 130)
BAD = (240, 96, 96)
WARN = (244, 196, 84)
ACCENT = (120, 200, 255)


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


def tint(surf, rect, color, alpha):
    s = pygame.Surface(rect.size, pygame.SRCALPHA)
    s.fill((*color, alpha))
    surf.blit(s, rect.topleft)


class Button:
    def __init__(self, rect, label, callback, enabled=True, color=(58, 66, 96),
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
        base = self.color if self.enabled else (34, 36, 48)
        if self.enabled and hover:
            base = tuple(min(255, c + 24) for c in base)
        pygame.draw.rect(surf, base, self.rect, border_radius=6)
        if self.active:
            pygame.draw.rect(surf, ACCENT, self.rect, 3, border_radius=6)
        elif self.enabled:
            pygame.draw.rect(surf, (96, 106, 144), self.rect, 1, border_radius=6)
        color = TEXT if self.enabled else (96, 100, 120)
        img = font.render(self.label, True, color)
        surf.blit(img, img.get_rect(center=self.rect.center))
