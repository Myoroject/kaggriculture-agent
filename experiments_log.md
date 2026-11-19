# Kaggriculture agent2.py experiment log

`agent2.py` is a fresh copy of `main.py` with every experiment below behind
an independent `KG_EXP_*` env flag, all defaulting OFF. `main.py` was not
touched. Harness: `h2h2.py` (same pattern as `h2h.py`), seeds 2101-2105 x
both seat orders = 10 games/experiment, `episodeSteps: 720`.

Exception check: `h2h2.py`'s runner inspects `env.steps[-1][*].status` after
every game and counts anything other than `ACTIVE`/`DONE` as an error. All
17 runs below (no-op gate + 16 experiments) reported `errs=0` — no turn
threw and got silently swallowed.

## No-op gate (REQUIRED before any experiment)

All `EXP_E*` flags off. Ran `agent2.py` vs `main.py` on seed 2101, both seat
orders, and compared to `main.py` vs `main.py` self-play on the same seed.

| Match | Result |
|---|---|
| main.py vs main.py (seed 2101) | `[107721.0, 104778.0]` |
| agent2.py vs main.py (seed 2101, agent2 seat 0) | `[107721.0, 104778.0]` |
| main.py vs agent2.py (seed 2101, agent2 seat 1) | `[107721.0, 104778.0]` |

**Byte-identical** in both seat orders. Gate **PASSED** — proceeded to
experiments.

## Results

All records are agent2 (variant) vs main.py, 10 games (5 seeds x 2 seat
orders), margin = mean(agent2_score − main_score).

| Exp | Hypothesis | W/L/T | Margin | Verdict | Implementation note |
|---|---|---|---|---|---|
| E1 | Optimal (Hungarian) matching beats greedy nearest-pair assignment | 8/2/0 | **+3,259** | **CONFIRMED** | Replaced the pass-2 greedy sort with `scipy.optimize.linear_sum_assignment` (`_assign_hungarian`). Approximation: cost matrix capped to `max(4*n_free_units, 40)` cheapest-priority open tasks to keep it small (workers are usually far outnumbered by open tasks); infeasible (req not met) pairs get cost 1e6 instead of being omitted, since scipy needs a dense matrix. Falls back to the old greedy pass if scipy import fails. |
| E2 | Radius cap (never farm beyond distance N=4 from shed) reduces travel waste | 2/8/0 | **-5,970** | **REFUTED** | Filtered `empties` to `dist(centre) <= 4` before planning. Cutting off outer tiles just shrinks the farm — capacity was travel-bound, not tile-bound; losing footprint hurt more than it saved. |
| E3 | Raising the DROP/carry threshold from 10 to 20 reduces trips to the shed | 2/8/0 | **-2,813** | **REFUTED** | Raised the idle-unit junk threshold that triggers "walk back to shed to drop" from a hardcoded 10 to `E3_CARRY=20`. Units hoard junk longer, delaying reinvestment/selling and blocking inventory slots needed for WHEAT/FERTILIZER pickups. |
| E4 | Boosting priority for tasks on tiles with 2+ queued ops keeps a worker finishing that tile before moving on | 1/9/0 | **-8,174** | **REFUTED (strongly)** | Applied a flat `pri -= 5` to any task whose target tile has >=2 queued tasks this turn. This uniformly disrupted the carefully-tuned priority ordering across unrelated task types sharing a tile (e.g. FEED pri 2/9 vs HARVEST pri 12 vs COLLECT_FERTILIZER pri 11 all landing on the same animal tile), causing mis-sequencing (e.g. HARVEST jumping ahead of FEED). The existing dist=0 term in the greedy score already captures most of the same-tile-stickiness benefit; this flag mostly just broke ordering. |
| E5a | Melon 9->6 tiles | 5/5/0 | +0 | **NO EFFECT** | `KG_MELON_TILES=6` (already tunable in main.py, no code change needed). |
| E5b | Melon 9->3 tiles | 3/3/4 | +0 | **NEUTRAL/MIXED** | `KG_MELON_TILES=3`. 4 exact ties is notable — melon's contribution to final score variance shrinks a lot at 3 tiles. |
| E5c | Melon 9->0 tiles | 4/4/2 | +0 | **NEUTRAL/MIXED** | `KG_MELON_TILES=0`. Essentially a wash across 5 seeds; melon is a real but not dominant profit centre — cutting it doesn't measurably hurt OR help within noise at this sample size. |
| E6a | Hard cap total productive tiles at 20 | 0/10/0 | **-23,556** | **REFUTED (strongly)** | `EXP_E6`+`E6_CAP=20`: once `n_animals+len(plants) >= cap`, truncate the tile plan (worst-ranked types dropped first: WHEAT, then MELON, then STRAWBERRY, then COOP/PASTURE last). Main.py's own footprint is already ~20-25 productive tiles some turns; capping below its natural growth path starves the farm. |
| E6b | Cap at 18 | 0/10/0 | **-25,433** | **REFUTED (strongly)** | Same mechanism, `E6_CAP=18`. Worse than E6a as expected (tighter cap). |
| E6c | Cap at 16 | 0/10/0 | **-30,660** | **REFUTED (strongly)** | Same mechanism, `E6_CAP=16`. Monotonically worse as the cap tightens — strong evidence main.py is *not* over-expanding; if anything it should expand more (consistent with the P3-style "idle-tile filler" ideas noted as future work, not tested here). |
| E7 | Dropping COLLECT_FERTILIZER entirely frees labour for higher-value tasks | 0/10/0 | **-35,610** | **REFUTED (very strongly)** | Skipped the `add(11, ..., ["COLLECT_FERTILIZER"])` call entirely. Catastrophic — fertilizer feeds the STRAWBERRY fertilize cycle; losing it guts strawberry yield. Consistent with main.py's own docstring note that ablating CARE cost -$45.3k; this is the same family of "don't skip maintenance actions" result. |
| E8 | Spreading premium (MELON/STRAWBERRY/WOOL/MILK) sales across days instead of dumping avoids eating the glut curve | 3/7/0 | **-2,024** | **REFUTED** | Capped per-turn SELL qty for the 4 premium items to `E8_CAP=12`, carrying remainder in shed (bounded by main.py's existing shed-pressure sell-floor logic). Matches main.py's own documented refuted finding ("throttling sales to hold the price up: -$1.4k to -$1.8k; the shed cap bins the held produce and delays reinvestment") — this experiment reproduces that result under a different throttle mechanism. |
| E9 | Buying wheat early while cheap (stockpile) beats buying at market rate as-needed | 8/2/0 | **+7,558** | **CONFIRMED (strongly)** | When `wp<=30` and shed has room, on top of the existing feed-wheat buy, top up toward a 60-unit stockpile (bounded by the 100-item shed cap). Big win — avoids paying the $25->$59 price climb on wheat bought piecemeal all game. |
| E10 | Pre-positioning idle workers toward known upcoming work beats idling | 5/5/0 | -924 | **MIXED/no clear effect** | Idle units with 0 junk and `EXP_E10` on step toward the nearest tile with a plant or animal (`plants + animals` list) instead of `PASS`. Roughly a wash — slightly negative but well within noise at n=10; the extra movement doesn't clearly pay for itself, possibly because "idle" units are already usually near active tiles due to the sticky/greedy assignment pulling them there anyway. |
| E11 | Re-opening the animal-purchase gate late (re-derive `room` off current spare capacity, ignoring pre-day-18 pinning) grows the herd further | 5/5/0 | +0 | **NO MEASURABLE EFFECT** | After `day > MELON_LAST_PLANT_DAY`, took `eff_room = max(room, int(capacity/ANIMAL_LOAD))` instead of the live `room` alone. Essentially neutral over 10 games — this implementation of the "fix" did not reproduce a strong freeze-then-reopen dynamic; main.py's `room` formula already recomputes fresh from current `spare` every turn (no stale caching was found in the code), so the mechanical bug as originally diagnosed may be softer than the trace suggested, or this approximation of "current spare capacity" doesn't diverge from main.py's own formula often enough to matter. |
| E12 | Hard target 8 cow + 4 sheep bought by day 8, then stop entirely (PRD/2883-notebook evidence) | 6/4/0 | **-1,263** | **MIXED / net REFUTED** | First 8 days: restrict `buyable` to whichever of COW/SHEEP is still short of its 8/4 target and cap purchase slots to the remaining gap; after day 8 (or once 8/4 is reached), `buyable=[]` — zero further animal purchases for the rest of the game, overriding the normal payback-based logic entirely. Won more individual games (6) than it lost (4) but the losses were large enough to make the mean margin negative — stopping the herd hard at 8/4 leaves money on the table in games where cash/capacity headroom persists past day 8. |

## E11 vs E12 (competing hypotheses)

These two are mutually exclusive by design (E11 = keep the gate open and buy
opportunistically to day 24; E12 = hard-stop the herd at 8 cow + 4 sheep by
day 8). Measured head-to-head against the same opponent (`main.py`) and the
same seed block:

- **E11 (keep buying opportunistically): margin +0 (5/10)** — statistically a wash, i.e. no worse than main.py's own (already-opportunistic) policy.
- **E12 (hard stop at 8/4): margin -1,263 (6/10)** — net negative despite a winning individual-game record; the loss games were more severe than the win games.

**Read:** neither confirms its hypothesis outright, but E11 comes out ahead
of E12 in this comparison — continuing to buy animals opportunistically
through day 24 is *at worst* neutral, while committing to a hard stop at
8 cow + 4 sheep measured net negative. This is some evidence against the
PRD/2883-notebook claim that an early hard-capped 8/4 herd is the winning
core, at least when transplanted directly into main.py's decision framework
(the notebook's bot may differ in other ways — land, labour, crop mix — that
make the hard cap work in its own context but not in main.py's).

## What's worth promoting into main.py

- **E1 (Hungarian matching)**: +3,259 margin, 8/10 wins, and it's a
  drop-in replacement for the existing greedy pass-2 assignment with no
  other side effects. Strongest, cleanest candidate for promotion.
- **E9 (wheat stockpile early)**: +7,558 margin, 8/10 wins, the largest
  effect size measured in this batch, and mechanically simple (a few lines
  in `_market_orders`). Second strongest candidate.

Everything else either refuted cleanly (E2, E3, E4, E6a/b/c, E7, E8) or
landed in statistical-noise territory (E5a/b/c, E10, E11, E12) and should
not be promoted as-is. E4 and E7 in particular refuted hard enough (-$8k
and -$35k) that they also serve as useful negative confirmations of things
already encoded correctly in main.py's tuned priority ordering.

## Caveats

- n=10 per experiment (5 seeds x 2 orders) is enough to see the large
  effects (E1, E6, E7, E9) clearly but is thin for anything with a margin
  under ~$3k (E5, E10, E11, E12) — those verdicts should be read as
  "no strong signal at this sample size," not "proven neutral."
- E1's Hungarian matching is an approximation (task list capped, infeasible
  pairs given a large finite cost rather than excluded) for performance; a
  literal full bipartite match over every open task every turn was not
  benchmarked for speed and could differ slightly.
- E4's and E11's implementations are one reasonable reading of an
  underspecified hypothesis each (see their notes above) — a different
  encoding of "finish the tile" or "reopen the gate" could plausibly change
  the verdict, especially for E11 where no clear mechanism for a stale
  freeze was found in the current code.

---

## E10 — animal payback gate + forecast species ranking (REFUTED)

**Hypothesis.** `ANIMAL_PAYBACK = 9.0` is a *fixed* multiple, so when milk
crashes the cows stop clearing it and the agent buys nothing while tiles sit
empty. Ladder evidence: across 37 v4 games, final milk price correlates +0.67
with our own final bank; milk-crashed games average $68,078 vs $93,277 (a $25k
swing) at identical cow counts, and we have never fielded a single goose
despite EGG being the one product with a log above-curve that cannot crash.

**Build.** Two knobs in `season.py`, both exact no-ops at default (verified
byte-identical to `main.py` on seeds 2000/2001): `PAYBACK_LATE` decays the gate
linearly from 9.0 at day 8 to a target at day 24; `RANK_FORECAST` ranks species
by projected price at first yield (own herd + deterministic town drain only, no
opponent modelling — the refuted H-experiment forecast-fed the *gate*, this
feeds only the *ranking*).

**Result — 272 games vs pinned `baseline.py`, 34 seeds x both seat orders:**

| variant | n | win% | 95% CI | margin | +/- | seeds |
|---|---|---|---|---|---|---|
| G_late3 | 68 | 47.1% | [36,59] | +282 | 1,225 | 8/34 |
| G_late3_fc | 68 | 47.1% | [36,59] | +248 | 1,232 | 8/34 |
| FC_only | 68 | 48.5% | [37,60] | -23 | 893 | 0/34 |
| G_late5 | 68 | 42.6% | [32,54] | -366 | 1,127 | 3/34 |

All flat; every CI crosses 50%. **Do not promote.**

**Why it failed — the mechanism, not the tuning.** Zero geese and zero coops
were built in all 272 games. The gate level was never what blocked them: the
gate is measured against *lifetime* revenue, and a goose's horizon
(`days_left = 29 - day - 4`) collapses faster than a decaying gate falls.

```
 day  gate  need($)  goose lifetime rev @ EGG=55   passes
   0   9.0     2700                        2750     YES
   8   9.0     2700                        1870      no
  16   6.0     1800                         990      no
  24   3.0      900                         110      no
```

EGG opens at base $50 (2 x 50 x 25 = 2,500 < 2,700, fails) and only reaches a
median $70 late in the game, by which point the horizon is gone. The goose
window is empty: it needs a high EGG price *and* a long horizon, and those two
never co-occur. Relaxing the gate bought more cows and sheep instead (avg empty
tiles 39.7 -> 35.4), which is roughly value-neutral.

`RANK_FORECAST` alone is very nearly a no-op: 33 of 34 seed-pairs came back
*exactly* zero, i.e. the projected price never changed a single ranking
decision. Today's price and the projected price agree on the ordering because
milk collapses so early that cows are already ranked below sheep either way.

**Methodological finding (important).** Median end-of-game MILK price in local
self-play is **$7** — milk is fully crashed in essentially 100% of local games,
versus 46% of ladder games. Both clones are cow-heavy, so they saturate milk
identically and the baseline suffers exactly as much as the variant. **Local
self-play structurally cannot measure any milk-saturation hypothesis.** Testing
this class of idea needs an opponent that does *not* sell milk (a crop/wool
archetype sparring partner), otherwise the effect is differenced away.

**What this does not refute.** Geese may still be correct as a *day-0 build*
decision — the one moment the horizon is long enough — which is a starting-mix
experiment, not a gate experiment. It competes directly for the early capital
whose starvation is already a documented loss ($500 sheep starving $400 cows).
