"""SIH26051 - AI indoor-temperature predictor."""
import json, os

from ai.dataset import FEATURES
from ai import train as trainer

MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.json")


def _load():
    if not os.path.exists(MODEL):
        trainer.train()
    with open(MODEL) as f:
        return json.load(f)


def features_from(params, res):
    return [float(params["outdoor_temp"]), float(params["irradiance"]),
            float(params["wind_speed"]), res["volume"], res["wall_area"],
            res["roof_area"], float(params["window_area"]), res["u_wall"],
            res["u_roof"], float(params["ach"]), res["q_int"]]


def predict_temperature(params, res):
    m = _load()
    x = (features_from(params, res) - __import__("numpy").array(m["mean"])) \
        / __import__("numpy").array(m["std"])
    w = m["weights"]
    return float(w[0] + sum(wi * xi for wi, xi in zip(w[1:], x)))