"""Local evaluation harness for Kaggriculture agents."""
import sys
import statistics
from kaggle_environments import make


def run(a, b, seed=None, steps=720, debug=False):
    cfg = {"episodeSteps": steps}
    if seed is not None:
        cfg["seed"] = seed
    env = make("kaggriculture", configuration=cfg, debug=debug)
    env.run([a, b])
    last = env.steps[-1]
    return [s.reward for s in last], env


def match(a, b, n=3, steps=720, verbose=True):
    scores = []
    for i in range(n):
        r, env = run(a, b, seed=1000 + i, steps=steps)
        scores.append(r)
        if verbose:
            print(f"  seed {1000+i}: P0={r[0]:,.0f}  P1={r[1]:,.0f}")
    p0 = [s[0] or 0 for s in scores]
    p1 = [s[1] or 0 for s in scores]
    wins = sum(1 for s in scores if (s[0] or 0) > (s[1] or 0))
    print(f"{a} vs {b}: P0 mean={statistics.mean(p0):,.0f}  P1 mean={statistics.mean(p1):,.0f}  P0 wins {wins}/{n}")
    return scores


def trace(a, b, seed=1000, steps=720, every=24):
    """Print a per-day summary of player 0."""
    _, env = run(a, b, seed=seed, steps=steps)
    for i, st in enumerate(env.steps):
        if i % every != 0:
            continue
        obs = st[0].observation
        farm = obs["farms"][0]
        priv = obs["private"]
        tiles = farm["tiles"]
        counts = {}
        for row in tiles:
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
                    k = t.get("kind")
                counts[k] = counts.get(k, 0) + 1
        shed = {k: v for k, v in priv["shed"].items() if v}
        prices = obs["market"]["prices"]
        px = " ".join(f"{k[:3]}{v}" for k, v in prices.items())
        print(f"day {obs['day']:2d} ${farm['money']:>9,.0f} | {counts} | shed={shed}")
        print(f"        prices: {px}")
    print("final:", [s.reward for s in env.steps[-1]])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "quick"
    if cmd == "quick":
        match("main.py", "starter", n=1)
    elif cmd == "trace":
        trace("main.py", "starter")
    elif cmd == "full":
        match("main.py", "starter", n=3)
        match("main.py", "main.py", n=1)
    elif cmd == "self":
        match("main.py", "main.py", n=1)
