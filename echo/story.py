"""The story of Echo Delve. All narrative text lives here, so the plot can be rewritten without
touching the game code. Echo Delve is one of three stories set on the same night (see
docs/universe.md); the other two are the sister games in echo/sisters/, and all three are woven
together in The Long Night (echo/campaign.py).

AUREL'S STORY (canon)
- The Loom of Hours, at the bottom of the Deep, weaves each day and sends it up to Hollowmere
  along one golden thread, through the Spindle, a bore sealed in the rock beside the Deep's
  stair. The thread is time itself. For years the Guild of Hours wound a little off every day onto
  the drum of their great clock, thinning it; 312 days ago it snapped halfway up, while carrying a
  day. The top half whipped up to the drum (the Guild's hoard) and its broken end fell out through
  a keeper's window onto the stair's first landing; the lower half fell slack down to the Loom; the
  rest of the day burst through the Spindle's wall into the caves beside it (Stillwater).
- There is only ever one day: each night the Loom unpicks the old day and weaves the next from the
  same thread.
  If the thread is tied, the Loom takes back everything left of the old one, the Guild's hoard with
  it. The Guild of Hours, holding the last of the light, would rather keep the night.
- The lantern passes from mother to daughter. When the dark came up, the Vells' mother took it
  down to find the break and never came back. It should have gone to Maren. She had seen the
  stair; she put the lantern into her brother's hands on the doorstep, said she was sorry, and ran
  (her story: The Tick). Aurel, who was never taught, went down in her place.
- The broken end lies on the first landing. It is still wound onto the Guild's drum above, so
  every hour the Guild lets go runs down it as slack. Whoever picks it up is bound to it: when a path fails,
  it pulls them back to where they began the floor, and their steps stay behind, woven into the
  stone. Those are ECHOES. They are only ever Aurel himself.
- The thread is finite. Unravelling an echo spends it. When it runs out, its holder is woven into
  the Deep for good: a WARDEN. The loose end drifts back up to the first landing for the next one.
  The Wardens are the people who went down before Aurel, his mother last.
- The stair has KEEPER'S WINDOWS into the Spindle, cut when the Guild first began drawing the thread
  up. Through one (floor 5) Aurel sees the Still's water through the break.
- Nobody knows who made the Loom, or whether anyone did. It just is.
- Aurel's chapters (The Long Night, and Echo Delve on its own): PROLOGUE before his first floor,
  INTERLUDES before floors 5 and 10 (his sister, as he understands her now; his mother at the door).
- Hooks to the other stories: the rings seen through the keeper's window (floor 5) and the pale
  shapes falling past a window in the Unlit Deep (floor 9) are the Still (Stillwater), who escape
  through the break and slide down the Spindle into the Loom's hall; the Tick striking wrong hours
  (floor 7) is Maren spending the Guild's hours; the ending shows both.
"""

TITLE = "The Lamplighter's Son"
HERO = "Aurel Vell"
ROLE = "the lamplighter's son, carrying a lantern that was never meant for him"
TOWN = "Hollowmere"
TAGLINE = "A borrowed lantern. A broken day. Ten floors of your own footsteps."

# (illustration key, text); illustrations are drawn in cinematics.py. One idea per panel.
INTRO = [
    ("town", "Hollowmere has not seen a morning in three hundred and twelve days. Each night the dark climbs a "
             "little higher up the cellar stairs, and nobody goes down to meet it any more."),
    ("loom", "Far below the town, at the bottom of the Deep, the Loom of Hours weaves each new day and sends it up "
             "on a single golden thread. For years the Guild of Hours took a little from every day. The thread "
             "wore thin, and then it broke."),
    ("lamplighter", "The Vells are lamplighters. For as long as there has been a stair down to the Loom, one of them has "
                    "walked it every evening, lighting the sconces so that whoever had to go down to tend the thread "
                    "could find the way. Nobody has gone down in years. The Vells lit them anyway."),
    ("lamplighter", "The lantern passes from mother to daughter. When the dark came up, your mother took it down to "
                    "find the break. She did not come back."),
    ("doorstep", "It should have gone to your sister. Maren put it into your hands on the doorstep, said she was "
                 "sorry, and was gone before you could ask her what for."),
    ("binding", "No one ever taught you the stair. For a long time you waited for someone else to go down it. Then "
                "you stopped waiting. On the first landing you found the broken end of the thread, still warm. It "
                "wound itself around your wrist, and it will not let go until the thread is whole."),
    ("echoes", "When a path fails you, the thread pulls you back to where you began, and your footsteps stay "
               "behind in the dark. Soon there are figures walking beside you. Do not be afraid of them. They are "
               "your own footsteps, walking again: your echoes."),
    ("spool", "The thread is not endless. Each echo you unravel spends a little of it, and when it is gone, the Deep "
              "keeps whoever was holding it. The loose end drifts back up to the first landing, to wait for the "
              "next one."),
    ("wardens", "That is what became of the ones who went down before you. They are the Wardens now, pacing out "
                "their last steps forever. One of them carries your mother's lantern."),
    ("descent", "The stair winds down beside the Spindle, ten floors, to the hall where the other end lies slack. "
                "Light the sconces as you go. Tie the thread, and bring the morning home."),
]

# The Long Night: the world has already been told, so Aurel's own chapter begins at the door.
PROLOGUE = [
    INTRO[2],
    INTRO[3],
    INTRO[4],
    ("binding", "No one ever taught you the stair. For a long time you waited for someone else to go down it. Then "
                "you stopped waiting. On the first landing the broken end of the thread found your wrist, and held "
                "on. When a path fails you, it pulls you back, and your footsteps stay behind in the dark, walking "
                "beside you. Do not be afraid of them. They are your own."),
    ("descent", "The other end lies slack at the bottom, beside the Loom. Light the sconces as you go down. Someone "
                "may need them, to find the way back up."),
]

# told before a floor (by its number), in Echo Delve and in The Long Night
INTERLUDES = {
    5: [
        ("rest", "Halfway down, you sit on a step to rest. Your echoes sit too, a little way off, the way Maren used "
                 "to when she was angry and didn't want you to know."),
        ("rest", "You used to think she ran because she was a coward. Down here you understand it better. You are "
                 "afraid all the time. You go on anyway, because someone has to carry the lantern, and she gave it "
                 "to you."),
    ],
    10: [
        ("loom_door", "The stair ends. Below is a hall full of a low golden hum, and at its door a Warden walks the "
                      "same few steps, back and forth, back and forth. She is carrying your mother's lantern."),
        ("loom_door", "You know what the thread does to the ones who run out of it. If it runs out here, you will walk "
                      "beside her forever. You lift the lantern she never meant for you, and go down."),
    ],
}

# per floor: (name, on arrival, on clearing)
FLOORS = [
    ("The Lamplighter's Stair",
     "The first sconces are cold. Your mother's chalk marks still point the way down.",
     "Your echo fades, its work done. The thread tugs you deeper."),
    ("The Flooded Chapel",
     "Water drips from the pews of a chapel nobody remembers building.",
     "The chapel bell rings once, though no one is there to touch it."),
    ("The Winch House",
     "Old gate-winches crouch in the dark, their chains gone slack. A lever swings its gate open; a second pull "
     "swings it shut again.",
     "The winches groan and settle. You are learning to be in two places at once."),
    ("The Ossuary",
     "Bones line the walls, set with care. Something down here still keeps order.",
     "You leave a candle burning for whoever these were."),
    ("The Cistern of Echoes",
     "A keeper's window, barred, looks from the stair into the Spindle. Through the break in its far wall you can "
     "see black water, and rings of light spreading on it, and fading. Something in there is awake.",
     "The rings follow you a little way along the wall, and then they stop."),
    ("The Lantern Works",
     "Your mother's tools hang by the door, cleaned and put away. She was here.",
     "You take her spare wick. It still smells of home."),
    ("The Clockwork Vaults",
     "Gears the size of houses turn without a sound, counting hours that never come.",
     "The great gears lurch one notch forward. Far above you, the Tick strikes an hour it should not."),
    ("The Hall of Wardens",
     "Grey figures stand in the alcoves, still as stone. One is the baker who went down after your mother.",
     "None of them turn to watch you go. You are not sure that is a mercy."),
    ("The Unlit Deep",
     "No sconce here has ever been lit. Beyond a keeper's window, something pale drops past in the dark of the "
     "Spindle, and then another.",
     "Below you, something golden hums. The Loom is close."),
    ("The Loom of Hours",
     "The Loom stands silent in its hall, its golden warp gone slack. Nobody knows who made it, or whether "
     "anyone did. A Warden walks before it, carrying your mother's lantern.",
     "You tie the thread."),
]

ENDING_TITLE_WON = "MORNING"
ENDING_TITLE_LOST = "THE THREAD RUNS OUT"
ENDING_WON = [
    "The Loom shudders, then sings. For the first time in three hundred and twelve days, the bells of "
    "Hollowmere ring for morning. Maren is waiting at the top of the stairs.",
    "Your echoes unravel into light, and so do the Wardens. On the last stair your mother sets down her "
    "lantern and smiles. Pale strangers who slid down the Spindle in the night stand blinking at the Loom's "
    "light, and then at you. You lead them up the stair you lit.",
]
ENDING_LOST = ("The Deep weaves you in: a Warden now, walking your last steps forever. The loose end "
               "drifts back up to the first landing, waiting for whoever comes down next.")

REWIND_LINE = "The thread pulls you back. Echo %d stays behind."

ENEMY_LORE = {
    "crawler": "Gloam-born. Chases anything warm.",
    "archer": "A drowned chapel guard. Shoots along rows and columns.",
    "brute": "Stone grown heavy in the dark. Hits hard every other turn.",
    "warden": "Held the thread before you, until it ran out. Now it guards the stairs.",
}


# The Long Night (and the Story): if Tarn has brought the Still down the Spindle before Aurel reaches the Loom
LOOM_WITH_STILL = [
    ("loom_door_still", "The stair ends. Below is a hall full of a low golden hum, and at its door a Warden walks the "
                        "same few steps, back and forth, back and forth. She is carrying your mother's lantern."),
    ("meeting", "You are not alone down here. At the edge of the light, pale people sit close together: strangers "
                "who came down the Spindle in the dark. They look at your lantern as if they have never seen one. "
                "Then one of them reaches out, very slowly, and touches your hand, the way you might touch water."),
    ("loom_door_still", "You know what the thread does to the ones who run out of it. If it runs out here, you will "
                        "walk beside her forever, and they will sit in the dark. You lift the lantern she never "
                        "meant for you, and go down."),
]

# The Long Night: if the Still have already gone through the break when Aurel reaches the window
STILL_GONE_ARRIVAL = ("A keeper's window, barred, looks from the stair into the Spindle. Through the break in its "
                      "far wall: black water, quite still. Whoever was stirring it has gone.")


def floor_name(n):
    return FLOORS[(n - 1) % len(FLOORS)][0]


def floor_arrival(n):
    return FLOORS[(n - 1) % len(FLOORS)][1]


def floor_cleared(n):
    return FLOORS[(n - 1) % len(FLOORS)][2]
