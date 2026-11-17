"""The application shell: window, screen stack and the flow between screens."""

import os
import sys

import pygame

from .run import Meta, Run
from .game_screen import GameScreen
from .menus import (EndScreen, ForgeScreen, HelpScreen, PauseScreen, TitleScreen, UpgradeScreen)

DEFAULT_META = os.path.join(os.path.expanduser("~"), ".echo_delve", "meta.json")
SIZE = (960, 660)


class App:
    def __init__(self, size=SIZE, meta_path=None, seed=None):
        pygame.init()
        pygame.font.init()
        self.size = size
        self.surface = pygame.display.set_mode(size)
        pygame.display.set_caption("Echo Delve")
        self.fonts = {s: pygame.font.Font(None, s) for s in (16, 18, 22, 26, 32, 44, 80)}
        self.meta = Meta(meta_path)
        self.seed = seed
        self.run = None
        self.recorded = False
        self.running = True
        self.dirty = True
        self.stack = [TitleScreen(self)]
        self.clock = pygame.time.Clock()

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

    def to_title(self):
        self.replace(TitleScreen(self))

    def show_help(self):
        self.push(HelpScreen(self))

    def show_forge(self):
        self.replace(ForgeScreen(self))

    def pause(self):
        self.push(PauseScreen(self))

    def new_run(self):
        seed = self.seed
        self.run = Run(seed, perks=dict(self.meta.data["perks"]))
        self.recorded = False
        self.replace(GameScreen(self))

    def abandon_run(self):
        if self.run is not None and self.run.state in ("playing", "upgrade"):
            self.run.state = "dead"
            self.run.reason = "You abandoned the run."
        self.end_run()

    def after_act(self):
        """Move to the screen the run state calls for."""
        st = self.run.state
        if st == "upgrade":
            self.replace(UpgradeScreen(self))
        elif st in ("dead", "won"):
            self.end_run()

    def choose_upgrade(self, key):
        self.run.apply_upgrade(key)
        self.replace(GameScreen(self))

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
        self.screen.handle(ev)

    def tick(self, dt):
        if self.screen.update(dt):
            self.dirty = True

    def draw(self):
        self.screen.draw(self.surface)
        self.dirty = False

    def screenshot(self, path):
        self.draw()
        pygame.image.save(self.surface, path)

    def loop(self):
        while self.running:
            for ev in pygame.event.get():
                self.handle(ev)
            self.tick(self.clock.tick(30) / 1000.0)
            if self.dirty:
                self.draw()
                pygame.display.flip()
        pygame.quit()


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    seed = None
    for a in argv:
        if a.startswith("--seed="):
            seed = int(a.split("=", 1)[1])
    App(meta_path=DEFAULT_META, seed=seed).loop()


if __name__ == "__main__":
    main()
