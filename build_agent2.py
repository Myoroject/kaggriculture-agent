"""Generate agent2.py = main.py + PRD layers P1/P2/P3.

main.py is never modified.  Unlike farmer.py (which REPLACED main.py's tuned land
plan and lost by $25k), these layers are ADDITIVE: the proven quotas still run,
and each layer only extends them.  Every layer is flag-gated so it can be
ablated:  KG_P1_LATE / KG_P2_OPP / KG_P3_FILL.
"""

LAYER = '''

# ==========================================================================
# PRD LAYERS  (P1 late-game engine, P2 opponent awareness, P3 idle-tile fill)
# ==========================================================================
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
}
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
# tile kinds available to the P3 filler: (name, product, units/day, actions/day,
# cash, first_yield_day, structure or None)
FILL_KINDS = [
    ("SHEEP",      "WOOL",       1.333, 3.5, 500, 6,  "PASTURE"),
    ("COW",        "MILK",       1.5,   3.5, 400, 8,  "PASTURE"),
    ("STRAWBERRY", "STRAWBERRY", 0.5,   1.3, 100, 10, None),
    ("CARROT",     "CARROT",     0.75,  1.3,  20, 2,  None),
    ("WHEAT",      "WHEAT",      0.8,   1.4,  10, 2,  None),
]


def _shape2(f, x):
    x = max(0.0, x)
    if f == "linear":
        return x
    if f == "sq":
        return x * x
    if f == "sqrt":
        return math.sqrt(x)
    return math.log(1.0 + x)


def _price_at2(item, inv):
    base, T, bf, bt, af, at = CURVE[item]
    d = abs(inv - I0)
    if inv < I0:
        return max(1.0, base + (bt * base / _shape2(bf, T)) * _shape2(bf, d))
    return max(1.0, base - (at * base / _shape2(af, T)) * _shape2(af, d))


def _season_drain(product):
    """Town demand once every shop is unlocked (all are by ~day 24)."""
    return sum(s.get(product, 0) for s in SHOP_DEMAND.values()) * 6 + 8


def _supply_rate(tiles, product):
    """Units/day a farm produces of `product` from what is on the ground."""
    rate = 0.0
    for row in tiles:
        for t in row:
            if not isinstance(t, dict):
                continue
            if t.get("animal"):
                a = ANIMALS[t["animal"]]
                if a["product"] == product:
                    rate += (1.0 + a["interval"]) / a["interval"]
            elif t.get("kind") == "PLANT" and t.get("crop") == product:
                if product == "STRAWBERRY":
                    rate += 0.5
                elif product == "MELON":
                    rate += 6 / 11.0
                elif product == "WHEAT":
                    rate += 0.8
                elif product == "CARROT":
                    rate += 0.75
    return rate


def _fill_options(day, prices, money, my_tiles, opp_tiles, inv, extra, wheat_price):
    """P3: rank what to put on an otherwise IDLE tile.  An empty tile earns $0,
    so any positive score beats leaving it alone."""
    out = []
    for name, product, rate, acts, cash, first, struct in FILL_KINDS:
        days = FINAL_DAY - day - first
        if days <= 1:
            continue
        if struct and money < cash:
            continue
        # price once every placed tile (both farms) has produced, net of the town
        mine = _supply_rate(my_tiles, product) + extra.get(product, 0.0) + rate
        theirs = _supply_rate(opp_tiles, product)
        net = mine + theirs - _season_drain(product)
        proj = _price_at2(product, inv.get(product, I0) + max(0.0, net) * days)
        px = 0.5 * float(prices.get(product, 0)) + 0.5 * proj
        profit = rate * px * days - (wheat_price * days if struct else 0.0) - cash
        if profit <= 0:
            continue
        out.append(dict(name=name, product=product, rate=rate, load=acts,
                        cash=cash, struct=struct, score=profit / (acts * days)))
    out.sort(key=lambda o: -o["score"])
    return out

'''


def build():
    src = open("main.py").read()

    anchor = "# --------------------------------------------------------------------------\n# core\n"
    assert anchor in src
    src = src.replace(anchor, LAYER + "\n" + anchor, 1)

    # ---- flags -----------------------------------------------------------
    src = src.replace("""    centre = (n / 2.0 - 0.5, n / 2.0 - 0.5)
    empties.sort(key=lambda p: abs(p[0] - centre[0]) + abs(p[1] - centre[1]))""",
"""    centre = (n / 2.0 - 0.5, n / 2.0 - 0.5)
    empties.sort(key=lambda p: abs(p[0] - centre[0]) + abs(p[1] - centre[1]))
    if MAX_RADIUS < 99:
        # E2: 57% of every action is walking.  A distant tile can cost more in
        # travel than it ever yields, so refuse to farm past a fixed radius.
        empties = [p for p in empties
                   if abs(p[0] - centre[0]) + abs(p[1] - centre[1]) <= MAX_RADIUS]""")

    # E6: hard cap on how many tiles we work at all.  The best ladder farms run
    # 16.5 productive tiles; we run 23.3 and earn less.
    src = src.replace('''    planned_melon = sum(1 for v in plan.values() if v == "MELON")''',
'''    if MAX_PRODUCTIVE < 99:
        room_ = MAX_PRODUCTIVE - (n_animals + len(plants))
        if room_ < len(plan):
            _rank = {"PASTURE": 0, "COOP": 1, "STRAWBERRY": 2, "MELON": 3, "WHEAT": 4}
            plan = dict(sorted(plan.items(), key=lambda kv: _rank.get(kv[1], 9))[:max(0, room_)])

    planned_melon = sum(1 for v in plan.values() if v == "MELON")''', 1)

    # E7: fertilizer crashes to $1-10 in contested games; 3.5% of all actions
    src = src.replace('''        if t["fertilizer_available"] and prices.get("FERTILIZER", 0) >= FERT_MIN_PRICE:''',
                      '''        if (not NO_FERT and t["fertilizer_available"]
                and prices.get("FERTILIZER", 0) >= FERT_MIN_PRICE):''')

    src = src.replace('LAND_MIN_EMPTY = _tune("LAND_MIN_EMPTY", 8)',
                      'LAND_MIN_EMPTY = _tune("LAND_MIN_EMPTY", 8)\n'
                      'P1_LATE = _tune("P1_LATE", 1)    # keep the engine growing late\n'
                      'P2_OPP  = _tune("P2_OPP", 1)     # prefer markets they are not in\n'
                      'P3_FILL = _tune("P3_FILL", 1)    # put idle tiles to work\n'
                      'MAX_RADIUS = _tune("MAX_RADIUS", 99)         # E2: farm near the shed only\n'
                      'MAX_PRODUCTIVE = _tune("MAX_PRODUCTIVE", 99) # E6: cap total worked tiles\n'
                      'NO_FERT = _tune("NO_FERT", 0)                # E7: skip fertilizer pickup')

    # ---- P1: a late animal does not need a 9x payback, only a profitable one
    old = '''    buyable = [k for k, (rev, _r, cost, dl) in animal_value.items()
               if dl > 0 and rev >= ANIMAL_PAYBACK * cost]
    buyable.sort(key=lambda k: -animal_value[k][1])'''
    new = '''    payback = ANIMAL_PAYBACK
    if P1_LATE:
        # The 9x hurdle is right on day 2 (capital is scarce and compounding).
        # By day 18 it blocks purchases that would still pay for themselves, and
        # our production decays while the opponent's keeps growing.
        payback = max(2.0, ANIMAL_PAYBACK * (1.0 - day / float(FINAL_DAY)))
    buyable = [k for k, (rev, _r, cost, dl) in animal_value.items()
               if dl > 0 and rev >= payback * cost]
    buyable.sort(key=lambda k: -animal_value[k][1])
    if P2_OPP and buyable:
        # Opponent awareness used to REORDER, never to cede: prefer the product
        # they are supplying least.  (Cutting our own output measured negative
        # three separate times.)
        opp_t = obs["farms"][1 - player]["tiles"]
        def _pref(k):
            p = ANIMALS[k]["product"]
            head = _season_drain(p) - _supply_rate(opp_t, p)
            return -(animal_value[k][1] * max(0.2, min(1.5, head / _season_drain(p))))
        buyable.sort(key=_pref)'''
    assert old in src
    src = src.replace(old, new)

    # ---- P3: after the tuned plan runs, put the leftover tiles to work ----
    old = '''    planned_melon = sum(1 for v in plan.values() if v == "MELON")'''
    new = '''    if P3_FILL:
        # main.py's quotas leave ~47 tiles idle all game.  Fill whatever the crew
        # can still service, best-scoring first, re-pricing as we go.
        used_now = set(plan)
        load_now = (n_animals * ANIMAL_LOAD + melon_planted * 1.1
                    + wheat_planted * 1.4 + straw_planted * 1.3
                    + sum(4.5 if v in ("COOP", "PASTURE") else 1.3 for v in plan.values()))
        cap_now = max(n_units, MIN_HANDS + 1) * 24 / ACTIONS_PER_TASK
        cash_now = money - 200 - sum(
            ANIMALS["COW"]["cost"] if v == "PASTURE" else
            (ANIMALS["GOOSE"]["cost"] if v == "COOP" else 80) for v in plan.values())
        extra_fill = {}
        inv_now = obs["market"]["inventory"]
        opp_t2 = obs["farms"][1 - player]["tiles"]
        for spot in empties:
            if spot in used_now or load_now >= cap_now * 0.95:
                continue
            opts = _fill_options(day, prices, max(0.0, cash_now), tiles, opp_t2,
                                 inv_now, extra_fill, prices.get("WHEAT", 25))
            if day > LAST_ANIMAL_BUY_DAY:
                opts = [o for o in opts if not o["struct"]]
            if not opts:
                break
            b = opts[0]
            if b["struct"]:
                plan[spot] = b["struct"]
                if b["struct"] == "COOP":
                    want_coops += 1
                else:
                    want_pastures += 1
                if b["name"] not in buyable:
                    buyable.append(b["name"])
            else:
                plan[spot] = b["name"]
            cash_now -= b["cash"]
            extra_fill[b["product"]] = extra_fill.get(b["product"], 0.0) + b["rate"]
            load_now += b["load"]

    planned_melon = sum(1 for v in plan.values() if v == "MELON")'''
    assert old in src
    src = src.replace(old, new, 1)

    # seed buying must follow the filler, not the old calendar windows
    src = src.replace("    if planned_straw > 0:", "    if planned_straw > 0:")
    src = src.replace('"""Kaggriculture agent.',
                      '"""Kaggriculture agent v2 = main.py + PRD layers (generated by build_agent2.py).\n\n'
                      'P1  late-game engine : the animal payback hurdle decays with the season, so\n'
                      '                       the herd keeps growing instead of stalling at day ~18.\n'
                      'P2  opponent aware   : REORDERS which animal to buy toward the market the\n'
                      '                       opponent is supplying least.  Never reduces our output -\n'
                      '                       ceding measured negative three times.\n'
                      'P3  idle-tile filler : after the tuned quotas run, put the ~47 leftover tiles\n'
                      '                       to work, best $/action first, capped by labour.\n\n'
                      'INHERITED NOTES:', 1)
    open("agent2.py", "w").write(src)
    print("agent2.py:", len(src.splitlines()), "lines")


if __name__ == "__main__":
    build()
