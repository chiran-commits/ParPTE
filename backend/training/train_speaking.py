"""Train ParPTE's speaking trait models on speechocean762 features.

    python training/extract_speechocean.py /path/to/speechocean762 features.csv
    python training/train_speaking.py features.csv models/speaking_traits.joblib

Trains on the official train split, reports Pearson correlation (PCC) with the expert ratings on the
held-out test split, then refits on all 5,000 utterances for the shipped model.
"""
import json
import sys

import joblib
import numpy as np
import pandas as pd
import sklearn
from scipy.stats import pearsonr
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GridSearchCV, GroupKFold

sys.path.insert(0, __file__.rsplit("/training", 1)[0])
from app.scoring.speaking import SPEAKING_FEATURES  # noqa: E402

TARGETS = ["accuracy", "fluency", "prosodic", "completeness"]


def main(csv_path: str, out_path: str) -> None:
    df = pd.read_csv(csv_path)
    df["speaker"] = df["utt"].astype(str).str.zfill(9).str[:5]
    tr, te = df[df.split == "train"], df[df.split == "test"]
    print(f"{len(tr)} train / {len(te)} test utterances, {len(SPEAKING_FEATURES)} features")
    grid = {"max_iter": [300, 600], "learning_rate": [0.03, 0.06], "max_leaf_nodes": [15, 31], "l2_regularization": [0.5, 2.0]}
    metrics, final = {}, {}
    for t in TARGETS:
        search = GridSearchCV(HistGradientBoostingRegressor(random_state=0, min_samples_leaf=20), grid,
                              cv=GroupKFold(5), scoring="neg_mean_squared_error", n_jobs=-1)
        search.fit(tr[SPEAKING_FEATURES].values, tr[t].values, groups=tr["speaker"].values)
        pred = search.best_estimator_.predict(te[SPEAKING_FEATURES].values)
        pcc = pearsonr(pred, te[t])[0]
        mae = float(np.abs(pred - te[t]).mean())
        metrics[t] = {"test_pcc": round(float(pcc), 3), "test_mae": round(mae, 3), "params": search.best_params_}
        print(f"{t:13s} PCC={pcc:.3f}  MAE={mae:.2f}  {search.best_params_}")
        final[t] = HistGradientBoostingRegressor(random_state=0, min_samples_leaf=20, **search.best_params_).fit(df[SPEAKING_FEATURES].values, df[t].values)
    bundle = {"version": "2.0", "feature_names": SPEAKING_FEATURES, "models": final, "metrics": metrics,
              "sklearn": sklearn.__version__, "data": "speechocean762 (CC BY 4.0)", "n_utterances": len(df)}
    joblib.dump(bundle, out_path, compress=3)
    print("saved", out_path)
    print(json.dumps({k: v["test_pcc"] for k, v in metrics.items()}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
