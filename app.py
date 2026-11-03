"""SIH26051 - Shelter Thermal Comfort Analyzer (Flask app)."""
from flask import Flask, render_template, request, jsonify

from data_loader import (load_materials, load_climates,
                         load_uvalue_targets, check_uvalue_compliance)
from temperature import evaluate_design, management_plan, required_active_power, simulate_day_managed

from optimization.scoring import score_design
from optimization.search import generate_candidates
from optimization.ranking import rank_candidates
from ai.predict import predict_temperature
from database import db

app = Flask(__name__)
MATERIALS = load_materials()
U_TARGETS = load_uvalue_targets()

FORM_KEYS = ("length", "width", "height", "window_area", "outdoor_temp",
             "irradiance", "wind_speed", "ach", "occupants", "equipment_w",
             "hours", "insulation", "shade", "evap_kw", "heater_kw",
             "sunrise", "sunset", "min_temp", "max_temp", "sim_mode")


def _params_from_form(f):
    return {k: f[k] for k in FORM_KEYS}


@app.route("/")
def index():
    return render_template("index.html",
                           materials=MATERIALS, climates=load_climates())


@app.route("/analyze", methods=["POST"])
def analyze():
    f = request.form
    params = _params_from_form(f)
    params["wall_mat"] = MATERIALS[f["wall_mat"]]
    params["roof_mat"] = MATERIALS[f["roof_mat"]]
    region = f.get("region") or "rajasthan"
    sim_mode = f.get("sim_mode", "single")

    # --- 24‑HOUR SIMULATION ---
    if sim_mode == "24h":
        # Get parameters
        outdoor_temp = float(params.get("outdoor_temp", 25))
        irradiance = float(params.get("irradiance", 500))
        
        min_temp = float(f.get("min_temp", outdoor_temp - 10))
        max_temp = float(f.get("max_temp", outdoor_temp + 5))
        sunrise = float(f.get("sunrise", 6.0))
        sunset = float(f.get("sunset", 18.0))
        peak_irr = float(f.get("irradiance", irradiance))

        # Run MANAGED 24‑hour simulation
        day_data = simulate_day_managed(params, min_temp, max_temp, sunrise, sunset, peak_irr)

        # Single-run dummy for U-values and cost
        dummy_p = dict(params)
        dummy_p["outdoor_temp"] = max_temp
        dummy_p["irradiance"] = peak_irr
        dummy_p["hours"] = 1
        dummy_res = evaluate_design(dummy_p)
        comp = check_uvalue_compliance(U_TARGETS, region,
                                       dummy_res["u_wall"], dummy_res["u_roof"])

        # Score based on managed performance
        comfort_score = (day_data['managed']['comfort_hours'] / 24) * 100
        cost_score = max(0, 100 - (dummy_res['cost'] / 50000) * 100)
        energy_score = max(0, 100 - (day_data['total_active_kwh'] / 50) * 100)
        total_score = 0.6 * comfort_score + 0.2 * cost_score + 0.2 * energy_score
        score = {
            "total": round(total_score, 2),
            "comfort": round(comfort_score, 2),
            "energy": round(energy_score, 2),
            "cost": round(cost_score, 2),
        }

        return render_template("results.html",
                               mode="24h",
                               day=day_data,
                               p=params,
                               region=region,
                               design_id="DAY-001",
                               comp=comp,
                               r=dummy_res,
                               s=score)

    # --- SINGLE‑RUN (existing logic) ---
    else:
        if f.get("auto", "1") == "1":
            plan = management_plan(params)
            res = plan["managed"]
            measures, active_w = plan["measures"], plan["active_w"]
            passive_t = plan["passive"]["t_after"]
        else:
            res = evaluate_design(params)
            measures, active_w = [], required_active_power(res, params["hours"])
            passive_t = res["t_after"]

        score = score_design(res, active_power_w=active_w)
        comp = check_uvalue_compliance(U_TARGETS, region,
                                       res["u_wall"], res["u_roof"])
        try:
            ai_pred = predict_temperature(params, res)
        except Exception:
            ai_pred = None

        stored = {k: params[k] for k in params if not isinstance(params[k], dict)}
        stored.update(wall_name=params["wall_mat"]["name"],
                      roof_name=params["roof_mat"]["name"],
                      wall_mat=f["wall_mat"], roof_mat=f["roof_mat"],
                      region=region)
        design_id = db.save_design(stored, res, score["total"])

        return render_template("results.html",
                               mode="single",
                               r=res, s=score, p=params,
                               ai=ai_pred, design_id=design_id, comp=comp,
                               region=region, measures=measures,
                               active_w=active_w, passive_t=passive_t)

@app.route("/optimize", methods=["POST"])
def optimize():
    stored = db.get_design(request.form["design_id"])
    params = {k: v for k, v in stored.items()
              if k not in ("wall_name", "roof_name",
                           "wall_mat", "roof_mat", "region")}
    params["wall_mat"] = MATERIALS[stored["wall_mat"]]
    params["roof_mat"] = MATERIALS[stored["roof_mat"]]
    ranked = rank_candidates(list(generate_candidates(MATERIALS, params)), top=15)
    return render_template("optimization.html", ranked=ranked,
                           design_id=request.form["design_id"])


@app.route("/compare")
def compare():
    return render_template("comparison.html")


@app.route("/api/history")
def history():
    return jsonify(db.list_designs())


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
