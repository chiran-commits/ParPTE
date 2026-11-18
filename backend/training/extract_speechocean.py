"""Extract ParPTE speaking features for every speechocean762 utterance.

    python training/extract_speechocean.py /path/to/speechocean762 features.csv --workers 2

Get the corpus with:  git clone https://github.com/jimbozhang/speechocean762  (free for commercial use)
"""
import argparse, csv, json, os, sys, wave
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("PARPTE_DISABLE_ML", "1")  # we only need the acoustic engine here

ROOT = None
SCORES = None


def init(root):
    global ROOT, SCORES
    ROOT = root
    SCORES = json.load(open(os.path.join(root, "resource", "scores.json") if os.path.exists(os.path.join(root, "resource")) else os.path.join(root, "scores.json")))


def work(item):
    from app.scoring.speaking import extract_features

    split, utt, rel = item
    try:
        with wave.open(os.path.join(ROOT, rel)) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        f = extract_features(x, SCORES[utt]["text"])
        s = SCORES[utt]
        return {"utt": utt, "split": split, **f, "accuracy": s["accuracy"], "fluency": s["fluency"], "prosodic": s["prosodic"],
                "completeness": s["completeness"], "total": s["total"]}
    except Exception as e:
        print("failed", utt, e, file=sys.stderr)
        return None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("out")
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    a = ap.parse_args()
    items = []
    for split in ("train", "test"):
        for line in open(os.path.join(a.root, split, "wav.scp")):
            utt, rel = line.split()
            items.append((split, utt, rel))
    rows = []
    with Pool(a.workers, initializer=init, initargs=(a.root,)) as pool:
        for i, r in enumerate(pool.imap_unordered(work, items, chunksize=8)):
            if r:
                rows.append(r)
            if i % 250 == 0:
                print(f"{i}/{len(items)}", flush=True)
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("wrote", len(rows), "rows to", a.out)
