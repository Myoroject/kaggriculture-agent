"""Head-to-head: agent2.py (KG_* env overrides) vs pinned main.py.

Same pattern as h2h.py but for agent2 vs main. Seeds 2101-2105 (distinct
from h2h.py's 11-14 and PRD's held-out 5000+ block) x both seat orders.
"""
import json, os, statistics, subprocess, sys, itertools

RUNNER = r'''
import json, sys
from kaggle_environments import make
seeds = json.loads(sys.argv[1])
res = []
errs = 0
for sd in seeds:
    for order in (0, 1):
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": sd})
        agents = ["agent2.py", "main.py"] if order == 0 else ["main.py", "agent2.py"]
        env.run(agents)
        r = [s.reward or 0 for s in env.steps[-1]]
        # check for swallowed exceptions: any step where our agent's status != ACTIVE/DONE
        for s in env.steps[-1]:
            st = s.status
            if st not in ("ACTIVE", "DONE"):
                errs += 1
        res.append([r[order], r[1 - order]])
print("RESULT" + json.dumps({"pairs": res, "errs": errs}))
'''

def h2h(cfg, seeds):
    env = dict(os.environ)
    for k, v in cfg.items():
        env["KG_" + str(k)] = str(v)
    p = subprocess.run([sys.executable, "-c", RUNNER, json.dumps(seeds)],
                       capture_output=True, text=True, env=env)
    for line in p.stdout.splitlines():
        if line.startswith("RESULT"):
            return json.loads(line[6:])
    print("NO RESULT. stdout tail:", p.stdout[-2000:], "stderr tail:", p.stderr[-2000:])
    return None

def run_experiment(label, cfg, seeds=(2101, 2102, 2103, 2104, 2105)):
    data = h2h(cfg, list(seeds))
    if not data:
        print(f"{label}: FAILED TO RUN")
        return None
    res = data["pairs"]
    errs = data["errs"]
    wins = sum(1 for a, b in res if a > b)
    losses = sum(1 for a, b in res if a < b)
    ties = len(res) - wins - losses
    margin = statistics.mean(a - b for a, b in res)
    print(f"{label}: cfg={cfg} wins {wins}/{len(res)} losses {losses} ties {ties}  "
          f"margin {margin:+,.0f}  errs={errs}", flush=True)
    return dict(label=label, cfg=cfg, res=res, wins=wins, losses=losses,
               ties=ties, margin=margin, errs=errs)

if __name__ == "__main__":
    grid = json.loads(sys.argv[1])
    seeds = [2101, 2102, 2103, 2104, 2105]
    keys = list(grid)
    for combo in itertools.product(*(grid[k] for k in keys)):
        cfg = dict(zip(keys, combo))
        run_experiment(str(cfg), cfg, seeds)
