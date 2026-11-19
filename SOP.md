# Kaggriculture — Standard Operating Procedure

Everything we did, why, and what came out of it. Written so you could hand it to
someone else and they could keep going.

---

## Part 0 — The one-paragraph version

The agent is a **shift manager**. Every turn it looks at the farm, writes a to-do
list, scores each (worker, job) pair, and assigns the best matches. It does that 720
times. It never looks ahead. Everything we "improved" was either a **bug** or a
**number in the scoring**, and we only believed a change after ~68 games measured
head-to-head against the previous version.

---

## Part 1 — The SOP (the actual working loop)

This is the procedure. Steps 4 and 7 are the ones that cost us the most when skipped.

### Step 0 — Read the source, not the docs
The truth lives in `site-packages/kaggle_environments/envs/kaggriculture/kaggriculture.py`.
The official docs disagree with it in at least two places (CARE banks +1, not +2;
fertilizer *can* be sold). Every strategy number we used came from reading that file.

### Step 1 — Get something legal running
An agent that never crashes beats a clever agent that throws. Wrap the whole thing in
`try/except` returning PASS. **But see Step 7** — that safety net is also a trap.

### Step 2 — Instrument before optimising
Don't guess where the money goes. Dump a day-by-day trace: bank, tile census, shed
contents, market orders. Every major win came from *looking at a trace*, not from theory:
- units pacing north/west forever → oscillation bug
- 47 wheat rotting in the shed → shed cap silently blocking purchases
- 36 idle tiles → labour, not land, was the constraint

### Step 3 — One hypothesis, one flag
Express the idea as a **single environment-variable flag** whose default changes nothing:
```python
PRI_WEIGHT = _tune("PRI_WEIGHT", 3)   # env KG_PRI_WEIGHT overrides
```

### Step 4 — Prove the flag is a no-op ⚠️
Run a fixed seed and confirm the score is **byte-identical** to before:
```bash
python -c "...env.run(['main.py','starter']); print(reward)"   # must equal 100,857
```
If it differs, you changed behaviour by accident and every measurement after this is
garbage. This step has caught real mistakes twice.

### Step 5 — Run 68 games, not 8
34 seeds × **both seat orders**, always against a *pinned* copy of the current best
(`baseline.py`), never against `starter`.
```bash
python batch.py run          # 7 parallel workers, ~7 min for 272 games
```
Why both seats: it removes any first/second-player asymmetry.
Why not `starter`: a baseline that never sells isn't competing with you for market
depth, so it will happily tell you a bad strategy is good.

### Step 6 — Read win rate and paired margin
```bash
python report.py r_h1.jsonl
```
Rank by **head-to-head win rate**, never by your own bank. The ladder scores wins, and
your own score is contaminated by what the opponent does — the *same* agent banks
$121k against `starter` and $101k in a mirror.

### Step 7 — Before believing a refutation, check the SHAPE ⚠️⚠️
A catastrophic loss is more often your bug than your idea. The tell is not the size of
the loss, it's the shape:

> Strawberry measured **−$108,178, 0/34 seeds**. Twice. Both were crashes — a missing
> function argument, then a missing dict key — swallowed by the Step 1 `try/except` and
> silently converted into "plays badly." The giveaway was that the farms ended with
> empty pastures, unsold milk, and the strawberry price *untouched at $314*. **A
> genuinely bad strategy still sells things.** Untouched prices mean nothing happened.

The check takes 30 seconds:
```python
def strict(obs, cfg=None):
    return main._agent(obs)          # no try/except — let it raise
```
After fixing, strawberry-planted-early still lost — but $12k, for a real reason.

### Step 8 — Promote, then re-pin
Bake the winner into the defaults, copy `main.py` → `baseline.py`, and measure
everything afterwards against the **new** bar. Otherwise you keep re-winning against a
version you already beat.

### Step 9 — Write refuted ideas into the code
The `main.py` docstring lists what *failed* and by how much, so nobody retries it.
Refutations are the expensive part; don't lose them.

---

## Part 2 — Test results

**4,038 games, 58 variant runs.** ~1 in 5 of those games was wasted on the two crashes.

### What we changed, and what it was worth

| Change | Effect | Confidence |
|---|---|---|
| Distance-aware assignment (was nearest-task) | +$22k | 1 seed, but structural |
| Labour budget — don't plant more than you can water | +$9k | 4 seeds |
| Value-driven livestock (live price × rate × days left) | +$17k | 68 games |
| Sell orders queued before hire orders | +$4,942 | 68 games, 30/34 seeds |
| 14 hands (was 12) | +$2,222 | 68 games, 30/34 seeds |
| **Strawberry, 12 tiles, planted day 13** | **+$15,473** | **68/68 games, 34/34 seeds** |
| **Scoring weight ×1 (was ×3)** | **+$10,197** | **68 games, 33/34 seeds** |
| Drop sticky assignment | +$3,172 | 68 games, 29/34 seeds |

### What we proved was wrong

| Idea | Cost | Why it failed |
|---|---|---|
| Ablate CARE | −$45,327 | CARE is the highest-ROI action in the game |
| Single-species livestock (goose) | −$79,720 | must rotate as markets saturate |
| Buy land early | −$24,739 | labour is the constraint, not land |
| Fertilise melons for a 9-day cycle | −$15,600 | sound on paper, dead in practice |
| Strawberry planted day 0 | −$12k to −$36k | starves the early animal build of capital |
| Scoring weight ×10 | −$19,992 | urgency swamps travel; workers trek |
| Throttle sales to protect price | −$1.4k to −$1.8k | shed cap bins the held produce |
| Fixed wheat policy (always grow / always buy) | −$5.1k / −$4.0k | adaptive threshold beats both |

### Meta findings (from 2,176 pooled games)

- **Median margin spread is $6,432.** 68 games resolves ~$1,500 on a typical variant,
  ~$5,400 on the noisiest. 70 games is enough for big effects, not small ones.
- **Own bank misranks strategies.** `wheat_d15` banked $95,756 — near the top — while
  losing 88% of its games.
- **Variance is a symptom, not an axis.** `corr(score sd, win rate) = +0.15`. Every
  high-variance variant was simply a losing strategy.

---

## Part 3 — What works (the strategy that emerged)

Nothing here was designed up front. All of it fell out of the price model plus measurement.

1. **Cared livestock is the engine.** `CARE` banks +1/day and pays on the next
   production, so a cow gives 3 milk every 2 days. Buy by *live value* —
   `rate × market price × days remaining` — and only when it clears 9× cost.
   **Mixed species always**: the model must rotate to sheep and geese as milk saturates.
2. **Melon is a small, sharp batch.** 9 tiles. Depth is only ~158 units and no town
   shop wants melon, so it is the first thing to crash.
3. **Strawberry is the late crop.** 12 tiles, planted **day 13**. Four shops drain it
   and one tile supplies 0.25/day, so its price *rises* all season.
4. **Wheat is feed, sized by price.** Grow more when wheat is dear, buy when it's cheap.
5. **Hire 14 hands.** Labour is nearly free; travel is the real cost.
6. **Everything clusters around the shed**, idle workers stand still, and assignment
   scores `priority + distance` with priority weighted ×1.

---

## Part 4 — Against a competitive opponent

Measured over 144 games (48 per opponent):

| Opponent | Win rate | My bank | Their bank | My 5th-percentile |
|---|---|---|---|---|
| `starter` | 100% | $120,898 | $3,499 | $102,820 |
| Previous version | 100% | $92,561 | $68,618 | $72,039 |
| **Mirror (itself)** | 50% | **$101,330** | $101,330 | $77,630 |

**The headline: against an opponent exactly as good, the agent still banks $101k — only
16% below its score against a punchbag.** An earlier version dropped 45% in the same
test. That improvement is not luck; it's structural, and this table shows why:

| Item | vs `starter` | Mirror | Change |
|---|---|---|---|
| Fertilizer | $32 | $4 | **−88%** |
| Milk | $286 | $170 | **−40%** |
| Melon | $281 | $192 | **−32%** |
| Strawberry | $296 | $282 | −5% |
| Wool | $249 | $240 | −4% |
| Egg | $70 | $70 | 0% |
| Wheat | $54 | $54 | 0% |

Two players competing crush **fertilizer, milk and melon**. They barely touch
**strawberry, wool, egg and wheat** — the town drains those faster than two farms can
supply them.

So the competitive strategy is: **earn most of your money in markets your opponent
cannot saturate.** That's exactly what the day-13 strawberry batch and the mixed-livestock
rotation do, which is why they were worth $15k and $80k respectively. Melon and
fertilizer are bonus income against weak players and near-worthless against strong ones —
correctly, we keep melon small.

### Known weaknesses

1. **No opponent modelling.** We can see their tiles — their ripening melons are a
   forecast of our future prices — and we ignore it completely.
2. **No lookahead.** Pure 1-ply greedy. Every tuning session has been a hand-search of
   a space that a rollout could search itself.
3. **Cash trough days 3–9.** Bank sits at $300–600, fully invested. It never failed in
   4,000 games, but there is no buffer.
4. **Milk over-production in mirror games.** Room is ~17 cows *split between two players*;
   we still build ~10 and watch the price fall 40%.

---

## Part 5 — Root level: what the agent literally does each turn

```
observation  →  6 stages  →  {"farmer": op, "hands": [op...], "market": [order...]}
```

1. **Census** — walk all 100 tiles once, bucket into animals / plants / weeds / empties.
2. **Land plan** — decide what each empty tile *should become*, limited by a labour
   budget (`crew × 24 / 3.5` jobs per day) so we never plant more than we can water.
3. **Task list** — emit every worthwhile job as `(priority, tile, action, requirement)`.
   The `requirement` matters: `FEED` needs the worker to be *carrying wheat*, so that job
   is never given to a worker who isn't.
4. **Assignment** — score every (worker, job) pair as `priority × 1 + distance`, sort,
   assign greedily.
5. **Idle** — carry produce to the shed if holding ≥10, else stand still.
6. **Market** — sells first, then hires, then feed/seeds/land/livestock, truncated to 10
   orders (the cap is real and silently drops the rest).

That is the entire agent. No search, no learning, no opponent model — a scoring function
and a scheduler, with every constant justified by ~68 games.

---

## Part 6 — Commands

```bash
python eval.py quick                  # one game vs starter
python eval.py trace                  # day-by-day dump — start every debug here
python report.py r_h1.jsonl           # win rate + CI + paired margin
python batch.py run                   # run the PLAN in batch.py across 7 workers
```

To test an idea: add a flag → prove it's a no-op at default → add it to `PLAN` in
`batch.py` → `python batch.py run` → `python report.py`.
