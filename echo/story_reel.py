"""The Story: the whole of The Long Night, front to back, as its painted scenes.

The world's story, then each of the three in turn (prologues, the interludes, the beats that matter),
in the order a good night would tell them. The two real choices are played, not told, over their
animated scenes: at the break Tarn takes his people through or lets them stay; in the Drum Room Maren
opens the brake or takes the Guildmaster's bargain. The ending follows from them (everything else as on
a perfect night).

Chapters appear along the bottom as they are reached; click one (or press its number) to go back to
it. Left / Backspace goes back a panel, across chapters. Going back past a choice and on again asks it
again, so every branch can be seen.

In dev mode (--dev) the Story also asks, before the ending, how the rest of the night went (sconces,
the Still, Maren, how the night ended, how much morning was left), so every ending can be seen without
playing a night. The same picker is on the Long Night's title as "Endings (dev)".
"""

import pygame

from . import campaign as cp
from . import ending, story
from .base import Screen
from .cinematics import IntroScreen, draw_scene
from .sisters import stillwater as sw
from .sisters import tick as tk
from .theme import GOLD, draw_glow_text, draw_panel, text_surface
from .widgets import ACCENT, BG, DIM, TEXT, draw_text, tint, wrap_text

W, H = 960, 660
CX = W // 2
ART_H = 420


def chapters():
    """(label, whose, panels, choice) in the order the Story tells them; `choice` names the choice
    asked when the chapter ends (its later chapters depend on the answer)."""
    return [
        ("The world", None, cp.INTRO, None),
        ("Aurel", "Aurel", story.PROLOGUE, None),
        ("Maren", "Maren", tk.PROLOGUE, None),
        ("Tarn", "Tarn", sw.PROLOGUE, None),
        ("The ledger", "Maren", [("ledger_desk", tk.BEATS[1])], None),
        ("A sconce lit", "Maren", tk.INTERLUDES[2], None),
        ("The old ones", "Tarn", sw.INTERLUDES[3], None),
        ("Halfway down", "Aurel", story.INTERLUDES[5], None),
        ("The break", "Tarn", sw.INTERLUDES["last"], "tarn"),
    ]


def after_the_break(choice):
    if choice == "stay":
        result = ("They stay", "Tarn", [("pool_glow", sw.ENDING_STAY)], None)
    else:
        result = ("Through", "Tarn", [("loom_arrival", sw.ENDING_ALL_DARK)], None)
    return [result, ("The Drum Room", "Maren", tk.INTERLUDES["last"], "maren")]


def after_the_drum(choice, still_choice):
    if choice == "bargain":
        result = ("The bargain", "Maren", [("drum_master", tk.ENDING_BARGAIN)], None)
    else:
        result = ("The brake", "Maren", [("drum_open", tk.ENDING_RELEASE)], None)
    door = story.LOOM_WITH_STILL if still_choice == "through" else story.INTERLUDES[10]
    return [result, ("The Loom's door", "Aurel", door, "end")]


class StoryScreen(IntroScreen):
    """The Story, as one long reel of panels grouped into chapters, with its two choices."""

    def __init__(self, app, on_done=None):
        self.chapters = list(chapters())
        self.outcome = ending.NightOutcome()          # a perfect night, until something says otherwise
        self.reached = 0                              # the furthest chapter seen
        super().__init__(app, on_done or app.to_title, self._flat(), title=None)
        self.btn("skip").label = "Title  (Esc)"
        self.add((200, H - 56, 140, 40), "Back  (Left)", self.back, tag="back")
        self.chapter_rects = []

    # -- the reel
    def _flat(self):
        """Every panel: (scene, text, whose, chapter index)."""
        out = []
        for ci, (_label, whose, panels, _choice) in enumerate(self.chapters):
            out.extend((key, text, whose, ci) for key, text in panels)
        return out

    def _rebuild(self):
        self.panels = self._flat()
        from .scenery import prewarm
        from .cinematics import PAINTED
        prewarm([PAINTED[p[0]] for p in self.panels if p[0] in PAINTED])

    @property
    def scene(self):
        key, text, _whose, _ci = self.panels[self.i]
        return key, text

    @property
    def chapter(self):
        return self.panels[self.i][3]

    def chapter_start(self, ci):
        return next(i for i, p in enumerate(self.panels) if p[3] == ci)

    def goto(self, i):
        self.i = max(0, min(len(self.panels) - 1, i))
        self.t = 0.0
        self.reached = max(self.reached, self.chapter)
        self.title = self.panels[self.i][2]
        last = self.i == len(self.panels) - 1 and self.chapters[self.chapter][3] is None
        self.btn("next").label = "The end  (Enter)" if last else "Next  (Enter)"

    def advance(self):
        if not self.line_done():
            self.t = len(self.scene[1]) / self.TYPE_SPEED + 0.01
            return
        ci = self.chapter
        if self.i + 1 < len(self.panels) and self.panels[self.i + 1][3] == ci:
            self.goto(self.i + 1)
            return
        self._end_of_chapter(ci)

    def back(self):
        if self.i > 0:
            self.goto(self.i - 1)
            self.t = 99.0

    def finish(self):                                  # Esc: leave the Story
        self.app.to_title()

    def _end_of_chapter(self, ci):
        choice = self.chapters[ci][3]
        if choice == "tarn":
            self._ask("The break", "Beyond the break the Spindle drops into the dark, toward a golden glow far below, "
                                   "and nobody has lit the stair beside it yet. Take your people through, and trust "
                                   "that someone will? Or let them stay here, in the light, for as long as it lasts?",
                      [("Take them through", "through"), ("Let them stay", "stay")], ci)
        elif choice == "maren":
            self._ask("The Drum Room", "The drum holds what the Guild has not sold tonight, and your watch a little "
                                       "more. The Guildmaster holds out his hand for the ledger. Open the brake and "
                                       "let it all run down the thread, to whoever is pulling; or take his bargain: "
                                       "enough for your brother to tie it, and the watch is yours.",
                      [("Open the brake", "released"), ("Take his bargain", "bargain")], ci)
        elif choice == "end":
            self._end_ci = ci
            if self.app.dev:
                self.app.replace(OutcomeScreen(self.app, self.outcome, self._the_end))
            else:
                self._the_end(self.outcome)
        elif ci + 1 < len(self.chapters):
            self.goto(self.chapter_start(ci + 1))
        else:
            from .night_screen import EpilogueScreen
            self.app.replace(EpilogueScreen(self.app, self.outcome, self.on_done))

    def _ask(self, title, body, options, ci):
        from .sisters.common import ChoiceCard
        (la, va), (lb, vb) = options
        self.app.push(ChoiceCard(self.app, title, body, [(la, lambda: self._chosen(ci, va)),
                                                         (lb, lambda: self._chosen(ci, vb))], color=GOLD))

    def _chosen(self, ci, value):
        self.app.pop()                                 # (the card)
        o = self.outcome
        del self.chapters[ci + 1:]                     # what follows depends on it
        if self.chapters[ci][3] == "tarn":
            o.still_choice = value
            self.chapters += after_the_break(value)
        else:
            o.hoard_choice = value
            o.released = 300 if value == "released" else 0
            self.chapters += after_the_drum(value, o.still_choice)
        self.reached = min(self.reached, ci)
        self._rebuild()
        self.goto(self.chapter_start(ci + 1))

    def _the_end(self, outcome):
        self.outcome = outcome
        if getattr(self, "_end_ci", None) is not None:
            del self.chapters[self._end_ci + 1:]       # (seen before: tell it again, as it is now)
        ci = len(self.chapters)
        self.chapters.append(("The end", None, ending.ending_panels(outcome), None))
        self._rebuild()
        self.app.replace(self)
        self.goto(self.chapter_start(ci))

    # -- input
    def handle(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for ci, r in self.chapter_rects:
                if r.collidepoint(ev.pos):
                    self.goto(self.chapter_start(ci))
                    self.app.dirty = True
                    return True
        if ev.type == pygame.KEYDOWN and pygame.K_1 <= ev.key <= pygame.K_9:
            ci = ev.key - pygame.K_1
            if ci <= self.reached and ci < len(self.chapters):
                self.goto(self.chapter_start(ci))
                self.app.dirty = True
                return True
        return super().handle(ev)

    # -- drawing
    def draw(self, surf):
        surf.fill(BG)
        art = pygame.Rect(0, 0, W, ART_H)
        key, text = self.scene
        draw_scene(surf, key, self.t, art)
        fade = pygame.Surface((W, 36), pygame.SRCALPHA)                # (short: the floor of a scene shows)
        for y in range(36):
            pygame.draw.line(fade, (*BG, int(255 * y / 36)), (0, y), (W, y))
        surf.blit(fade, (0, ART_H - 36))
        if self.t < 0.5:
            veil = pygame.Surface((W, ART_H), pygame.SRCALPHA)
            veil.fill((*BG, int(255 * (1 - self.t / 0.5))))
            surf.blit(veil, (0, 0))
        if self.title:
            draw_text(surf, self.app.italic[22], self.title, (28, 18), (214, 184, 130))
            pygame.draw.line(surf, (150, 120, 80), (28, 46), (28 + self.app.italic[22].size(self.title)[0], 46))
        shown = text[:self.typed()]
        font = self.app.italic[26]
        y, used = ART_H + 12, 0
        for line in wrap_text(font, text, 820):
            part = shown[used:used + len(line)]
            used += len(line) + 1
            if part:
                surf.blit(font.render(part, True, TEXT), (70, y))
            y += font.get_linesize() + 2
        self._draw_chapters(surf)
        self.draw_buttons(surf)

    def _draw_chapters(self, surf):
        """The chapters reached so far, along the dark strip at the bottom; the current one lit. When
        they no longer fit, a window of them around the current one, with arrows for the rest."""
        font = self.app.italic[16]
        labels = [(ci, c[0]) for ci, c in enumerate(self.chapters) if ci <= self.reached]
        widths = {ci: font.size(label)[0] + 18 for ci, label in labels}
        room = W - 80
        cur = min(self.chapter, labels[-1][0])
        lo = hi = cur
        used = widths[cur]
        while True:                                  # grow the window around the current chapter
            grew = False
            if hi + 1 <= labels[-1][0] and used + 6 + widths[hi + 1] <= room:
                hi += 1
                used += 6 + widths[hi]
                grew = True
            if lo - 1 >= 0 and used + 6 + widths[lo - 1] <= room:
                lo -= 1
                used += 6 + widths[lo]
                grew = True
            if not grew:
                break
        x = CX - used // 2
        y = H - 92
        if lo > 0:
            draw_text(surf, self.app.bold[18], "<", (x - 22, y + 2), DIM)
        if hi < labels[-1][0]:
            draw_text(surf, self.app.bold[18], ">", (x + used + 10, y + 2), DIM)
        self.chapter_rects = []
        for ci, label in labels[lo:hi + 1]:
            w = widths[ci]
            r = pygame.Rect(x, y, w, 24)
            on = ci == self.chapter
            pygame.draw.rect(surf, (44, 36, 34) if on else (22, 18, 22), r, border_radius=6)
            pygame.draw.rect(surf, ACCENT if on else (70, 60, 56), r, 1, border_radius=6)
            surf.blit(text_surface(font, label, ACCENT if on else DIM), (r.x + 9, r.y + 3))
            self.chapter_rects.append((ci, r))
            x += w + 6


class StoryReel:
    """Starts the Story (kept for callers that expect a reel with start())."""

    def __init__(self, app, on_done=None):
        self.app = app
        self.on_done = on_done

    def start(self):
        self.app.replace(StoryScreen(self.app, self.on_done))

    def _the_end(self, outcome):
        screen = StoryScreen(self.app, self.on_done)
        screen._the_end(outcome)


# ---------------------------------------------------------------- dev: how did the night go?

ROWS = [
    ("How the night ends", ["Morning", "The thread ran out", "Aurel was woven in"]),
    ("Aurel's sconces", ["Every one lit", "About half", "None"]),
    ("The Still", ["Everyone home", "Some lost on the way", "Many left in the caves", "Tarn never reached them",
                   "Tarn let them stay"]),
    ("Maren", ["Opened the brake", "Took the Guild's bargain", "Caught on the stairs", "Never reached the drum"]),
    ("The first morning", ["A long day", "Until noon", "Barely a morning"]),
]
PERFECT = [0, 0, 0, 0, 0]
WORST = [0, 2, 2, 1, 2]


def outcome_for(sel, total_lamps=75):
    """A NightOutcome from the picker's choices."""
    state = ["morning", "endless", "woven"][sel[0]]
    lit = [total_lamps, total_lamps // 2, 0][sel[1]]
    saved, total, below, done, choice_t = [(12, 12, 0, True, "through"), (9, 12, 0, True, "through"),
                                           (4, 4, 8, False, "through"), (0, 0, 12, False, "through"),
                                           (12, 12, 0, True, "stay")][sel[2]]
    choice, failed = [("released", False), ("bargain", False), (None, True), (None, False)][sel[3]]
    day = [11 * 60, 6 * 60, 20][sel[4]]
    strayed = int(saved * (1 - lit / total_lamps) * cp.DARK_LOSS) if state == "morning" and choice_t == "through" else 0
    return ending.NightOutcome(state=state, lamps_lit=lit, lamps_total=total_lamps, still_saved=saved,
                               still_total=total, still_below=below, still_done=done, strayed=strayed,
                               still_choice=choice_t, hoard_choice=choice,
                               released=300 if choice == "released" else 0, bargain_slack=96,
                               tick_failed=failed, day_woven=day, thread_left=day * 2)


class OutcomeScreen(Screen):
    """Dev: pick how the night went, then see its ending. Up/Down choose a row, Left/Right change it,
    P a perfect night, X the worst morning, Enter the ending, Esc the title."""

    def __init__(self, app, outcome=None, then=None):
        super().__init__(app)
        self.then = then or (lambda o: StoryReel(app)._the_end(o))
        self.sel = list(PERFECT)
        if outcome is not None:
            if outcome.hoard_choice == "bargain":
                self.sel[3] = 1
            if outcome.still_choice == "stay":
                self.sel[2] = 4
        self.row = 0
        self.t = 0.0
        self.add((CX - 160, H - 64, 320, 44), "See the ending  (Enter)", self.go, tag="go",
                 key=(pygame.K_RETURN, pygame.K_KP_ENTER))

    def go(self):
        self.then(outcome_for(self.sel))

    def update(self, dt):
        self.t += dt
        return True

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN:
            k = ev.key
            if k == pygame.K_ESCAPE:
                self.app.to_title()
            elif k in (pygame.K_UP, pygame.K_w):
                self.row = (self.row - 1) % len(ROWS)
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.row = (self.row + 1) % len(ROWS)
            elif k in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                step = -1 if k in (pygame.K_LEFT, pygame.K_a) else 1
                self.sel[self.row] = (self.sel[self.row] + step) % len(ROWS[self.row][1])
            elif k == pygame.K_p:
                self.sel = list(PERFECT)
            elif k == pygame.K_x:
                self.sel = list(WORST)
            else:
                return super().handle(ev)
            self.app.dirty = True
            return True
        return super().handle(ev)

    def draw(self, surf):
        draw_scene(surf, "three", self.t, pygame.Rect(0, 0, W, H))
        tint(surf, surf.get_rect(), (4, 2, 8), 170)
        box = pygame.Rect(110, 40, W - 220, H - 120)
        draw_panel(surf, box, fill=(24, 20, 26))
        draw_glow_text(surf, self.app.bold[32], "How did the night go?", (CX, box.y + 36), ACCENT)
        draw_text(surf, self.app.italic[18], "Dev mode: pick an outcome and see its ending.", (CX, box.y + 66), DIM,
                  center=True)
        y = box.y + 100
        for i, (name, opts) in enumerate(ROWS):
            on = i == self.row
            draw_text(surf, self.app.bold[22], name, (box.x + 40, y), ACCENT if on else TEXT)
            draw_text(surf, self.app.fonts[22], "<  %s  >" % opts[self.sel[i]], (box.right - 40, y + 2),
                      GOLD if on else DIM, right=True)
            y += 52
        o = outcome_for(self.sel)
        verdict = "a perfect night" if o.perfect else ("morning" if o.morning else "no morning")
        draw_text(surf, self.app.bold[22], "This makes %s." % verdict, (CX, box.bottom - 96), GOLD, center=True)
        draw_text(surf, self.app.italic[18], "Up/Down choose   Left/Right change   P perfect   X worst",
                  (CX, box.bottom - 62), DIM, center=True)
        draw_text(surf, self.app.italic[18], "Enter the ending   Esc title", (CX, box.bottom - 38), DIM, center=True)
        self.draw_buttons(surf)
