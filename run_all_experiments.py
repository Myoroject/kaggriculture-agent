import json
from h2h2 import run_experiment

EXPERIMENTS = [
    ("E1", {"EXP_E1": 1}),
    ("E2", {"EXP_E2": 1, "E2_RADIUS": 4}),
    ("E3", {"EXP_E3": 1, "E3_CARRY": 20}),
    ("E4", {"EXP_E4": 1}),
    ("E5a", {"MELON_TILES": 6}),
    ("E5b", {"MELON_TILES": 3}),
    ("E5c", {"MELON_TILES": 0}),
    ("E6a", {"EXP_E6": 1, "E6_CAP": 20}),
    ("E6b", {"EXP_E6": 1, "E6_CAP": 18}),
    ("E6c", {"EXP_E6": 1, "E6_CAP": 16}),
    ("E7", {"EXP_E7": 1}),
    ("E8", {"EXP_E8": 1, "E8_CAP": 12}),
    ("E9", {"EXP_E9": 1}),
    ("E10", {"EXP_E10": 1}),
    ("E11", {"EXP_E11": 1}),
    ("E12", {"EXP_E12": 1}),
]

if __name__ == "__main__":
    results = {}
    for label, cfg in EXPERIMENTS:
        r = run_experiment(label, cfg)
        results[label] = r
    with open("experiments_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print("DONE")
