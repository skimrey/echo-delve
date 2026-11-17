"""Title, help, forge, upgrade, end and pause screens."""

import pygame

from .base import Screen
from .consts import MAX_FLOOR, PERKS, UPGRADES
from .widgets import (ACCENT, BAD, BG, DIM, GOOD, PANEL, PANEL_LIGHT, TEXT, WARN, Button, draw_text,
                      draw_wrapped, tint)

CX = 480


def _center_button_rect(y, w=300, h=48):
    return (CX - w // 2, y, w, h)


class TitleScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.add(_center_button_rect(250), "New Run  (N)", app.new_run, tag="new",
                 key=(pygame.K_n, pygame.K_RETURN, pygame.K_KP_ENTER))
        self.add(_center_button_rect(312), "Echo Forge  (F)", app.show_forge, tag="forge", key=pygame.K_f)
        self.add(_center_button_rect(374), "How to Play  (H)", app.show_help, tag="help", key=pygame.K_h)
        self.add(_center_button_rect(436), "Quit  (Esc)", app.quit, tag="quit", key=pygame.K_ESCAPE)

    def draw(self, surf):
        surf.fill(BG)
        f = self.app.fonts
        draw_text(surf, f[80], "ECHO DELVE", (CX, 130), ACCENT, center=True)
        draw_text(surf, f[26], "Every loop you leave behind comes back to help you.", (CX, 190), TEXT, center=True)
        d = self.app.meta.data
        draw_text(surf, f[22], "Runs %d   Wins %d   Best floor %d/%d   Shards %d" %
                  (d["runs"], d["wins"], d["best_floor"], MAX_FLOOR, d["shards"]),
                  (CX, 560), DIM, center=True)
        self.draw_buttons(surf)


HELP_TEXT = (
    "GOAL: reach the gold stairs on each of 6 floors.\n"
    "THE CATCH: numbered doors seal the only way forward. Door N is open only while something "
    "stands on plate N (same colour and number).\n"
    "ECHOES: every loop you end becomes an echo that replays your exact moves in later loops, "
    "starting from the entrance. Send loop 1 to a plate, anchor there, and from loop 2 on your echo "
    "holds the plate while you walk through the door. Door 2 needs a second echo, and so on.\n"
    "ENDING A LOOP: Anchor (E, press twice) leaves your echo standing where you are. If the turn "
    "counter runs out you are anchored automatically. If you die, your echo replays the loop and "
    "fades when you fell. Each floor gives you a limited number of loops.\n"
    "ECHOES ARE LITERAL: they repeat keystrokes, not intentions. If an enemy is not where it was, an "
    "echo may swing at air or bump a wall. Enemies attack echoes too and reset every loop.\n"
    "CONTROLS: arrows / WASD move or strike, Space or . waits, E anchors, Tab shows echo paths, "
    "click an adjacent tile to step, H help, Esc menu. Walking into a wall or sealed door costs no turn.\n"
    "DANGERS: Crawlers chase, Archers shoot along rows and columns, Brutes hit hard every other turn "
    "(a ! marks the turn they act), spikes are up for 2 turns and down for 2."
)


class HelpScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.add((CX - 100, 596, 200, 44), "Back  (Esc)", app.pop, tag="back",
                 key=(pygame.K_ESCAPE, pygame.K_h, pygame.K_RETURN, pygame.K_SPACE))

    def draw(self, surf):
        surf.fill(BG)
        f = self.app.fonts
        draw_text(surf, f[44], "How to Play", (CX, 44), ACCENT, center=True)
        draw_wrapped(surf, f[22], HELP_TEXT, (60, 84), 840, TEXT, spacing=4)
        self.draw_buttons(surf)


class ForgeScreen(Screen):
    ORDER = ["hp", "slots", "time", "atk"]

    def __init__(self, app):
        super().__init__(app)
        self.meta = app.meta
        for i, key in enumerate(self.ORDER):
            self.add((700, 150 + i * 92, 190, 44), "", lambda k=key: self.buy(k), tag="buy:" + key,
                     key=pygame.K_1 + i)
        self.add((CX - 100, 590, 200, 44), "Back  (Esc)", app.to_title, tag="back", key=pygame.K_ESCAPE)
        self.refresh()
        self.say("Spend shards on permanent perks. You earn them by clearing floors.")

    def refresh(self):
        for key in self.ORDER:
            b = self.btn("buy:" + key)
            lvl, mx = self.meta.level(key), PERKS[key][2]
            b.label = "Maxed" if lvl >= mx else "Buy  (%d shards)" % self.meta.cost(key)
            b.color = (58, 66, 96) if self.meta.can_buy(key) else (44, 46, 62)

    def buy(self, key):
        name, _, mx, _ = PERKS[key]
        if self.meta.level(key) >= mx:
            self.say("%s is already maxed." % name, WARN)
        elif not self.meta.can_buy(key):
            self.say("%s costs %d shards; you have %d." % (name, self.meta.cost(key), self.meta.data["shards"]), BAD)
        else:
            self.meta.buy(key)
            self.say("Bought %s (level %d)." % (name, self.meta.level(key)), GOOD)
        self.refresh()

    def draw(self, surf):
        surf.fill(BG)
        f = self.app.fonts
        draw_text(surf, f[44], "Echo Forge", (CX, 44), ACCENT, center=True)
        draw_text(surf, f[26], "Shards: %d" % self.meta.data["shards"], (CX, 92), WARN, center=True)
        for i, key in enumerate(self.ORDER):
            name, desc, mx, _ = PERKS[key]
            y = 140 + i * 92
            pygame.draw.rect(surf, PANEL, (70, y, 840, 80), border_radius=8)
            draw_text(surf, f[26], "%d. %s" % (i + 1, name), (90, y + 12), TEXT)
            draw_text(surf, f[18], desc, (90, y + 44), DIM)
            lvl = self.meta.level(key)
            for p in range(mx):
                r = pygame.Rect(480 + p * 30, y + 28, 22, 22)
                pygame.draw.rect(surf, ACCENT if p < lvl else PANEL_LIGHT, r, border_radius=4)
        draw_text(surf, f[22], self.msg, (CX, 556), self.msg_color, center=True)
        self.draw_buttons(surf)


class UpgradeScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.run = app.run
        for i, key in enumerate(self.run.options):
            self.add((60 + i * 290, 190, 270, 250), "", lambda k=key: app.choose_upgrade(k),
                     tag="up%d" % i, key=pygame.K_1 + i, color=PANEL_LIGHT)

    def draw(self, surf):
        surf.fill(BG)
        f = self.app.fonts
        r = self.run
        draw_text(surf, f[44], "Floor %d cleared" % r.floor_no, (CX, 56), GOOD, center=True)
        draw_text(surf, f[22], "Loops used: %d.  Pick one upgrade (1-3)." % r.play.loop_no, (CX, 100), TEXT, center=True)
        for i, key in enumerate(r.options):
            b = self.btn("up%d" % i)
            pygame.draw.rect(surf, b.color if b is not self.hover else (58, 62, 86), b.rect, border_radius=10)
            pygame.draw.rect(surf, ACCENT if b is self.hover else (96, 106, 144), b.rect, 2, border_radius=10)
            name, desc = UPGRADES[key]
            draw_text(surf, f[32], "%d. %s" % (i + 1, name), (b.rect.x + 16, b.rect.y + 20), TEXT)
            draw_wrapped(surf, f[22], desc, (b.rect.x + 16, b.rect.y + 80), b.rect.w - 32, DIM)
        draw_text(surf, f[22], "Now: HP %d   Attack %d   Echo slots %d   Turns/loop +%d   Sight %d   Echo bonus HP +%d" %
                  (r.max_hp, r.atk, r.slots, r.limit_bonus, r.sight, r.ghost_hp), (CX, 500), DIM, center=True)


class EndScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.run = app.run
        self.add((CX - 150, 440, 300, 48), "New Run  (N)", app.new_run, tag="new",
                 key=(pygame.K_n, pygame.K_RETURN, pygame.K_KP_ENTER))
        self.add((CX - 150, 500, 300, 48), "Echo Forge  (F)", app.show_forge, tag="forge", key=pygame.K_f)
        self.add((CX - 150, 560, 300, 48), "Title  (Esc)", app.to_title, tag="title", key=pygame.K_ESCAPE)

    def draw(self, surf):
        surf.fill(BG)
        f = self.app.fonts
        r = self.run
        won = r.state == "won"
        draw_text(surf, f[80], "VICTORY" if won else "THE LOOPS END", (CX, 120), GOOD if won else BAD, center=True)
        if won:
            draw_text(surf, f[26], "Every echo walked you to the bottom.", (CX, 190), TEXT, center=True)
        else:
            draw_text(surf, f[26], r.reason, (CX, 190), TEXT, center=True)
        lines = ["Floors cleared: %d / %d" % (r.cleared, MAX_FLOOR), "Shards earned: %d" % r.shards_earned(),
                 "Seed: %d" % r.seed]
        if r.picked:
            lines.append("Upgrades: " + ", ".join(UPGRADES[k][0] for k in r.picked))
        for i, line in enumerate(lines):
            draw_text(surf, f[26], line, (CX, 250 + i * 34), TEXT if i < 2 else DIM, center=True)
        self.draw_buttons(surf)


class PauseScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.parent = app.stack[-1]
        self.confirm = False
        self.add((CX - 140, 250, 280, 48), "Resume  (Esc)", app.pop, tag="resume", key=pygame.K_ESCAPE)
        self.add((CX - 140, 312, 280, 48), "How to Play  (H)", app.show_help, tag="help", key=pygame.K_h)
        self.add((CX - 140, 374, 280, 48), "Abandon Run  (A)", self.abandon, tag="abandon", key=pygame.K_a)

    def abandon(self):
        if not self.confirm:
            self.confirm = True
            self.btn("abandon").label = "Really abandon? Click again"
            self.btn("abandon").color = (120, 50, 56)
            self.say("Press A or click again to end this run. Esc cancels.", WARN)
        else:
            self.app.abandon_run()

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE and self.confirm:
            self.confirm = False
            b = self.btn("abandon")
            b.label, b.color = "Abandon Run  (A)", (58, 66, 96)
            self.say("Abandon cancelled.")
            self.app.dirty = True
            return True
        return super().handle(ev)

    def draw(self, surf):
        self.parent.draw(surf)
        tint(surf, surf.get_rect(), (0, 0, 0), 170)
        draw_text(surf, self.app.fonts[44], "Paused", (CX, 190), ACCENT, center=True)
        draw_text(surf, self.app.fonts[22], self.msg, (CX, 470), self.msg_color, center=True)
        self.draw_buttons(surf)
