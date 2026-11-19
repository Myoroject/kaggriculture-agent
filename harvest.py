"""Download every ladder replay, extract a summary, delete the 22MB file.

Keeps disk usage flat while giving us the full match history.
"""
import csv
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(HERE, "rtmp")
OUT = os.path.join(HERE, "ladder_all.jsonl")
ME = "james nazareth"


def census(farm):
    c = {}
    for row in farm["tiles"]:
        for t in row:
            if t is None:
                k = "empty"
            elif t == "LOCKED":
                continue
            elif t.get("kind") == "PLANT":
                k = t["crop"]
            elif t.get("kind") == "WEED":
                k = "weed"
            elif t.get("animal"):
                k = t["animal"]
            else:
                k = t["kind"]
            c[k] = c.get(k, 0) + 1
    return c


def summarise(path):
    d = json.load(open(path))
    names = d["info"]["TeamNames"]
    if ME not in names:
        return None
    me = names.index(ME)
    steps = d["steps"]
    farms = steps[-1][0]["observation"]["farms"]
    curve = []
    for day in range(0, 30, 3):
        fs = steps[min(day * 24, len(steps) - 1)][0]["observation"]["farms"]
        curve.append([fs[me]["money"], fs[1 - me]["money"]])
    return {
        "ep": d["info"]["EpisodeId"], "opp": names[1 - me],
        "my": d["rewards"][me], "their": d["rewards"][1 - me],
        "win": int(d["rewards"][me] > d["rewards"][1 - me]),
        "mycen": census(farms[me]), "opcen": census(farms[1 - me]),
        "prices": steps[-1][0]["observation"]["market"]["prices"],
        "curve": curve,
    }


def have():
    if not os.path.exists(OUT):
        return set()
    return {json.loads(l)["ep"] for l in open(OUT)}


def fetch(ep):
    path = os.path.join(TMP, f"episode-{ep}-replay.json")
    if not os.path.exists(path):
        subprocess.run(["kaggle", "competitions", "replay", str(ep), "-p", TMP],
                       capture_output=True, text=True, timeout=600)
    if not os.path.exists(path):
        return None
    try:
        s = summarise(path)
    except Exception as e:
        print("parse fail", ep, e, flush=True)
        s = None
    try:
        os.remove(path)
    except OSError:
        pass
    return s


def main():
    os.makedirs(TMP, exist_ok=True)
    done = have()
    # seed from replays we already downloaded in full
    for f in os.listdir(os.path.join(HERE, "replays")):
        if f.endswith(".json"):
            s = summarise(os.path.join(HERE, "replays", f))
            if s and s["ep"] not in done:
                with open(OUT, "a") as fh:
                    fh.write(json.dumps(s) + "\n")
                done.add(s["ep"])
    ids = [int(r["id"]) for r in csv.DictReader(open("eps.csv"))
           if (r.get("type") or "").endswith("PUBLIC")]
    todo = [e for e in ids if e not in done]
    print(f"{len(done)} already summarised, {len(todo)} to fetch", flush=True)
    n = [0]

    def go(ep):
        s = fetch(ep)
        n[0] += 1
        if s:
            with open(OUT, "a") as fh:
                fh.write(json.dumps(s) + "\n")
        print(f"[{n[0]}/{len(todo)}] {ep} {'ok' if s else 'skip'}", flush=True)

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(go, todo))
    print("total summarised:", len(have()))


if __name__ == "__main__":
    main()
