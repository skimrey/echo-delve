"""Screens shared by the sister-game prototypes: a title, a rules card and a text card."""

import pygame

from ..base import Screen
from ..cinematics import draw_scene
from ..theme import draw_glow_text, draw_panel, draw_rule
from ..widgets import ACCENT, DIM, TEXT, draw_text, draw_wrapped, tint, wrap_text

W, H = 960, 660


class ProtoTitle(Screen):
    """Title for a prototype: its own painted backdrop, name and tagline."""

    def __init__(self, app, title, tagline, scene, on_play, on_story, rules):
        super().__init__(app)
        self.title, self.tagline, self.scene, self.rules = title, tagline, scene, rules
        self.t = 0.0
        self.add((W // 2 - 150, 356, 300, 44), "Play  (N)", on_play, tag="play",
                 key=(pygame.K_n, pygame.K_RETURN, pygame.K_KP_ENTER))
        self.add((W // 2 - 150, 408, 300, 44), "The Story  (S)", on_story, tag="story", key=pygame.K_s)
        self.add((W // 2 - 150, 460, 300, 44), "How to Play  (H)",
                 lambda: app.push(RulesCard(app, title, rules)), tag="help", key=pygame.K_h)
        self.add((W // 2 - 150, 512, 300, 44), "Quit  (Esc)", app.quit, tag="quit", key=pygame.K_ESCAPE)

    def update(self, dt):
        self.t += dt
        return True

    def draw(self, surf):
        draw_scene(surf, self.scene, self.t, pygame.Rect(0, 0, W, H))
        tint(surf, surf.get_rect(), (0, 0, 0), 110)
        draw_glow_text(surf, self.app.bold[80], self.title.upper(), (W // 2, 150), ACCENT, (140, 80, 30))
        draw_rule(surf, W // 2, 198, 340)
        draw_text(surf, self.app.italic[26], self.tagline, (W // 2, 228), TEXT, center=True)
        draw_text(surf, self.app.italic[18], "A prototype set on the same night as Echo Delve", (W // 2, 262), DIM,
                  center=True)
        self.draw_buttons(surf)


class RulesCard(Screen):
    def __init__(self, app, title, rules):
        super().__init__(app)
        self.title, self.rules = title, rules
        self.parent = app.stack[-1]
        self.add((W // 2 - 100, H - 70, 200, 42), "Back  (Esc)", app.pop, tag="back",
                 key=(pygame.K_ESCAPE, pygame.K_h, pygame.K_RETURN, pygame.K_SPACE))

    def update(self, dt):
        return self.parent.update(dt)

    def draw(self, surf):
        self.parent.draw(surf)
        tint(surf, surf.get_rect(), (4, 2, 8), 190)
        box = pygame.Rect(60, 26, W - 120, H - 102)
        draw_panel(surf, box, fill=(24, 20, 26))
        draw_glow_text(surf, self.app.bold[44], "How to play " + self.title, (W // 2, box.y + 40), ACCENT)
        y = box.y + 76
        for head, body in self.rules:
            draw_text(surf, self.app.bold[22], head, (box.x + 40, y), ACCENT)
            y = draw_wrapped(surf, self.app.fonts[18], body, (box.x + 40, y + 22), box.w - 80, TEXT, spacing=3) + 6
        self.draw_buttons(surf)


class Card(Screen):
    """A centred text card over the screen below it: level intros, results and endings."""

    def __init__(self, app, title, body, button, on_continue, color=ACCENT):
        super().__init__(app)
        self.parent = app.stack[-1]
        self.title, self.body, self.color = title, body, color
        self.on_continue = on_continue
        self.add((W // 2 - 150, 0, 300, 44), button, on_continue, tag="continue",
                 key=(pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE))
        lines = len(wrap_text(app.italic[22], body, 640 - 88))
        h = max(300, 80 + lines * (app.italic[22].get_linesize() + 4) + 84)     # (tall enough for the text)
        self.box = pygame.Rect(W // 2 - 320, max(20, (H - h) // 2 - 10), 640, h)
        self.btn("continue").rect.y = self.box.bottom - 64

    def update(self, dt):
        return self.parent.update(dt)

    def draw(self, surf):
        self.parent.draw(surf)
        tint(surf, surf.get_rect(), (4, 2, 8), 150)
        draw_panel(surf, self.box, fill=(24, 20, 26))
        draw_glow_text(surf, self.app.bold[32], self.title, (W // 2, self.box.y + 42), self.color)
        draw_wrapped(surf, self.app.italic[22], self.body, (self.box.x + 44, self.box.y + 80), self.box.w - 88, TEXT,
                     spacing=4)
        self.draw_buttons(surf)


class ChoiceCard(Card):
    """A card with two answers (the end of a story that asks you something)."""

    def __init__(self, app, title, body, choices, color=ACCENT):
        (label_a, cb_a), (label_b, cb_b) = choices
        super().__init__(app, title, body, label_a, cb_a, color)
        b = self.btn("continue")
        b.rect.x, b.rect.w = W // 2 - 310, 300
        b.key = (pygame.K_1,)
        b.label = "1. " + label_a
        self.add((W // 2 + 10, b.rect.y, 300, 44), "2. " + label_b, cb_b, tag="other", key=(pygame.K_2,))
