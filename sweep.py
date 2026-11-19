"""Parameter sweep for the Kaggriculture agent (uses KG_* env overrides)."""
import itertools
import os
import statistics
import subprocess
import sys
import json

RUNNER = r'''
import os, json, sys
from kaggle_environments import make
seeds = json.loads(sys.argv[1])
out = []
for sd in seeds:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": sd})
    env.run(["main.py", "starter"])
    out.append(env.steps[-1][0].reward)
print("RESULT" + json.dumps(out))
'''


def run(cfg, seeds):
    env = dict(os.environ)
    for k, v in cfg.items():
        env["KG_" + k] = str(v)
    p = subprocess.run([sys.executable, "-c", RUNNER, json.dumps(seeds)],
                       capture_output=True, text=True, env=env)
    for line in p.stdout.splitlines():
        if line.startswith("RESULT"):
            return json.loads(line[6:])
    print(p.stdout[-2000:], p.stderr[-2000:])
    return [0]


def sweep(grid, seeds=(1000, 1001)):
    keys = list(grid)
    rows = []
    for combo in itertools.product(*(grid[k] for k in keys)):
        cfg = dict(zip(keys, combo))
        scores = run(cfg, list(seeds))
        m = statistics.mean(scores)
        rows.append((m, cfg, scores))
        print(f"{m:>10,.0f}  {cfg}  {[f'{s:,.0f}' for s in scores]}", flush=True)
    rows.sort(reverse=True, key=lambda r: r[0])
    print("\nbest:")
    for m, cfg, sc in rows[:5]:
        print(f"{m:>10,.0f}  {cfg}")
    return rows


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "capacity"
    grids = {
        "capacity": {"ACTIONS_PER_TASK": [2.5, 3.5, 5.0], "MAX_HANDS": [10, 13]},
        "melon": {"MELON_TILES": [10, 13, 16, 20]},
        "hands": {"MAX_HANDS": [11, 12, 13, 14], "HAND_DIVISOR": [8.0, 10.0]},
        "fert": {"USE_MELON_FERT": [0, 1], "MELON_LAST_DAY": [18, 20]},
        "stock": {"COW_QUOTA": [0, 2, 3], "SHEEP_QUOTA": [0, 2, 3]},
    }
    sweep(grids[which])
