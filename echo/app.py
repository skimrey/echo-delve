"""The application shell: window, screen stack and the flow between screens."""

import os
import sys

import pygame

from .run import Meta, Run
from .theme import load_fonts
from .game_screen import GameScreen
from .menus import (EndScreen, ForgeScreen, HelpScreen, PauseScreen, TitleScreen, UpgradeScreen)
from .unravel_screen import UnravelScreen
from .cinematics import IntroScreen, VictoryScreen

DEFAULT_META = os.path.join(os.path.expanduser("~"), ".echo_delve", "meta.json")
SIZE = (960, 660)


class App:
    def __init__(self, size=SIZE, meta_path=None, seed=None, game="echo", dev=False):
        pygame.init()
        self.dev = dev or os.environ.get("ECHO_DEV") == "1"      # dev mode: see echo/dev.py, docs/dev.md
        self.dev_help = False
        pygame.font.init()
        self.size = size
        self.game = game                  # "echo", a sister prototype ("stillwater", "tick"), or "night"
        self.campaign = None              # The Long Night in progress (game == "night")
        self.surface = pygame.display.set_mode(size)
        pygame.display.set_caption({"echo": "Echo Delve", "stillwater": "Stillwater (prototype)",
                                    "tick": "The Tick (prototype)", "night": "The Long Night"}.get(game, "Echo Delve"))
        styles = load_fonts()
        self.fonts, self.bold, self.italic = styles["regular"], styles["bold"], styles["italic"]
        self.time = 0.0                   # seconds since start: drives flicker and idle animation
        self.meta = Meta(meta_path)
        self.seed = seed
        self.run = None
        self.recorded = False
        self.running = True
        self.dirty = True
        self.stack = [self.title_screen()]
        self.thread = pygame.time.Clock()

    # -- screen stack
    @property
    def screen(self):
        return self.stack[-1]

    def push(self, screen):
        self.stack.append(screen)
        self.dirty = True

    def pop(self):
        if len(self.stack) > 1:
            self.stack.pop()
        self.dirty = True

    def replace(self, screen):
        self.stack = [screen]
        self.dirty = True

    # -- flow
    def quit(self):
        self.running = False

    def title_screen(self):
        if self.game == "echo":
            return TitleScreen(self)
        if self.game == "night":
            from .night_screen import NightTitle
            return NightTitle(self)
        from .sisters.common import ProtoTitle
        if self.game == "stillwater":
            from .sisters import stillwater as sw
            from .sisters.still_screen import RULES, StillScreen
            return ProtoTitle(self, sw.TITLE, sw.TAGLINE, "pool_glow",
                              lambda: self.play_sister(sw.INTRO, lambda: StillScreen(self)),
                              lambda: self.replace(IntroScreen(self, self.to_title, sw.INTRO)), RULES)
        if self.game == "tick":
            from .sisters import tick as tk
            from .sisters.tick_screen import RULES, TickScreen
            return ProtoTitle(self, tk.TITLE, tk.TAGLINE, "tick_halls",
                              lambda: self.play_sister(tk.INTRO, lambda: TickScreen(self)),
                              lambda: self.replace(IntroScreen(self, self.to_title, tk.INTRO)), RULES)
        raise ValueError("unknown game %r" % self.game)

    # -- The Long Night
    def night_story(self):
        """The whole story, front to back, with the Drum Room's choice (see story_reel.py)."""
        from .story_reel import StoryReel
        StoryReel(self).start()

    def dev_endings(self):
        """Dev: pick how a night went, and see its ending."""
        from .story_reel import OutcomeScreen
        self.replace(OutcomeScreen(self))

    def begin_night(self):
        """Build the night (every level), then ask how much thread is left."""
        from .campaign import Campaign
        from .night_screen import LengthScreen, LoadingScreen
        perks = dict(self.meta.data["perks"])
        self.replace(LoadingScreen(self, lambda: Campaign(self.seed, perks=perks),
                                   lambda c: self.replace(LengthScreen(self, c))))

    def cut_thread(self, campaign, length):
        campaign.set_length(length)
        self._night_ready(campaign)

    def _night_ready(self, campaign):
        from . import campaign as cp
        self.campaign = campaign
        if not self.meta.data.get("seen_intro_night"):
            def begin():
                self.meta.data["seen_intro_night"] = True
                self.meta.save()
                self.to_night()
            self.replace(IntroScreen(self, begin, cp.INTRO))
        else:
            self.to_night()

    def to_night(self):
        """Back to the hub, or (once the night is over) to its ending: a scene for each of the three,
        then the epilogue."""
        from . import campaign as cp
        from .night_screen import EpilogueScreen, NightScreen
        from .sisters.common import Card
        c = self.campaign
        c.check_thread()
        if c.state != "night":
            if not c.ending_told:
                c.ending_told = True
                self.tell(c.ending_panels(), lambda: self.replace(EpilogueScreen(self)))
            else:
                self.replace(EpilogueScreen(self))
            return
        self.replace(NightScreen(self))
        if c.prologue_next is None and not c.order_told:         # the opening is over: say what order means
            c.order_told = True
            self.push(Card(self, cp.ORDER_TITLE, cp.ORDER_TEXT, "Continue  (Enter)", self.pop))

    def home(self):
        """Where a level's "leave" goes: the night's hub in The Long Night, else the title."""
        if self.campaign is not None and self.game == "night":
            self.to_night()
        else:
            self.to_title()

    def tell(self, panels, then, title=None):
        """Tell some of the story, if there is any to tell, then go on."""
        if panels:
            self.replace(IntroScreen(self, then, panels, title=title))
        else:
            then()

    def unseen(self, story_id, panels):
        """Chapters told in the games on their own: each one only the first time it comes round."""
        seen = self.meta.data["seen_scenes"]
        if not panels or story_id in seen:
            return []
        seen.append(story_id)
        self.meta.save()
        return panels

    def play_track(self, track):
        """The Long Night: play the next level of a story, telling its chapter first if one is due."""
        from . import campaign as cp
        panels = self.campaign.scenes_before(track)
        self.tell(panels, lambda: self._enter_track(track), title=cp.HEROES[track])

    def _enter_track(self, track):
        c = self.campaign
        if track == "echo":
            self.run = c.echo
            self.recorded = True                      # the night keeps its own record
            self.replace(GameScreen(self))
        elif track == "still":
            from .sisters.still_screen import StillScreen
            self.replace(StillScreen(self, c.still))
        else:
            from .sisters.tick_screen import TickScreen
            self.replace(TickScreen(self, c.tick))

    def in_night(self):
        return self.campaign is not None and self.game == "night"

    def play_sister(self, intro, make_screen):
        """Play a sister prototype; the first time, its story comes first."""
        flag = "seen_intro_" + self.game

        def begin():
            self.meta.data[flag] = True
            self.meta.save()
            self.replace(make_screen())
        if not self.meta.data.get(flag):
            self.replace(IntroScreen(self, begin, intro))
        else:
            begin()

    def to_title(self):
        self.replace(self.title_screen())

    def show_help(self):
        self.push(HelpScreen(self))

    def show_forge(self):
        self.replace(ForgeScreen(self))

    def pause(self):
        self.push(PauseScreen(self))

    def start_new_run(self):
        """New Run from the menus: the first time, the story comes first."""
        if not self.meta.data.get("seen_intro"):
            self.replace(IntroScreen(self, self._intro_then_run))
        else:
            self.new_run()

    def _intro_then_run(self):
        self.meta.data["seen_intro"] = True
        self.meta.save()
        self.new_run()

    def show_story(self):
        self.replace(IntroScreen(self, self.to_title))

    def new_run(self):
        seed = self.seed
        self.run = Run(seed, perks=dict(self.meta.data["perks"]))
        self.recorded = False
        self.replace(GameScreen(self))

    def abandon_run(self):
        if self.in_night():                       # in The Long Night, "leave" goes back to the night
            self.to_night()
            return
        if self.run is not None and self.run.state in ("playing", "upgrade", "unravel"):
            self.run.state = "dead"
            self.run.reason = "You abandoned the run."
        self.end_run()

    def after_act(self):
        """Move to the screen the run state calls for."""
        st = self.run.state
        if st == "unravel":
            self.push(UnravelScreen(self, forced=True))
        elif st == "upgrade":
            self.push(VictoryScreen(self, final=False))
        elif st == "won":
            self.push(VictoryScreen(self, final=True))
        elif st == "dead":
            if self.in_night():
                self.campaign.aurel_woven()
                self.to_night()
            else:
                self.end_run()

    def after_victory(self):
        """The floor's victory scene is over: pick an upgrade, or (last floor) see the ending."""
        if self.run.state == "upgrade":
            self.replace(UpgradeScreen(self))
        elif self.in_night():
            self.campaign.thread_tied()
            self.to_night()
        else:
            self.end_run()

    def open_unravel(self):
        """Voluntary unravel from the game screen (the run must allow it)."""
        self.push(UnravelScreen(self, forced=False))

    def finish_unravel(self, script):
        """run.unravel() succeeded: drop the picker and let the game screen start the new loop."""
        self.pop()
        self.screen.after_unravel(script)

    def choose_upgrade(self, key):
        from . import story
        self.run.apply_upgrade(key)
        if self.in_night():
            self.to_night()
        else:
            n = self.run.floor_no
            self.tell(self.unseen("echo:%d" % n, story.INTERLUDES.get(n)), lambda: self.replace(GameScreen(self)),
                      title="Aurel")

    def end_run(self):
        if not self.recorded:
            self.meta.record(self.run)
            self.recorded = True
        self.replace(EndScreen(self))

    # -- loop
    def handle(self, ev):
        if ev.type == pygame.QUIT:
            self.running = False
            return
        if self.dev and ev.type == pygame.KEYDOWN:
            from . import dev
            if ev.key in dev.KEYS and dev.handle(self, ev.key):
                return
        self.screen.handle(ev)

    def tick(self, dt):
        self.time += dt
        if self.screen.update(dt):
            self.dirty = True

    def draw(self):
        self.screen.draw(self.surface)
        if self.dev:
            from . import dev
            dev.draw_overlay(self, self.surface)
        self.dirty = False

    def screenshot(self, path):
        self.draw()
        pygame.image.save(self.surface, path)

    def loop(self):
        while self.running:
            for ev in pygame.event.get():
                self.handle(ev)
            self.tick(self.thread.tick(30) / 1000.0)
            if self.dirty:
                self.draw()
                pygame.display.flip()
        pygame.quit()


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    seed, game, dev = None, "echo", False
    for a in argv:
        if a.startswith("--seed="):
            seed = int(a.split("=", 1)[1])
        elif a.startswith("--game="):            # stillwater | tick | night (The Long Night)
            game = a.split("=", 1)[1]
        elif a == "--dev":                       # dev mode: keys to finish levels, the endings picker
            dev = True
    App(meta_path=DEFAULT_META, seed=seed, game=game, dev=dev).loop()


if __name__ == "__main__":
    main()
