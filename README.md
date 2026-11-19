# Kaggriculture agent

`main.py` is the submission (single file, `agent` is the last callable — required,
because kaggle-environments loads the *last* callable defined in the file).

## Results (720-turn games, local)

| Opponent | Result |
|---|---|
| `starter` | ~$110k–126k vs $3.5k |
| previous agent (`baseline_v2.py`) | +$19k–20k, wins every seed tried |
| itself (self-play) | symmetric |

Runtime ≈ 3s per full game, so the per-turn budget is never a concern.

## Hypothesis register — the 50-hypothesis sweep

20 variants × 68 games (34 seeds × both seats) = 1,360 games, each against a pinned
baseline. Raw data in `r_h1.jsonl` … `r_h5.jsonl`; run `python report.py r_h*.jsonl`.

| # | Hypothesis | Measured | Verdict |
|---|---|---|---|
| H1 | Less walking → more money | random assign −$80.9k; urgency-only −$57.2k | **confirmed** |
| H2 | Persistent assignment beats reassigning | no-sticky **+$3,172**, 29/34 | **refuted** |
| H3 | Nearest worker beats random | +$80.9k equivalent | **confirmed** |
| H4 | Distance matters *less* than urgency | distance-blind −$57.2k vs urgency-blind −$37.7k | **refuted — reversed** |
| H7 | ×3 is the right coefficient | w1 **+$10,197** (33/34); w2 +$1.1k; w5 −$8.2k; w10 −$20.0k | **refuted → now ×1** |
| H9 | CARE should outrank harvesting | CARE below harvest −$1,661 | **confirmed** |
| H10 | Harvest outranks watering after day 20 | −$2,482 | **refuted** |
| H16 | Growing wheat is cheaper than buying | always-grow −$5,145; always-buy −$3,965 | **both refuted** |
| H17 | An optimal wheat threshold exists | adaptive rule beats both extremes | **confirmed** |
| H19 | Earlier land purchase improves income | −$24,739, 0/34 seeds | **refuted** |
| H20 | Delaying land improves liquidity | same test, inverted | **confirmed** |
| H21 | 9 melon tiles is optimal | 11 → −$5,365; 12 → −$4,603; 16/20/24 worse | **confirmed** |
| H24 | Wheat should stop after day 15 | −$4,596 | **refuted** |
| H26 | Strawberry pays after day X | X = 13: **+$15,473, 34/34 seeds** | **confirmed** |
| H27 | Goose first | goose-only −$79,720 | **refuted** |
| H28 | Cow first | cow-only −$16,056 | **refuted** |
| H29 | Sheep first | sheep-only −$35,973 | **refuted** |
| H30 | Mixed animals beat single-species | every restriction loses badly | **confirmed** |
| H32 | CARE is the highest-ROI action | ablating CARE costs **−$45,327** | **confirmed** |
| H33/H34 | Gradual selling beats bulk | −$1,385 (frac .5) / −$1,807 (frac .7) | **refuted** |

### Meta (H45–H50), from 2,176 pooled head-to-head games

- **H45/H46** — median margin sd is **$6,432**. 68 games resolves ~$1,500 on a typical
  variant but only ~$5,400 on the noisiest. So 70 games is enough for effects above
  ~$5k, and *not* enough below ~$2k; the worst variant needs ~490 games.
- **H47/H48** — `corr(win rate, margin) = +0.76`, `corr(own bank, margin) = +0.84`, but
  own bank **misranks**: `wheat_d15` banked $95,756 and still lost 88% of its games.
  Own score is contaminated by the opponent (same agent: $113k vs `starter`, $61k vs
  itself). Rank by head-to-head win rate, not by absolute money.
- **H49/H50** — `corr(score sd, win rate) = +0.15`, i.e. essentially nothing. High
  variance isn't an independent axis; it's a *symptom* — every high-variance variant
  here (land_early sd $18.4k, pri_w10 sd $17.0k) was simply a losing strategy.

### Not tested (needs new code, not a flag)

H5/H6 specialised crews · H11–H15 layout placement · H18 · H22/H23 carrots &
mixed cropping · H31 · H35–H39 market timing and manipulation · **H40–H44 planning /
lookahead / MCTS** — the last group is the real frontier and a multi-day build.

## Hypothesis register (earlier round)

Measured head-to-head vs a pinned baseline, 34 seeds × both seats = 68 games each.
Win rate is the metric that matters — the ladder scores wins, not coin margin.

| Hypothesis | Result | Verdict |
|---|---|---|
| Sell orders before hire orders (10-order cap) | +$4,942, 30/34 seeds | **adopted** |
| 14 hands, hire divisor 8 | +$2,222, 30/34 seeds | **adopted** |
| Strawberry, 12 tiles, planted **day 13** | +$15,473, **34/34 seeds, 68/68 games** | **adopted** |
| Strawberry, 16 tiles, day 13 | +$14,838, 34/34 | ~tied, kept 12 (tighter CI) |
| Strawberry planted day 0 | −$12k (4 tiles) to −$36k (8 tiles) | refuted |
| Fertilized melon, 9-day cycle | −$15,600, 0/34 seeds | refuted |
| Throttle sales to hold price (`SELL_FRAC`) | −$1,385 (0.5) / −$1,807 (0.7) | refuted |
| 16 hands | margin exactly $0 | no-op (formula-capped at 14) |

The strawberry result is the headline: **the same 12 tiles lose $12k planted on day 0
and win $15k planted on day 13.** Market depth said strawberry was under-supplied and
that was true — but early capital is the binding constraint, and $1,200 of seed on day 0
starves the animal build that pays for everything else. Market room ≠ profit.

### Two bugs that masqueraded as refutations

Both produced clean, confident, completely wrong measurements:

1. `planned_straw` wasn't passed into `_market_orders` → `NameError` every turn →
   the `try/except` returned PASS → "strawberry loses $108k."
2. The local `CROPS` table had no `interval` key → `KeyError` on production-day
   maths → PASS on 48 turns → "strawberry still loses $105k."

The tell in both cases was the *shape* of the failure, not the size: the farm ended
with empty pastures, unsold milk in the shed, and the strawberry price untouched at
$314. A real refutation doesn't leave the product unsold. **When a mechanic looks
strong on paper and measures catastrophically, suspect the implementation first** —
run the agent with the `try/except` removed before believing the number.

## Strategy

Derived by reading the price model in `kaggriculture.py` rather than by guessing:

* **Cared livestock is the best tile in the game.** `CARE` banks +1 per fed day and
  pays the whole bank on the next scheduled production, so a cow yields 3 milk every
  2 days (1.5/day × $160) and a sheep 4 wool every 3 days (1.33/day × $200) — far
  above a goose (2 eggs/day × $50). Town shops (pizza / ice cream / smoothie / yarn)
  drain milk and wool continuously, so prices hold near base.
* **Melons** are the best crop: 6 units per cycle at ~$250, and town demand absorbs
  most of the supply. But the glut curve is quadratic (`250 − 0.01·excess²`), so the
  batch is capped at ~9 tiles per cycle.
* **Fertilizer** is free income — every surviving animal produces 1/day whether fed
  or not, and it only loses $0.20 per unit sold.
* **Eggs** are the only unbounded product (`log` glut curve): 1000 eggs sold still
  price near $38. Geese are the fallback once milk/wool prices sag.
* **Wheat** is feed. Buying drains the market (`25 + sqrt(deficit)`), so the
  wheat-tile quota scales with the current wheat price instead of being fixed.
* **Farm hands** cost `fib(n)` — ten hands are $143/day for 240 actions. Labour is
  cheap; the real limits are **travel time**, land and market saturation.

### What actually drove the score

1. **Travel, not actions, is the bottleneck.** Assignment scores each (unit, task)
   pair by `priority*3 + distance`, so a unit already in the melon patch keeps
   working the melon patch, and idle units stay put instead of walking home.
2. **A labour budget.** Tiles are only planted / coops only built if the crew can
   still service them (`ACTIONS_PER_TASK` model). Over-planting turns crops into
   weeds, which cost more than the missed yield.
3. **Sticky assignment.** Without it, units oscillate between two tasks forever as
   distances flip each turn.
4. **Shed hygiene.** The shed caps at 100 items and a full shed *silently* blocks
   `BUY_ANIMAL` / `BUY_PRODUCT`. Hoarded wheat once stalled the whole engine.
5. **Value-driven livestock.** Each turn the agent prices every animal at
   `rate × market_price × days_left` and buys the best one whose return clears
   `ANIMAL_PAYBACK × cost`. This beat every fixed quota tried.

## Local workflow

```bash
python eval.py quick      # one game vs starter
python eval.py trace      # per-day farm/price dump
python eval.py self       # self-play
```

`sweep.py` grid-searches parameters against `starter`; `h2h.py` runs a variant
(via `KG_*` env overrides) head-to-head against the pinned `baseline.py` over 4
seeds × both seat orders — that win/margin signal is what the ladder rewards, and
it is much less noisy than absolute score.

```bash
python h2h.py '{"ANIMAL_PAYBACK":[6.0,9.0]}'
```

To promote a winning config: bake it into `main.py` defaults, then re-copy
`main.py` → `baseline.py` (with `_tune` pinned to defaults) so later variants are
measured against the new bar.

## Submitting

The Kaggle CLI is not installed here yet:

```bash
pip install kaggle
```

Then add the API token to `~/.kaggle/access_token`, join the competition on the
website, and:

```bash
kaggle competitions submit kaggriculture -f main.py -m "v1: value-driven livestock"
```
