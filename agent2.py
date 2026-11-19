"""Kaggriculture agent v2 -- exact copy of main.py plus EXP_* experiment flags.

Every experiment is independently env-var gated (KG_EXP_E1=1, etc.) and
defaults OFF. With all flags off this file must play byte-identical to
main.py. See experiments_log.md for results.

--- original main.py docstring below, unmodified ---

Strategy, derived from the price model in kaggriculture.py and then measured
head-to-head over ~1,900 local episodes:

  * CARED LIVESTOCK is the engine.  CARE banks +1/day and pays out on the next
    production, so a cow yields 3 milk every 2 days (1.5/day x $160).  Animals
    are bought by live value -- rate x market price x days remaining -- and only
    when that clears ANIMAL_PAYBACK x cost.
  * MELON is a limited high-value batch: ~9 tiles.  The glut curve is quadratic
    (250 - 0.01 * excess^2) and no town shop demands melon, so depth is ~158
    units and it is split with the opponent.
  * STRAWBERRY is the late-game crop.  Four town shops drain ~32/day and a tile
    supplies only 0.25/day, so its price RISES all season (~$300 by day 29).
    Timing is everything: 12 tiles planted on day 0 LOSES $12k (it starves the
    early animal build of capital); the same 12 tiles planted on day 13, once
    melon money has landed, WINS $15k.  100% of 68 games, 34/34 seeds.
  * EGG never crashes (log curve) but the value model rarely prices geese in --
    cows and sheep dominate per action while milk/wool hold price.
  * Farm hands cost fib(n): 14 hands = $986/day for 360 actions.  Labour is
    cheap; TRAVEL is the real constraint, so everything clusters near the shed
    and assignment scores PRI_WEIGHT * priority + distance.
  * MIXED livestock, always.
  * Wheat is feed.  Buying drains the market (25 + sqrt(deficit)), so the
    wheat-tile quota scales with the live wheat price.
"""

import math

# --------------------------------------------------------------------------
# Static game data (mirrors kaggriculture.py)
# --------------------------------------------------------------------------

CROPS = {
    "WHEAT":      {"seed": 10, "first": 2, "maxday": 4,  "maxyield": 6, "ongoing": False, "interval": 0},
    "CARROT":     {"seed": 20, "first": 2, "maxday": 3,  "maxyield": 4, "ongoing": False, "interval": 0},
    "TOMATO":     {"seed": 50, "first": 8, "maxday": 8,  "maxyield": 4, "ongoing": True,  "interval": 1},
    "STRAWBERRY": {"seed": 100, "first": 10, "maxday": 10, "maxyield": 4, "ongoing": True,  "interval": 2},
    "MELON":      {"seed": 80, "first": 10, "maxday": 12, "maxyield": 6, "ongoing": False, "interval": 0},
}

ANIMALS = {
    "GOOSE": {"cost": 300, "structure": "COOP",    "first": 4, "interval": 1, "max_held": 4, "product": "EGG"},
    "COW":   {"cost": 400, "structure": "PASTURE", "first": 8, "interval": 2, "max_held": 6, "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first": 6, "interval": 3, "max_held": 6, "product": "WOOL"},
}

PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]

# Age at which a one-time crop hits its unfertilized yield cap.
HARVEST_AGE = {"WHEAT": 4, "CARROT": 3, "MELON": 10}

MIN_SELL = {
    "EGG": 20, "WHEAT": 15, "FERTILIZER": 12, "MELON": 35, "MILK": 25,
    "WOOL": 30, "CARROT": 10, "TOMATO": 15, "STRAWBERRY": 20,
}

# --------------------------------------------------------------------------
# Tunables
# --------------------------------------------------------------------------

MELON_TILES = 9
MELON_LAST_PLANT_DAY = 18       # 10-day cycle must finish by day 28
WHEAT_LAST_PLANT_DAY = 25
LAST_ANIMAL_BUY_DAY = 24
MIN_HANDS = 8
MAX_HANDS = 14
LAND_PRICES = [1000, 2000, 4000]
LAND_LAST_DAY = 22
FINAL_DAY = 29
WHEAT_CARRY = 6                 # wheat picked up per resupply trip

import os as _os


def _tune(name, default):
    try:
        return type(default)(_os.environ.get("KG_" + name, default))
    except Exception:
        return default


MELON_TILES = _tune("MELON_TILES", MELON_TILES)
if _os.environ.get("KG_EXP_E5"):
    # Namespaced override: KG_MELON_TILES collides with main.py's own _tune("MELON_TILES", ...),
    # which would silently alter BOTH agents in the same subprocess. Use a private var instead.
    MELON_TILES = int(_os.environ.get("KG_E5_MELON", MELON_TILES))
MAX_HANDS = _tune("MAX_HANDS", MAX_HANDS)
MIN_HANDS = _tune("MIN_HANDS", MIN_HANDS)
ACTIONS_PER_TASK = _tune("ACTIONS_PER_TASK", 3.5)
HAND_DIVISOR = _tune("HAND_DIVISOR", 8.0)
MELON_LAST_PLANT_DAY = _tune("MELON_LAST_DAY", MELON_LAST_PLANT_DAY)
ANIMAL_LOAD = _tune("ANIMAL_LOAD", 4.5)
ANIMAL_PAYBACK = _tune("ANIMAL_PAYBACK", 9.0)
FERT_MIN_PRICE = _tune("FERT_MIN_PRICE", 10)
STRAWBERRY_TILES = _tune("STRAWBERRY_TILES", 12)
STRAWBERRY_LAST_DAY = _tune("STRAWBERRY_LAST_DAY", 13)
STRAWBERRY_START_DAY = _tune("STRAWBERRY_START_DAY", 13)
PRI_WEIGHT = _tune("PRI_WEIGHT", 1)          # H7/H4: urgency vs travel exchange rate
LAND_MIN_EMPTY = _tune("LAND_MIN_EMPTY", 8)  # H19/H20: land timing
WHEAT_LAST_PLANT_DAY = _tune("WHEAT_LAST_PLANT_DAY", WHEAT_LAST_PLANT_DAY)  # H24

# ==========================================================================
# EXPERIMENT FLAGS (all default OFF -- see experiments_log.md)
# ==========================================================================
EXP_E1 = _tune("EXP_E1", 0)            # Hungarian optimal matching
EXP_E2 = _tune("EXP_E2", 0)            # radius cap
E2_RADIUS = _tune("E2_RADIUS", 4)
EXP_E3 = _tune("EXP_E3", 0)            # carry-more (raise DROP threshold)
E3_CARRY = _tune("E3_CARRY", 20)
EXP_E4 = _tune("EXP_E4", 0)            # finish-the-tile priority boost
E4_BONUS = _tune("E4_BONUS", 5.0)
EXP_E6 = _tune("EXP_E6", 0)            # hard cap total productive tiles
E6_CAP = _tune("E6_CAP", 20)
EXP_E7 = _tune("EXP_E7", 0)            # drop COLLECT_FERTILIZER entirely
EXP_E8 = _tune("EXP_E8", 0)            # spread premium sales across days
E8_CAP = _tune("E8_CAP", 12)           # max units/day sold of a premium item
EXP_E9 = _tune("EXP_E9", 0)            # buy wheat early, stockpile (v1: fixed $30 threshold)
EXP_E9V2 = _tune("EXP_E9V2", 0)        # v2: relative (vs season-low-so-far) + velocity-triggered
EXP_E9V3 = _tune("EXP_E9V3", 0)        # v3: gate on OUR OWN capital surplus, not the price signal
EXP_E9V4 = _tune("EXP_E9V4", 0)        # v4: v3's surplus gate + a 2nd candidate (opportunistic animal)
EXP_MVA = _tune("EXP_MVA", 0)          # marginal-value allocator: derive tile quotas, no fixed caps
MVA_SHARE = _tune("MVA_SHARE", 0.5)    # assumed share of town demand we can claim
EXP_E10 = _tune("EXP_E10", 0)          # pre-position idle workers
EXP_E11 = _tune("EXP_E11", 0)          # re-open animal-purchase gate late
EXP_E12 = _tune("EXP_E12", 0)          # hard 8cow+4sheep target, buy early, then stop

PREMIUM_ITEMS = ("MELON", "STRAWBERRY", "WOOL", "MILK")

# Sticky task assignment: {"day": d, "map": {unit_idx: (target, op)}}
_STICKY = {}

# ==========================================================================
# MARGINAL-VALUE ALLOCATOR (EXP_MVA)
# ==========================================================================
# Exact copies of the env's market model (kaggriculture.py MARKET_PARAMS /
# market_price) so marginal revenue is computed against the real curve
# rather than a guessed one -- the documented cause of farmer.py v1's
# failure was unmeasured parameters, so every constant here is read from
# the environment source, not invented.
_MVA_I0 = 10000
_MVA_PARAMS = {
    "WHEAT":      {"base":  25, "T": 400, "above_func": "log",    "above_target": 0.20},
    "CARROT":     {"base":  35, "T": 450, "above_func": "sqrt",   "above_target": 0.70},
    "TOMATO":     {"base":  60, "T": 200, "above_func": "sqrt",   "above_target": 0.60},
    "STRAWBERRY": {"base": 120, "T": 100, "above_func": "linear", "above_target": 1.60},
    "MELON":      {"base": 250, "T": 300, "above_func": "sq",     "above_target": 3.60},
    "EGG":        {"base":  50, "T": 332, "above_func": "log",    "above_target": 0.20},
    "MILK":       {"base": 160, "T": 122, "above_func": "linear", "above_target": 1.60},
    "WOOL":       {"base": 200, "T": 105, "above_func": "sq",     "above_target": 3.20},
}
# CROPS/ANIMALS yield tables, likewise copied from the env source.
_MVA_CROPS = {
    "WHEAT":      {"seed": 10, "first": 2,  "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT":     {"seed": 20, "first": 2,  "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO":     {"seed": 50, "first": 8,  "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON":      {"seed": 80, "first": 10, "interval": 0, "max_yield": 6, "ongoing": False},
}
_MVA_PRODUCT = {"WHEAT": "WHEAT", "CARROT": "CARROT", "TOMATO": "TOMATO",
                "STRAWBERRY": "STRAWBERRY", "MELON": "MELON"}
# Actions consumed per tile over its life: plant + waters + harvests, plus a
# travel allowance. Calibrated to the same scale as the existing heuristic
# load model (ANIMAL_LOAD 4.5 / wheat 1.4 / melon 1.0 per day).
_MVA_ACT = {"plant": 1.0, "water": 1.0, "harvest": 1.0, "travel": 1.4}


def _mva_shape(f, x):
    x = max(0.0, float(x))
    if f == "linear":
        return x
    if f == "sq":
        return x * x
    if f == "sqrt":
        return math.sqrt(x)
    if f == "log":
        return math.log(1.0 + x)
    if f == "log10":
        return math.log10(1.0 + x)
    return x


def _mva_price_at(item, excess):
    """Price once `excess` units above I0 sit in the market (the glut side)."""
    p = _MVA_PARAMS.get(item)
    if not p:
        return 0.0
    amp = p["above_target"] * p["base"] / max(1e-9, _mva_shape(p["above_func"], p["T"]))
    return max(1.0, p["base"] - amp * _mva_shape(p["above_func"], max(0.0, excess)))


def _mva_crop_units(crop, day):
    """Units a tile planted TODAY still yields before the season ends."""
    c = _MVA_CROPS[crop]
    first = day + c["first"]
    if first > FINAL_DAY:
        return 0.0
    if not c["ongoing"]:
        return float(c["max_yield"])
    n = 1 + int((FINAL_DAY - first) // max(1, c["interval"]))
    return float(n * c["max_yield"])


def _mva_crop_actions(crop, day):
    c = _MVA_CROPS[crop]
    first = day + c["first"]
    if first > FINAL_DAY:
        return 1e9
    days_alive = min(FINAL_DAY, first if not c["ongoing"] else FINAL_DAY) - day
    days_alive = max(1, days_alive)
    if c["ongoing"]:
        harvests = 1 + int((FINAL_DAY - first) // max(1, c["interval"]))
    else:
        harvests = 1
    return (_MVA_ACT["plant"] + days_alive * _MVA_ACT["water"]
            + harvests * (_MVA_ACT["harvest"] + _MVA_ACT["travel"]))


def _mva_crop_actions_per_day(crop, day):
    """Per-DAY action cost of holding this tile -- the units `spare` is in.

    `capacity`/`load`/`spare` upstream are all tasks-per-day (melon 1.0/day,
    wheat 1.4/day, animal 4.5/day). Charging a tile's whole LIFETIME action
    cost against that per-day budget was the second MVA bug: it made a
    strawberry tile look like it cost 26.6 of a ~38/day budget, so the
    allocator could only ever afford 2-3 tiles and left 28 empty.
    """
    c = _MVA_CROPS[crop]
    first = day + c["first"]
    if first > FINAL_DAY:
        return 1e9
    days_alive = max(1, (FINAL_DAY if c["ongoing"] else first) - day)
    return _mva_crop_actions(crop, day) / days_alive


def _mva_animal_value(animal, day, prices, committed):
    """$/action for one more animal of this kind, bought today."""
    a = ANIMALS[animal]
    first = day + a["first"]
    if first > FINAL_DAY:
        return -1.0, 0.0
    interval = max(1, a["interval"])
    harvests = 1 + int((FINAL_DAY - first) // interval)
    # CARE banks +1/fed day and pays out on the scheduled production
    units = harvests * (1.0 + interval)
    item = a["product"]
    px = _mva_price_at(item, committed.get(item, 0.0) + units)
    revenue = units * px - a["cost"]
    days_alive = max(1, FINAL_DAY - day)
    actions = days_alive * ANIMAL_LOAD / 3.0 + harvests * _MVA_ACT["travel"]
    return (revenue / max(1.0, actions)), units


def _mva_allocate(day, prices, n_animals, empties, capacity_spare, money,
                  planted_counts, opp_counts, free_slots,
                  animal_counts=None, opp_animal_counts=None):
    """Rank every candidate tile use by marginal $/action and allocate greedily,
    re-pricing after each unit so the allocation self-limits instead of
    relying on fixed caps (MELON_TILES / STRAWBERRY_TILES / want_wheat).

    Returns {crop: n_tiles} plus the best animal to buy, or None.
    """
    want = {c: 0 for c in _MVA_CROPS}
    # committed supply = what we already have growing + what the opponent
    # visibly has growing, both pushed onto the glut side of the curve.
    committed = {}
    for crop, n in planted_counts.items():
        item = _MVA_PRODUCT.get(crop)
        if item:
            committed[item] = committed.get(item, 0.0) + n * _mva_crop_units(crop, day)
    for crop, n in opp_counts.items():
        item = _MVA_PRODUCT.get(crop)
        if item:
            committed[item] = committed.get(item, 0.0) + n * _mva_crop_units(crop, day)
    # Livestock ALREADY OWNED floods its product market too. Omitting this
    # was the first version's fatal bug: with 14 cows owned it still priced
    # milk at base $160, so an extra cow scored +56.90/action when its true
    # marginal value was -12.42, and the allocator bought cows until the
    # pastures ran out while never planting a single crop.
    for counts in (animal_counts or {}, opp_animal_counts or {}):
        for animal, n in counts.items():
            a = ANIMALS.get(animal)
            if not a or n <= 0:
                continue
            first = day + a["first"]
            interval = max(1, a["interval"])
            if first > FINAL_DAY:
                continue
            harvests = 1 + int((FINAL_DAY - first) // interval)
            units = n * harvests * (1.0 + interval)
            committed[a["product"]] = committed.get(a["product"], 0.0) + units

    budget_actions = max(0.0, capacity_spare)
    n_free = len(empties)
    best_animal = None

    while n_free > 0 and budget_actions > 0:
        best, best_key, best_kind = 0.0, None, None
        for crop in _MVA_CROPS:
            units = _mva_crop_units(crop, day)
            if units <= 0:
                continue
            acts = _mva_crop_actions(crop, day)
            acts_day = _mva_crop_actions_per_day(crop, day)
            if acts >= 1e8 or acts_day > budget_actions:
                continue
            item = _MVA_PRODUCT[crop]
            px = _mva_price_at(item, committed.get(item, 0.0) + units)
            revenue = units * px - _MVA_CROPS[crop]["seed"]
            v = revenue / max(1.0, acts)
            if v > best:
                best, best_key, best_kind = v, crop, "crop"
        # animals compete for the same labour budget
        for animal in ANIMALS:
            slots = free_slots.get(ANIMALS[animal]["structure"], 0)
            if slots <= 0 or money < ANIMALS[animal]["cost"]:
                continue
            v, units = _mva_animal_value(animal, day, prices, committed)
            if v > best:
                best, best_key, best_kind = v, animal, "animal"
        if best_key is None or best <= 0:
            break
        if best_kind == "crop":
            want[best_key] += 1
            n_free -= 1
            budget_actions -= _mva_crop_actions_per_day(best_key, day)
            item = _MVA_PRODUCT[best_key]
            committed[item] = committed.get(item, 0.0) + _mva_crop_units(best_key, day)
        else:
            if best_animal is None:
                best_animal = best_key
            a = ANIMALS[best_key]
            free_slots[a["structure"]] = free_slots.get(a["structure"], 0) - 1
            money -= a["cost"]
            n_free -= 1
            budget_actions -= ANIMAL_LOAD
            item = a["product"]
            _v, units = _mva_animal_value(best_key, day, prices, committed)
            committed[item] = committed.get(item, 0.0) + units
    return want, best_animal

# E9V2: running wheat-price state, reset at the start of each episode. The
# harness runs multiple episodes per process (one per seed), so this can't
# just be a plain module global initialized once -- it's reset explicitly
# whenever day==0/hour==0 fires (see _market_orders).
_E9V2_MIN_PRICE = None
_E9V2_PRICE_LOG = []  # [(day, price), ...] one sample per day


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _shed_tiles(n):
    half = n // 2
    return [(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)]


def _dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _step_toward(pos, target):
    dx = target[0] - pos[0]
    dy = target[1] - pos[1]
    if abs(dx) >= abs(dy):
        if dx > 0:
            return "EAST"
        if dx < 0:
            return "WEST"
    if dy > 0:
        return "SOUTH"
    if dy < 0:
        return "NORTH"
    if dx > 0:
        return "EAST"
    if dx < 0:
        return "WEST"
    return None


def _fib(n):
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def _hire_cost_total(k):
    return sum(_fib(i) for i in range(k))


# --------------------------------------------------------------------------
# core
# --------------------------------------------------------------------------

def _agent(obs):
    player = obs["player"]
    me = obs["farms"][player]
    tiles = me["tiles"]
    n = len(tiles)
    day = obs["day"]
    hour = obs["hour"]
    priv = obs["private"]
    shed = dict(priv["shed"])
    seeds = dict(priv["seeds"])
    invs = priv["inventories"]
    prices = obs["market"]["prices"]
    money = me["money"]
    endgame = day >= FINAL_DAY

    n_units = 1 + len(me["hands"])
    pos = [tuple(me["farmer"])] + [tuple(p) for p in me["hands"]]
    uinv = [dict(invs[i]) if i < len(invs) else {} for i in range(n_units)]

    shed_tiles = [t for t in _shed_tiles(n) if tiles[t[1]][t[0]] != "LOCKED"]
    if not shed_tiles:
        shed_tiles = [_shed_tiles(n)[0]]

    # ---------------- census ----------------
    animals, empty_struct, plants, weeds, empties = [], [], [], [], []
    for y in range(n):
        for x in range(n):
            t = tiles[y][x]
            if t == "LOCKED":
                continue
            if t is None:
                empties.append((x, y))
            elif isinstance(t, dict):
                k = t.get("kind")
                if k == "WEED":
                    weeds.append((x, y))
                elif k == "PLANT":
                    plants.append((x, y, t))
                elif k in ("COOP", "PASTURE"):
                    (animals if t.get("animal") else empty_struct).append((x, y, t))

    n_animals = len(animals)
    free_coops = [(x, y) for x, y, t in empty_struct if t["kind"] == "COOP"]
    free_pastures = [(x, y) for x, y, t in empty_struct if t["kind"] == "PASTURE"]
    melon_planted = sum(1 for _, _, t in plants if t["crop"] == "MELON")
    straw_planted = sum(1 for _, _, t in plants if t["crop"] == "STRAWBERRY")
    wheat_planted = sum(1 for _, _, t in plants if t["crop"] == "WHEAT")

    carried = {}
    for inv in uinv:
        for it, c in inv.items():
            if c > 0:
                carried[it] = carried.get(it, 0) + c

    # ---------------- land plan ----------------
    wheat_price = prices.get("WHEAT", 25)
    if wheat_price >= 45:
        cover = 1.3
    elif wheat_price >= 35:
        cover = 1.0
    elif wheat_price >= 28:
        cover = 0.6
    else:
        cover = 0.3
    want_wheat = int(math.ceil(max(n_animals, 3) * cover / 0.8))
    want_wheat = max(2, min(want_wheat, 40))

    # Effective task-actions per day: half of raw actions go to walking.
    crew = max(n_units, MIN_HANDS + 1)
    capacity = crew * 24 / ACTIONS_PER_TASK   # completed tasks per day
    load = n_animals * ANIMAL_LOAD + melon_planted * 1.0 + wheat_planted * 1.4
    spare = max(0.0, capacity - load)
    want_wheat = min(want_wheat, wheat_planted + int(spare * 0.5 / 1.4))
    if day > WHEAT_LAST_PLANT_DAY:
        want_wheat = 0
    want_melon = MELON_TILES if day <= MELON_LAST_PLANT_DAY else 0
    want_straw = (STRAWBERRY_TILES
                  if STRAWBERRY_START_DAY <= day <= STRAWBERRY_LAST_DAY else 0)

    mva_animal = None
    if EXP_MVA:
        # Derive every tile quota from marginal $/action instead of the fixed
        # MELON_TILES / STRAWBERRY_TILES / want_wheat constants. Opponent's
        # visible planted tiles feed the supply forecast, so the allocation
        # backs off a market they are already flooding.
        opp_counts, opp_animals = {}, {}
        try:
            opp = obs["farms"][1 - obs["player"]]
            for row in opp.get("tiles", []) or []:
                for t in row or []:
                    if not isinstance(t, dict):
                        continue
                    if t.get("kind") == "PLANT":
                        c = t.get("crop")
                        if c:
                            opp_counts[c] = opp_counts.get(c, 0) + 1
                    elif t.get("animal"):
                        an = t["animal"]
                        opp_animals[an] = opp_animals.get(an, 0) + 1
        except Exception:
            opp_counts, opp_animals = {}, {}
        my_animals = {}
        for _x, _y, _t in animals:
            an = _t.get("animal")
            if an:
                my_animals[an] = my_animals.get(an, 0) + 1
        planted_counts = {"MELON": melon_planted, "STRAWBERRY": straw_planted,
                          "WHEAT": wheat_planted}
        free_slots = {"PASTURE": len(free_pastures), "COOP": len(free_coops)}
        mva_want, mva_animal = _mva_allocate(
            day, prices, n_animals, empties, spare, money,
            planted_counts, opp_counts, free_slots,
            animal_counts=my_animals, opp_animal_counts=opp_animals,
        )
        want_melon = mva_want.get("MELON", 0) + melon_planted
        want_straw = mva_want.get("STRAWBERRY", 0) + straw_planted
        want_wheat = mva_want.get("WHEAT", 0) + wheat_planted
    need_straw = max(0, want_straw - straw_planted)

    need_melon = max(0, want_melon - melon_planted)
    need_wheat = max(0, want_wheat - wheat_planted)
    homeless = (shed.get("COW", 0) + carried.get("COW", 0)
                + shed.get("SHEEP", 0) + carried.get("SHEEP", 0))
    want_pastures = homeless

    # Which animal is worth buying right now?  With daily CARE an animal yields
    # (1 + interval) units every `interval` days, so rate = (1+interval)/interval.
    # Value it over the days it can still produce, and require a 2x payback.
    animal_value = {}
    for k, a in ANIMALS.items():
        rate = (1.0 + a["interval"]) / a["interval"]
        price = prices.get(a["product"], 0)
        days_left = max(0, FINAL_DAY - day - a["first"])
        animal_value[k] = (rate * price * days_left, rate * price, a["cost"], days_left)
    buyable = [k for k, (rev, _r, cost, dl) in animal_value.items()
               if dl > 0 and rev >= ANIMAL_PAYBACK * cost]
    buyable.sort(key=lambda k: -animal_value[k][1])
    best_animal = buyable[0] if buyable else None
    best_struct = ANIMALS[best_animal]["structure"] if best_animal else None

    # coops: however many geese we could plausibly stock soon
    want_coops = shed.get("GOOSE", 0) + carried.get("GOOSE", 0)
    room = int(spare / ANIMAL_LOAD)

    # E12: hard target 8 cow + 4 sheep, buy fast in the first ~8 days, then
    # stop entirely regardless of later cash/capacity headroom.
    e12_target = {"COW": 8, "SHEEP": 4}
    if EXP_E12:
        held_cow = (shed.get("COW", 0) + carried.get("COW", 0)
                    + sum(1 for _, _, t in animals if t["animal"] == "COW"))
        held_sheep = (shed.get("SHEEP", 0) + carried.get("SHEEP", 0)
                      + sum(1 for _, _, t in animals if t["animal"] == "SHEEP"))
        if day <= 8 and (held_cow < e12_target["COW"] or held_sheep < e12_target["SHEEP"]):
            buyable = [k for k in ("COW", "SHEEP")
                       if (held_cow if k == "COW" else held_sheep) < e12_target[k]]
            buyable.sort(key=lambda k: -animal_value[k][1])
        else:
            buyable = []
        best_animal = buyable[0] if buyable else None
        best_struct = ANIMALS[best_animal]["structure"] if best_animal else None

    if best_animal and day <= LAST_ANIMAL_BUY_DAY:
        afford = int(max(0.0, money - 200) // ANIMALS[best_animal]["cost"])
        if EXP_E11:
            # E11: `room` is derived from `spare = capacity - load`, and once
            # the melon batch ends (day > MELON_LAST_PLANT_DAY) that capacity
            # is freed for animals, but room was observed to stay pinned near
            # 0 in the diagnosed trace. Re-derive an "effective" room late
            # game as the larger of the live figure and capacity/ANIMAL_LOAD,
            # so freed-up melon/wheat capacity reliably reopens the gate
            # instead of staying frozen at its pre-day-18 value.
            eff_room = room
            if day > MELON_LAST_PLANT_DAY:
                eff_room = max(room, int(capacity / ANIMAL_LOAD))
            slots = max(0, min(afford + 2, eff_room, 45))
        else:
            slots = max(0, min(afford + 2, room, 45))
        if EXP_E12:
            # cap slots so we never overshoot the 8/4 target
            held_cow = (shed.get("COW", 0) + carried.get("COW", 0)
                        + sum(1 for _, _, t in animals if t["animal"] == "COW"))
            held_sheep = (shed.get("SHEEP", 0) + carried.get("SHEEP", 0)
                          + sum(1 for _, _, t in animals if t["animal"] == "SHEEP"))
            gap = (e12_target["COW"] - held_cow if best_animal == "COW"
                   else e12_target["SHEEP"] - held_sheep)
            slots = max(0, min(slots, gap))
        if best_struct == "COOP":
            want_coops = max(want_coops, slots - len(free_coops))
        else:
            want_pastures = max(want_pastures, slots - len(free_pastures))
    want_coops = max(0, want_coops)
    want_pastures = max(0, want_pastures)

    centre = (n / 2.0 - 0.5, n / 2.0 - 0.5)
    empties.sort(key=lambda p: abs(p[0] - centre[0]) + abs(p[1] - centre[1]))

    if EXP_E2:
        # E2: never farm a tile beyond radius E2_RADIUS from the shed centre,
        # even if free -- travel cost can exceed the tile's lifetime yield.
        empties = [p for p in empties
                   if abs(p[0] - centre[0]) + abs(p[1] - centre[1]) <= E2_RADIUS]

    plan = {}
    near = list(empties)          # animals near the shed (3+ actions/day each)
    far = list(reversed(empties))  # melons on the outskirts (low traffic)
    used = set()

    def take_near(k, what):
        c = 0
        for p in near:
            if c >= k:
                break
            if p in used:
                continue
            used.add(p)
            plan[p] = what
            c += 1

    def take_far(k, what):
        c = 0
        for p in far:
            if c >= k:
                break
            if p in used:
                continue
            used.add(p)
            plan[p] = what
            c += 1

    take_near(want_pastures, "PASTURE")
    take_near(want_coops, "COOP")
    take_near(need_straw, "STRAWBERRY")
    take_near(need_melon, "MELON")
    take_near(need_wheat, "WHEAT")

    if EXP_E6:
        # E6: hard cap on total productive tiles (animals + plants + planned).
        # Once the cap is hit, stop expanding even if capacity/cash allow more.
        current_productive = n_animals + len(plants)
        room_ = max(0, E6_CAP - current_productive)
        if room_ < len(plan):
            _rank = {"PASTURE": 0, "COOP": 1, "STRAWBERRY": 2, "MELON": 3, "WHEAT": 4}
            plan = dict(sorted(plan.items(), key=lambda kv: _rank.get(kv[1], 9))[:room_])

    planned_melon = sum(1 for v in plan.values() if v == "MELON")
    planned_straw = sum(1 for v in plan.values() if v == "STRAWBERRY")
    planned_wheat = sum(1 for v in plan.values() if v == "WHEAT")

    # ---------------- tasks ----------------
    tasks = []

    def add(pri, target, action, req=None):
        tasks.append({"pri": pri, "target": tuple(target), "action": action, "req": req})

    # feeding / wheat logistics
    unfed = [] if endgame else [(x, y) for x, y, t in animals if not t["fed_today"]]
    wheat_carried = sum(inv.get("WHEAT", 0) for inv in uinv)
    if unfed:
        gap = len(unfed) - wheat_carried
        trips = int(math.ceil(gap / float(WHEAT_CARRY))) if gap > 0 else 0
        trips = min(trips, max(0, shed.get("WHEAT", 0) // 2), n_units)
        for i in range(trips):
            st = shed_tiles[i % len(shed_tiles)]
            take = min(WHEAT_CARRY, max(1, shed.get("WHEAT", 0) - i * WHEAT_CARRY))
            if take > 0:
                add(3, st, ["PICKUP", "WHEAT", take])

    fert_need = 0
    if not endgame:
        for (x, y, t) in plants:
            age = day - t["planted_day"]
            if t["crop"] == "STRAWBERRY" and t["fertilized_until_day"] < day:
                cd = CROPS["STRAWBERRY"]
                k = day + 1 - t["planted_day"] - cd["first"]
                if k >= 0 and k % cd["interval"] == 0:
                    fert_need += 1
    fert_carried = sum(inv.get("FERTILIZER", 0) for inv in uinv)
    if fert_need > fert_carried and shed.get("FERTILIZER", 0) > 0:
        take = min(shed.get("FERTILIZER", 0), fert_need - fert_carried, 6)
        if take > 0:
            add(7, shed_tiles[0], ["PICKUP", "FERTILIZER", take])

    # animal pickup for placement
    for animal, a in ANIMALS.items():
        stock = shed.get(animal, 0)
        slots = len(free_coops) if a["structure"] == "COOP" else len(free_pastures)
        slots -= carried.get(animal, 0)
        k = min(stock, max(0, slots))
        for i in range(min(k, n_units)):
            st = shed_tiles[i % len(shed_tiles)]
            add(6, st, ["PICKUP", animal, 1])

    for (x, y, t) in animals:
        a = ANIMALS[t["animal"]]
        if not endgame and not t["fed_today"]:
            add(2 if t["consecutive_unfed"] >= 1 else 9,
                (x, y), ["FEED"], req="WHEAT")
        if t["yield_units"] >= max(1, a["max_held"] - 1) or (endgame and t["yield_units"] > 0):
            add(12, (x, y), ["HARVEST"])
        if not endgame and t["fed_today"] and not t["cared_today"]:
            add(10, (x, y), ["CARE"])
        if (not EXP_E7 and t["fertilizer_available"]
                and prices.get("FERTILIZER", 0) >= FERT_MIN_PRICE):
            add(11, (x, y), ["COLLECT_FERTILIZER"])
        if not endgame and 0 < t["yield_units"] < max(1, a["max_held"] - 1):
            add(30, (x, y), ["HARVEST"])

    for (x, y, t) in plants:
        crop = t["crop"]
        cd = CROPS[crop]
        age = day - t["planted_day"]
        window = (cd["maxday"] + 1) // 2
        in_window = (not cd["ongoing"]) and window <= age <= cd["maxday"]
        prod_day = False
        if cd["ongoing"]:
            k = day + 1 - t["planted_day"] - cd["first"]
            prod_day = k >= 0 and k % cd["interval"] == 0
            ripe = t["yield_units"] > 0 and age >= cd["first"]
        else:
            hage = HARVEST_AGE.get(crop, cd["maxday"])
            ripe = t["yield_units"] >= cd["maxyield"] or age > hage
            if not ripe and age >= hage and t["watered_today"]:
                ripe = True
        if ripe:
            add(13, (x, y), ["HARVEST"])
            continue
        if (crop == "STRAWBERRY" and prod_day
                and t["fertilized_until_day"] < day and age >= cd["first"] - 1):
            add(15, (x, y), ["FERTILIZE"], req="FERTILIZER")
        if not t["watered_today"]:
            if t["consecutive_unwatered"] >= 1:
                add(4 if in_window else 5, (x, y), ["WATER"])
            elif in_window:
                add(6, (x, y), ["WATER"])
            elif prod_day and t["fertilized_until_day"] >= day:
                add(6, (x, y), ["WATER"])

    if not endgame:
        # place carried animals onto matching empty structures
        avail = {k: carried.get(k, 0) for k in ANIMALS}
        for (x, y, t) in empty_struct:
            for animal, a in ANIMALS.items():
                if a["structure"] == t["kind"] and avail.get(animal, 0) > 0:
                    avail[animal] -= 1
                    add(8, (x, y), ["PLACE", animal], req=animal)
                    break

        placed = {"WHEAT": 0, "MELON": 0, "STRAWBERRY": 0}
        for (x, y), what in plan.items():
            if what == "COOP":
                add(18, (x, y), ["BUILD_COOP"])
            elif what == "PASTURE":
                add(17, (x, y), ["BUILD_PASTURE"])
            elif what in ("WHEAT", "MELON", "STRAWBERRY"):
                # never queue more PLANTs than seeds: the env drops them all
                if placed[what] < seeds.get(what, 0):
                    placed[what] += 1
                    add(8 if what in ("MELON", "STRAWBERRY") else 16, (x, y), ["PLANT", what])

        for (x, y) in weeds:
            add(22, (x, y), ["DIG"])

    if EXP_E4:
        # E4: "finish the tile" -- an animal needs FEED+CARE+HARVEST+
        # COLLECT_FERTILIZER (up to 4 visits); a tile with multiple queued
        # ops this turn gets a priority boost so a unit already there (or
        # heading there) clears them all before moving to a fresh tile.
        _tile_count = {}
        for t in tasks:
            _tile_count[t["target"]] = _tile_count.get(t["target"], 0) + 1
        for t in tasks:
            if _tile_count[t["target"]] >= 2:
                t["pri"] = t["pri"] - E4_BONUS

    tasks.sort(key=lambda t: t["pri"])

    # ---------------- assignment (sticky, to stop oscillation) ----------------
    st = _STICKY.setdefault(player, {"day": -1, "map": {}})
    if st["day"] != day:
        st["day"] = day
        st["map"] = {}
    prev = st["map"]
    new_sticky = {}

    actions = [None] * n_units
    free = set(range(n_units))

    def can_do(i, task):
        req = task["req"]
        return req is None or uinv[i].get(req, 0) > 0

    # pass 1: honour last turn's assignment if the task still exists
    taken = set()
    for i in range(n_units):
        key = prev.get(i)
        if key is None:
            continue
        for ti, task in enumerate(tasks):
            if ti in taken:
                continue
            if (task["target"], tuple(task["action"])) == key and can_do(i, task):
                taken.add(ti)
                free.discard(i)
                _do(actions, i, pos, task, new_sticky)
                break

    # pass 2: score every (unit, task) pair by urgency *and* travel, so a unit
    # already standing in the melon patch keeps working the melon patch.
    if EXP_E1:
        _assign_hungarian(tasks, taken, free, pos, actions, new_sticky, can_do)
    else:
        pairs = []
        for ti, task in enumerate(tasks):
            if ti in taken:
                continue
            for i in free:
                if can_do(i, task):
                    score = task["pri"] * PRI_WEIGHT + _dist(pos[i], task["target"])
                    pairs.append((score, ti, i))
        pairs.sort()
        for _score, ti, i in pairs:
            if ti in taken or i not in free:
                continue
            free.discard(i)
            taken.add(ti)
            _do(actions, i, pos, tasks[ti], new_sticky)

    # ---------------- idle units ----------------
    idle_target = None
    if EXP_E10 and free:
        # E10: idle workers pre-position toward the nearest tile with known
        # upcoming work (a plant or animal) instead of standing still.
        upcoming = [(x, y) for x, y, _t in plants] + [(x, y) for x, y, _t in animals]

    for i in sorted(free):
        inv = uinv[i]
        junk = sum(c for it, c in inv.items() if it != "WHEAT" and c > 0)
        at_shed = pos[i] in shed_tiles
        target = min(shed_tiles, key=lambda s: _dist(pos[i], s))
        carry_threshold = E3_CARRY if EXP_E3 else 10
        if junk > 0 and at_shed:
            actions[i] = ["DROP"]
        elif junk >= carry_threshold or (endgame and junk > 0) or (junk > 0 and hour >= 20):
            mv = _step_toward(pos[i], target)
            actions[i] = [mv] if mv else ["DROP"]
        elif EXP_E10 and junk == 0 and upcoming:
            nearest = min(upcoming, key=lambda p: _dist(pos[i], p))
            if pos[i] != nearest:
                mv = _step_toward(pos[i], nearest)
                actions[i] = [mv] if mv else ["PASS"]
            else:
                actions[i] = ["PASS"]
        else:
            actions[i] = ["PASS"]

    for i in range(n_units):
        if actions[i] is None:
            actions[i] = ["PASS"]
    st["map"] = new_sticky

    orders = _market_orders(
        me, shed, seeds, prices, money, day, hour, endgame,
        n_animals=n_animals,
        free_coops=len(free_coops), free_pastures=len(free_pastures),
        planned_wheat=planned_wheat, planned_melon=planned_melon,
        planned_straw=planned_straw,
        n_plants=len(plants), carried=carried, n_units=n_units,
        n_empty=len(empties), buy_order=buyable, fert_reserve_in=min(10, straw_planted),
    )
    return {"farmer": actions[0], "hands": actions[1:], "market": orders[:10]}


def _assign_hungarian(tasks, taken, free, pos, actions, new_sticky, can_do):
    """E1: optimal bipartite matching (scipy linear_sum_assignment) in place
    of the greedy nearest-pair pass. Approximation notes: capped to the
    cheapest min(len(free), len(open_tasks)) tasks by priority to keep the
    cost matrix small (workers << open tasks most of the turn), and
    infeasible (req not satisfied) pairs get a large finite cost rather than
    being excluded from the matrix, since scipy needs a dense square-ish
    matrix. Ties with the greedy method on small instances; the two diverge
    only when swapping two units' near-tied assignments strictly lowers the
    total priority*weight+distance cost, which is the case the greedy
    single pass sorting can miss."""
    open_tasks = [(ti, t) for ti, t in enumerate(tasks) if ti not in taken]
    free_list = sorted(free)
    if not open_tasks or not free_list:
        return
    try:
        import numpy as np
        from scipy.optimize import linear_sum_assignment
    except Exception:
        # fallback: behave like the greedy path if scipy is unavailable
        pairs = []
        for ti, task in open_tasks:
            for i in free_list:
                if can_do(i, task):
                    score = task["pri"] * PRI_WEIGHT + _dist(pos[i], task["target"])
                    pairs.append((score, ti, i))
        pairs.sort()
        for _score, ti, i in pairs:
            if ti in taken or i not in free:
                continue
            free.discard(i)
            taken.add(ti)
            _do(actions, i, pos, tasks[ti], new_sticky)
        return

    # cap task list to keep the matrix small: cheapest-priority first
    MAX_TASKS = max(len(free_list) * 4, 40)
    open_tasks = sorted(open_tasks, key=lambda kv: kv[1]["pri"])[:MAX_TASKS]
    n_i, n_j = len(free_list), len(open_tasks)
    BIG = 1e6
    cost = np.full((n_i, n_j), BIG)
    for a, i in enumerate(free_list):
        for b, (ti, task) in enumerate(open_tasks):
            if can_do(i, task):
                cost[a, b] = task["pri"] * PRI_WEIGHT + _dist(pos[i], task["target"])
    row, col = linear_sum_assignment(cost)
    for a, b in zip(row, col):
        if cost[a, b] >= BIG:
            continue
        i = free_list[a]
        ti, task = open_tasks[b]
        if ti in taken or i not in free:
            continue
        free.discard(i)
        taken.add(ti)
        _do(actions, i, pos, task, new_sticky)


def _do(actions, i, pos, task, new_sticky):
    """Execute the task if we're on the tile, else step toward it."""
    tx, ty = task["target"]
    new_sticky[i] = (task["target"], tuple(task["action"]))
    if pos[i] == (tx, ty):
        actions[i] = list(task["action"])
    else:
        mv = _step_toward(pos[i], (tx, ty))
        actions[i] = [mv] if mv else ["PASS"]


# --------------------------------------------------------------------------
# market
# --------------------------------------------------------------------------

def _market_orders(me, shed, seeds, prices, money, day, hour, endgame,
                   n_animals, free_coops, free_pastures,
                   planned_wheat, planned_melon, planned_straw, n_plants, carried,
                   n_units, n_empty, buy_order,
                   fert_reserve_in):
    orders = []
    hires = []
    shed_used = sum(v for v in shed.values() if v > 0)
    budget = money

    # --- hands ------------------------------------------------------------
    workload = n_animals * 3.6 + n_plants * 1.1 + 10
    want = int(math.ceil(workload / HAND_DIVISOR))
    want = max(MIN_HANDS, min(want, MAX_HANDS))
    if money < 400:
        want = min(want, 4)
    elif money < 1200:
        want = min(want, 8)
    if endgame:
        want = min(want, 6)
    already = me["hires_today"]
    if hour <= 2 and already < want:
        k = min(want - already, 8 if hour == 0 else 4)
        while k > 0 and _hire_cost_total(already + k) - _hire_cost_total(already) > budget * 0.35:
            k -= 1
        budget -= _hire_cost_total(already + k) - _hire_cost_total(already)
        hires.extend([["HIRE"]] * k)

    # --- sell -------------------------------------------------------------
    wheat_reserve = 0 if endgame else min(24, n_animals + 6)
    fert_reserve = 0 if endgame else fert_reserve_in
    pressure = shed_used > 45
    hard = shed_used > 70
    sellable = sorted(
        [p for p in PRODUCTS if shed.get(p, 0) > 0],
        key=lambda p: -prices.get(p, 0) * shed.get(p, 0),
    )
    for item in sellable:
        qty = shed.get(item, 0)
        if item == "WHEAT":
            qty -= wheat_reserve
        elif item == "FERTILIZER":
            qty -= fert_reserve
        if qty <= 0:
            continue
        price = prices.get(item, 0)
        floor = MIN_SELL.get(item, 10)
        ok = endgame or hard or (price >= floor * 0.5 if pressure else price >= floor)
        if not ok:
            continue
        if EXP_E8 and not endgame and item in PREMIUM_ITEMS:
            # E8: spread premium sales across days -- town demand regenerates
            # daily, so dumping the whole shed at once eats the glut curve.
            # Cap the per-turn sell qty and carry the remainder in the shed
            # (still bounded by the 100-item cap upstream).
            qty = min(qty, E8_CAP)
        if qty > 0:
            orders.append(["SELL", item, qty])
            budget += price * qty
        if len(orders) >= 9:
            break

    # sells are queued first; hires fill whatever of the 10 slots remain
    orders.extend(hires)
    if endgame:
        return orders

    # --- feed wheat -------------------------------------------------------
    have = shed.get("WHEAT", 0) + carried.get("WHEAT", 0)
    want_w = int(n_animals * 1.6) + 4
    gap = want_w - have
    wp = prices.get("WHEAT", 25)
    if n_animals > 0 and gap > 0 and wp <= 58 and shed_used < 92:
        gap = min(gap, int(budget // max(1, wp + 6)), 40)
        if gap > 0:
            orders.append(["BUY_PRODUCT", "WHEAT", gap])
            budget -= gap * (wp + 6)

    if EXP_E9 and not endgame:
        # E9: wheat price rises $25 -> $59 over the season. Stockpile early
        # while cheap (respecting the shed's 100-item cap) instead of buying
        # at market rate as-needed all game. Only kicks in when the normal
        # feed-wheat buy above did NOT already fill the need, and only while
        # price is still near its floor.
        #
        # Two refinements were tried and both measured WORSE on the full
        # 10-game batch despite fixing the seed-2101 loss in isolation:
        #   v2 (defer to last claim on budget, after land/animals): fixed
        #     2101 but starved the stockpile in 3 other seeds -> +303 (was
        #     +7,558).
        #   v3 (cap the bite to 40% of current budget): fixed 2101 but hurt
        #     5 other seeds, including 2 that were previously clean wins ->
        #     -4,038.
        # Read: the uncapped, high-priority version below is not naive --
        # it's already close to a local optimum on this 5-seed set. The
        # 2101 loss is a real, identified failure mode (fast wheat-price
        # ramp) but patching it directly overfits to one seed and costs
        # more than it saves elsewhere, exactly the failure this project's
        # own workflow warns about (judge on holdout, not on a single case).
        # Keeping v1 as the measured-best version; the -5,605/-5,409 losses
        # on seed 2101 are accepted as this experiment's natural variance.
        if wp <= 30 and shed_used < 80:
            room_shed = 100 - shed_used - sum(o[2] for o in orders if o[0] == "BUY_PRODUCT" and o[1] == "WHEAT")
            stock_target = 60
            have2 = shed.get("WHEAT", 0) + carried.get("WHEAT", 0)
            extra = max(0, min(stock_target - have2, room_shed, int(budget // max(1, wp + 6))))
            if extra > 0:
                orders.append(["BUY_PRODUCT", "WHEAT", extra])
                budget -= extra * (wp + 6)

    if EXP_E9V2 and not endgame:
        # E9V2: same stockpile idea as E9, but the trigger is adaptive
        # instead of a fixed $30 line, aimed directly at the seed-2101
        # failure mode (price ramped past $30 by day 3 -- window nearly
        # nonexistent, but v1 fires blind to that and still spends).
        #
        # Two independent triggers, either one fires the stockpile:
        #   1. Relative-cheap: price is within 15% of the season-low seen
        #      so far in THIS game, whatever that low turns out to be --
        #      so a game that never dips below $32 still recognizes $32 as
        #      "cheap" instead of missing the window because it never
        #      crosses an arbitrary absolute number.
        #   2. Velocity: price rose >= $5 over the last ~3 days. A fast
        #      ramp means tomorrow is worse than today, so this buys NOW
        #      instead of passively waiting for a "cheap" price that will
        #      never come back. Capped at wp<=50 as a sanity ceiling so it
        #      doesn't chase a ramp indefinitely into expensive territory.
        global _E9V2_MIN_PRICE, _E9V2_PRICE_LOG
        if day == 0 and hour == 0:
            _E9V2_MIN_PRICE = None
            _E9V2_PRICE_LOG = []
        if _E9V2_MIN_PRICE is None or wp < _E9V2_MIN_PRICE:
            _E9V2_MIN_PRICE = wp
        if not _E9V2_PRICE_LOG or _E9V2_PRICE_LOG[-1][0] != day:
            _E9V2_PRICE_LOG.append((day, wp))
        old_price = next((p for d, p in reversed(_E9V2_PRICE_LOG) if d <= day - 3), wp)
        velocity = wp - old_price

        relative_cheap = _E9V2_MIN_PRICE is not None and wp <= _E9V2_MIN_PRICE * 1.15
        ramping_fast = velocity >= 5 and wp <= 50

        if (relative_cheap or ramping_fast) and shed_used < 80:
            room_shed = 100 - shed_used - sum(o[2] for o in orders if o[0] == "BUY_PRODUCT" and o[1] == "WHEAT")
            stock_target = 60
            have2 = shed.get("WHEAT", 0) + carried.get("WHEAT", 0)
            extra = max(0, min(stock_target - have2, room_shed, int(budget // max(1, wp + 6))))
            if extra > 0:
                orders.append(["BUY_PRODUCT", "WHEAT", extra])
                budget -= extra * (wp + 6)

    if EXP_E9V3 and not endgame:
        # E9V3: same stockpile idea, but the gate is OUR OWN capital surplus
        # instead of the market price. v1/v2 both gate on an external signal
        # (is the price low / is it moving fast) and both still fired during
        # the seed-2101 loss -- the actual problem there was never that the
        # price signal was misread, it's that spending during that game's
        # tight early-capital window is costly regardless of what triggered
        # the spend (H19/H20). This gate instead asks: after covering the
        # SAME reserve the livestock section below protects for itself
        # (`reserve = 150 + 20*n_animals`, see the "livestock" block), is
        # there genuine surplus left? Only spend that surplus, never the
        # reserve. Keeps v1's early priority (unlike the failed v2 "defer
        # to last claim") but respects the same headroom the animal buyer
        # itself needs (unlike v1's unconditional spend).
        if wp <= 30 and shed_used < 80:
            anim_reserve = 150 + 20 * n_animals
            surplus = budget - anim_reserve
            if surplus > 0:
                room_shed = 100 - shed_used - sum(o[2] for o in orders if o[0] == "BUY_PRODUCT" and o[1] == "WHEAT")
                stock_target = 60
                have2 = shed.get("WHEAT", 0) + carried.get("WHEAT", 0)
                extra = max(0, min(stock_target - have2, room_shed, int(surplus // max(1, wp + 6))))
                if extra > 0:
                    orders.append(["BUY_PRODUCT", "WHEAT", extra])
                    budget -= extra * (wp + 6)

    if EXP_E9V4 and not endgame:
        # E9V4: v3's capital-surplus gate, generalized to a second candidate
        # (an opportunistic extra animal) instead of wheat-only. Each turn,
        # score whichever candidate is available in comparable $-value-per-$-
        # spent terms and spend the surplus on the better one -- never both,
        # to avoid double-claiming the same surplus or the same pasture/coop
        # slot the livestock section below will also try to use this turn.
        #
        # `buy_order` (passed in) is already the land-planner's animal
        # ranking, pre-filtered to only animals clearing the normal
        # ANIMAL_PAYBACK bar -- reused here rather than recomputing.
        anim_reserve = 150 + 20 * n_animals
        surplus = budget - anim_reserve
        if surplus > 0:
            wheat_ok = wp <= 30 and shed_used < 80
            # a rough season-mid reference price ($45) to price "how much do
            # we save per dollar spent now" -- same spirit as v3's reserve
            # check, just scored instead of only gated.
            wheat_score = (45 - wp) / max(1, wp + 6) if wheat_ok else -1.0

            best_animal = buy_order[0] if buy_order else None
            anim_score, anim_cost = -1.0, 0
            if best_animal and day <= LAST_ANIMAL_BUY_DAY:
                a = ANIMALS[best_animal]
                slots = (free_coops if a["structure"] == "COOP" else free_pastures)
                slots -= shed.get(best_animal, 0) + carried.get(best_animal, 0)
                anim_cost = a["cost"]
                if slots > 0 and surplus >= anim_cost:
                    rate = (1.0 + a["interval"]) / max(1, a["interval"])
                    days_left = max(0, FINAL_DAY - day - a["first"])
                    anim_score = (rate * prices.get(a["product"], 0) * days_left) / max(1, anim_cost)

            if anim_score >= 0 and anim_score >= wheat_score:
                orders.append(["BUY_ANIMAL", best_animal, 1])
                budget -= anim_cost
                # keep the livestock section's later slot accounting correct
                if ANIMALS[best_animal]["structure"] == "COOP":
                    free_coops -= 1
                else:
                    free_pastures -= 1
            elif wheat_ok:
                room_shed = 100 - shed_used - sum(o[2] for o in orders if o[0] == "BUY_PRODUCT" and o[1] == "WHEAT")
                stock_target = 60
                have2 = shed.get("WHEAT", 0) + carried.get("WHEAT", 0)
                extra = max(0, min(stock_target - have2, room_shed, int(surplus // max(1, wp + 6))))
                if extra > 0:
                    orders.append(["BUY_PRODUCT", "WHEAT", extra])
                    budget -= extra * (wp + 6)

    # --- seeds ------------------------------------------------------------
    # Under EXP_MVA the allocator owns the plant/no-plant decision, so the
    # fixed day gates below must not veto what it asked for -- otherwise the
    # tile quota says "plant strawberry" and the seed buy silently refuses,
    # which is exactly the half-integration that made the first MVA run
    # build zero strawberry and zero wheat all game.
    if day <= MELON_LAST_PLANT_DAY or EXP_MVA:
        want_s = max(0, planned_melon - seeds.get("MELON", 0))
        if want_s > 0:
            want_s = min(want_s, int(max(0.0, budget - 150) // 80))
            if want_s > 0:
                orders.append(["BUY_SEED", "MELON", want_s])
                budget -= want_s * 80
    if (day <= STRAWBERRY_LAST_DAY or EXP_MVA) and planned_straw > 0:
        want_s = max(0, planned_straw - seeds.get("STRAWBERRY", 0))
        want_s = min(want_s, int(max(0.0, budget - 200) // 100))
        if want_s > 0:
            orders.append(["BUY_SEED", "STRAWBERRY", want_s])
            budget -= want_s * 100
    if day <= WHEAT_LAST_PLANT_DAY or EXP_MVA:
        want_s = max(0, planned_wheat - seeds.get("WHEAT", 0))
        if want_s > 0:
            want_s = min(want_s, int(max(0.0, budget - 100) // 10))
            if want_s > 0:
                orders.append(["BUY_SEED", "WHEAT", want_s])
                budget -= want_s * 10

    # --- land -------------------------------------------------------------
    n_extra = len(me["unlocked_quadrants"]) - 1
    if n_extra < len(LAND_PRICES) and day <= LAND_LAST_DAY and n_empty <= LAND_MIN_EMPTY:
        cost = LAND_PRICES[n_extra]
        if budget >= cost + 600 + 300 * n_extra:
            orders.append(["BUY_LAND"])
            budget -= cost

    # --- livestock --------------------------------------------------------
    if day <= LAST_ANIMAL_BUY_DAY and shed_used < 85:
        reserve = 150 + 20 * n_animals
        for animal in buy_order:
            a = ANIMALS[animal]
            slots = free_coops if a["structure"] == "COOP" else free_pastures
            slots -= shed.get(animal, 0) + carried.get(animal, 0)
            k = min(max(0, slots), 8, int(max(0.0, budget - reserve) // a["cost"]))
            if k > 0:
                orders.append(["BUY_ANIMAL", animal, k])
                budget -= k * a["cost"]

    return orders


# NOTE: kaggle-environments loads the *last* callable in the file, so `agent`
# must stay at the bottom.
def agent(obs, config=None):
    return _agent(obs)
