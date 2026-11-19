"""Summarise a head-to-head results file: win rate, CI, paired margin."""
import json, math, statistics as st, sys
from collections import defaultdict


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * (c - h), 100 * (c + h)


def report(path):
    R = [json.loads(l) for l in open(path)]
    by = defaultdict(list)
    for r in R:
        by[r["matchup"]].append(r)
    print(f"{'variant':<13}{'n':>4}{'win%':>7}{'95% CI':>13}{'margin':>10}{'+/-':>8}"
          f"{'seeds':>8}{'bank':>10}{'verdict':>9}")
    out = []
    for m, rs in sorted(by.items()):
        n = len(rs)
        w = sum(r["win"] for r in rs)
        lo, hi = wilson(w, n)
        mg = [r["me"] - r["opp"] for r in rs]
        mean = st.mean(mg)
        se = st.pstdev(mg) / math.sqrt(n)
        ps = defaultdict(list)
        for r in rs:
            ps[r["seed"]].append(r["me"] - r["opp"])
        pairs = [st.mean(v) for v in ps.values() if len(v) == 2]
        sw = sum(1 for p in pairs if p > 0)
        v = "WIN" if (lo > 50 and mean > 0) else ("LOSS" if (hi < 50 and mean < 0) else "flat")
        out.append((mean, m, v))
        print(f"{m:<13}{n:>4}{100*w/n:>6.1f}%{f'[{lo:.0f},{hi:.0f}]':>13}{mean:>10,.0f}"
              f"{1.96*se:>8,.0f}{f'{sw}/{len(pairs)}':>8}"
              f"{st.median([r['me'] for r in rs]):>10,.0f}{v:>9}")
    return out


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(f"\n=== {p} ===")
        report(p)
