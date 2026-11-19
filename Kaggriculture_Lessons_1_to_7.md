# Kaggriculture Learning Notes (Lessons 1--7)

> **Purpose**
>
> These lessons are a learning guide based on the competition overview
> and getting-started guide. They are intended to build intuition before
> writing an agent.

------------------------------------------------------------------------

# Lesson 1 -- Understanding the World

## Chapter 1 -- What is Kaggriculture?

Kaggriculture is **not really a farming game**.

The farm is simply the environment where an AI agent makes decisions.

Your real job is:

> Maximize the amount of money in the bank after one season.

Think of it like running a startup instead of a farm.

Every purchase (seed, animal, worker, land) is an investment.

### Example

You start with **₹3000**.

You could:

-   Buy wheat
-   Buy a goose
-   Buy land
-   Hire a worker

Each decision changes the future.

------------------------------------------------------------------------

## Chapter 2 -- Objective

Only **cash in the bank at the end of the season** determines the
winner.

Unsold inventory does **not** count.

### Example

Player A

-   ₹90,000 cash

Player B

-   ₹70,000 cash
-   200 melons

Player A wins until Player B actually sells the melons.

------------------------------------------------------------------------

## Chapter 3 -- Time

The season contains:

-   30 Days
-   24 Turns per day
-   720 total turns

Every turn allows decisions.

Example

Turn 1

Buy seed

Turn 2

Plant

Turn 3

Water

Turn 4

Move

------------------------------------------------------------------------

## Chapter 4 -- Every Turn Has Value

Think of turns as money.

Every wasted turn is an opportunity lost forever.

PASS is sometimes correct, but unnecessary PASS actions reduce your
ability to generate value.

------------------------------------------------------------------------

## Chapter 5 -- State

The **state** is everything the agent currently knows.

It includes:

-   Money
-   Day
-   Hour
-   Market prices
-   Crops
-   Animals
-   Workers
-   Inventory
-   Opponent farm
-   Town shops

Different states require different decisions.

------------------------------------------------------------------------

## Chapter 6 -- Action

The agent observes the state and chooses an action.

Examples:

-   WATER
-   HARVEST
-   BUY_SEED
-   BUY_ANIMAL
-   MOVE
-   PASS

Actions transform the state.

------------------------------------------------------------------------

## Chapter 7 -- Decision Chain

One decision influences many future decisions.

Buying a goose today may eventually produce eggs, money, cows, land
expansion and additional workers.

------------------------------------------------------------------------

# Lesson 2 -- Decision Making

## Chapter 1 -- Every Turn Is A Choice

Each turn presents mutually exclusive options.

Choosing one means giving up others.

------------------------------------------------------------------------

## Chapter 2 -- Opportunity Cost

Opportunity cost is the value of the best option you didn't choose.

Example:

Buy Goose

vs

Buy Wheat

If Goose earns ₹500 more by Day 30, then Wheat had an opportunity cost
of ₹500.

------------------------------------------------------------------------

## Chapter 3 -- Think Long Term

Strong agents optimize Day 30.

Weak agents optimize today's income.

------------------------------------------------------------------------

## Chapter 4 -- Strategy

A strategy is a collection of decisions serving one long-term objective.

Examples:

-   Wheat Economy
-   Animal Economy
-   Expansion Strategy
-   High-value Crop Strategy

------------------------------------------------------------------------

## Chapter 5 -- Hypothesis

Example:

"I believe buying a Goose on Day 1 beats buying Wheat."

This is not knowledge.

It must be tested.

------------------------------------------------------------------------

## Chapter 6 -- Experiments

Run many games.

Measure average money.

Accept or reject the hypothesis.

------------------------------------------------------------------------

## Chapter 7 -- Experiment Log

Record every change.

  Experiment   Change   Result
  ------------ -------- ----------
  E1           Wheat    Baseline
  E2           Goose    Better

------------------------------------------------------------------------

# Lesson 3 -- Economics

Understand every purchase as an investment.

For every object ask:

-   Initial Cost
-   Maintenance Cost
-   Time before earning
-   Lifetime Profit
-   ROI
-   Payback Period
-   Opportunity Cost

Example:

Buying a Cow is not spending ₹400.

It is purchasing a future stream of milk.

------------------------------------------------------------------------

# Lesson 4 -- Crops

Study every crop individually.

For each crop learn:

-   Seed Cost
-   Yield
-   Water Requirement
-   Fertilizer Effect
-   Harvest Timing
-   Market Behaviour

Example:

Melon

High profit

Long wait

Large risk if prices collapse.

Example:

Wheat

Cheap

Fast

Useful as animal feed.

------------------------------------------------------------------------

# Lesson 5 -- Animals

Animals are long-term investments.

Understand:

-   Feed
-   CARE
-   Harvest
-   Fertilizer
-   Hidden maintenance

Questions to answer:

Why buy Goose?

Why buy Cow?

Why buy Sheep?

When do they outperform crops?

------------------------------------------------------------------------

# Lesson 6 -- Market Dynamics

The market is shared.

Prices change according to:

-   Player selling
-   Player buying
-   Town consumption

Scarcity increases prices.

Oversupply decreases prices.

Questions to explore:

Should we sell immediately?

Should we wait?

Can we influence prices?

------------------------------------------------------------------------

# Lesson 7 -- AI Agent Thinking

The agent follows one loop.

Observe State

↓

Evaluate Options

↓

Estimate Future Reward

↓

Choose Best Action

↓

Receive New State

↓

Repeat

Eventually the agent should replace hardcoded rules with measured
evidence.

------------------------------------------------------------------------

# Master Learning Loop

Observe

↓

Think

↓

Hypothesis

↓

Experiment

↓

Measure

↓

Learn

↓

Improve

↓

Repeat

This is the mindset behind successful Kaggle competitors and production
ML teams.
