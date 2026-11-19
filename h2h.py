"""Head-to-head: variant (KG_* env overrides) vs pinned baseline.py."""
import json, os, statistics, subprocess, sys, itertools

RUNNER = r'''
import json, sys
from kaggle_environments import make
seeds = json.loads(sys.argv[1])
res = []
for sd in seeds:
    for order in (0, 1):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": sd})
        agents = ["main.py", "baseline.py"] if order == 0 else ["baseline.py", "main.py"]
        env.run(agents)
        r = [s.reward or 0 for s in env.steps[-1]]
        res.append([r[order], r[1 - order]])
print("RESULT" + json.dumps(res))
'''

def h2h(cfg, seeds):
    env = dict(os.environ)
    for k, v in cfg.items():
        env["KG_" + k] = str(v)
    p = subprocess.run([sys.executable, "-c", RUNNER, json.dumps(seeds)],
                       capture_output=True, text=True, env=env)
    for line in p.stdout.splitlines():
        if line.startswith("RESULT"):
            return json.loads(line[6:])
    print(p.stdout[-1500:], p.stderr[-1500:]); return []

if __name__ == "__main__":
    grid = json.loads(sys.argv[1])
    seeds = [11, 12, 13, 14]
    keys = list(grid)
    for combo in itertools.product(*(grid[k] for k in keys)):
        cfg = dict(zip(keys, combo))
        res = h2h(cfg, seeds)
        if not res:
            continue
        wins = sum(1 for a, b in res if a > b)
        margin = statistics.mean(a - b for a, b in res)
        mine = statistics.mean(a for a, _ in res)
        print(f"{cfg}: wins {wins}/{len(res)}  margin {margin:+,.0f}  mine {mine:,.0f}", flush=True)
