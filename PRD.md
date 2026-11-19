# PRD — "Experienced Farmer" agent (v2)

**Status:** proposed
**Evidence base:** 79 rated ladder games (4,145-team field) + ~4,400 local games
**Current agent:** `main.py` — rating 838, rank 1,837 / 4,145 (top 44%), 42W–37L

---

## 1. Problem

Our agent plays **one fixed strategy** and wins or loses depending on what the
opponent happens to do. Across all 79 rated games its farm is statistically
identical in wins and losses (8.2 cows, ~4 sheep, 11.2 strawberry, 0 geese,
~47 empty tiles). It does not observe the opponent, does not forecast prices,
and does not change plan.

At a 53% win rate the rating has reached equilibrium at ~838. It will not climb
further without a structurally better agent. Prize positions need ~3,200.

### 1.1 The single most important finding

**We build a big early lead and lose it in the last third.**

Median money gap (us − them) in games we lost:

| Day | 9 | 12 | 15 | 18 | 21 | 24 | 27 |
|---|---|---|---|---|---|---|---|
| Gap | −46 | **+10,625** | +10,656 | +6,597 | +1,678 | −4,252 | **−8,151** |

Against the strongest opponents (≥$90k), the trajectories are:

| Day | 9 | 12 | 18 | 24 | 27 |
|---|---|---|---|---|---|
| Them | 498 | 7,300 | 22,213 | 65,554 | **84,523** |
| Us | 335 | **16,931** | 28,409 | 49,752 | 67,503 |

They are **4× behind on day 12 and finish 25% ahead.** Our melon rush produces a
one-time windfall; their livestock **compounds**. A windfall decays, an engine
accelerates. We are optimising the wrong half of the season.

### 1.2 Two beliefs the data killed

Both were mine, stated confidently earlier, and both are wrong:

| Claim | Reality |
|---|---|
| "Ten geese would have won every game we lost" | Opponents **with** geese median $53,680; **without** $76,570. Geese correlate **−0.32** with final bank — the strongest negative in the dataset. We beat goose farms **73%** of the time. |
| "47 empty tiles is our biggest waste" | Top farms (≥$90k) average **50.3 empty tiles**; weak farms 41.8. Top farms run **16.5** productive tiles, we run **23.3**. Farm *fullness is not the constraint.* |

The egg reasoning was right (eggs never crash) but incomplete: a goose earns
~2 × $58 = $116/tile/day, while a sheep earns ~1.33 × $200 = **$266**. Eggs are
safe *and* low-yield. Safety was never the binding constraint.

### 1.3 What the strongest farms actually look like

| | Top (≥$90k, n=15) | Weak (<$50k, n=13) | Us |
|---|---|---|---|
| Cows | 6.0 | 6.5 | 8.2 |
| **Sheep** | **5.5** | 4.1 | 3.8 |
| Geese | 0.3 | 2.5 | 0.0 |
| Strawberry | 3.2 | 4.2 | **11.2** |
| Productive tiles | **16.5** | 20.8 | 23.3 |
| Weeds | 7.9 | 8.4 | 0.4 |

Best farm seen: **khalid harouach, $147,569 — 8 cows, 4 sheep, 3 wheat, 56 tiles
empty.** Second: Roland Luethy, $121,003 — 8 cows, **15 sheep**, zero crops.

The winning shape is a **small, livestock-dense farm**, not a full one. We hold
more tiles and earn less: our problem is **yield per tile-day, not tile count.**

---

## 1.4 The economic map � the real objective

The town is the only buyer that never saturates. Selling exactly its daily drain
holds inventory at I0, so price stays at base. That is the **sustainable
extraction rate, and it defines the size of the game**:

| Product | Units the town buys (30d) | $ at base | Share |
|---|---|---|---|
| **Milk** | 437 | **$69,920** | 22.9% |
| **Wool** | 338 | **$67,600** | 22.2% |
| **Strawberry** | 536 | **$64,320** | 21.1% |
| Melon | 140 | $35,000 | 11.5% |
| Tomato | 338 | $20,280 | 6.6% |
| Egg | 338 | $16,900 | 5.5% |
| Wheat | 635 | $15,875 | 5.2% |
| Carrot | 437 | $15,295 | 5.0% |
| **TOTAL** | 3,199 | **$305,190** | |

**Half-share = $152,595.** Best farm observed: **$147,569 (97% of it).** Our
median: $75,564 (**50%**).

Milk + wool + strawberry are **66% of all money in the game**. Eggs are 5.5% �
which is why geese lose: a goose spends a prime animal tile and 3.5 actions/day
to reach a $16,900 market while a sheep reaches a $67,600 one with the same cost.

### Demand caps tile counts

| Market | Tiles supported | Contested (half) | We run |
|---|---|---|---|
| Cows | 17.3 | 8.7 | 8.2 |
| Sheep | 15.0 | 7.5 | 3.8 |
| **Strawberry** | **64.0** | **32.0** | **11.2** |
| Melon | 14.7 | 7.3 | ~9 |
| Geese | 10.0 | 5.0 | 0 |

Livestock is high-yield but slot-limited (~16 contested animal tiles). Strawberry
is lower-yield per tile but is the only market with room to absorb a large farm.
This is why strong farms leave 50 tiles empty: **filling land is not the goal,
filling demand is.**

## 1.5 Objective function

> For every product, hold our production as close as possible to
> `town_drain x our_share`, prioritised by forecast $/action, for as many days as
> possible.

Opponent-aware by construction (their supply reduces our share), robust to unseen
strategies (a new opponent only changes the numbers), and measurable against a
fixed ceiling instead of a moving field.

## 2. Goals

| # | Goal | Measure |
|---|---|---|
| G1 | Beat `main.py` head-to-head | ≥60% over 68 games, 2 seat orders |
| G2 | Win the last third of the season | Median money gap at day 27 ≥ gap at day 15 |
| G3 | Adapt to the opponent | Farm composition differs measurably by opponent type |
| G4 | Robust to unseen strategies | ≥60% vs 4+ archetypes it was never tuned against |
| G5 | Ladder rating | >1,600 (top 25%) within 100 rated games |
| **G6** | **Share of the pie extracted** | **from 50% -> 75%+ of $152,595** |

### Non-goals

- Beating the specific 79 opponents we have replays for (that is overfitting)
- Reproducing `main.py`'s tuned constants with a "principled" model for its own
  sake — v1 of `farmer.py` did exactly that and lost by $30k over 68 games
- Full lookahead / MCTS in this version

---

## 3. Principles (what makes it robust rather than a counter-strategy)

1. **Compounding beats windfalls.** Value an asset by what it earns *for the
   rest of the season*, not by its unit price today. This is why livestock
   should dominate and why the melon rush is a trap.
2. **Sell into demand, not into price.** The town's daily drain is the only
   demand that cannot be crushed. Size production against *absorption*, and halve
   the allowance when the opponent is in the same market.
3. **The opponent is a supply forecast, not an enemy.** We do not counter their
   strategy; we price the market they are about to create.
4. **Never idle capital or labour, but never over-extend either.** Add capacity
   while marginal value per action exceeds the marginal cost of servicing it.
5. **Every constant must be measured.** A principled model with unmeasured
   parameters is worse than a crude model with measured ones — this is the
   documented cause of v1's failure.

---

## 4. Architecture

```
                     OBSERVATION
                          |
        +-----------------+-----------------+
        |                 |                 |
   MARKET MODEL     OPPONENT MODEL     OWN-FARM MODEL
   price curve      their tiles ->     capacity, cash,
   + trend +        future supply      herd age, labour
   town drain       + build rate
        |                 |                 |
        +--------> SITUATION VECTOR <-------+
                          |
                   STRATEGY SELECTOR         <-- NEW
              (which markets are ours to take)
                          |
                  PORTFOLIO ALLOCATOR        <-- NEW
        (marginal $/action, capped by absorption share)
                          |
                    ACTION PLANNER
                          |
                  WORKER SCHEDULER           <-- UNCHANGED from main.py
                          |
                       ACTIONS
```

The scheduler at the bottom is proven and stays untouched. Everything new sits
above it.

### 4.1 Components

**C1 — Market model.** Real price curve (already implemented in `farmer.py`),
plus per-item price history for trend, plus town drain from unlocked shops.
Outputs `expected_price(item, horizon)`.

**C2 — Opponent model.** From their visible tiles: current production rate,
production not yet online (`placed_day` + `first_yield_day` gives exact timing),
build rate over the last N days, and whether they CARE (`pending_care_bonus` is
visible — it reveals a competent agent). Outputs `opponent_supply(item, day)`.

**C3 — Own-farm model.** Labour capacity, cash, herd composition and age,
committed supply. Outputs `capacity_remaining` and `own_supply(item)`.

**C4 — Strategy selector.** For each product computes
`headroom = town_drain × share − (our supply + their supply)`, where `share`
falls when the opponent is committed to that market. Markets with headroom are
"ours to take"; the rest are closed. This is what makes it opponent-aware without
being a hard-coded counter.

**C5 — Portfolio allocator.** Ranks every tile use by **marginal $ per action
over the remaining season**, respecting headroom, cash, and a diversification
cap. Re-prices after each allocation so it self-limits.

### 4.2 Explicit rules derived from the evidence

| Rule | Justification |
|---|---|
| Value assets by remaining-season earnings, not spot price | §1.1 — compounding beats windfalls |
| Sheep before cows before geese, subject to headroom | Sheep $266/tile/day vs cow $126 vs goose $116 |
| Cap melon hard; treat it as optional | Melon ends at $19 in wins *and* losses on the ladder |
| Do not fill land for its own sake | Top farms leave 50 tiles empty |
| Livestock purchases continue while headroom exists, to ~day 24 | We plateau after day 21; they do not |
| Back off a market when our forecast price drops below X% of base | The milk-crash mechanism |

---

## 5. Success metrics

| Metric | Baseline (`main.py`) | Target |
|---|---|---|
| Win rate vs `main.py` | — | **≥60%** (68 games) |
| Win rate vs 4 unseen archetypes | 100% (weak bots) | ≥60% vs *strong* archetypes |
| Day-27 money gap in losses | −$8,151 | ≥ −$2,000 |
| Median final bank (mirror) | $101,330 | ≥ $110,000 |
| Ladder rating | 838 | >1,600 |

---

## 6. Test plan

1. **Crash gate.** Run with `try/except` removed; zero exceptions required before
   any measurement is believed. (Two false refutations were caused by skipping this.)
2. **No-op gate.** Every new flag defaults to current behaviour; fixed-seed score
   must be byte-identical.
3. **Head-to-head.** 34 seeds × 2 seat orders vs pinned `baseline.py`.
4. **Robustness.** vs 4+ archetype bots rebuilt from ladder replays — including a
   **strong** livestock archetype (8 cows + 15 sheep), which we currently lack.
5. **Held-out seeds.** Confirm on seeds never used in tuning (5000+).
6. **Ladder.** Submit; require ≥60% over 50+ rated games before promoting.

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| **Unmeasured parameters** (killed v1) | Every constant exposed as a flag and swept; ship only what beats baseline |
| **Overfitting to today's field** | Judge on archetypes + held-out seeds, never on the 79 specific opponents |
| Opponent model misleads (as in the −$13.6k experiment) | Feed it into *relative* ranking, never into an absolute accept/reject threshold |
| Complexity regression | Scheduler untouched; new layer is additive and flag-gated |
| Ladder drift | Re-measure monthly; the field changes as others improve |

---

## 8. Phasing

| Phase | Content | Exit criterion |
|---|---|---|
| **P0** | Strong archetype sparring bots from replays (8 cow + 15 sheep; 8 cow + 4 sheep + wheat) | Bots reach $90k+ vs `starter` |
| **P1** | Late-game engine: keep buying livestock while headroom exists | Day-27 gap improves; ≥55% vs baseline |
| **P2** | Strategy selector (headroom + opponent share) | ≥60% vs baseline, farm composition varies by opponent |
| **P3** | Portfolio allocator replaces fixed quotas | ≥60% and ≥60% vs all archetypes |
| **P4** | Submit, measure 50+ rated games | Rating >1,200, then iterate to 1,600 |

**P0 is a prerequisite.** Our current sparring bots top out around $40k; the real
field reaches $147k. We cannot tune a late game against opponents who never
challenge it — this is precisely why the opponent-forecast experiment gave a
misleading local result.
