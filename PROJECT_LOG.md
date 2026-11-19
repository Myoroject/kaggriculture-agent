# Kaggriculture — Full Project Log

**A complete record of this project: what we built, what we learned, what we
proved wrong, and where it stands.**

- **Competition:** Kaggriculture (Kaggle), 4,145 teams, $50,000 prize pool ($5,000
  × top 10), deadline 2026-09-30
- **Submitted agent:** `main.py`, submission `55413960`
- **Ladder rating:** 838 → 844 (top ~44% of the field, rank ≈1,837/4,145)
- **Local games run:** ~4,950 across ~80 experiment batches
- **Ladder games analysed:** 79 real, rated matches
- **Status:** `main.py` is live on the ladder. A v2 rebuild (`agent2.py` / `farmer.py`)
  was attempted and, as of this log, **loses to `main.py` in every configuration
  tried** — that failure, and why, is documented in full below because it is as
  important as anything that worked.

---

## Table of contents

1. [The game, in brief](#1-the-game-in-brief)
2. [Phase 1 — Building the first agent](#2-phase-1--building-the-first-agent)
3. [Phase 2 — Systematic tuning: the 724-game analysis](#3-phase-2--systematic-tuning-the-724-game-analysis)
4. [Phase 3 — Learning the SOP and cleaning the code](#4-phase-3--learning-the-sop-and-cleaning-the-code)
5. [Phase 4 — Reading the getting-started guide](#5-phase-4--reading-the-getting-started-guide)
6. [Phase 5 — The 50-hypothesis sweep](#6-phase-5--the-50-hypothesis-sweep)
7. [Phase 6 — Getting onto Kaggle](#7-phase-6--getting-onto-kaggle)
8. [Phase 7 — Reading the ladder: 12 games, then 79](#8-phase-7--reading-the-ladder-12-games-then-79)
9. [Phase 8 — Reverse-engineering the economy](#9-phase-8--reverse-engineering-the-economy)
10. [Phase 9 — The PRD and the v2 rebuild](#10-phase-9--the-prd-and-the-v2-rebuild)
11. [Phase 10 — Why every v2 attempt lost](#11-phase-10--why-every-v2-attempt-lost)
12. [Phase 11 — Reverse-engineering agent2.py, overfitting check, external research](#12-phase-11--reverse-engineering-agent2py-overfitting-check-external-research)
13. [The hypothesis register — everything tested](#13-the-hypothesis-register--everything-tested)
14. [What we got wrong, in our own words](#14-what-we-got-wrong-in-our-own-words)
15. [Current architecture](#15-current-architecture)
16. [Current goal and next steps](#16-current-goal-and-next-steps)
17. [File index](#17-file-index)

---

## 1. The game, in brief

Two players, a 30-day season (720 turns), a 10×10 farm split into four 5×5
quadrants (only the NW quadrant owned at the start). Each turn every hired
worker takes one action (move, water, harvest, feed, care, build...) and the
player may also submit up to 10 free market orders (buy/sell/hire/expand land).

Crops (wheat, carrot, tomato, strawberry, melon) and animals (goose→egg,
cow→milk, sheep→wool) produce goods that sell into a **shared, dynamic market**:
selling drives the price down, buying or town consumption drives it up, and the
curve is asymmetric per product (steep on one side, forgiving on the other).
Winner = most money in the bank at turn 720. Unsold inventory is worthless.

---

## 2. Phase 1 — Building the first agent

**Starting point:** the official `starter` baseline (a single wheat-loop) scores
about $3,500 over a $3,000 starting bank — barely better than doing nothing.

We read the environment's actual source
(`kaggriculture.py` in the installed package) rather than trusting the docs,
because the docs and the source already disagreed on at least two points (CARE's
bonus mechanics; whether fertilizer can be sold — it can).

**The first working agent** was built as a six-stage pipeline, run every turn:

1. **Census** — walk the 100 tiles once, bucket into animals/plants/weeds/empty.
2. **Land plan** — decide what empty tiles *should become* (wheat/melon/coop/pasture),
   bounded by a labour budget so the farm never plants more than the crew can water.
3. **Task generation** — emit every economically meaningful action this turn
   (`water`, `harvest`, `feed`, `care`...), each tagged with a priority and, where
   relevant, a resource requirement (e.g. `FEED` requires the acting unit to be
   *carrying* wheat, since feed comes from personal inventory, not the shed).
4. **Assignment** — score every (worker, task) pair as `priority × weight + travel
   distance`, sort, assign greedily. A "sticky" rule initially kept a worker on a
   task it was already walking toward, to stop oscillation.
5. **Idle logistics** — leftover workers carry produce home or stand still
   (standing still turned out to matter: an earlier version walked idle units
   back to base "to be ready" and burned ~15% of all actions on nothing).
6. **Market orders** — hires, sells, seed/animal purchases, land — ordered by
   importance and truncated to 10.

**First measured result:** this pipeline beat `starter` **100% of the time**,
roughly $95k–$125k vs $3.5k, in the first batch of local games.

---

## 3. Phase 2 — Systematic tuning: the 724-game analysis

Once the pipeline worked, we ran **724 local games** in parallel (7 worker
processes) across 8 matchups (`starter`, mirror self-play, and 6 single-parameter
variants), then did formal statistical analysis: win-rate with Wilson confidence
intervals, paired-by-seed margins, and noise-floor estimation.

**Key numbers from that batch:**

| Matchup | n | Win rate | Margin |
|---|---|---|---|
| vs `starter` | 200 | 100% | +$109,932 |
| Mirror (self-play) | 120 | 50% | $0 (as expected) |
| `MAX_HANDS=14` | 68 | 86.8% | +$2,222 |

**The critical statistical lesson from this phase:** identical agents on the same
seed finish a median of **$362 apart**, but *variant-vs-baseline* margins had
standard deviations up to **$17,420**. That meant an 8-game test — which is what
we'd been running until this point — could resolve some effects and be a coin
flip on others. This is why every subsequent test used **68 games (34 seeds ×
both seat orders)** as the minimum standard, and why we started reporting
confidence intervals instead of point estimates.

**Findings from this phase (later revised — see Phase 6):**
- CARE is the single most valuable repeatable action (banks +1/day, paid out on
  the next production — a cow yields 3 milk every 2 days when cared for, not 1).
- Melon has explosive $/tile-day but a brutal glut curve — capped at ~9 tiles.
- Distance-aware task assignment was worth **+$22,000** in isolation — travel,
  not action count, was the real bottleneck.
- A "labour budget" (don't plan more tiles than the crew can service) was worth
  **+$9,000** — before it existed, over-planted crops died into weeds.

---

## 4. Phase 3 — Learning the SOP and cleaning the code

At this point we stepped back and documented the **method**, not just the
results, in `SOP.md`. The core discipline that emerged and was followed for
the rest of the project:

```
1. Read the source, not the docs
2. Instrument before optimising (trace day-by-day; don't guess)
3. One hypothesis = one flag, defaulting to NO CHANGE
4. Prove the flag is a no-op at default (byte-identical score on a fixed seed)
5. Run 68 games (34 seeds × both seats) against a PINNED copy of the current best
6. Rank by head-to-head win rate, never by absolute bank
7. Before believing a refutation, check the SHAPE — a catastrophic loss is
   usually a bug, not evidence
8. Promote the winner, then RE-PIN the baseline
9. Write refuted ideas into the code so nobody retries them
```

Two of these rules (7 and 8) were learned the hard way and are documented below
because they each cost real time.

We also did a **code cleanup pass**: `main.py` went from 816 lines with 13 dead
experimental flags (settled questions still branching in the code) down to 669
lines with 16 *tunable numbers* (things worth re-sweeping) and zero dead
branches. The rule applied: *a flag that selects between code paths is dead code
once the question is settled; a flag that scales a number is just a named
constant.*

---

## 5. Phase 4 — Reading the getting-started guide

Buried inside a long chat-transcript file (`Overview and rules.txt`) was an
official "Complete Getting Started Guide" notebook we hadn't fully read. It
independently re-derived several things we'd found empirically, and corrected
two of our own numbers:

| Guide's claim | Our data | Verdict |
|---|---|---|
| CARE banks **+1**/day, not the docs' claimed +2 | Our value model already used +1 | confirmed |
| Cluster around the shed; count MOVE actions — "the number will surprise you" | Compacting the farm layout was worth ~$20k | confirmed independently |
| Shed cap silently bins overflow; a full shed blocks buying | A full shed had silently stalled our engine earlier | confirmed independently |
| Hiring profitable to 16–18 hands/day | We were capped at 12 | led us to raise the cap |
| **"Egg = the money printer," sell unlimited** | We had **zero geese** and were still winning | **later found to be actively wrong for our economy — see Phase 8** |
| **Strawberry: town drains it faster than one farm can supply, ~128 tiles of room** | We grew zero | **partially right (demand exists) but the framing "room = profit" was later disproven — see below** |
| Fertilizer has no town demand — price only falls | Confirmed | led to a fertilizer sell-floor |

This is also where we found the guide's own warning, which we quoted back to
ourselves multiple times over the following weeks and violated anyway at least
twice: *"If a mechanic looks strong on paper and measures terribly, suspect your
implementation before you rewrite the theory."*

---

## 6. Phase 5 — The 50-hypothesis sweep

The user supplied a structured list of 50 hypotheses across 9 categories (labour
optimisation, task prioritisation, farm planning, economics, crop strategy,
animals, market, AI/planning, and meta-methodology). We built a flag for each
testable one and ran **20 variants × 68 games = 1,360 games** in one sweep,
plus answered the 6 meta-questions from the ~2,176 games already on disk.

**The big surprises — where our own earlier tuning had been wrong:**

- **H7 (task-scoring weight):** we had been using `priority × 3 + distance`.
  Sweeping the weight: **×1 beat ×3 by $10,197** (33/34 seeds); ×5 lost $8,211;
  ×10 lost $19,992. We had shipped an unmeasured guess for weeks.
- **H4 (does distance matter less than urgency?):** the opposite was true —
  ignoring distance entirely cost **−$57,174**, more than ignoring urgency
  (−$37,738).
- **H2 (persistent/"sticky" assignment):** originally added to fix oscillation,
  it had become a net **−$3,172** cost once the scored matcher (from H7) existed
  to fix the same problem better. A fix that outlived the bug it fixed.
- **H30 (mixed vs single-species livestock):** decisive. Goose-only: **−$79,720**.
  Sheep-only: −$35,973. Cow-only: −$16,056. The agent needs to rotate species as
  markets saturate.
- **H32 (CARE is the highest-ROI action):** confirmed at scale — removing it
  costs **−$45,327**, the single largest-magnitude effect measured in the
  project.
- **H20 (delay land purchases):** buying land early cost **−$24,739** — labour,
  not land, was the real constraint.
- **H26 (strawberry pays off after some day X):** X = **day 13**, 12 tiles:
  **+$15,473, 100% of 68 games, 34/34 seeds.** (This became one of the two
  headline tuned constants of `main.py` — and later, in Phase 9, we discovered
  it does *not* transfer to a different architecture.)

**Meta-findings (from pooled data, no new games needed):**
- Median margin standard deviation across variants: **$6,432**. 68 games
  resolves effects above ~$5k reliably; below ~$2k, you may need 400+ games.
- **Own final bank is a worse ranking signal than win rate.** One variant
  (`wheat_d15`) had a near-top bank ($95,756) while losing 88% of its games —
  its wins were inflated by a few blowouts.
- Score variance and win rate were essentially uncorrelated (r=+0.15); a
  "risky" variant wasn't a distinct thing, high variance was just a symptom of
  losing.

**A costly bug found in this phase (the value of Rule 7):** the first two
strawberry-timing experiments came back at **−$108,178, 0/34 seeds** — a
seemingly decisive refutation. Both were actually silent crashes: a missing
function argument, then a missing dict key, each swallowed by the agent's own
`try/except` safety net and converted into "plays badly." The tell was the
*shape* of the loss — the farm ended with untouched market prices and unsold
milk, which a genuinely bad strategy doesn't produce. After fixing the bugs,
strawberry-early still lost, but for **$12k, not $108k**, and for the real
economic reason described in Phase 9.

---

## 7. Phase 6 — Getting onto Kaggle

With the local evidence base strong (~3,900 games, no crashes, held-out-seed
validation passed at +$25,150 — actually *better* than the tuned-seed result of
+$23,943, so no overfitting to our own test seeds), we went through the
submission process:

1. Installed the Kaggle CLI.
2. User accepted competition rules on kaggle.com.
3. Hit a **403 Forbidden — "You must Identity Verify your account"** on first
   submit attempt. User completed phone verification.
4. A pasted API token in chat was treated as compromised on sight and never
   written to disk; user regenerated it and saved it directly to
   `~/.kaggle/access_token` themselves (never pasted again).
5. Pre-flight checks before submitting: confirmed `agent` is the **last callable**
   in the file (the #1 cause of silent submission failure — the framework loads
   whichever callable appears last in the file, not necessarily the one named
   `agent`), confirmed the validation self-play run completes with `DONE`/`DONE`
   status, confirmed runtime (~2.8ms/turn/agent, no timeout risk), confirmed file
   size (27KB of a 100MiB cap).
6. Submitted `main.py` as submission `55413960`. Validation passed. Initial
   rating: 600 (the default starting rating).

---

## 8. Phase 7 — Reading the ladder: 12 games, then 79

**First check (12 games):** rating had already moved 600 → 832. A quick replay
pull of the first 6 games showed a 3W–3L record and revealed the ladder market
behaves nothing like local self-play (melon crashed to $20, milk to $50 — vs
$280 in our local sims). This raised the first serious concern: our tuned
constants might not transfer.

**Correction — the user asked whether it had really only played 12 games.**
It had not: **79 rated games** had actually completed. We built a harvesting
pipeline (`harvest.py`) that downloads each 20MB replay, extracts a lightweight
JSON summary (final money, farm composition, prices, a money curve every 3
days), and deletes the replay — keeping disk flat while retaining full history
across all 79 games.

**Full 79-game record: 42W–37L (53.2%).** Rating stabilised around **838**.

**Where that actually sits — checked against the full leaderboard (4,145
teams):** rank **≈1,837 (top 44%)**. Median score on the leaderboard is 737; the
top score is 3,235. A 53% win rate is not a strong result — it's a rating
*equilibrium*, meaning the matchmaker has found our true level and it will not
climb further without a structurally different agent.

**Form drifted down as opponents got stronger:**

| Games (chronological) | Record | Median bank |
|---|---|---|
| 1–20 | 11W–9L (55%) | $85,082 |
| 21–40 | 13W–7L (65%) | $73,044 |
| 41–60 | 9W–11L (45%) | $75,278 |
| 61–79 | 9W–10L (47%) | $68,785 |

**Two beliefs we'd held from local testing were disproven by the ladder:**

1. *"Ten geese would have won every game we lost"* — false. Opponents **with**
   geese had a median bank of $53,680; opponents **without**, $76,570. Geese
   correlated **−0.32** with final bank, the strongest negative signal in the
   dataset. We beat goose-farming opponents 73% of the time.
2. *"~47 empty tiles is our biggest waste"* — false. Top farms (≥$90k) averaged
   **50.3** empty tiles; weak farms averaged 41.8. The strongest farm we
   faced left 56 tiles empty. Filling land was never the goal.

**Our farm was statistically identical whether we won or lost** — same cow
count, same sheep count, same 11–12 strawberry tiles, always zero geese, always
~47 empty tiles, in all 79 games. The agent doesn't adapt; results depended
entirely on what the opponent happened to do.

**The single most important structural finding of the whole project, in
response to the direct question "why do we lose":**

> **We build a large early lead and then lose it in the last third of the
> season.**

| Day (median gap, us − them, in games we lost) | 9 | 12 | 15 | 18 | 21 | 24 | 27 |
|---|---|---|---|---|---|---|---|
| Gap | −46 | **+10,625** | +10,656 | +6,597 | +1,678 | −4,252 | **−8,151** |

Against the strongest opponents specifically: they are **4× behind us on day
12** and finish **25% ahead**. Our melon rush is a one-time windfall; their
livestock **compounds**. A windfall decays after harvest; an engine accelerates.

**Chronologically, by day 18 we're leading in 69/79 games (87%). By day 27,
only 39/79 (49%).** We win the day 9–12 block decisively (+$16,774 vs their
+$4,297 — the melon payday) and then **lose every subsequent 3-day block**.

---

## 9. Phase 8 — Reverse-engineering the economy

Rather than continue chasing individual opponents (which the user explicitly
flagged as a trap — "if new competitors come we lose again"), we computed the
**size of the game itself**.

The town is the only buyer that never saturates: it removes a fixed amount of
product per day for free, regardless of price. Selling exactly that amount
holds market inventory steady and the price at base. That defines the
**sustainable extraction rate — the theoretical size of the entire economy**:

| Product | Units the town buys over 30 days | $ at base price | Share of the economy |
|---|---|---|---|
| **Milk** | 437 | $69,920 | 22.9% |
| **Wool** | 338 | $67,600 | 22.2% |
| **Strawberry** | 536 | $64,320 | 21.1% |
| Melon | 140 | $35,000 | 11.5% |
| Tomato | 338 | $20,280 | 6.6% |
| Egg | 338 | $16,900 | 5.5% |
| Wheat | 635 | $15,875 | 5.2% |
| Carrot | 437 | $15,295 | 5.0% |
| **Total** | 3,199 | **$305,190** | |

**Split two ways: $152,595 each, if both farms only sell into demand.**

The best real farm we faced, khalid harouach, scored **$147,569 — 97% of the
theoretical half-share.** Our median across 79 games: **$75,564 — 50%.**

This reframed everything:

- **Milk + wool + strawberry = 66% of all the money in the game.** Eggs are
  5.5% — this is *why* geese lose, not despite eggs being "safe." A goose spends
  a prime animal tile and 3.5 actions/day to access a $16,900 market; a sheep
  spends the same resources to access a $67,600 one.
- **Demand caps how many tiles each market can profitably hold:**

  | Market | Tiles the demand supports | Contested (halved) | We ran |
  |---|---|---|---|
  | Cows | 17.3 | 8.7 | 8.2 |
  | Sheep | 15.0 | 7.5 | 3.8 |
  | **Strawberry** | **64.0** | **32.0** | **11.2** |
  | Melon | 14.7 | 7.3 | ~9 |
  | Geese | 10.0 | 5.0 | 0 |

  Livestock is high-yield but slot-limited (~16 contested animal tiles total in
  the whole game). Strawberry is lower-yield per tile but is the *only* market
  with real headroom — which is why the top farms nonetheless leave 50 tiles
  empty: filling land was never the objective, **filling demand** is.

**New objective function, replacing "beat the opponent":**

> For every product, hold production as close as possible to
> `town_drain × our_share`, prioritised by forecast $/action, for as many days
> as possible.

This is opponent-aware by construction (their supply reduces our share) and
robust to *unseen* opponents (a new strategy just changes the numbers, not the
method) — directly answering the user's concern about overfitting to today's
79 opponents.

---

## 10. Phase 9 — The PRD and the v2 rebuild

We wrote `PRD.md`: a formal product spec for an "Experienced Farmer" v2 agent,
built around the economic-share objective above. Goals included beating
`main.py` head-to-head (≥60% over 68 games), winning the last third of the
season (fixing the day-18 collapse), being provably robust to unseen
strategies, and — the new headline metric — **extracting ≥75% of the
theoretical $152,595 share**, up from 50%.

Two build approaches were tried, both generated from `main.py` via a builder
script so **`main.py` itself was never edited**:

### Attempt A — `farmer.py` (full replacement of the land-planning brain)

A from-scratch "knapsack allocator": score every possible use of every free
tile in $/action using a real price-curve forecast (today's price + trend +
supply not yet online, from *both* farms), fill toward a labour cap.

Went through several iterations as bugs were found and fixed one at a time:
- v1 (fudge-factor discount, capped at 75%): planted **25 melons on day 0**,
  because no market could ever look bad enough to avoid.
- Fixed to use the real price curve → then planted **41 tiles of strawberry**,
  no diversification.
- Added a market-share cap → planted strawberry on **day 3**, the exact mistake
  Phase 6 (H26) had already measured at −$12k to −$36k.
- Added "animals before crops" ordering to fix the timing → **now under-planted**,
  36 empty tiles.

Final result after all fixes: **0 wins in 68 games against `main.py`,
margin −$30,533.** Verified 100% against four weak archetype bots (melon rush,
goose farm, crop farm — all built as local sparring partners).

### Attempt B — demand-anchored rewrite of the same allocator

Replaced the discount-factor forecast with an explicit projection of market
inventory using the real price curve, and capped each market at
`town_drain × share`, halved when the opponent was already supplying it.

Swept the share parameter from 0.7 to 5.0 — **the result plateaued around
−$25,000 regardless.** Ceding market share to the opponent (the "halved when
contested" rule) turned out to be actively harmful: revenue is
`our_units × price(total supply)`, and yielding units lowers our revenue
without meaningfully raising the price, because the opponent simply fills the
gap. **Unilateral restraint lost money every time it was tried** — this
pattern recurred three separate times across the project (see Phase 10).

---

## 11. Phase 10 — Why every v2 attempt lost

Rather than keep rebuilding `farmer.py`'s brain, the user asked for the four
PRD layers (P1–P4) to be built **additively on top of `main.py`'s proven,
tuned core** instead — a copy (`agent2.py`), with each layer behind its own
flag so it could be ablated.

**P1 — decaying animal-payback hurdle** (buy livestock later in the season even
at lower ROI, so the herd keeps growing instead of stalling around day 18).
**P2 — opponent-aware purchase ordering** (prefer whichever animal the opponent
is supplying least, without reducing our own output).
**P3 — idle-tile filler** (after `main.py`'s tuned quotas run, put the ~47
leftover tiles to work using the same $/action scoring as `farmer.py`).

All three were verified as true no-ops when disabled (agent2 with all flags off
scored byte-identical to `main.py`), then tested individually and combined
over 68 games each against a pinned baseline:

| Layer | Win rate | Margin | Seeds won |
|---|---|---|---|
| P1 alone | 4.4% | **−$45,363** | 1/34 |
| P2 alone | 45.6% | −$679 | 18/34 (flat — the only non-loser) |
| P3 alone | 0% | **−$51,091** | 0/34 |
| All three | 0% | −$48,633 | 0/34 |

We also directly tested the "not enough labour" hypothesis (more hands would
let P3's extra tiles actually get serviced), sweeping 15 and 16 hands with a
lowered hire-cost divisor: **more hands alone lost** (−$9,884 to −$13,232, the
15th/16th hand's Fibonacci cost outweighed the marginal value it unlocked), and
**more hands combined with P3 lost worse** (−$54,514 to −$63,831).

**The pattern across seven separate attempts, all against the same 68-game bar:**
every single change that *added workload* to the farm — more tiles, more
animals, more hands — lost money. `main.py`'s 47 empty tiles, its ANIMAL_PAYBACK
threshold, and its fixed quotas turned out not to be crude approximations of a
better answer; they sit at a genuine constrained optimum for a scheduler with
~14 workers and heavy travel costs. Adding more assets simply diluted the
labour already servicing the assets that were producing well.

---

## 12. Phase 11 — Reverse-engineering agent2.py, overfitting check, external research

Asked directly to explain *mechanistically* why P1 and P3 failed (not just that
they failed), we traced both turn-by-turn on a fixed seed.

**P3's bug:** it re-planted 10 strawberry tiles **on day 0**, because
`_fill_options()` — the function powering the idle-tile filler — used its own
independent scoring loop that never checked `STRAWBERRY_START_DAY`, the
hard-won day-13 timing rule from Phase 6. The farm's cash dropped to $2 by day 3
and never recovered a healthy trajectory. **Root cause: two allocators
(the tuned quotas and the new filler) that don't share state or constraints.**

**P1's bug:** with the payback hurdle decaying over the season, it built **32
cows and 13 sheep by day 27** — a herd roughly 2–3× larger than the ~17-cow,
~15-sheep ceiling the Phase 8 economic model itself calculated the market can
absorb. Nothing capped total exposure against market size; each purchase looked
individually profitable while the portfolio as a whole overshot demand and
crashed its own prices. Cash collapsed to under $1,000 repeatedly from day 15
onward, from feed costs on an oversized herd.

**Overfitting check.** `main.py`'s tuned constants: **not overfit** — the
held-out-seed validation (Phase 6) already showed a *better* result on unseen
seeds than on tuned ones. Today's failed v2 experiments: **also not
overfitting** — margins of −$45k to −$63k with mechanistically-traced causes
are real bugs, not statistical noise; overfitting shows up as small,
inconsistent effects, not this. The one genuine gap identified: nothing has
ever been tested against the actual strongest ladder-farm shape (8 cows + 15
sheep, near-zero crops) — every local test used weak archetype bots or
self-play.

**External research.** Searched for how comparable Kaggle simulation
competitions (Halite III, Lux AI — same shape: many workers, many tiles, one
action each per turn, shared resources) solved worker-to-task assignment. Top
Halite III bots replaced exactly the kind of greedy "sort by score, assign
nearest" matching our scheduler uses with the **Hungarian algorithm** — optimal
bipartite matching between units and tasks, guaranteed collision-free and
provably better than greedy. This is attractive specifically because, unlike
every P1–P3 layer, **it adds zero workload** — same tasks, same tiles, same
quotas, only a better assignment of the existing ~340 daily actions. Lux AI's
strongest teams were also predominantly rule-based rather than ML/RL, a mild
validation of the overall approach taken here. This is the current proposed
next experiment, not yet built.

---

## 13. The hypothesis register — everything tested

Across the whole project, roughly **27 of an eventual 50 user-supplied
hypotheses** were tested with dedicated game batches, plus 6 meta-questions
answered from pooled data, plus a further ~10 hypotheses generated internally
during the PRD/v2 work. Full detail lives in `README.md` and `PRD.md`; the
headline confirmed/refuted list:

### Confirmed (kept in the live agent)
- Distance-aware task assignment over nearest-task (+$22k)
- A labour budget that caps planning to what the crew can service (+$9k)
- Value-driven, mixed-species livestock purchasing (+$17k; single-species
  variants all lost badly — geese −$79.7k, sheep −$36.0k, cow −$16.1k)
- Selling before hiring in the market-order queue (+$4,942)
- 14 farm hands (+$2,222)
- Strawberry, 12 tiles, planted day 13 (+$15,473, 34/34 seeds)
- Task-scoring weight of ×1 rather than ×3 (+$10,197)
- CARE prioritised above harvesting (removing CARE costs −$45,327)
- Sell orders queued ahead of hires within the 10-order cap

### Refuted (tried, measured, reverted, documented in code so they aren't retried)
- Fertilising melons for a 9-day cycle (−$15,600, 0/34 seeds)
- Throttling sales to protect price (−$1.4k to −$1.8k — the shed cap bins the
  held produce)
- Strawberry planted early / day 0 (−$12k to −$36k depending on quantity)
- Sticky (persistent) assignment, once the scored matcher existed (−$3,172)
- Buying land early (−$24,739)
- A fixed wheat policy, always-grow or always-buy, vs the adaptive threshold
  (−$5,145 / −$3,965)
- Harvest-over-water priority after day 20 (−$2,482)
- Opponent-aware *forecast-driven restraint* on animal buying (−$13,564) —
  the forecast itself was later shown to be directionally correct on the
  ladder, but the *policy* (cede the market) was wrong twice over: it compared
  a cow to a fixed threshold instead of the tile's true alternative use
  (an idle tile earning $0), and unilateral restraint in a shared market simply
  gifted the opponent the market they were about to take anyway.
- The entire v2 rebuild in every form tried: full replacement (`farmer.py`,
  −$30,533), demand-anchored rewrite (plateau ≈−$25,000), and additive layers
  on top of `main.py` (P1 −$45,363, P3 −$51,091, all combined −$48,633)
- More farm hands beyond 14, even with a lowered hire-cost curve (−$9,884 to
  −$13,232)

### Corrected beliefs (stated confidently, then measured and found wrong)
- *"Ten geese would win every game we lost"* — false; geese correlate −0.32
  with final bank across 79 ladder games
- *"~47 empty tiles is our biggest waste"* — false; the strongest ladder farms
  run *more* empty tiles than we do (50.3 average vs our 47.1); the real
  problem is yield-per-tile-day among the tiles that ARE productive, not tile
  count
- *"Sheep are bad"* (an early correlational finding, r=−0.81 with final bank)
  — false; the correlation was confounded by capital timing (buying $500 sheep
  early starved cheaper $400 cows), not by wool economics

### Untested (need new architecture, not a flag)
Specialised worker crews, farm layout/placement optimisation, carrots and
mixed-cropping, opponent strategy classification over time, true lookahead /
Monte Carlo planning, and — the current leading candidate — Hungarian-algorithm
optimal task assignment in place of the greedy scheduler.

---

## 14. What we got wrong, in our own words

This project produced as much value from being wrong as from being right, and
it's worth listing plainly:

1. **We shipped an unmeasured constant for weeks** (the ×3 task-scoring weight)
   simply because it was the first number that worked, and it cost $10k+ once
   actually swept.
2. **We told the user "ten geese would have won every lost game"** based on a
   plausible-sounding but untested chain of reasoning. The ladder data flatly
   contradicted it.
3. **We told the user "our biggest waste is 47 empty tiles"** — also wrong, and
   in fact the opposite of the truth; strong farms run *more* idle land than we
   do.
4. **Twice, a genuine crash in our own code was mistaken for a decisive
   experimental refutation** (−$108k, "strawberry is a disaster") before being
   traced to a missing function argument and a missing dict key.
5. **We built a more "principled" model (the real price curve, explicit
   opponent-supply forecasting) and it performed worse than the "crude," hand-
   tuned original**, repeatedly. A model can be theoretically correct and still
   attached to a bad decision rule — this happened at least three separate
   times (the sell-throttle experiment, the opponent-aware animal-payback
   experiment, and the entire v2 rebuild).
6. **We initially recommended countering the specific 79 opponents faced**,
   before the user redirected us toward reverse-engineering the underlying
   economy instead — a materially better frame that the rest of the project
   was then built around.

---

## 15. Current architecture

**`main.py` — the live, submitted agent.** 669 lines, no dead code, 16 named
tunable constants (all swept, all justified in the docstring alongside every
refuted alternative). Architecture: census → labour-budgeted land plan → task
generation → greedy scored assignment → idle logistics → market orders. Rating
838–844 on the live ladder, extracting roughly 50% of the theoretical maximum
economy.

**`agent2.py` (generated by `build_agent2.py`) — the v2 experiment, currently
losing.** Additive layers (P1 late-game engine, P2 opponent-aware ordering, P3
idle-tile filler) on top of an unmodified copy of `main.py`'s core. All three
layers are flag-gated (`P1_LATE`, `P2_OPP`, `P3_FILL`) and default to a verified
byte-identical no-op. P2 is roughly neutral; P1 and P3 both lose decisively for
mechanistically understood reasons (see Phase 11) and are **not** currently
recommended for promotion.

**`farmer.py` (generated by `build_farmer.py`) — the earlier full-replacement
attempt.** A standalone demand-anchored $/action allocator. Also currently
losing to `main.py`. Kept on disk as a working platform for the price-forecast
machinery, which several later experiments reused.

**Supporting infrastructure:**
- `batch.py` — parallel local game runner (7 workers), configurable via a `PLAN`
  list of (name, opponent, config-overrides, seed-count) tuples
- `report.py` — win-rate / confidence-interval / paired-margin summariser
- `harvest.py` — downloads, summarises, and discards ladder replays (keeps disk
  flat across 79+ 20MB files)
- `spar_melon.py` / `spar_goose.py` / `spar_crops.py` / `spar_land.py` /
  `spar_wool.py` — locally-built archetype opponents, used as robustness
  sparring partners so tuning isn't judged only against self-play
- `PRD.md` — the formal v2 product spec, including the full economic model
- `SOP.md` — the methodology document
- `README.md` — running log of the hypothesis register with citations

---

## 16. Current goal and next steps

**Stated goal (per the PRD, restated in economic terms):** move the agent from
extracting **~50%** of the game's theoretical $152,595 half-share to **≥75%**,
by building a genuinely opponent-aware, non-overfit strategy layer — not by
countering today's 79 known opponents, but by reverse-engineering and
exploiting the underlying demand structure of the game, which is robust to any
future opponent.

**Where we actually are against that goal:** every attempt to add a smarter
strategy layer on top of the proven scheduler has *lost* to the scheduler
alone, because every attempt added workload and workload — not capital, not
land, not "smart resource valuation" — is the actual binding constraint in this
architecture. That is itself a real and useful finding, not a failure to
report quietly: it means the next lever has to be one that makes the *existing*
work more efficient rather than adding more of it.

**Concrete next step proposed and not yet built:** replace the greedy
`priority × weight + distance` task assignment with a **Hungarian-algorithm
optimal bipartite matching** between workers and tasks — the technique top
Halite III competitors used for the same class of problem. This is the one
candidate identified so far that does not add work; it only reallocates the
work already being done. To be tested with the same discipline as everything
above: flag-gated, verified as a no-op when disabled, then 68 games against the
pinned baseline before any promotion is considered.

**Also outstanding:**
- Build a genuinely strong local sparring partner (8 cows / 15 sheep,
  near-zero crops, matching the best ladder farm's shape) — none of our current
  archetype bots reach that level, which means every local robustness test so
  far has a blind spot at exactly the opponent type that beats us on the ladder.
- Decide whether to submit a v2 at all, or continue hardening `main.py`'s
  existing architecture (only 4 submissions/day, and only the latest 2 stay
  active for the final leaderboard, so submissions should not be spent on
  unproven ideas).

---

## 17. File index

| File | What it is |
|---|---|
| `main.py` | **The submitted agent.** Untouched by every v2 experiment. |
| `baseline.py` | Pinned copy of `main.py` at its current best, used as the fixed opponent in every head-to-head test |
| `baseline_v2.py` | An earlier pinned version of `main.py`, kept for measuring cumulative improvement over time |
| `agent2.py` / `build_agent2.py` | v2 attempt: `main.py` + additive P1/P2/P3 layers, and the script that generates it |
| `farmer.py` / `build_farmer.py` | v2 attempt: full replacement land-planning brain, and its generator |
| `eval.py`, `sweep.py`, `h2h.py` | Early single/few-game local test harnesses |
| `batch.py` | Parallel multi-game local test harness (current standard tool) |
| `report.py` | Win-rate / CI / margin summariser for batch output |
| `analyze.py` | Statistical analysis over a batch's `.jsonl` results |
| `harvest.py` | Downloads and summarises ladder replays, discards the large files |
| `spar_*.py` | Local archetype sparring-partner bots |
| `results*.jsonl`, `r_*.jsonl` | Raw local-game batch outputs (~4,950 games total) |
| `ladder_all.jsonl` | Summarised record of all 79 real ladder games |
| `eps.csv` | Raw episode listing pulled from the Kaggle API |
| `PRD.md` | v2 product requirements doc, including the full economic model |
| `SOP.md` | Methodology document |
| `README.md` | Hypothesis register with evidence |
| `PROJECT_LOG.md` | This document |
| `Overview and rules.txt`, `Kaggriculture_Lessons_1_to_7.md`, `Overview.txt` | Reference material: the official rules/getting-started guide and early tutorial notes |
