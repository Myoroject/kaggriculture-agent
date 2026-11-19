"""Kaggriculture agent.

Strategy, derived from the price model in kaggriculture.py:

  * MELON is the best $/tile in the game: 6 units per 11-day cycle at ~$250,
    and the glut curve (price = 250 - 0.01 * excess^2) only bites after roughly
    155 units sold.  ~12 tiles x 2 cycles lands right on that cap.
  * FERTILIZER is free money: every surviving animal makes 1 unit/day whether
    or not it is fed, and fertilizer only loses $0.20 per unit sold.  Early
    animals pay for themselves in manure alone.
  * EGG is the only unbounded product (above_func="log"): 1000 eggs sold still
    price at ~$38.  A fed + cared goose gives 2 eggs/day forever.
  * MILK / WOOL crash after ~75 / ~58 units, so a couple of cows and sheep are
    worth it for the high first sales, no more.
  * Farm hands cost fib(n) (1,1,2,3,5,8,...): ten hands = $143/day for 240
    actions.  Labour is free; land, capital and market saturation are not.
  * Wheat is feed.  Buying drains the market (price 25+sqrt(deficit)), so the
    wheat-tile quota scales with the wheat price.
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

MARKET_I0 = 10000
MARKET_PARAMS = {
    "WHEAT":      {"base": 25,  "T": 400, "bf": "sqrt",   "bt": 0.80, "af": "log",    "at": 0.20},
    "CARROT":     {"base": 35,  "T": 450, "bf": "log",    "bt": 0.20, "af": "sqrt",   "at": 0.70},
    "TOMATO":     {"base": 60,  "T": 200, "bf": "linear", "bt": 0.40, "af": "sqrt",   "at": 0.60},
    "STRAWBERRY": {"base": 120, "T": 100, "bf": "sqrt",   "bt": 0.70, "af": "linear", "at": 1.60},
    "MELON":      {"base": 250, "T": 300, "bf": "log",    "bt": 0.20, "af": "sq",     "at": 3.60},
    "EGG":        {"base": 50,  "T": 332, "bf": "linear", "bt": 0.40, "af": "log",    "at": 0.20},
    "MILK":       {"base": 160, "T": 122, "bf": "sqrt",   "bt": 0.60, "af": "linear", "at": 1.60},
    "WOOL":       {"base": 200, "T": 105, "bf": "log",    "bt": 0.20, "af": "sq",     "at": 3.20},
    "FERTILIZER": {"base": 100, "T": 200, "bf": "linear", "bt": 0.40, "af": "linear", "at": 0.40},
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


def _price_at(item, inv):
    p = MARKET_PARAMS[item]
    d = abs(inv - MARKET_I0)
    if inv < MARKET_I0:
        amp = p["bt"] * p["base"] / _shape(p["bf"], p["T"])
        px = p["base"] + amp * _shape(p["bf"], d)
    else:
        amp = p["at"] * p["base"] / _shape(p["af"], p["T"])
        px = p["base"] - amp * _shape(p["af"], d)
    return max(1.0, round(px))


def _units_above(item, inv, floor_price, cap):
    """How many units can we sell before the marginal price drops below floor?"""
    n = 0
    while n < cap and _price_at(item, inv + n) >= floor_price:
        n += 1
    return n


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
        return default
    except Exception:
        return default


MELON_TILES = _tune("MELON_TILES", MELON_TILES)
MAX_HANDS = _tune("MAX_HANDS", MAX_HANDS)
MIN_HANDS = _tune("MIN_HANDS", MIN_HANDS)
ACTIONS_PER_TASK = _tune("ACTIONS_PER_TASK", 3.5)
HAND_DIVISOR = _tune("HAND_DIVISOR", 8.0)
USE_MELON_FERT = _tune("USE_MELON_FERT", 0)
MELON_LAST_PLANT_DAY = _tune("MELON_LAST_DAY", MELON_LAST_PLANT_DAY)
ANIMAL_LOAD = _tune("ANIMAL_LOAD", 4.5)
ANIMAL_PAYBACK = _tune("ANIMAL_PAYBACK", 9.0)
FERT_MIN_PRICE = _tune("FERT_MIN_PRICE", 10)
STRAWBERRY_TILES = _tune("STRAWBERRY_TILES", 0)
STRAWBERRY_LAST_DAY = _tune("STRAWBERRY_LAST_DAY", 13)
STRAWBERRY_START_DAY = _tune("STRAWBERRY_START_DAY", 0)
SELL_FRAC = _tune("SELL_FRAC", 0.0)   # 0 = sell all above MIN_SELL
SELLS_FIRST = _tune("SELLS_FIRST", 1)

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
            if USE_MELON_FERT and t["crop"] == "MELON" and 6 <= age <= 7 and t["fertilized_until_day"] < day + 2:
                fert_need += 1
            elif t["crop"] == "STRAWBERRY" and t["fertilized_until_day"] < day:
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
            add(2 if t["consecutive_unfed"] >= 1 else 9, (x, y), ["FEED"], req="WHEAT")
        if t["yield_units"] >= max(1, a["max_held"] - 1) or (endgame and t["yield_units"] > 0):
            add(12, (x, y), ["HARVEST"])
        if not endgame and t["fed_today"] and not t["cared_today"]:
            add(10, (x, y), ["CARE"])
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
        if (crop == "STRAWBERRY" and prod_day
                and t["fertilized_until_day"] < day and age >= cd["first"] - 1):
            add(15, (x, y), ["FERTILIZE"], req="FERTILIZER")
        if (USE_MELON_FERT and crop == "MELON"
                and t["fertilized_until_day"] < day + 2
                and window <= age <= window + 1):
            add(14, (x, y), ["FERTILIZE"], req="FERTILIZER")
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
                pairs.append((task["pri"] * 3 + _dist(pos[i], task["target"]), ti, i))
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
        me, shed, seeds, prices, obs["market"]["inventory"], money, day, hour, endgame,
        n_animals=n_animals,
        free_coops=len(free_coops), free_pastures=len(free_pastures),
        planned_wheat=planned_wheat, planned_melon=planned_melon,
        planned_straw=planned_straw,
        n_plants=len(plants), carried=carried, n_units=n_units,
        n_empty=len(empties), buy_order=buyable, fert_reserve_in=(min(8, melon_planted) if USE_MELON_FERT else 0) + min(10, straw_planted),
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

def _market_orders(me, shed, seeds, prices, market_inv, money, day, hour, endgame,
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
        if not SELLS_FIRST:
            orders.extend(hires)
            hires = []

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
        # Revenue is sum(price(I0+k)), not n*price(I0).  With SELL_FRAC on, stop
        # the order before the marginal unit falls below frac * base and let the
        # town's daily drain lift the price back up before the next batch.
        if SELL_FRAC > 0 and not endgame and not hard and item in MARKET_PARAMS:
            inv = market_inv.get(item)
            if inv is not None:
                room = _units_above(item, inv, SELL_FRAC * MARKET_PARAMS[item]["base"], qty)
                qty = min(qty, max(room, 1 if pressure else 0))
        if qty > 0:
            orders.append(["SELL", item, qty])
            budget += price * qty
        if len(orders) >= 9:
            break

    if hires:
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
    if n_extra < len(LAND_PRICES) and day <= LAND_LAST_DAY and n_empty <= 8:
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
