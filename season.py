"""Kaggriculture agent.

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
    and assignment scores PRI_WEIGHT * priority + distance.  Measured: weight 1
    beats 3 by $10.2k (33/34 seeds), 5 loses $8.2k, 10 loses $20k.  But travel
    is not the ONLY term -- ignoring urgency entirely costs $37.7k.
  * MIXED livestock, always.  Restricting to one species costs $16k (cow),
    $36k (sheep) or $80k (goose): the value model needs all three to switch to
    as milk and wool saturate.
  * Wheat is feed.  Buying drains the market (25 + sqrt(deficit)), so the
    wheat-tile quota scales with the live wheat price.

Refuted by measurement, kept here so they are not retried:
  * Fertilizing melons for a 9-day cycle: 0/34 seeds, -$15.6k.
  * Throttling sales to hold the price up: -$1.4k to -$1.8k; the shed
    cap bins the held produce and delays reinvestment.
  * Strawberry planted early: -$12k to -$36k.  Market room != profit; the
    opportunity cost of early capital is what matters.
  * Sticky assignment: measured +$3.2k to REMOVE it, but that was against a
    PRI_WEIGHT=3 baseline.  Combined with PRI_WEIGHT=1 the gain collapsed to
    +$584 (CI crosses zero) -- the two changes fix the same problem, so they do
    not stack.  STICKY_ON is still 1; removing it is NOT an established win.
  * Buying land early: -$24.7k.  Labour, not land, is the constraint.
  * Fixed wheat policy: always-grow -$5.1k, always-buy -$4.0k.  The
    price-adaptive quota beats both.
  * Opponent-aware pricing: project both farms' production forward, net of town
    demand, and value an animal at the average of today's and the projected
    price.  -$13.6k, 3/34 seeds.  The forecast was ACCURATE (milk does crash)
    but the decision rule was wrong twice over: (a) it compares an animal
    against a fixed payback multiple, not against the next best use of the tile
    -- which is an EMPTY tile earning $0, so a cheap cow still beats nothing;
    (b) in a shared market, unilateral restraint is a gift to the opponent.
    Holding back left milk at $227 instead of $170 -- we paid for the restraint
    and they sold into the high price.
  * Stopping wheat at day 15: -$4.6k.  Harvest priority over watering after
    day 20: -$2.5k.  CARE below harvest: -$1.7k.  Ablating CARE: -$45.3k.
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
# SEASON-PLAN KNOBS  (idea #1)
# Every knob below defaults to EXACTLY current V4 behaviour, so with no
# KG_* overrides this file is a byte-identical no-op clone of main.py.
# The optimizer searches over these; anything that hurts stays at its
# default. Claims 1a/1b/2a/2b/3/4 are each represented as a knob rather
# than hardcoded, because several were MEASURED negative for this agent
# (E8 bundling -2,024; front-loaded hiring is the swept optimum) and must
# not be imposed.
# ==========================================================================
# -- 1a: hoard premium crops, sell in timed bundles (E8 measured -2,024) --
SELL_HOARD_MIN = _tune("SELL_HOARD_MIN", 0)      # 0 = sell immediately (current)
SELL_PRICE_MULT = _tune("SELL_PRICE_MULT", 1.0)  # 1.0 = current MIN_SELL floors
# -- 1b: use free animal fertilizer on crops --
FERT_RESERVE_MULT = _tune("FERT_RESERVE_MULT", 1.0)  # scales fert held back from sale
FERT_ALL_CROPS = _tune("FERT_ALL_CROPS", 0)          # 0 = strawberry only (current)
# -- 2a: grow your own wheat vs buy it --
WHEAT_GROW_MULT = _tune("WHEAT_GROW_MULT", 1.0)  # scales the wheat tile quota
WHEAT_BUY_CAP = _tune("WHEAT_BUY_CAP", 58)       # max price we'll buy feed wheat at
# -- 2b: daily CARE routine (already done; expose priorities) --
CARE_PRI = _tune("CARE_PRI", 10)
FEED_PRI = _tune("FEED_PRI", 9)
# -- 3: hire spreading vs front-loading (front-load is the swept optimum) --
HIRE_H0 = _tune("HIRE_H0", 8)
HIRE_LATER = _tune("HIRE_LATER", 4)
HIRE_FRAC = _tune("HIRE_FRAC", 0.35)
# -- 4: pivot to newly-unlocked town shops (NEW capability, off by default) --
SHOP_BIAS = _tune("SHOP_BIAS", 0.0)  # 0.0 = ignore shops entirely (current)
# -- late-game land refill (the gap the blowout analysis identified) --
LATE_REFILL = _tune("LATE_REFILL", 0)        # extra fast-crop tiles after melon ends
LATE_REFILL_DAY = _tune("LATE_REFILL_DAY", 21)

# -- 5: animal payback gate + species ranking (the "geese when milk crashes"
#       hypothesis).  ANIMAL_PAYBACK is a FIXED multiple, so a goose scores
#       2.0 * 50 * 25 = 2,500 against a 9 * 300 = 2,700 gate on day 0 and
#       fails forever; when milk crashes to ~$13 the cows fail it too and we
#       buy NOTHING while tiles sit empty.  PROJECT_LOG already diagnosed
#       this: the gate compares an animal against a fixed multiple, not
#       against the next best use of the tile (an empty tile earning $0).
#       PAYBACK_LATE == ANIMAL_PAYBACK is an exact no-op.
PAYBACK_LATE = _tune("PAYBACK_LATE", ANIMAL_PAYBACK)   # gate at LAST_ANIMAL_BUY_DAY
PAYBACK_FROM_DAY = _tune("PAYBACK_FROM_DAY", 8)        # gate is flat until here
# Rank the buyable species by PROJECTED price at first yield instead of
# today's price.  NOTE: the refuted H-experiment forecast-fed the *gate*;
# this feeds only the *ranking*, and uses only our own herd plus the
# deterministic town drain -- no opponent modelling.
RANK_FORECAST = _tune("RANK_FORECAST", 0)


def _payback_gate(day):
    """Linear decay of the payback multiple from ANIMAL_PAYBACK to PAYBACK_LATE."""
    if PAYBACK_LATE == ANIMAL_PAYBACK or day <= PAYBACK_FROM_DAY:
        return ANIMAL_PAYBACK
    span = max(1, LAST_ANIMAL_BUY_DAY - PAYBACK_FROM_DAY)
    frac = min(1.0, (day - PAYBACK_FROM_DAY) / float(span))
    return ANIMAL_PAYBACK + frac * (PAYBACK_LATE - ANIMAL_PAYBACK)


# The real price curve (same numbers as MARKET_PARAMS in kaggriculture.py),
# so a projected inventory can be priced instead of guessed at.
I0 = 10000
CURVE = {
    "WHEAT":      (25,  400, "sqrt",   0.80, "log",    0.20),
    "CARROT":     (35,  450, "log",    0.20, "sqrt",   0.70),
    "TOMATO":     (60,  200, "linear", 0.40, "sqrt",   0.60),
    "STRAWBERRY": (120, 100, "sqrt",   0.70, "linear", 1.60),
    "MELON":      (250, 300, "log",    0.20, "sq",     3.60),
    "EGG":        (50,  332, "linear", 0.40, "log",    0.20),
    "MILK":       (160, 122, "sqrt",   0.60, "linear", 1.60),
    "WOOL":       (200, 105, "log",    0.20, "sq",     3.20),
    "FERTILIZER": (100, 200, "linear", 0.40, "linear", 0.40),
}


def _shape(f, x):
    x = max(0.0, x)
    if f == "linear":
        return x
    if f == "sq":
        return x * x
    if f == "sqrt":
        return math.sqrt(x)
    return math.log(1.0 + x)


def _unshape(f, y):
    """Inverse of _shape, for turning an observed price back into inventory."""
    y = max(0.0, y)
    if f == "linear":
        return y
    if f == "sq":
        return math.sqrt(y)
    if f == "sqrt":
        return y * y
    return math.exp(y) - 1.0


def _price_at(item, inv):
    base, T, bf, bt, af, at = CURVE[item]
    d = abs(inv - I0)
    if inv < I0:
        px = base + (bt * base / _shape(bf, T)) * _shape(bf, d)
    else:
        px = base - (at * base / _shape(af, T)) * _shape(af, d)
    return max(1.0, px)


def _inv_at(item, px):
    """Invert the price curve: what market inventory implies this price?"""
    base, T, bf, bt, af, at = CURVE[item]
    if px >= base:
        amp = bt * base / _shape(bf, T)
        return I0 - _unshape(bf, (px - base) / amp) if amp else I0
    amp = at * base / _shape(af, T)
    return I0 + _unshape(af, (base - px) / amp) if amp else I0


# Town center drains every 12 steps (2/day) at a day-scaled multiplier.
def _center_drain(day):
    mult = 4 if day >= 20 else (2 if day >= 10 else 1)
    return 2 * mult

PREMIUM_ITEMS = ("MELON", "STRAWBERRY", "WOOL", "MILK")

SHOPS = {
    "BAKERY":         ["EGG", "WHEAT"],
    "PIZZA_SHOP":     ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT":    ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE":     ["WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"],
    "PET_CAFE":       ["CARROT"],
    "SMOOTHIE_SHOP":  ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}


def _shop_demand(obs):
    """Units/day the town drains per product from unlocked shops.

    Exact mechanics from kaggriculture.py: every `townShopSellInterval`
    (4) steps each unlocked shop removes 1 of each of its products, or 2
    if it sells only one product. 24 turns/day => 6 drains/day.
    """
    d = {}
    try:
        shops = (obs.get("town") or {}).get("unlocked_shops", []) or []
    except Exception:
        return d
    for s in shops:
        prods = SHOPS.get(s, [])
        mult = 2 if len(prods) == 1 else 1
        for p in prods:
            d[p] = d.get(p, 0) + mult * 6
    return d


# Sticky task assignment: {"day": d, "map": {unit_idx: (target, op)}}
_STICKY = {}


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
    want_wheat = max(2, min(int(round(want_wheat * WHEAT_GROW_MULT)), 40))

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

    # -- 4: pivot toward products the unlocked town shops actually drain.
    # SHOP_BIAS = 0.0 (default) leaves every target untouched. The town is
    # the only demand that never saturates, so a shop unlocking is a real,
    # permanent increase in absorbable supply -- this replaces guessing at
    # it with the observed shop list.
    if SHOP_BIAS > 0:
        _dem = _shop_demand(obs)
        if _dem:
            _s_str = _dem.get("STRAWBERRY", 0)
            if _s_str and day <= FINAL_DAY - CROPS["STRAWBERRY"]["first"]:
                want_straw = max(want_straw,
                                 int(round(STRAWBERRY_TILES * (1.0 + SHOP_BIAS * _s_str / 6.0))))
            _s_wh = _dem.get("WHEAT", 0)
            if _s_wh:
                want_wheat = max(want_wheat,
                                 int(round(want_wheat * (1.0 + SHOP_BIAS * _s_wh / 12.0))))

    # -- late-game land refill: melon frees ~9 tiles around day 21 and
    # nothing reclaims them (measured: empty tiles 16 -> 43 between day 14
    # and 28 in self-play). LATE_REFILL = 0 disables.
    if LATE_REFILL > 0 and day >= LATE_REFILL_DAY and day <= FINAL_DAY - 3:
        want_wheat = min(40, want_wheat + LATE_REFILL)
    need_straw = max(0, want_straw - straw_planted)

    need_melon = max(0, want_melon - melon_planted)
    need_wheat = max(0, want_wheat - wheat_planted)
    homeless = (shed.get("COW", 0) + carried.get("COW", 0)
                + shed.get("SHEEP", 0) + carried.get("SHEEP", 0))
    want_pastures = homeless

    # Which animal is worth buying right now?  With daily CARE an animal yields
    # (1 + interval) units every `interval` days, so rate = (1+interval)/interval.
    # Value it over the days it can still produce, and require a 2x payback.
    herd = {}
    for _x, _y, _t in animals:
        herd[_t["animal"]] = herd.get(_t["animal"], 0) + 1
    shop_drain = _shop_demand(obs) if RANK_FORECAST else {}

    def _projected_price(product, ahead):
        """Price of `product` in `ahead` days, from OUR OWN supply plus the
        deterministic town drain.  The opponent is deliberately not modelled."""
        px_now = prices.get(product, 0)
        if px_now <= 0 or ahead <= 0 or product not in CURVE:
            return px_now
        mine = 0.0
        for k, a in ANIMALS.items():
            if a["product"] == product:
                mine += herd.get(k, 0) * (1.0 + a["interval"]) / a["interval"]
        drain = shop_drain.get(product, 0) + _center_drain(day)
        inv = _inv_at(product, px_now) + (mine - drain) * ahead
        return _price_at(product, inv)

    gate = _payback_gate(day)
    animal_value = {}
    for k, a in ANIMALS.items():
        rate = (1.0 + a["interval"]) / a["interval"]
        price = prices.get(a["product"], 0)
        days_left = max(0, FINAL_DAY - day - a["first"])
        rank_px = _projected_price(a["product"], a["first"]) if RANK_FORECAST else price
        animal_value[k] = (rate * price * days_left, rate * rank_px, a["cost"], days_left)
    buyable = [k for k, (rev, _r, cost, dl) in animal_value.items()
               if dl > 0 and rev >= gate * cost]
    buyable.sort(key=lambda k: -animal_value[k][1])
    best_animal = buyable[0] if buyable else None
    best_struct = ANIMALS[best_animal]["structure"] if best_animal else None

    # coops: however many geese we could plausibly stock soon
    want_coops = shed.get("GOOSE", 0) + carried.get("GOOSE", 0)
    room = int(spare / ANIMAL_LOAD)
    if best_animal and day <= LAST_ANIMAL_BUY_DAY:
        afford = int(max(0.0, money - 200) // ANIMALS[best_animal]["cost"])
        slots = max(0, min(afford + 2, room, 45))
        if best_struct == "COOP":
            want_coops = max(want_coops, slots - len(free_coops))
        else:
            want_pastures = max(want_pastures, slots - len(free_pastures))
    want_coops = max(0, want_coops)
    want_pastures = max(0, want_pastures)

    centre = (n / 2.0 - 0.5, n / 2.0 - 0.5)
    empties.sort(key=lambda p: abs(p[0] - centre[0]) + abs(p[1] - centre[1]))

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
            add(2 if t["consecutive_unfed"] >= 1 else FEED_PRI,
                (x, y), ["FEED"], req="WHEAT")
        if t["yield_units"] >= max(1, a["max_held"] - 1) or (endgame and t["yield_units"] > 0):
            add(12, (x, y), ["HARVEST"])
        if not endgame and t["fed_today"] and not t["cared_today"]:
            add(CARE_PRI, (x, y), ["CARE"])
        if t["fertilizer_available"] and prices.get("FERTILIZER", 0) >= FERT_MIN_PRICE:
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
        _fert_ok = (crop == "STRAWBERRY") or (FERT_ALL_CROPS and cd["ongoing"])
        if (_fert_ok and prod_day
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
    for i in sorted(free):
        inv = uinv[i]
        junk = sum(c for it, c in inv.items() if it != "WHEAT" and c > 0)
        at_shed = pos[i] in shed_tiles
        target = min(shed_tiles, key=lambda s: _dist(pos[i], s))
        if junk > 0 and at_shed:
            actions[i] = ["DROP"]
        elif junk >= 10 or (endgame and junk > 0) or (junk > 0 and hour >= 20):
            mv = _step_toward(pos[i], target)
            actions[i] = [mv] if mv else ["DROP"]
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
        k = min(want - already, HIRE_H0 if hour == 0 else HIRE_LATER)
        while k > 0 and _hire_cost_total(already + k) - _hire_cost_total(already) > budget * HIRE_FRAC:
            k -= 1
        budget -= _hire_cost_total(already + k) - _hire_cost_total(already)
        hires.extend([["HIRE"]] * k)

    # --- sell -------------------------------------------------------------
    wheat_reserve = 0 if endgame else min(24, n_animals + 6)
    fert_reserve = 0 if endgame else int(fert_reserve_in * FERT_RESERVE_MULT)
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
        if item in PREMIUM_ITEMS:
            floor = floor * SELL_PRICE_MULT
        ok = endgame or hard or (price >= floor * 0.5 if pressure else price >= floor)
        if not ok:
            continue
        # 1a: hoard premium crops until a bundle has accumulated. Default
        # SELL_HOARD_MIN=0 disables this entirely (current behaviour).
        if (SELL_HOARD_MIN > 0 and item in PREMIUM_ITEMS
                and not endgame and not hard and qty < SELL_HOARD_MIN):
            continue
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
    if n_animals > 0 and gap > 0 and wp <= WHEAT_BUY_CAP and shed_used < 92:
        gap = min(gap, int(budget // max(1, wp + 6)), 40)
        if gap > 0:
            orders.append(["BUY_PRODUCT", "WHEAT", gap])
            budget -= gap * (wp + 6)

    # --- opportunistic surplus (E9V4) --------------------------------------
    # After covering the same reserve the livestock section below protects
    # for itself (reserve = 150 + 20*n_animals), spend any genuine capital
    # surplus on whichever of two candidates -- a cheap wheat stockpile, or
    # an extra unit of the best-ranked animal -- currently scores higher in
    # $-value-per-$-spent terms. Never both in the same turn, to avoid
    # double-claiming the surplus or a pasture/coop slot the livestock
    # section will also try to use. Held-out validation (20 games, seeds
    # never used in tuning): 16/20 wins, +$6,484 avg margin vs a fixed-
    # threshold wheat-only version's 10/20 (a coin flip out of sample).
    if not endgame:
        anim_reserve = 150 + 20 * n_animals
        surplus = budget - anim_reserve
        if surplus > 0:
            wheat_ok = wp <= 30 and shed_used < 80
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
    if day <= MELON_LAST_PLANT_DAY:
        want_s = max(0, planned_melon - seeds.get("MELON", 0))
        if want_s > 0:
            want_s = min(want_s, int(max(0.0, budget - 150) // 80))
            if want_s > 0:
                orders.append(["BUY_SEED", "MELON", want_s])
                budget -= want_s * 80
    if day <= STRAWBERRY_LAST_DAY and planned_straw > 0:
        want_s = max(0, planned_straw - seeds.get("STRAWBERRY", 0))
        want_s = min(want_s, int(max(0.0, budget - 200) // 100))
        if want_s > 0:
            orders.append(["BUY_SEED", "STRAWBERRY", want_s])
            budget -= want_s * 100
    if day <= WHEAT_LAST_PLANT_DAY:
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
    try:
        return _agent(obs)
    except Exception:
        try:
            n_hands = len(obs["farms"][obs["player"]]["hands"])
        except Exception:
            n_hands = 0
        return {"farmer": ["PASS"], "hands": [["PASS"]] * n_hands, "market": []}
