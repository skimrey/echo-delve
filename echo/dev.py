"""Dev mode: test any part of the games without playing to it. Run with --dev (or ECHO_DEV=1).

Keys (see docs/dev.md):
  F1   show or hide these keys
  F9   finish this level: a clean clear, at par (the turns par would have cost are spent)
  F10  finish it perfectly: every sconce lit / everyone in the chamber saved / no hoard spent
  F11  fail it: Aurel's thread runs out / an eel finds Tarn / a warden sees Maren
  F12  (The Long Night's hub) skip ahead: the opening told, and all three at their last level
  F5 / F6  (The Long Night's hub) lengthen / shorten the thread by an hour
The Long Night's title also gets "Endings (dev)": pick how the night went and see its ending, and the
Story asks the same before its ending.
"""

import pygame

KEYS = (pygame.K_F1, pygame.K_F5, pygame.K_F6, pygame.K_F9, pygame.K_F10, pygame.K_F11, pygame.K_F12)
HELP = ["DEV MODE", "F9  finish this level (at par)", "F10  finish it perfectly", "F11  fail it",
        "F12  hub: skip to the last levels", "F5 / F6  hub: thread +1h / -1h", "F1  hide this"]


def handle(app, key):
    """Handle a dev key; True if it did something."""
    if key == pygame.K_F1:
        app.dev_help = not app.dev_help
        app.dirty = True
        return True
    name = type(app.screen).__name__
    fn = {"GameScreen": _echo, "StillScreen": _still, "TickScreen": _tick, "NightScreen": _hub}.get(name)
    if fn is None:
        return False
    fn(app, key)
    app.dirty = True
    return True


# ---------------------------------------------------------------- Echo Delve

def _echo(app, key):
    run = app.run
    if run.state != "playing" or key not in (pygame.K_F9, pygame.K_F10, pygame.K_F11):
        return
    if key == pygame.K_F11:
        run.state = "dead"
        run.reason = "The thread ran out (dev)."
        app.after_act()
        return
    if key == pygame.K_F10:
        run.lit = set(run.torches)
    par = run.par_for(len(run.lit)) or run.par or 0
    extra = max(0, par - run.play.turns_spent)
    if run.thread is not None:
        run.thread.spend(extra)
    run.play.turns_spent += extra
    run.play.status = "cleared"
    run._floor_cleared()
    app.after_act()


# ---------------------------------------------------------------- Stillwater

def _still(app, key):
    from .sisters import stillwater as sw
    scr = app.screen
    sim = scr.sim
    if sim.over or scr.intro or key not in (pygame.K_F9, pygame.K_F10, pygame.K_F11):
        return
    if key == pygame.K_F11:
        sim.over = "caught"
        scr.say("An eel finds you (dev). B steps back; R tries the chamber again.")
        return
    par = sw.walkthrough(scr.level, light=sim.light).turn
    if scr.run.spend(max(0, par - sim.turn), sim.light):
        scr._dawn()
        return
    for k in sim.kin:
        if k.state == "following" or (key == pygame.K_F10 and k.state == "stranded"):
            k.state = "saved"
        elif k.state == "stranded":
            k.state = "lost"
    sim.over = "out"
    scr._chamber_done()


# ---------------------------------------------------------------- The Tick

def _tick(app, key):
    from .sisters import tick as tk
    scr = app.screen
    sim = scr.sim
    if sim.over or scr.intro or key not in (pygame.K_F9, pygame.K_F10, pygame.K_F11):
        return
    if key == pygame.K_F11:
        sim.over = "caught"
        scr.say("A warden's lantern finds you (dev). R tries the floor again.")
        return
    plan = tk.solve(scr.level, has_watch=sim.has_watch) or []
    moves = sum(1 for a in plan if a[0] != "r")
    if key == pygame.K_F9:
        cost = min(scr.level.min_cost or 0, sim.hoard)
        sim.hoard -= cost
        sim.spent += cost
    if scr.run.thread is not None:
        scr.run.thread.spend(max(0, moves - sim.t))
    sim.over = "out"
    scr._floor_done()


# ---------------------------------------------------------------- The Long Night's hub

def _hub(app, key):
    from . import campaign as cp
    c = app.campaign
    if key == pygame.K_F5:
        c.thread.give(60)
    elif key == pygame.K_F6:
        c.thread.spend(60)
    elif key == pygame.K_F12:
        c.told |= {("echo", "prologue"), ("tick", "prologue"), ("still", "prologue")}
        c.order_told = True
        if c.echo.state == "playing" and not c.echo.last_floor:
            c.echo.cleared = len(cp.ECHO_FLOORS) - 1
            c.echo.floor_no = cp.ECHO_FLOORS[-1]
            c.echo.start_floor()
        if c.tick.state == "playing":
            c.tick.index = c.tick.floors - 1
            c.tick._pending = None
            c.tick._level = c.tick._build(c.tick.index)
        if c.still.state == "playing":
            c.still.index = c.still.chambers - 1
            c.still.chamber = c.still._build(c.still.index)
    else:
        return
    app.to_night()


def draw_overlay(app, surf):
    """A small DEV badge (and, with F1, the keys)."""
    font = app.fonts[16]
    lines = HELP if app.dev_help else ["DEV  (F1 keys)"]
    w = max(font.size(s)[0] for s in lines) + 16
    h = len(lines) * 18 + 8
    box = pygame.Surface((w, h), pygame.SRCALPHA)
    box.fill((10, 8, 12, 200))
    surf.blit(box, (surf.get_width() - w - 4, surf.get_height() - h - 56))
    for i, s in enumerate(lines):
        img = font.render(s, True, (255, 160, 120) if i == 0 else (220, 210, 200))
        surf.blit(img, (surf.get_width() - w + 4, surf.get_height() - h - 52 + i * 18))
