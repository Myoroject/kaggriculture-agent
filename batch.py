"""Batch runner: many episodes in parallel worker processes, JSONL telemetry out.

  python batch.py plan          # write jobs/*.json (724 games)
  python batch.py run           # execute the plan across workers
  python batch.py worker A B    # internal: run one chunk
"""
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
JOBDIR = os.path.join(HERE, "jobs")
OUT = os.path.join(HERE, "r_gate.jsonl")
WORKERS = 7

# matchup -> (opponent file, config overrides for main.py, number of seeds)
AGENT = "season.py"
# Experiment 5: the animal payback gate + species ranking.
#   PAYBACK_LATE  - gate decays from ANIMAL_PAYBACK(9.0) at day 8 to this
#                   value at LAST_ANIMAL_BUY_DAY(24).  9.0 == exact no-op.
#   RANK_FORECAST - rank species by projected price at first yield (own herd
#                   + deterministic town drain only; no opponent modelling).
PLAN = [
    ("G_late3",    "baseline.py", dict(PAYBACK_LATE=3.0),                     34),
    ("G_late5",    "baseline.py", dict(PAYBACK_LATE=5.0),                     34),
    ("G_late3_fc", "baseline.py", dict(PAYBACK_LATE=3.0, RANK_FORECAST=1),    34),
    ("FC_only",    "baseline.py", dict(RANK_FORECAST=1),                      34),
]
CHUNK = 13


def census(farm):
    c = {}
    for row in farm["tiles"]:
        for t in row:
            if t is None:
                k = "empty"
            elif t == "LOCKED":
                k = "locked"
            elif t.get("kind") == "PLANT":
                k = t["crop"]
            elif t.get("kind") == "WEED":
                k = "weed"
            elif t.get("animal"):
                k = t["animal"]
            else:
                k = t["kind"]
            c[k] = c.get(k, 0) + 1
    return c


def worker(jobfile, outfile):
    from kaggle_environments import make
    spec = json.load(open(jobfile))
    for k, v in spec["config"].items():
        os.environ["KG_" + k] = str(v)
    rows = []
    for seed, order in spec["jobs"]:
        mine = spec.get("agent", "main.py")
        agents = [mine, spec["opp"]] if order == 0 else [spec["opp"], mine]
        t0 = time.time()
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run(agents)
        last = env.steps[-1]
        rew = [s.reward or 0 for s in last]
        me, opp = rew[order], rew[1 - order]
        obs = last[order].observation
        money_curve = []
        for d in range(0, 30, 3):
            idx = min(d * 24, len(env.steps) - 1)
            money_curve.append(env.steps[idx][order].observation["farms"][order]["money"])
        rows.append({
            "matchup": spec["name"], "config": spec["config"], "seed": seed,
            "order": order, "me": me, "opp": opp, "win": int(me > opp),
            "tie": int(me == opp), "secs": round(time.time() - t0, 1),
            "money_curve": money_curve,
            "end_census": census(obs["farms"][order]),
            "end_prices": dict(obs["market"]["prices"]),
            "quadrants": len(obs["farms"][order]["unlocked_quadrants"]),
            "shops": len(obs["town"]["unlocked_shops"]),
        })
        del env
    with open(outfile, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def plan():
    os.makedirs(JOBDIR, exist_ok=True)
    for f in os.listdir(JOBDIR):
        os.remove(os.path.join(JOBDIR, f))
    chunks, total = [], 0
    for name, opp, cfg, n_seeds in PLAN:
        jobs = [(2000 + i, o) for i in range(n_seeds) for o in (0, 1)]
        total += len(jobs)
        for i in range(0, len(jobs), CHUNK):
            part = jobs[i:i + CHUNK]
            path = os.path.join(JOBDIR, f"{name}_{i//CHUNK}.json")
            json.dump({"name": name, "opp": opp, "config": cfg, "jobs": part,
                       "agent": AGENT}, open(path, "w"))
            chunks.append(path)
    print(f"{total} games in {len(chunks)} chunks")
    return chunks


def run():
    chunks = plan()
    t0 = time.time()
    done = [0]

    def go(path):
        out = path.replace(".json", ".out")
        p = subprocess.run([sys.executable, os.path.abspath(__file__), "worker", path, out],
                           capture_output=True, text=True, cwd=HERE)
        done[0] += 1
        if not os.path.exists(out):
            print("FAILED", path, p.stderr[-800:], flush=True)
        else:
            print(f"[{done[0]}/{len(chunks)}] {os.path.basename(path)} "
                  f"({time.time()-t0:.0f}s)", flush=True)
        return out

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        outs = list(ex.map(go, chunks))
    with open(OUT, "w") as f:
        for o in outs:
            if os.path.exists(o):
                f.write(open(o).read())
    n = sum(1 for _ in open(OUT))
    print(f"wrote {n} rows to {OUT} in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "worker":
        worker(sys.argv[2], sys.argv[3])
    elif cmd == "plan":
        plan()
    else:
        run()
