"""Generate farmer.py = main.py + the experienced-farmer strategy layer.

main.py is never modified; this only ever writes farmer.py.
"""

BRAIN = '''

# ==========================================================================
# EXPERIENCED-FARMER LAYER
# ==========================================================================
# Market depth: units sold that halve the price (read off the price curve).
# Wheat and egg are effectively bottomless; wool / strawberry / milk are shallow.
DEPTH = {"WHEAT": 4000, "EGG": 4000, "CARROT": 231, "TOMATO": 136,
         "MELON": 113, "MILK": 39, "STRAWBERRY": 32, "WOOL": 43, "FERTILIZER": 500}

# The town eats product for free every day, and that demand is what makes a
# market safe to enter.  Only supply ABOVE the town drain depresses the price.
SHOP_DEMAND = {
    "BAKERY":         {"EGG": 1, "WHEAT": 1},
    "PIZZA_SHOP":     {"MILK": 1, "TOMATO": 1, "WHEAT": 1},
    "BRUNCH_SPOT":    {"EGG": 1, "WHEAT": 1, "STRAWBERRY": 1},
    "YARN_STORE":     {"WOOL": 2},
    "ICE_CREAM_SHOP": {"STRAWBERRY": 1, "MILK": 1, "WHEAT": 1},
    "PET_CAFE":       {"CARROT": 2},
    "SMOOTHIE_SHOP":  {"STRAWBERRY": 1, "MILK": 1},
    "FARMERS_MARKET": {"WHEAT": 1, "CARROT": 1, "TOMATO": 1, "STRAWBERRY": 1},
}


def _town_drain(product, shops, day):
    """Units/day the town removes: each shop ticks 6x/day, town centre 2x/day."""
    per_shop = sum(SHOP_DEMAND.get(s, {}).get(product, 0) for s in shops) * 6
    mult = 4 if day >= 20 else (2 if day >= 10 else 1)
    centre = 0 if product == "FERTILIZER" else 2 * mult
    return per_shop + centre


# The real price curve, so we can price PROJECTED inventory instead of guessing
# at a discount factor.  (Same numbers as MARKET_PARAMS in kaggriculture.py.)
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


def _price_at(item, inv):
    base, T, bf, bt, af, at = CURVE[item]
    d = abs(inv - I0)
    if inv < I0:
        px = base + (bt * base / _shape(bf, T)) * _shape(bf, d)
    else:
        px = base - (at * base / _shape(af, T)) * _shape(af, d)
    return max(1.0, px)


ANIMAL_ACTIONS = 3.5          # feed + care + harvest + walking, per animal per day
CROP_PLAN = {
    # crop: (seed, first_yield, cycle_days, units, actions_per_day)
    "STRAWBERRY": (100, 10, 16, 8, 1.3),   # 4 productions, doubled by fertilizer
    "MELON":      (80,  10, 11, 6, 1.1),
    "WHEAT":      (10,   2,  5, 4, 1.4),
    "CARROT":     (20,   2,  4, 3, 1.3),
}

_PRICE_HIST = {}


def _remember_prices(player, day, prices):
    h = _PRICE_HIST.setdefault(player, {})
    if h.get("_day") == day:
        return
    if h.get("_day") is not None and day < h["_day"]:
        h.clear()                      # new episode in a reused process
    h["_day"] = day
    for item, px in prices.items():
        lst = h.setdefault(item, [])
        lst.append((day, px))
        if len(lst) > 32:
            lst.pop(0)


def _trend(player, item, lookback=6):
    """Dollars per day the price has been moving lately."""
    lst = _PRICE_HIST.get(player, {}).get(item, [])
    if not isinstance(lst, list) or len(lst) < 2:
        return 0.0
    d_now, p_now = lst[-1]
    for d, p in reversed(lst):
        if d_now - d >= lookback:
            return (p_now - p) / float(d_now - d)
    d0, p0 = lst[0]
    return (p_now - p0) / float(max(1, d_now - d0))


def _hidden_supply(tiles, product, day):
    """Units/day from tiles that have NOT started producing yet - supply the
    market price has not felt, which is the only part worth forecasting."""
    rate = 0.0
    for row in tiles:
        for t in row:
            if not isinstance(t, dict):
                continue
            if t.get("animal"):
                a = ANIMALS[t["animal"]]
                if a["product"] == product and day - t.get("placed_day", day) < a["first"]:
                    rate += (1.0 + a["interval"]) / a["interval"]
            elif t.get("kind") == "PLANT" and t.get("crop") == product:
                cd = CROPS[product]
                if day - t.get("planted_day", day) < cd["first"] and product in CROP_PLAN:
                    _s, _f, cyc, un, _a = CROP_PLAN[product]
                    rate += un / float(cyc)
    return rate


def _forecast(player, item, prices, days, my_tiles, opp_tiles, day, shops, inv,
              extra_rate=0.0):
    """Average price we expect to realise over the next `days` days.

    Three inputs: today's price; the recent trend (which already contains both
    farms' selling); and supply that is placed but not yet producing.
    """
    now = float(prices.get(item, 0))
    if days <= 0 or item not in CURVE:
        return now
    # Where will market inventory be once every placed tile has produced, net of
    # what the town eats?  Read the price off the real curve at that point.
    hidden = (_hidden_supply(my_tiles, item, day)
              + _hidden_supply(opp_tiles, item, day) + extra_rate)
    net = hidden - _town_drain(item, shops, day)
    proj_inv = inv.get(item, I0) + net * days
    proj = _price_at(item, proj_inv)
    trend_px = now + _trend(player, item) * days * 0.5
    return max(1.0, 0.4 * now + 0.4 * proj + 0.2 * max(1.0, trend_px))


def _my_rate(tiles, product):
    """Units/day this farm already produces of `product` (placed or planted)."""
    rate = 0.0
    for row in tiles:
        for t in row:
            if not isinstance(t, dict):
                continue
            if t.get("animal"):
                a = ANIMALS[t["animal"]]
                if a["product"] == product:
                    rate += (1.0 + a["interval"]) / a["interval"]
            elif t.get("kind") == "PLANT" and t.get("crop") == product and product in CROP_PLAN:
                _s, _f, cyc, un, _a = CROP_PLAN[product]
                rate += un / float(cyc)
    return rate


def _room(product, shops, day, my_tiles, opp_tiles, extra):
    """How much more of this product can we sell per day before we are just
    crushing our own price?  The town eats a fixed amount every day; that is the
    real capacity, and a competing farm splits it with us."""
    capacity = _town_drain(product, shops, max(day, 20))     # season-end demand
    opp = _my_rate(opp_tiles, product)
    if opp > 0.05:
        capacity *= 0.55                                     # contested market
    mine = _my_rate(my_tiles, product) + extra.get(product, 0.0)
    return capacity - mine


# What one tile of each kind produces per day, and what it costs to service.
# (product, units/day, actions/day, cash, first_yield_day, structure_or_crop)
TILE_KINDS = [
    ("SHEEP",      "WOOL",       1.333, 3.5, 500, 6,  "PASTURE"),
    ("COW",        "MILK",       1.5,   3.5, 400, 8,  "PASTURE"),
    ("GOOSE",      "EGG",        2.0,   3.5, 300, 4,  "COOP"),
    ("MELON",      "MELON",      6/11., 1.1,  80, 10, None),
    ("STRAWBERRY", "STRAWBERRY", 0.5,   1.3, 100, 10, None),   # 16-day tile lock
    ("CARROT",     "CARROT",     0.75,  1.3,  20, 2,  None),
    ("WHEAT",      "WHEAT",      0.8,   1.4,  10, 2,  None),
]


def _season_drain(product):
    """Demand once every shop is unlocked (they all are by ~day 24).  An animal
    placed today produces for the REST of the season, so capacity must be sized
    against the season's demand, not against today's."""
    per_shop = sum(s.get(product, 0) for s in SHOP_DEMAND.values()) * 6
    centre = 0 if product == "FERTILIZER" else 8
    return per_shop + centre


def _demand_target(product, rate, shops, day, opp_tiles):
    """How many tiles of this product the market can still absorb.

    The town's daily drain is demand that cannot be crushed.  Whatever the
    opponent already supplies comes out of it first - that is the opponent
    model, and it needs no assumption about their intentions.
    """
    drain = _season_drain(product)
    # Revenue = our_units x price(TOTAL supply).  Ceding capacity to the opponent
    # lowers our units without meaningfully raising the price - they simply fill
    # the gap.  Market share here is won by building, not by yielding, so we
    # target the whole drain and let the price curve arbitrate.
    return drain * SHARE / rate


def _tile_options(player, day, prices, money, my_tiles, opp_tiles, wheat_price,
                  extra, shops, inv):
    """Rank what to put on a free tile: only products with demand headroom,
    ordered by forecast $ per task-action over the days that remain."""
    out = []
    for name, product, rate, acts, cash, first, struct in TILE_KINDS:
        days = FINAL_DAY - day - first
        if days <= 1:
            continue
        target = _demand_target(product, rate, shops, day, opp_tiles)
        held = (_my_rate(my_tiles, product) + extra.get(product, 0.0)) / rate
        if held >= target:
            continue                            # market already covered
        if struct and money < cash * 0.25:
            continue          # structures are free: plan ahead of the cash
        px = _forecast(player, product, prices, days, my_tiles, opp_tiles, day,
                       shops, inv, extra.get(product, 0.0) + rate)
        gross = rate * px * days
        upkeep = wheat_price * days if struct else 0.0   # animals eat wheat
        profit = gross - upkeep - cash
        if not struct and day > FINAL_DAY - 12 and name in ("CARROT", "WHEAT"):
            profit *= 1.5     # late on, a fast crop beats an empty tile
        if profit <= 0:
            continue
        out.append(dict(kind="ANIMAL" if struct else "CROP", what=name,
                        product=product, rate=rate, load=acts, cash=cash,
                        score=profit / (acts * days), headroom=target - held))
    # Livestock compounds from day 4-8 onward and funds everything else, so take
    # it first while the market still has room; crops fill what is left.
    out.sort(key=lambda o: (0 if o["kind"] == "ANIMAL" else 1, -o["score"]))
    return out

'''

NEW_PLAN = '''    # ---------------- land plan: knapsack over every tile use ----------------
    _remember_prices(player, day, prices)
    opp_tiles = obs["farms"][1 - player]["tiles"]
    shops = obs["town"].get("unlocked_shops", [])
    inv = obs["market"]["inventory"]
    wheat_price = prices.get("WHEAT", 25)

    crew = max(n_units, MIN_HANDS + 1)
    capacity = crew * 24 / ACTIONS_PER_TASK
    load = (n_animals * ANIMAL_LOAD + melon_planted * 1.1
            + wheat_planted * 1.4 + straw_planted * 1.3)

    centre = (n / 2.0 - 0.5, n / 2.0 - 0.5)
    empties.sort(key=lambda p: abs(p[0] - centre[0]) + abs(p[1] - centre[1]))

    plan = {}
    homeless = (shed.get("COW", 0) + carried.get("COW", 0)
                + shed.get("SHEEP", 0) + carried.get("SHEEP", 0))
    want_pastures = homeless
    want_coops = shed.get("GOOSE", 0) + carried.get("GOOSE", 0)
    buyable = []
    # animals are the only expensive commitment: reserve feed money for the herd
    # we already own before deciding how many more we can afford.
    feed_reserve = n_animals * wheat_price * 3
    budget_left = money - CASH_FLOOR - feed_reserve
    extra = {}

    # Fill toward the demand target, re-pricing after each choice.
    for spot in empties:
        if load >= capacity * FILL_TARGET:
            break
        opts = _tile_options(player, day, prices, max(0.0, budget_left),
                             tiles, opp_tiles, wheat_price, extra, shops, inv)
        if day > LAST_ANIMAL_BUY_DAY:
            opts = [o for o in opts if o["kind"] == "CROP"]
        if not opts:
            break
        best = opts[0]
        if best["kind"] == "ANIMAL":
            a = ANIMALS[best["what"]]
            plan[spot] = a["structure"]
            if a["structure"] == "COOP":
                want_coops += 1
            else:
                want_pastures += 1
            buyable.append(best["what"])
            budget_left -= a["cost"]
        else:
            plan[spot] = best["what"]
            budget_left -= best["cash"]
        extra[best["product"]] = extra.get(best["product"], 0.0) + best["rate"]
        load += best["load"]

    planned_melon = sum(1 for v in plan.values() if v == "MELON")
    planned_straw = sum(1 for v in plan.values() if v == "STRAWBERRY")
    planned_wheat = sum(1 for v in plan.values() if v == "WHEAT")
    seen_ = set()
    buyable = [a for a in buyable if not (a in seen_ or seen_.add(a))]

'''


def build():
    src = open("main.py").read()

    anchor = "# --------------------------------------------------------------------------\n# core\n"
    assert anchor in src
    src = src.replace(anchor, BRAIN + "\n" + anchor, 1)

    start = src.index("    # ---------------- land plan ----------------")
    end = src.index("    # ---------------- tasks ----------------")
    src = src[:start] + NEW_PLAN + src[end:]

    # the allocator decides timing, so seed buys follow the plan not the calendar
    src = src.replace("    if day <= STRAWBERRY_LAST_DAY and planned_straw > 0:",
                      "    if planned_straw > 0:")
    src = src.replace("    if day <= MELON_LAST_PLANT_DAY:\n        want_s = max(0, planned_melon",
                      "    if planned_melon > 0:\n        want_s = max(0, planned_melon")
    src = src.replace("    if day <= WHEAT_LAST_PLANT_DAY:\n        want_s = max(0, planned_wheat",
                      "    if planned_wheat > 0:\n        want_s = max(0, planned_wheat")

    src = src.replace('ONLY_ANIMAL_PLACEHOLDER', '')
    src = src.replace('LAND_MIN_EMPTY = _tune("LAND_MIN_EMPTY", 8)',
                      'LAND_MIN_EMPTY = _tune("LAND_MIN_EMPTY", 8)\n'
                      'FILL_TARGET = _tune("FILL_TARGET", 0.95)   # run at the labour wall\n'
                      'CASH_FLOOR = _tune("CASH_FLOOR", 150)      # liquidity kept back\n'
                      'SHARE = _tune("SHARE", 1.0)                # of town demand we supply')

    src = src.replace('"""Kaggriculture agent.',
                      '"""Kaggriculture agent - EXPERIENCED FARMER (generated by build_farmer.py).\n\n'
                      'Same scheduler as main.py, with a strategy brain on top.  Every turn it\n'
                      'scores every possible use of every free tile in $/action, using a price\n'
                      'forecast built from (a) today\'s price, (b) the recent trend, and (c) supply\n'
                      'placed by BOTH farms that has not started producing yet.  It then fills the\n'
                      'farm to the labour wall.  No hardcoded crop quotas: the mix - and when to\n'
                      'back off milk - falls out of the market.\n\nINHERITED NOTES:', 1)
    open("farmer.py", "w").write(src)
    print("farmer.py:", len(src.splitlines()), "lines")


if __name__ == "__main__":
    build()
