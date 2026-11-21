"""Tunable constants for Echo Delve."""

GRID_W, GRID_H = 40, 24
TILE = 24
MAX_FLOOR = 10

BASE_HP = 10
BASE_ATK = 2
BASE_SLOTS = 4          # echoes you may leave behind on one floor
SLOT_CAP = 7
BASE_SIGHT = 7
BASE_GHOST_HP = 0        # echoes have your max HP plus this bonus
BASE_THREADS = 2         # unravelling an echo costs one thread; a run starts with this many
THREADS_PER_FLOOR = 1    # ...and earns this many per floor cleared (unused threads carry over)
POTION_HEAL = 3

DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]
WAKE = 6                # path distance at which a sleeping enemy notices someone
CHASE = 16              # an awake enemy only chases targets this close (path distance)

# spikes are up for 2 turns, down for 2 turns; each spike has a phase 0/1
SPIKE_HALF = 2

# kind: hp, damage, acts every N turns, archer range / cooldown
ENEMIES = {
    "crawler": dict(hp=2, dmg=1, period=1, rng=0, cd=0, name="Crawler"),
    "archer": dict(hp=2, dmg=1, period=1, rng=5, cd=2, name="Archer"),
    "brute": dict(hp=4, dmg=2, period=2, rng=0, cd=0, name="Brute"),
    "warden": dict(hp=9, dmg=2, period=1, rng=0, cd=0, name="Warden"),
}

# what bars the way on each floor, in order from the entrance:
#   plate: a door that is open while something stands on its plate (an echo must hold it)
#   lever: a gate that flips each time its lever is pulled; the lever is far from the gate, too far
#          to pull it and still reach the stairs in one loop, so an echo must pull it in time
LOCKS_PER_FLOOR = [
    ("plate",),
    ("plate", "plate"),
    ("lever",),
    ("plate", "lever"),
    ("plate", "plate"),
    ("lever", "plate"),
    ("plate", "lever", "plate"),
    ("plate", "lever", "lever"),
    ("plate", "plate", "lever"),
    ("plate", "lever", "plate"),
]
LEVER_MIN_DIST = 16      # a lever's walking distance from its gate, at least
LEVER_SLACK = 12         # lever floors: turns per loop beyond the longest loop of the par solution

# colour AND number identify a door/plate pair (never colour alone)
PAIR_COLORS = [(238, 132, 72), (92, 172, 244), (126, 214, 126), (222, 104, 204)]
# colour AND letter identify a gate/lever pair
LEVER_COLORS = [(96, 222, 200), (236, 226, 120), (240, 150, 150)]
GHOST_COLORS = [(150, 230, 255), (190, 160, 255), (255, 190, 150), (160, 255, 190),
                (255, 160, 200), (230, 230, 150), (150, 190, 255), (255, 225, 170)]

# in-run upgrades offered after each floor
UPGRADES = {
    "hp": ("Tough Hide", "+2 max HP (and heal 2)."),
    "atk": ("Sharper Edge", "+1 attack damage."),
    "slot": ("Echo Well", "+1 echo slot: one more loop on every floor."),
    "time": ("Slow Hours", "+12 turns before each loop collapses."),
    "sight": ("Owl Eyes", "+2 sight radius."),
    "guard": ("Stalwart Echoes", "Your echoes get +2 HP on top of yours."),
}

# permanent perks bought with shards in the Echo Forge: key -> (name, description, max level, base cost)
PERKS = {
    "hp": ("Hardy Start", "+1 max HP per level.", 4, 3),
    "slots": ("Deep Well", "+1 echo slot per level.", 2, 6),
    "time": ("Long Day", "+8 turns per loop per level.", 3, 4),
    "atk": ("Whetstone", "+1 attack at level 1.", 1, 8),
}
LAMP_REACH = 2.3        # Aurel lights a sconce from this close (in tiles), if nothing solid is in between
