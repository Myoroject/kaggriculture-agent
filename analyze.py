"""Analysis of batch results (results.jsonl)."""
import json
import math
import statistics as st
from collections import defaultdict

ROWS = [json.loads(l) for l in open("results.jsonl")]


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * (c - h), 100 * (c + h))


def fmt(x):
    return f"{x:,.0f}"


def describe(vals):
    vals = sorted(vals)
    n = len(vals)
    return {
        "n": n, "mean": st.mean(vals), "median": st.median(vals),
        "sd": st.pstdev(vals) if n > 1 else 0.0,
        "p05": vals[int(0.05 * n)], "p25": vals[int(0.25 * n)],
        "p75": vals[int(0.75 * n)], "p95": vals[min(int(0.95 * n), n - 1)],
        "min": vals[0], "max": vals[-1],
    }


by = defaultdict(list)
for r in ROWS:
    by[r["matchup"]].append(r)

print(f"=== {len(ROWS)} games ===\n")

# ---------------------------------------------------------------- overall
print("--- score distribution (agent's own bank) ---")
print(f"{'matchup':<14}{'n':>5}{'mean':>10}{'median':>10}{'sd':>9}{'p05':>10}{'p95':>10}{'min':>10}{'max':>10}")
for m, rs in by.items():
    d = describe([r["me"] for r in rs])
    print(f"{m:<14}{d['n']:>5}{fmt(d['mean']):>10}{fmt(d['median']):>10}{fmt(d['sd']):>9}"
          f"{fmt(d['p05']):>10}{fmt(d['p95']):>10}{fmt(d['min']):>10}{fmt(d['max']):>10}")

# ------------------------------------------------------------ head to head
print("\n--- head-to-head vs opponent ---")
print(f"{'matchup':<14}{'n':>5}{'win%':>7}{'95% CI':>16}{'margin':>11}{'+/-SE':>9}{'sig':>5}")
for m, rs in by.items():
    n = len(rs)
    w = sum(r["win"] for r in rs)
    lo, hi = wilson(w, n)
    marg = [r["me"] - r["opp"] for r in rs]
    mean_m = st.mean(marg)
    se = st.pstdev(marg) / math.sqrt(n) if n > 1 else 0
    sig = "yes" if abs(mean_m) > 1.96 * se and (lo > 50 or hi < 50) else "no"
    print(f"{m:<14}{n:>5}{100*w/n:>6.1f}%{f'[{lo:.0f},{hi:.0f}]':>16}"
          f"{fmt(mean_m):>11}{fmt(1.96*se):>9}{sig:>5}")

# ------------------------------------------------------- seat / seed effect
print("\n--- seat effect (mirror match: identical agents) ---")
mir = by.get("mirror", [])
if mir:
    for o in (0, 1):
        sub = [r for r in mir if r["order"] == o]
        w = sum(r["win"] for r in sub)
        print(f"  seat {o}: n={len(sub)}  win {100*w/len(sub):.1f}%  "
              f"mean bank {fmt(st.mean([r['me'] for r in sub]))}")
    marg = [abs(r["me"] - r["opp"]) for r in mir]
    d = describe(marg)
    print(f"  |margin| between identical agents: median {fmt(d['median'])}, "
          f"p95 {fmt(d['p95'])}, max {fmt(d['max'])}")
    sd = st.pstdev([r["me"] - r["opp"] for r in mir])
    print(f"  margin sd = {fmt(sd)}  ->  detecting a $2k edge at 95% needs "
          f"n ~ {math.ceil((1.96*sd/2000)**2)} games; $5k needs "
          f"n ~ {math.ceil((1.96*sd/5000)**2)}")

# ----------------------------------------------------------- money curves
print("\n--- median bank by day (vs_starter) ---")
vs = by.get("vs_starter", [])
if vs:
    days = list(range(0, 30, 3))
    med = [st.median([r["money_curve"][i] for r in vs]) for i in range(len(days))]
    for d, v in zip(days, med):
        bar = "#" * int(40 * v / max(med)) if max(med) else ""
        print(f"  day {d:>2}: {fmt(v):>10}  {bar}")

# --------------------------------------------------------- end-state stats
print("\n--- end-of-season farm (vs_starter, medians) ---")
if vs:
    keys = set()
    for r in vs:
        keys |= set(r["end_census"])
    for k in sorted(keys):
        vals = [r["end_census"].get(k, 0) for r in vs]
        if st.mean(vals) < 0.3:
            continue
        print(f"  {k:<12} median {st.median(vals):>5.0f}   mean {st.mean(vals):>6.1f}   max {max(vals):>4}")
    print(f"  quadrants owned: mean {st.mean([r['quadrants'] for r in vs]):.2f}")

print("\n--- end-of-season market prices (vs_starter vs mirror medians) ---")
if vs and mir:
    items = sorted(vs[0]["end_prices"])
    print(f"{'item':<12}{'vs starter':>12}{'mirror':>10}")
    for it in items:
        a = st.median([r["end_prices"][it] for r in vs])
        b = st.median([r["end_prices"][it] for r in mir])
        print(f"{it:<12}{a:>12,.0f}{b:>10,.0f}")

# ---------------------------------------------------- drivers of the score
print("\n--- what correlates with final bank (vs_starter) ---")


def corr(xs, ys):
    n = len(xs)
    mx, my = st.mean(xs), st.mean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = math.sqrt(sum((a - mx) ** 2 for a in xs))
    dy = math.sqrt(sum((b - my) ** 2 for b in ys))
    return num / (dx * dy) if dx and dy else 0.0


if vs:
    y = [r["me"] for r in vs]
    feats = {
        "cows": lambda r: r["end_census"].get("COW", 0),
        "sheep": lambda r: r["end_census"].get("SHEEP", 0),
        "geese": lambda r: r["end_census"].get("GOOSE", 0),
        "animals": lambda r: sum(r["end_census"].get(k, 0) for k in ("COW", "SHEEP", "GOOSE")),
        "weeds": lambda r: r["end_census"].get("weed", 0),
        "empty": lambda r: r["end_census"].get("empty", 0),
        "quadrants": lambda r: r["quadrants"],
        "shops": lambda r: r["shops"],
        "milk_price": lambda r: r["end_prices"]["MILK"],
        "wool_price": lambda r: r["end_prices"]["WOOL"],
        "melon_price": lambda r: r["end_prices"]["MELON"],
        "wheat_price": lambda r: r["end_prices"]["WHEAT"],
    }
    out = sorted(((corr([f(r) for r in vs], y), name) for name, f in feats.items()),
                 key=lambda t: -abs(t[0]))
    for c, name in out:
        print(f"  {name:<12} r = {c:+.2f}")

# ------------------------------------------------------------ worst games
print("\n--- worst 5 games (vs_starter) ---")
for r in sorted(vs, key=lambda r: r["me"])[:5]:
    cen = {k: v for k, v in r["end_census"].items() if k not in ("locked",)}
    print(f"  seed {r['seed']} seat {r['order']}: {fmt(r['me']):>9}  {cen}")
