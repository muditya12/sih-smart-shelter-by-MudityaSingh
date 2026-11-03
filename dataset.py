"""SIH26051 - Synthetic dataset generator (uses physics engine)."""
import csv, os, random

from data_loader import load_materials
from temperature import evaluate_design

HERE = os.path.dirname(os.path.abspath(__file__))
FEATURES = ["t_out", "irradiance", "wind_speed", "volume", "wall_area",
            "roof_area", "window_area", "u_wall", "u_roof", "ach", "q_int"]


def generate_dataset(n=2000, seed=42):
    rng = random.Random(seed)
    mats = list(load_materials().values())
    path = os.path.join(HERE, "dataset.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(FEATURES + ["t_steady"])
        for _ in range(n):
            p = {
                "length": rng.uniform(2, 6), "width": rng.uniform(2, 6),
                "height": rng.uniform(2, 3.5),
                "window_area": rng.uniform(0, 4),
                "outdoor_temp": rng.uniform(-20, 45),
                "irradiance": rng.uniform(0, 1000),
                "wind_speed": rng.uniform(0, 6),
                "ach": rng.uniform(0.5, 3),
                "occupants": rng.randint(0, 6),
                "equipment_w": rng.uniform(0, 500),
                "insulation": rng.choice([0, 0.05, 0.1]),
                "wall_mat": rng.choice(mats), "roof_mat": rng.choice(mats),
            }
            r = evaluate_design(p)
            row = [p["outdoor_temp"], p["irradiance"], p["wind_speed"],
                   r["volume"], r["wall_area"], r["roof_area"], p["window_area"],
                   r["u_wall"], r["u_roof"], p["ach"], r["q_int"], r["t_steady"]]
            w.writerow([round(float(x), 4) for x in row])
    return path


if __name__ == "__main__":
    print("dataset written to", generate_dataset())