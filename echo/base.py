"""Screen base class: buttons, hover, key shortcuts and a status message."""

import pygame

from .widgets import DIM, Button


class Screen:
    def __init__(self, app):
        self.app = app
        self.buttons = []
        self.hover = None
        self.msg = ""
        self.msg_color = DIM

    def add(self, rect, label, callback, **kw):
        b = Button(rect, label, callback, **kw)
        self.buttons.append(b)
        return b

    def say(self, msg, color=DIM):
        self.msg, self.msg_color = msg, color
        self.app.dirty = True

    def button_at(self, pos):
        for b in reversed(self.buttons):
            if b.rect.collidepoint(pos):
                return b
        return None

    def btn(self, tag):
        for b in self.buttons:
            if b.tag == tag:
                return b
        return None

    def draw_buttons(self, surf):
        font = self.app.fonts[22]
        for b in self.buttons:
            b.draw(surf, font, hover=b is self.hover)

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            hb = self.button_at(ev.pos)
            if hb is not self.hover:
                self.hover = hb
                self.app.dirty = True
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            b = self.button_at(ev.pos)
            if b is not None:
                b.click()
                self.app.dirty = True
                return True
        elif ev.type == pygame.KEYDOWN:
            for b in list(self.buttons):
                keys = b.key if isinstance(b.key, (tuple, list)) else (b.key,)
                if ev.key in keys and b.callback:
                    b.callback()
                    self.app.dirty = True
                    return True
        return False

    def update(self, dt):
        return False
