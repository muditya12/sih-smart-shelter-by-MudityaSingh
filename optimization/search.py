"""SIH26051 - Candidate search over materials, insulation AND shade."""
from temperature import evaluate_design, required_active_power
from optimization.scoring import score_design

INS_OPTIONS = (0.0, 0.05, 0.10)
SHADE_OPTIONS = (0, 1)


def generate_candidates(materials, base_params):
    for wm in materials.values():
        for rm in materials.values():
            for ins in INS_OPTIONS:
                for shade in SHADE_OPTIONS:
                    p = dict(base_params)
                    p.update(wall_mat=wm, roof_mat=rm,
                             insulation=ins, shade=shade,
                             evap_kw=0, heater_kw=0)
                    res = evaluate_design(p)
                    aw = required_active_power(res, p.get("hours"))
                    yield {"wall": wm["name"], "roof": rm["name"],
                           "insulation": ins, "shade": shade,
                           "active_w": aw, "result": res,
                           "score": score_design(res, aw)}