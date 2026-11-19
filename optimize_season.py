"""Idea #1: whole-season plan search.

Searches the season.py knob space with the REAL simulator as the objective,
rather than an analytic model. The marginal-value allocator (EXP_MVA) failed
precisely because its analytic model omitted capital sequencing and travel;
here every candidate is scored by actually playing games against the shipped
V4 main.py, so no modelling error is possible.

Method: hill-climb from the current V4 defaults (which score 0.0 by
definition). Each round perturbs one or two knobs, plays N games x 2 seat
orders, and keeps the candidate only if it beats the incumbent on WIN RATE
(the ladder metric) with margin as the tie-break.

Claims 1a/1b/2a/2b/3/4 are all present as knobs. None is imposed: each
starts at its current-behaviour default and is only adopted if measured
better. Several were previously measured NEGATIVE (E8 bundling -2,024;
front-loaded hiring is the swept optimum), so this design lets the data
overrule the advice rather than the reverse.
"""
import json
import os
import random
import statistics
import subprocess
import sys

SEEDS_TUNE = [2101, 2102, 2103, 2104, 2105, 2106, 2107, 2108]
SEEDS_HOLD = [5001, 5002, 5003, 5004, 5005, 5006, 5007, 5008, 5009, 5010]

RUNNER = r'''
import json, sys
from kaggle_environments import make
seeds = json.loads(sys.argv[1])
res = []
for sd in seeds:
    for order in (0, 1):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": sd})
        agents = ["season.py", "main.py"] if order == 0 else ["main.py", "season.py"]
        env.run(agents)
        r = [s.reward or 0 for s in env.steps[-1]]
        st = [s.status for s in env.steps[-1]]
        bad = sum(1 for x in st if x not in ("ACTIVE", "DONE"))
        res.append([r[order], r[1 - order], bad])
print("RESULT" + json.dumps(res))
'''

# knob: (low, high, is_int)  -- defaults live in season.py itself
SPACE = {
    # -- 1a: hoard premium crops / sell in bundles (E8 measured -2,024) --
    "SELL_HOARD_MIN":    (0, 40, True),
    "SELL_PRICE_MULT":   (0.6, 2.0, False),
    # -- 1b: free animal fertilizer onto crops --
    "FERT_RESERVE_MULT": (0.0, 4.0, False),
    "FERT_ALL_CROPS":    (0, 1, True),
    # -- 2a: grow own wheat vs buy --
    "WHEAT_GROW_MULT":   (0.5, 3.0, False),
    "WHEAT_BUY_CAP":     (25, 58, True),
    # -- 2b: CARE / FEED priority --
    "CARE_PRI":          (2, 14, True),
    "FEED_PRI":          (2, 14, True),
    # -- 3: hire spreading vs front-loading --
    "HIRE_H0":           (1, 10, True),
    "HIRE_LATER":        (1, 8, True),
    "HIRE_FRAC":         (0.1, 0.6, False),
    # -- 4: pivot to unlocked town shops (new capability) --
    "SHOP_BIAS":         (0.0, 2.0, False),
    # -- late-game land refill --
    "LATE_REFILL":       (0, 16, True),
    "LATE_REFILL_DAY":   (15, 26, True),
    # -- core season plan --
    "MELON_TILES":       (0, 16, True),
    "STRAWBERRY_TILES":  (4, 32, True),
    "STRAWBERRY_START_DAY": (6, 20, True),
    "STRAWBERRY_LAST_DAY":  (6, 24, True),
    "WHEAT_LAST_PLANT_DAY": (10, 29, True),
    "MAX_HANDS":         (8, 22, True),
    "HAND_DIVISOR":      (4.0, 14.0, False),
    "ANIMAL_PAYBACK":    (3.0, 16.0, False),
    "LAND_MIN_EMPTY":    (2, 20, True),
}

DEFAULTS = {}  # empty = season.py's own defaults = V4


def play(cfg, seeds):
    env = dict(os.environ)
    for k, v in cfg.items():
        env["KG_" + k] = str(v)
    p = subprocess.run([sys.executable, "-c", RUNNER, json.dumps(seeds)],
                       capture_output=True, text=True, env=env)
    for line in p.stdout.splitlines():
        if line.startswith("RESULT"):
            return json.loads(line[6:])
    sys.stderr.write("NO RESULT\n" + p.stdout[-800:] + p.stderr[-800:] + "\n")
    return None


def score(cfg, seeds):
    res = play(cfg, seeds)
    if not res:
        return None
    bad = sum(r[2] for r in res)
    wins = sum(1 for a, b, _ in res if a > b)
    margin = statistics.mean(a - b for a, b, _ in res)
    return {"wins": wins, "n": len(res), "margin": margin, "errs": bad}


def better(a, b):
    """Win rate first (the ladder metric), margin as tie-break."""
    if a["wins"] != b["wins"]:
        return a["wins"] > b["wins"]
    return a["margin"] > b["margin"]


def perturb(cfg, rng, k=2):
    new = dict(cfg)
    for key in rng.sample(list(SPACE), k):
        lo, hi, is_int = SPACE[key]
        if is_int:
            new[key] = rng.randint(int(lo), int(hi))
        else:
            new[key] = round(rng.uniform(lo, hi), 3)
    # keep the strawberry window coherent
    if "STRAWBERRY_START_DAY" in new and "STRAWBERRY_LAST_DAY" in new:
        if new["STRAWBERRY_LAST_DAY"] < new["STRAWBERRY_START_DAY"]:
            new["STRAWBERRY_LAST_DAY"] = new["STRAWBERRY_START_DAY"]
    return new


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    rng = random.Random(7)
    log = open("season_search.log", "a", encoding="utf-8")

    def emit(s):
        print(s, flush=True)
        log.write(s + "\n")
        log.flush()

    base = score(DEFAULTS, SEEDS_TUNE)
    emit(f"BASELINE (V4 defaults): {base['wins']}/{base['n']} margin {base['margin']:+,.0f} errs={base['errs']}")
    best_cfg, best = dict(DEFAULTS), base

    for i in range(rounds):
        cand = perturb(best_cfg, rng, k=rng.choice([1, 1, 2]))
        s = score(cand, SEEDS_TUNE)
        if s is None:
            emit(f"[{i+1}/{rounds}] FAILED TO RUN {cand}")
            continue
        if s["errs"]:
            emit(f"[{i+1}/{rounds}] REJECT (errs={s['errs']}) {cand}")
            continue
        tag = ""
        if better(s, best):
            best_cfg, best, tag = cand, s, "  <-- NEW BEST"
            with open("season_best.json", "w") as f:
                json.dump({"cfg": best_cfg, "score": best}, f, indent=2)
        changed = {k: v for k, v in cand.items() if DEFAULTS.get(k) != v}
        emit(f"[{i+1}/{rounds}] {s['wins']}/{s['n']} margin {s['margin']:+8,.0f}  {changed}{tag}")

    emit(f"\nBEST on tuning seeds: {best['wins']}/{best['n']} margin {best['margin']:+,.0f}")
    emit(f"BEST cfg: {json.dumps(best_cfg)}")
    hold = score(best_cfg, SEEDS_HOLD)
    if hold:
        emit(f"HELD-OUT (seeds 5001-5010): {hold['wins']}/{hold['n']} margin {hold['margin']:+,.0f} errs={hold['errs']}")
    base_hold = score(DEFAULTS, SEEDS_HOLD)
    if base_hold:
        emit(f"HELD-OUT baseline (V4):     {base_hold['wins']}/{base_hold['n']} margin {base_hold['margin']:+,.0f}")
    emit("DONE")


if __name__ == "__main__":
    main()
