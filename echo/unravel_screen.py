"""The unravel picker: choose an echo to erase so its slot can be recorded again.

Opened two ways:
- forced: your last loop ended short of the stairs with every echo slot full. Pick an echo to
  unravel (the loop you just played is one of the choices) or end the run.
- voluntary: U / the Unravel button during a loop. Esc cancels; unravelling restarts the loop.

The selected echo's whole route is drawn on the map so you can see what you are erasing.
"""

import pygame

from .base import Screen
from .game_screen import GRID_H, OY, TILE, ghost_color, lever_color, script_path
from .sim import LETTERS
from .theme import vertical_gradient
from .widgets import (ACCENT, BAD, DIM, PANEL_LIGHT, TEXT, THREAD, WARN, draw_spool, draw_text, draw_wrapped,
                      tint)
from .consts import PAIR_COLORS

W, H = 960, 660
PANEL_H = 178
CARD_W, CARD_H, CARD_GAP = 106, 62, 8
NUMBER_KEYS = {getattr(pygame, "K_%d" % n): n for n in range(1, 10)}
NUMBER_KEYS.update({getattr(pygame, "K_KP%d" % n): n for n in range(1, 10)})


class UnravelScreen(Screen):
    def __init__(self, app, forced):
        super().__init__(app)
        self.parent = app.stack[-1]
        self.parent.hover_tile = None             # no game tooltip under the picker
        self.run = app.run
        self.forced = forced
        self.selected = None
        self.confirm_end = False
        self.panel_y = H - PANEL_H
        labels = [s.label for s in self.run.play.scripts]
        for label in labels:
            self.add((0, 0, CARD_W, CARD_H), "", lambda n=label: self.select(n), tag="echo:%d" % label)
        self.add((0, 0, 236, 36), "", self.unravel, tag="confirm")
        if forced:
            self.add((0, 0, 150, 36), "End Run", self.end_run, tag="end", color=(86, 44, 52))
        else:
            self.add((0, 0, 150, 36), "Cancel  (Esc)", self.cancel, tag="cancel")
        self.layout()
        self._refresh_confirm()
        self.say("Pick an echo (1-%d or click), then press Enter to unravel it." % max(labels or [1]))

    # ------------------------------------------------------------ layout
    def _panel_side(self):
        """Put the panel where it hides less of the selected echo's route (bottom by default)."""
        if self.selected is None:
            return H - PANEL_H
        pts = self.path(self.selected)
        top_rows = (PANEL_H - OY) / TILE
        bottom_rows = GRID_H - (H - PANEL_H - OY) / TILE

        def hidden(fn):
            return sum(1 for p in pts if fn(p[1])) + 10 * fn(pts[-1][1])
        under_bottom = hidden(lambda y: y + 1 > GRID_H - bottom_rows)
        under_top = hidden(lambda y: y < top_rows)
        return 0 if under_bottom > under_top else H - PANEL_H

    def layout(self):
        self.panel_y = y = self._panel_side()
        labels = [s.label for s in self.run.play.scripts]
        n = len(labels)
        total = n * CARD_W + (n - 1) * CARD_GAP
        x0 = max(16, (W - total) // 2)
        for i, label in enumerate(labels):
            self.btn("echo:%d" % label).rect.topleft = (x0 + i * (CARD_W + CARD_GAP), y + 66)
        self.btn("confirm").rect.topleft = (W - 16 - 236, y + 136)
        other = self.btn("end") or self.btn("cancel")
        other.rect.topleft = (W - 16 - 236 - 10 - 150, y + 136)

    # ------------------------------------------------------------ actions
    def path(self, label):
        s = self.run.play.script(label)
        return script_path(self.run.floor, s.actions) if s else []

    def select(self, label):
        if self.run.play.script(label) is None:
            self.say("There is no echo %d." % label, WARN)
            return
        self.selected = label
        self._reset_end()
        self.layout()
        self._refresh_confirm()
        if self.forced and label == self.run.play.last_label:
            hint = "That is the loop you just played: unravel it to try that loop again."
        elif self.forced:
            hint = "Your next loop is recorded as echo %d in its place." % label
        else:
            hint = "The loop restarts without it; your next loop becomes echo %d." % label
        self.say("Echo %d: %s" % (label, hint), TEXT)

    def cycle(self, step):
        labels = [s.label for s in self.run.play.scripts]
        if not labels:
            return
        if self.selected not in labels:
            self.select(labels[0] if step > 0 else labels[-1])
        else:
            self.select(labels[(labels.index(self.selected) + step) % len(labels)])

    def _refresh_confirm(self):
        b = self.btn("confirm")
        if self.selected is None:
            b.label = "Unravel  (pick an echo)"
            b.color = (40, 34, 38)
        else:
            b.label = "Unravel echo %d  (Enter)" % self.selected
            b.color = (112, 62, 116)

    def unravel(self):
        if self.selected is None:
            self.say("Pick an echo first: press its number or click its card.", WARN)
            return
        script = self.run.play.script(self.selected)
        self.run.unravel(self.selected)
        self.app.finish_unravel(script)

    def cancel(self):
        if self.forced:
            self.say("Your echo slots are full: unravel an echo, or end the run.", WARN)
            return
        self.app.pop()
        self.parent.say("Unravel cancelled.")

    def end_run(self):
        if not self.confirm_end:
            self.confirm_end = True
            b = self.btn("end")
            b.label, b.color = "Really end the run?", (140, 50, 58)
            self.say("Click End Run again to let the loops end. Esc cancels.", WARN)
            return
        self.app.abandon_run()

    def _reset_end(self):
        if self.confirm_end:
            self.confirm_end = False
            b = self.btn("end")
            b.label, b.color = "End Run", (86, 44, 52)
            return True
        return False

    # ------------------------------------------------------------ input
    def handle(self, ev):
        if ev.type == pygame.KEYDOWN:
            k = ev.key
            if k == pygame.K_ESCAPE:
                if self._reset_end():
                    self.say("Kept going. Pick an echo to unravel.")
                else:
                    self.cancel()
                self.app.dirty = True
                return True
            if k in NUMBER_KEYS:
                self.select(NUMBER_KEYS[k])
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.unravel()
            elif k in (pygame.K_RIGHT, pygame.K_d, pygame.K_TAB, pygame.K_DOWN, pygame.K_s):
                self.cycle(1)
            elif k in (pygame.K_LEFT, pygame.K_a, pygame.K_UP, pygame.K_w):
                self.cycle(-1)
            elif k == pygame.K_h:
                self.app.show_help()
            else:
                return False
            self.app.dirty = True
            return True
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            b = self.button_at(ev.pos)
            if b is not None and b.tag != "end":
                self._reset_end()
        return super().handle(ev)

    def update(self, dt):
        return self.parent.update(dt)          # let hit numbers and flashes underneath fade out

    # ------------------------------------------------------------ drawing
    def draw(self, surf):
        self.parent.draw(surf)
        tint(surf, pygame.Rect(0, 0, W, H), (6, 6, 12), 120)
        play, floor = self.run.play, self.run.floor
        for s in play.scripts:                      # every route, faintly...
            if s.label != self.selected:
                pts = script_path(floor, s.actions)
                self.parent.draw_path(surf, pts, s.label, s.ending, 1,
                                      tuple(v // 2 for v in ghost_color(s.label)))
        if self.selected is not None:                # ...the selected one bright
            s = play.script(self.selected)
            pts = script_path(floor, s.actions)
            self.parent.draw_path(surf, pts, s.label, s.ending, 4, ghost_color(s.label))
            c = self.parent.tile_center(floor.start)
            pygame.draw.circle(surf, ghost_color(s.label), c, 5)
            ex, ey = self.parent.tile_center(pts[-1])
            draw_text(surf, self.app.bold[22], s.label, (ex + 12, ey - 12), ghost_color(s.label), center=True)
        self._draw_panel(surf)

    def _draw_panel(self, surf):
        f = self.app.fonts
        run, play = self.run, self.run.play
        y = self.panel_y
        surf.blit(vertical_gradient((W, PANEL_H), (34, 28, 36), (20, 16, 22)), (0, y))
        edge_y = y if y else PANEL_H - 1
        pygame.draw.line(surf, THREAD, (0, edge_y), (W, edge_y), 2)
        title = "Your echo slots are full" if self.forced else "Unravel an echo"
        draw_text(surf, self.app.bold[32], title, (16, y + 8), WARN if self.forced else ACCENT)
        # cost, right-aligned
        r = draw_text(surf, f[22], run.unravel_cost_text(), (W - 16, y + 14), THREAD, right=True)
        draw_spool(surf, (r.x - 12, r.centery), THREAD)
        if self.forced:
            sub = ("Your last loop ended short of the stairs. Unravel one echo to free its slot and keep "
                   "going; the loop you just played is one of the choices.")
        else:
            sub = ("Erase an echo you no longer want. The current loop restarts without it, and your next "
                   "loop is recorded in its slot.")
        draw_wrapped(surf, f[18], sub, (16, y + 42), W - 32, DIM, spacing=1)
        for s in play.scripts:
            self._draw_card(surf, s)
        draw_wrapped(surf, f[18], self.msg, (16, y + 138), W - 16 - 236 - 10 - 150 - 32,
                     self.msg_color, spacing=1)
        self.draw_buttons_except_cards(surf)

    def _draw_card(self, surf, s):
        f = self.app.fonts
        b = self.btn("echo:%d" % s.label)
        r = b.rect
        c = ghost_color(s.label)
        sel = s.label == self.selected
        hov = b is self.hover
        pygame.draw.rect(surf, (62, 42, 66) if sel else (PANEL_LIGHT if not hov else (56, 48, 58)), r, border_radius=8)
        pygame.draw.rect(surf, THREAD if sel else (c if hov else tuple(v // 2 for v in c)), r, 3 if sel else 1,
                         border_radius=8)
        # number badge
        center = (r.x + 20, r.y + r.h // 2)
        pygame.draw.circle(surf, tuple(v // 2 for v in c), center, 13)
        pygame.draw.circle(surf, c, center, 13, 2)
        draw_text(surf, self.app.bold[26], s.label, center, (255, 255, 255), center=True)
        tx = r.x + 40
        draw_text(surf, f[18], "Loop %d" % s.loop if s.loop else "Echo %d" % s.label, (tx, r.y + 8), TEXT)
        fell = s.ending == "dead"
        plate = self.run.floor.plate_at.get(s.end_pos) if s.end_pos else None
        if s.pulls:                                  # for lever echoes, the timing is what matters
            levers = sorted({lv for _, lv in s.pulls})
            c = lever_color(levers[0])
            draw_text(surf, f[16], "Pulls " + ", ".join(LETTERS[lv] for lv in levers), (tx, r.y + 26), c)
            turns = [str(t) for t, _ in s.pulls]
            draw_text(surf, f[16], ("turn " if len(turns) == 1 else "turns ") + ", ".join(turns),
                      (tx, r.y + 41), c)
        else:
            draw_text(surf, f[16], "Fell" if fell else "Anchored", (tx, r.y + 26), BAD if fell else DIM)
            if plate is not None and not fell:
                draw_text(surf, f[16], "on plate %d" % (plate + 1), (tx, r.y + 41),
                          PAIR_COLORS[plate % len(PAIR_COLORS)])
            else:
                draw_text(surf, f[16], "%d turn%s" % (len(s.actions), "" if len(s.actions) == 1 else "s"),
                          (tx, r.y + 41), DIM)
        if self.forced and s.label == self.run.play.last_label:
            tag = pygame.Rect(r.right - 34, r.y - 7, 30, 14)
            pygame.draw.rect(surf, WARN, tag, border_radius=4)
            draw_text(surf, f[16], "NEW", tag.center, (30, 24, 10), center=True)

    def draw_buttons_except_cards(self, surf):
        font = self.app.fonts[22]
        for b in self.buttons:
            if not b.tag.startswith("echo:"):
                b.draw(surf, font, hover=b is self.hover)
