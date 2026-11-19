"""Sparring partner: spar_goose.

A deliberately one-dimensional opponent, used to test whether our findings
survive against strategies that are not copies of ourselves.  Not tuned.
"""
MODE = "wool"

CROPS = {"WHEAT": (10, 2, 4), "CARROT": (20, 2, 3), "MELON": (80, 10, 10)}
SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]


def _dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _step(pos, tgt):
    dx, dy = tgt[0] - pos[0], tgt[1] - pos[1]
    if abs(dx) >= abs(dy):
        return "EAST" if dx > 0 else ("WEST" if dx < 0 else ("SOUTH" if dy > 0 else "NORTH"))
    return "SOUTH" if dy > 0 else ("NORTH" if dy < 0 else ("EAST" if dx > 0 else "WEST"))


def _play(obs):
    me = obs["farms"][obs["player"]]
    tiles, day, hour = me["tiles"], obs["day"], obs["hour"]
    priv, shed = obs["private"], obs["private"]["shed"]
    n = len(tiles)
    units = [tuple(me["farmer"])] + [tuple(p) for p in me["hands"]]
    invs = priv["inventories"]
    uinv = [dict(invs[i]) if i < len(invs) else {} for i in range(len(units))]
    home = [t for t in SHED if tiles[t[1]][t[0]] != "LOCKED"] or [SHED[0]]

    # ---- market ----
    mk = []
    for item, q in shed.items():
        if q > 0 and item not in ("GOOSE", "COW", "SHEEP") and not (MODE == "wool" and item == "WHEAT"):
            mk.append(["SELL", item, q])
    if hour <= 1 and me["hires_today"] < 10:
        mk += [["HIRE"]] * (10 - me["hires_today"])
    money = me["money"]
    empties = [(x, y) for y in range(n) for x in range(n) if tiles[y][x] is None]
    if MODE in ("melon", "crops", "land"):
        crop = "MELON" if MODE == "melon" else ("WHEAT" if day % 2 else "CARROT")
        want = min(len(empties), 12) - priv["seeds"].get(crop, 0)
        if want > 0 and money > CROPS[crop][0] * want:
            mk.append(["BUY_SEED", crop, want])
    if MODE == "wool":
        past = sum(1 for r in tiles for t in r
                   if isinstance(t, dict) and t.get("kind") == "PASTURE" and not t.get("animal"))
        n_sheep = sum(1 for r in tiles for t in r
                      if isinstance(t, dict) and t.get("animal") == "SHEEP")
        n_cow = sum(1 for r in tiles for t in r
                    if isinstance(t, dict) and t.get("animal") == "COW")
        held = shed.get("SHEEP", 0) + shed.get("COW", 0)
        if past > 0 and held < 1 and day <= 22:
            if n_sheep < 15 and money > 900:
                mk.append(["BUY_ANIMAL", "SHEEP", 1])
            elif n_cow < 8 and money > 800:
                mk.append(["BUY_ANIMAL", "COW", 1])
        if shed.get("WHEAT", 0) < 3 * (n_sheep + n_cow) and money > 300:
            mk.append(["BUY_PRODUCT", "WHEAT", 8])
    if MODE == "land" and len(me["unlocked_quadrants"]) < 4 and money > 4500:
        mk.append(["BUY_LAND"])

    # ---- jobs ----
    jobs = []
    for y in range(n):
        for x in range(n):
            t = tiles[y][x]
            if t is None or t == "LOCKED":
                continue
            if t.get("kind") == "PLANT":
                c = t["crop"]
                age = day - t["planted_day"]
                ripe = t["yield_units"] >= (6 if c == "MELON" else 4) or age >= CROPS.get(c, (0, 0, 4))[2]
                if ripe and age >= CROPS.get(c, (0, 2, 4))[1]:
                    jobs.append((0, (x, y), ["HARVEST"], None))
                elif not t["watered_today"]:
                    jobs.append((1, (x, y), ["WATER"], None))
            elif t.get("animal"):
                if not t["fed_today"]:
                    jobs.append((0, (x, y), ["FEED"], "WHEAT"))
                if t["yield_units"] >= 2:
                    jobs.append((1, (x, y), ["HARVEST"], None))
                if not t["cared_today"]:
                    jobs.append((2, (x, y), ["CARE"], None))
            elif t.get("kind") == "WEED":
                jobs.append((4, (x, y), ["DIG"], None))
    if MODE == "wool":
        n_past = sum(1 for r in tiles for t in r
                     if isinstance(t, dict) and t.get("kind") == "PASTURE")
        if n_past < 24:
            for p in empties[:2]:
                jobs.append((3, p, ["BUILD_PASTURE"], None))
        for y in range(n):
            for x in range(n):
                t = tiles[y][x]
                if isinstance(t, dict) and t.get("kind") == "PASTURE" and not t.get("animal"):
                    for an in ("SHEEP", "COW"):
                        jobs.append((2, (x, y), ["PLACE", an], an))
    else:
        crop = "MELON" if MODE == "melon" else ("WHEAT" if day % 2 else "CARROT")
        seeds = priv["seeds"].get(crop, 0)
        for p in empties[:seeds]:
            jobs.append((3, p, ["PLANT", crop], None))
    jobs.sort(key=lambda j: j[0])

    # ---- assign ----
    acts = [None] * len(units)
    free = set(range(len(units)))
    used = set()
    for ji, (pri, tgt, act, req) in enumerate(jobs):
        cands = [i for i in free if req is None or uinv[i].get(req, 0) > 0]
        if not cands or ji in used:
            continue
        i = min(cands, key=lambda i: _dist(units[i], tgt))
        free.discard(i)
        used.add(ji)
        acts[i] = list(act) if units[i] == tgt else [_step(units[i], tgt)]
    for i in sorted(free):
        junk = sum(v for k, v in uinv[i].items() if v > 0)
        tgt = min(home, key=lambda h: _dist(units[i], h))
        if units[i] in home:
            free_coop = any(isinstance(t, dict) and t.get("kind") == "COOP" and not t.get("animal")
                            for r in tiles for t in r)
            carrying_animal = uinv[i].get("SHEEP", 0) > 0 or uinv[i].get("COW", 0) > 0
            if junk and not carrying_animal:
                acts[i] = ["DROP"]
            elif MODE == "goose" and free_coop and shed.get("GOOSE", 0) > 0 and not carrying_animal:
                acts[i] = ["PICKUP", "SHEEP" if shed.get("SHEEP", 0) else "COW", 1]
            elif MODE == "wool" and shed.get("WHEAT", 0) > 0 and uinv[i].get("WHEAT", 0) < 6:
                acts[i] = ["PICKUP", "WHEAT", 6]
            else:
                acts[i] = ["PASS"]
        elif junk >= 4 or (MODE == "wool" and not uinv[i].get("WHEAT")
                           and not carrying_animal):
            acts[i] = [_step(units[i], tgt)]
        else:
            acts[i] = ["PASS"]
    return {"farmer": acts[0], "hands": acts[1:], "market": mk[:10]}


def agent(obs, config=None):
    try:
        return _play(obs)
    except Exception:
        try:
            h = len(obs["farms"][obs["player"]]["hands"])
        except Exception:
            h = 0
        return {"farmer": ["PASS"], "hands": [["PASS"]] * h, "market": []}
