"""SIH26051 - Ridge regression trainer (numpy only)."""
import csv, json, os
import numpy as np

from ai.dataset import FEATURES, generate_dataset

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "model.json")


def train(dataset_csv=None):
    if dataset_csv is None or not os.path.exists(dataset_csv):
        dataset_csv = generate_dataset()
    X, y = [], []
    with open(dataset_csv) as f:
        for r in csv.DictReader(f):
            X.append([float(r[k]) for k in FEATURES])
            y.append(float(r["t_steady"]))
    X, y = np.array(X), np.array(y)
    mean, std = X.mean(0), X.std(0)
    std[std == 0] = 1.0
    Z = (X - mean) / std
    Zb = np.hstack([np.ones((len(Z), 1)), Z])
    lam = 1e-3
    I = lam * np.eye(Zb.shape[1]); I[0, 0] = 0
    w = np.linalg.solve(Zb.T @ Zb + I, Zb.T @ y)
    r2 = 1 - np.sum((Zb @ w - y) ** 2) / np.sum((y - y.mean()) ** 2)
    with open(MODEL, "w") as f:
        json.dump({"weights": w.tolist(), "mean": mean.tolist(),
                   "std": std.tolist(), "features": FEATURES, "r2": float(r2)}, f)
    print(f"model saved, R2={r2:.4f}")
    return MODEL


if __name__ == "__main__":
    train()