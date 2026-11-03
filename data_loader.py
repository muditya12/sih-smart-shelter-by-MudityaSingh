"""SIH26051 - CSV loaders (materials, climates, U-value targets)."""
import csv
import os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def load_materials():
    mats = {}
    with open(os.path.join(DATA, "materials.csv")) as f:
        for r in csv.DictReader(f):
            mats[r["id"]] = {
                "name": r["name"],
                "conductivity": float(r["conductivity"]),
                "density": float(r["density"]),
                "specific_heat": float(r["specific_heat"]),
                "thickness": float(r["thickness"]),
                "cost_per_m2": float(r["cost_per_m2"]),
                "absorptivity": float(r["absorptivity"]),
            }
    return mats


def load_climates():
    out = []
    with open(os.path.join(DATA, "climate.csv")) as f:
        for r in csv.DictReader(f):
            out.append({
                "id": r["id"],
                "region": r.get("region") or r["id"],   # works with old & new CSV
                "name": r["name"],
                "temp": float(r["outdoor_temp"]),
                "irradiance": float(r["solar_irradiance"]),
                "wind": float(r["wind_speed"]),
            })
    return out


def load_uvalue_targets():
    out = []
    path = os.path.join(DATA, "uvalue_targets.csv")
    if not os.path.exists(path):        # don't crash if file missing yet
        return out
    with open(path) as f:
        for r in csv.DictReader(f):
            out.append({
                "region": r["region"],
                "component": r["component"],
                "u_min": float(r["u_min"]),
                "u_max": float(r["u_max"]),
                "strategy": r.get("strategy", ""),
            })
    return out


def check_uvalue_compliance(targets, region, u_wall, u_roof):
    res = {}
    for comp, u in (("external_wall", u_wall), ("roof", u_roof)):
        t = next((x for x in targets
                  if x["region"] == region and x["component"] == comp), None)
        res[comp] = None if t is None else {
            "ok": t["u_min"] <= u <= t["u_max"],
            "range": (t["u_min"], t["u_max"]),
            "strategy": t["strategy"],
        }
    return res