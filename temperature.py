"""
temperature.py – Indoor temperature engine for crop shelters (25–30 °C).
Now with region‑aware material costs and sunrise/sunset‑based solar averaging.
"""
import math
from datetime import datetime, timezone, timedelta

# Your existing external modules (assumed to be in the same directory)
from solar import solar_gain
from heat_loss import u_value, overall_heat_loss_coeff
from thermal_mass import thermal_capacity, time_constant_hours

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
AIR_DENSITY, AIR_CP = 1.2, 1005.0
INS_COST_PER_M3 = 3000.0
SHADE_COST_PER_M2 = 25.0
SHADE_FACTOR = 0.4          # shade net + reflective coating cuts 60% solar gain

TARGET_MIN, TARGET_MAX, TARGET_MID = 25.0, 30.0, 27.5


# ----------------------------------------------------------------------
# Region‑specific material database (from PDF)
# ----------------------------------------------------------------------
# Helper: convert Rs/sq ft to Rs/m² (1 sq ft = 0.092903 m²)
def _rs_per_sqft_to_m2(rs_per_sqft):
    return rs_per_sqft / 0.092903

# Helper: convert Rs/cu m to Rs/m² for a given thickness (m)
def _rs_per_cum_to_m2(rs_per_cum, thickness_m):
    return rs_per_cum * thickness_m

# Material definitions for each region.
# Each entry is a dict with: conductivity, thickness, density, specific_heat,
# absorptivity, cost_per_m2 (in Rs/m²).
# Typical properties are assumed where the PDF only gave costs.
REGION_MATERIALS = {
    "Meghalaya Warm-Humid": {
        "wall": {
            "name": "Ikra Wall/Bamboo Frame",
            "conductivity": 0.15,      # W/mK (typical for bamboo)
            "thickness": 0.15,         # m (assumed)
            "density": 500,            # kg/m³
            "specific_heat": 1200,     # J/kgK
            "absorptivity": 0.6,
            "cost_per_m2": _rs_per_sqft_to_m2((180 + 280) / 2)  # ~ Rs 230 / sq ft avg
        },
        "roof": {
            "name": "CGI Sheets + Timber Frame",
            "conductivity": 0.5,       # W/mK (metal + timber composite)
            "thickness": 0.08,         # m
            "density": 600,
            "specific_heat": 900,
            "absorptivity": 0.7,
            "cost_per_m2": _rs_per_sqft_to_m2((220 + 350) / 2)
        }
    },
    "Ladakh Cold-Arid": {
        "wall": {
            "name": "Rammed Earth / Adobe",
            "conductivity": 0.8,
            "thickness": 0.30,
            "density": 2000,
            "specific_heat": 800,
            "absorptivity": 0.65,
            "cost_per_m2": _rs_per_sqft_to_m2((140 + 220) / 2)
        },
        "roof": {
            "name": "Poplar Beams + Mud Cap",
            "conductivity": 0.6,
            "thickness": 0.25,
            "density": 1200,
            "specific_heat": 850,
            "absorptivity": 0.7,
            "cost_per_m2": _rs_per_sqft_to_m2((160 + 260) / 2)
        }
    },
    "Chennai Hot-Humid": {
        "wall": {
            "name": "AAC Block Masonry",
            "conductivity": 0.2,
            "thickness": 0.20,
            "density": 700,
            "specific_heat": 800,
            "absorptivity": 0.6,
            "cost_per_m2": _rs_per_cum_to_m2((3200 + 4500) / 2, 0.20)  # avg Rs 3850/cu m * 0.2m
        },
        "roof": {
            "name": "RCC Slab + Cool Roof Tile",
            "conductivity": 1.5,
            "thickness": 0.15,
            "density": 2400,
            "specific_heat": 840,
            "absorptivity": 0.5,       # cool roof
            "cost_per_m2": _rs_per_sqft_to_m2((420 + 580) / 2)
        }
    },
    "Jaisalmer Hot-Arid": {
        "wall": {
            "name": "Sandstone Ashlar Masonry",
            "conductivity": 2.0,
            "thickness": 0.25,
            "density": 2500,
            "specific_heat": 800,
            "absorptivity": 0.7,
            "cost_per_m2": _rs_per_sqft_to_m2((250 + 400) / 2)
        },
        "roof": {
            "name": "Stone Slab Over Timber Joists",
            "conductivity": 1.8,
            "thickness": 0.20,
            "density": 2300,
            "specific_heat": 800,
            "absorptivity": 0.7,
            "cost_per_m2": _rs_per_sqft_to_m2((280 + 420) / 2)
        }
    }
}

def get_region_materials(region_name):
    """
    Return (wall_mat, roof_mat) for a given region name.
    Returns None if region not found.
    """
    if region_name in REGION_MATERIALS:
        r = REGION_MATERIALS[region_name]
        return r["wall"], r["roof"]
    return None, None


# ----------------------------------------------------------------------
# Sunrise / Sunset helper (if not provided by the user)
# ----------------------------------------------------------------------
def sunrise_sunset(lat_deg, lon_deg, date, tz_offset=0):
    """
    Returns (sunrise_utc, sunset_utc) as datetime objects.
    lat_deg, lon_deg: float (degrees)
    date: datetime.date object
    tz_offset: hours from UTC (e.g., +5.5 for IST)
    """
    lat = math.radians(lat_deg)
    # Day of year
    start = datetime(date.year, 1, 1).toordinal()
    doy = date.toordinal() - start + 1

    # Solar declination (degrees)
    dec_deg = 23.45 * math.sin(math.radians(360 / 365 * (284 + doy)))
    dec = math.radians(dec_deg)

    # Hour angle at sunrise/sunset (radians)
    cos_ha = -math.tan(lat) * math.tan(dec)
    cos_ha = max(-1, min(1, cos_ha))  # clamp
    ha = math.acos(cos_ha)  # in radians

    # Solar noon (UTC) – approximate equation of time
    b = math.radians(360 / 365 * (doy - 81))
    eot = 9.87 * math.sin(2*b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)  # minutes
    solar_noon_utc = 12.0 - (lon_deg / 15.0) - (eot / 60.0)

    sunrise_utc = solar_noon_utc - math.degrees(ha) / 15.0
    sunset_utc   = solar_noon_utc + math.degrees(ha) / 15.0

    # Convert to datetime
    base = datetime(date.year, date.month, date.day, tzinfo=timezone.utc)
    sunrise_dt = base + timedelta(hours=sunrise_utc)
    sunset_dt  = base + timedelta(hours=sunset_utc)

    return sunrise_dt, sunset_dt


def _get_sunrise_sunset_hours(p):
    """
    Return (sunrise_hour, sunset_hour) in local time (float 0–24).
    If p has 'sunrise' and 'sunset' keys, use them.
    Otherwise, compute from latitude/longitude/date if available.
    If neither, return (None, None).
    """
    if "sunrise" in p and "sunset" in p:
        return float(p["sunrise"]), float(p["sunset"])

    lat = p.get("latitude")
    lon = p.get("longitude")
    date = p.get("date")
    if lat is not None and lon is not None and date is not None:
        # date can be a string "YYYY-MM-DD" or a datetime.date object
        if isinstance(date, str):
            try:
                date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError("date must be YYYY-MM-DD string or datetime.date object")
        tz = float(p.get("timezone_offset", 0))
        sunrise_dt, sunset_dt = sunrise_sunset(lat, lon, date, tz)
        # Convert to hours of the day (local time)
        sunrise_local = sunrise_dt + timedelta(hours=tz)
        sunset_local = sunset_dt + timedelta(hours=tz)
        sunrise_hour = sunrise_local.hour + sunrise_local.minute / 60.0 + sunrise_local.second / 3600.0
        sunset_hour = sunset_local.hour + sunset_local.minute / 60.0 + sunset_local.second / 3600.0
        return sunrise_hour, sunset_hour

    return None, None


def _average_irradiance(peak_irr, start_hour, duration, sunrise, sunset):
    """
    Compute the average irradiance over the time window [start_hour, start_hour+duration]
    assuming a half‑sine shape between sunrise and sunset.
    If the window is entirely outside daylight, returns 0.
    If sunrise/sunset are None, returns peak_irr (constant).
    """
    if sunrise is None or sunset is None or sunset <= sunrise:
        return peak_irr  # fallback to constant

    # Clamp the simulation window to [0, 24] (assume hours are 0‑24)
    start = max(0.0, start_hour)
    end = min(24.0, start_hour + duration)
    if end <= start:
        return 0.0

    # Intersect with daylight
    dawn = max(start, sunrise)
    dusk = min(end, sunset)
    if dusk <= dawn:
        return 0.0

    # Numerical integration over the overlap
    steps = max(1, int((dusk - dawn) * 10))  # 0.1 h resolution
    total = 0.0
    day_len = sunset - sunrise
    for i in range(steps):
        t = dawn + (i / steps) * (dusk - dawn)
        if sunrise <= t <= sunset:
            frac = (t - sunrise) / day_len
            val = peak_irr * math.sin(math.pi * frac)
            total += val
    avg = total / steps
    return avg


# ----------------------------------------------------------------------
# Core design evaluation
# ----------------------------------------------------------------------
def evaluate_design(p):
    """
    Evaluates a design with optional region‑aware materials and solar averaging.
    Expects dict p with keys:
        - length, width, height (m)
        - window_area (m²), wind_speed (m/s), ach (1/h)
        - irradiance (peak W/m²) – used for the sine shape
        - outdoor_temp (°C), occupants, equipment_w (W)
        - hours (duration of simulation, h) – default 6
        - start_hour (hour of day when simulation starts, 0‑24) – default 0
        - insulation (m), shade (0/1), evap_kw, heater_kw
        - region (str) – if provided, and wall_mat/roof_mat are absent, uses region defaults.
        - wall_mat, roof_mat (dicts) – if provided, they override region defaults.
        - Optional: sunrise, sunset (hours) OR latitude, longitude, date, timezone_offset
    Returns a dict with results.
    """
    # ---- Extract parameters ----
    L, W, Ht = float(p["length"]), float(p["width"]), float(p["height"])
    win   = float(p.get("window_area", 0))
    wind  = float(p.get("wind_speed", 1.0))
    ach   = float(p.get("ach", 1.0))
    t_out = float(p.get("outdoor_temp", 20))
    occ   = int(p.get("occupants", 0))
    equip = float(p.get("equipment_w", 0))
    hours = float(p.get("hours", 6.0))
    start_hour = float(p.get("start_hour", 0.0))
    ins   = float(p.get("insulation", 0))
    shade = int(p.get("shade", 0))
    evap  = float(p.get("evap_kw", 0)) * 1000.0
    heat  = float(p.get("heater_kw", 0)) * 1000.0

    # ---- Material handling ----
    # Get region defaults if no explicit materials
    region = p.get("region")
    wall_mat = p.get("wall_mat")
    roof_mat = p.get("roof_mat")
    if wall_mat is None or roof_mat is None:
        if region:
            default_wall, default_roof = get_region_materials(region)
            if default_wall and default_roof:
                if wall_mat is None:
                    wall_mat = default_wall
                if roof_mat is None:
                    roof_mat = default_roof
        # If still missing, raise error
        if wall_mat is None or roof_mat is None:
            raise ValueError("Missing wall_mat/roof_mat or valid region.")

    # Ensure they are dicts (they might come as strings if the front‑end only sent names)
    if isinstance(wall_mat, str):
        # Look up by name? For now, we assume it's already a dict.
        # In practice, you might want to lookup from a global material registry.
        pass
    if isinstance(roof_mat, str):
        pass

    wm, rm = wall_mat, roof_mat

    # ---- Geometry ----
    wall_gross = 2 * (L + W) * Ht
    wall_area  = max(0.0, wall_gross - win)
    roof_area  = L * W
    volume     = L * W * Ht

    # ---- Heat loss ----
    u_wall = u_value(wm["conductivity"], wm["thickness"], wind, insulation=ins)
    u_roof = u_value(rm["conductivity"], rm["thickness"], wind, insulation=ins)
    H = overall_heat_loss_coeff(u_wall, wall_area, u_roof, roof_area,
                                win, volume, ach)

    # ---- Solar gain (time‑averaged) ----
    peak_irr = float(p.get("irradiance", 0))
    sunrise, sunset = _get_sunrise_sunset_hours(p)
    avg_irr = _average_irradiance(peak_irr, start_hour, hours, sunrise, sunset)

    q_solar = solar_gain(avg_irr, roof_area, wall_area, win,
                         rm["absorptivity"], wm["absorptivity"])
    if shade:
        q_solar *= SHADE_FACTOR

    q_int = occ * 100.0 + equip
    q_active = heat - evap

    # ---- Steady‑state and transient ----
    t_steady = steady_state_temp(t_out, q_solar + q_int + q_active, H)

    capacity = thermal_capacity([
        (wall_gross * wm["thickness"], wm["density"], wm["specific_heat"]),
        (roof_area * rm["thickness"], rm["density"], rm["specific_heat"]),
        (volume, AIR_DENSITY, AIR_CP),
    ])
    tau = time_constant_hours(capacity, H)
    t_after = transient_temp(t_out, t_steady, tau, hours)

    # ---- Cost ----
    cost = (wall_gross * wm["cost_per_m2"] + roof_area * rm["cost_per_m2"]
            + (wall_gross + roof_area) * ins * INS_COST_PER_M3)
    if shade:
        cost += (wall_gross + roof_area) * SHADE_COST_PER_M2

    return {
        "wall_area": wall_area,
        "roof_area": roof_area,
        "volume": volume,
        "u_wall": u_wall,
        "u_roof": u_roof,
        "H": H,
        "q_solar": q_solar,
        "q_int": q_int,
        "capacity": capacity,
        "tau_hours": tau,
        "t_steady": t_steady,
        "t_after": t_after,
        "cost": cost,
        "t_out": t_out,
        "shade": shade,
        "active_w": q_active,
        "avg_irradiance": avg_irr,
        "wall_material_name": wm.get("name", "Custom"),
        "roof_material_name": rm.get("name", "Custom"),
    }


# ----------------------------------------------------------------------
# Helper functions (unchanged)
# ----------------------------------------------------------------------
def steady_state_temp(t_out, gains_w, H):
    return t_out + gains_w / H


def transient_temp(t_start, t_steady, tau_h, hours):
    if tau_h <= 0:
        return t_steady
    return t_steady + (t_start - t_steady) * math.exp(-hours / tau_h)


def required_active_power(res, hours=None, t_target=TARGET_MID):
    """+W = heating needed, -W = cooling needed to hit t_target after `hours`."""
    tau = res["tau_hours"]
    h = float(hours) if hours else None
    if h and tau > 0:
        e = math.exp(-h / tau)
        t_ss_need = (t_target - res["t_out"] * e) / (1 - e) if e < 0.999 else t_target
    else:
        t_ss_need = t_target
    return res["H"] * (t_ss_need - res["t_out"]) - (res["q_solar"] + res["q_int"])


# ----------------------------------------------------------------------
# Management plan (unchanged)
# ----------------------------------------------------------------------
def management_plan(params):
    """Auto-manage: shade -> then size cooler/heater so indoor lands at 27.5 C."""
    base = evaluate_design(params)
    p, measures, active = dict(params), [], 0.0

    if base["t_after"] > TARGET_MAX:                      # too HOT
        p["shade"] = 1
        measures.append("Shade net + reflective coating (−60% solar gain)")
        shaded = evaluate_design(p)
        cool = -required_active_power(shaded, p.get("hours"))
        if cool > 0:
            p["evap_kw"] = round(cool / 1000.0, 2)
            active = -cool
            measures.append(f"Evaporative cooler ≈ {p['evap_kw']:.1f} kW (hot-dry)")
        managed = evaluate_design(p)
    elif base["t_after"] < TARGET_MIN:                    # too COLD
        heat = required_active_power(base, p.get("hours"))
        if heat > 0:
            p["heater_kw"] = round(heat / 1000.0, 2)
            active = heat
            measures.append(f"Heater / passive-solar backup ≈ {p['heater_kw']:.1f} kW")
        managed = evaluate_design(p)
    else:
        managed = base

    return {"passive": base, "managed": managed,
            "measures": measures, "active_w": active}

# ----------------------------------------------------------------------
# 24‑Hour Dynamic Simulation
# ----------------------------------------------------------------------

def step_design(p, t_out, irradiance, t_start, dt_hours):
    """
    Run a single time step (e.g., 1 hour) of the transient simulation.
    Returns (t_after, q_solar, q_loss) where:
        t_after  = indoor temperature after dt_hours
        q_solar  = solar heat gain during that hour (W)
        q_loss   = heat loss to outside during that hour (W, positive = heat leaving)
    """
    # Extract parameters (reuse the same logic as evaluate_design)
    L, W, Ht = float(p["length"]), float(p["width"]), float(p["height"])
    win   = float(p.get("window_area", 0))
    wind  = float(p.get("wind_speed", 1.0))
    ach   = float(p.get("ach", 1.0))
    ins   = float(p.get("insulation", 0))
    shade = int(p.get("shade", 0))
    occ   = int(p.get("occupants", 0))
    equip = float(p.get("equipment_w", 0))

    # Materials (must be dicts)
    wm = p["wall_mat"]
    rm = p["roof_mat"]

    # Geometry
    wall_gross = 2 * (L + W) * Ht
    wall_area  = max(0.0, wall_gross - win)
    roof_area  = L * W
    volume     = L * W * Ht

    # Heat loss coefficient
    u_wall = u_value(wm["conductivity"], wm["thickness"], wind, insulation=ins)
    u_roof = u_value(rm["conductivity"], rm["thickness"], wind, insulation=ins)
    H = overall_heat_loss_coeff(u_wall, wall_area, u_roof, roof_area, win, volume, ach)

    # Solar gain (at the given irradiance)
    q_solar = solar_gain(irradiance, roof_area, wall_area, win,
                         rm["absorptivity"], wm["absorptivity"])
    if shade:
        q_solar *= SHADE_FACTOR

    # Internal gains
    q_int = occ * 100.0 + equip

    # Total heat gain (W)
    q_total = q_solar + q_int

    # Steady-state temperature at current outdoor temp
    t_steady = steady_state_temp(t_out, q_total, H)

    # Thermal capacity
    capacity = thermal_capacity([
        (wall_gross * wm["thickness"], wm["density"], wm["specific_heat"]),
        (roof_area * rm["thickness"], rm["density"], rm["specific_heat"]),
        (volume, AIR_DENSITY, AIR_CP),
    ])
    tau = time_constant_hours(capacity, H)

    # New indoor temperature after dt_hours
    t_after = transient_temp(t_start, t_steady, tau, dt_hours)

    # Heat loss = H * (t_start - t_out)   (positive if indoor > outdoor)
    q_loss = H * (t_start - t_out)

    return t_after, q_solar, q_loss


def simulate_day(p, min_temp=None, max_temp=None, sunrise=None, sunset=None, peak_irr=None, steps=24):
    """
    Run a full 24‑hour simulation with diurnal outdoor temperature and solar irradiance.

    If min_temp, max_temp, sunrise, sunset are not provided, they are derived from
    the parameters (e.g., from latitude/longitude/date or user inputs).
    peak_irr is taken from p['irradiance'] if not given.

    Returns a dict with:
        - history: list of dicts for each hour with keys: hour, t_out, t_in, solar_gain_w, heat_loss_w
        - min_temp, max_temp, avg_temp (indoor)
        - comfort_hours (number of hours indoor temp is 25–30°C)
        - solar_gain_kwh, heat_loss_kwh (total over 24h)
    """
    # Default values
    if peak_irr is None:
        peak_irr = float(p.get("irradiance", 500.0))

    # Get sunrise/sunset if not provided
    if sunrise is None or sunset is None:
        sr, ss = _get_sunrise_sunset_hours(p)
        if sr is not None and ss is not None:
            sunrise, sunset = sr, ss
        else:
            # Fallback: assume 6:00 – 18:00
            sunrise, sunset = 6.0, 18.0

    # Get min/max outdoor temp if not provided
    if min_temp is None or max_temp is None:
        # Use p['outdoor_temp'] as average and assume a swing of ±15°C
        avg_t = float(p.get("outdoor_temp", 25.0))
        min_temp = avg_t - 15.0
        max_temp = avg_t + 15.0

    dt = 1.0  # 1 hour per step
    avg_temp = (min_temp + max_temp) / 2.0
    amp_temp = (max_temp - min_temp) / 2.0

    # Start the indoor temp at the average of min/max (initial condition)
    t_in = avg_temp

    history = []
    total_solar_kwh = 0.0
    total_heat_loss_kwh = 0.0
    comfort_hours = 0
    sum_temp = 0.0
    peak_temp = -1e9
    min_temp_indoor = 1e9

    for h in range(steps):
        # 1. Outdoor temperature: sinusoidal with peak at 15:00 (3 PM), min at 5:00 AM
        t_out = avg_temp + amp_temp * math.sin((h - 15) * math.pi / 12.0)

        # 2. Solar irradiance: half‑sine between sunrise and sunset
        if sunrise <= h <= sunset:
            day_len = sunset - sunrise
            frac = (h - sunrise) / day_len
            irr = peak_irr * math.sin(math.pi * frac)
            if irr < 0:
                irr = 0
        else:
            irr = 0.0

        # 3. Run one step
        t_in_new, q_solar, q_loss = step_design(p, t_out, irr, t_in, dt)

        # 4. Record data
        history.append({
            'hour': h,
            't_out': round(t_out, 2),
            't_in': round(t_in_new, 2),
            'solar_gain_w': round(q_solar, 2),
            'heat_loss_w': round(q_loss, 2)
        })

        # 5. Accumulate
        total_solar_kwh += q_solar * dt / 1000.0
        total_heat_loss_kwh += q_loss * dt / 1000.0  # positive if heat escapes
        if 25.0 <= t_in_new <= 30.0:
            comfort_hours += 1
        if t_in_new > peak_temp:
            peak_temp = t_in_new
        if t_in_new < min_temp_indoor:
            min_temp_indoor = t_in_new
        sum_temp += t_in_new

        t_in = t_in_new  # update for next step

    avg_temp_indoor = sum_temp / steps

    return {
        'history': history,
        'min_temp': round(min_temp_indoor, 2),
        'max_temp': round(peak_temp, 2),
        'avg_temp': round(avg_temp_indoor, 2),
        'comfort_hours': comfort_hours,
        'solar_gain_kwh': round(total_solar_kwh, 2),
        'heat_loss_kwh': round(total_heat_loss_kwh, 2),
    }


def simulate_day_managed(p, min_temp=None, max_temp=None, sunrise=None, sunset=None, peak_irr=None, steps=24):
    """
    Run a full 24‑hour simulation WITH active heating/cooling management.
    At each hour, applies the optimal heating/cooling to maintain 25-30°C.
    
    Returns a dict with:
        - history: list of dicts for each hour with keys:
            hour, t_out, t_in_passive, t_in_managed, solar_gain_w, 
            heat_loss_w, active_power_w, heater_power, cooler_power
        - passive: dict with min/max/avg/comfort_hours/solar_gain/heat_loss (no controls)
        - managed: dict with min/max/avg/comfort_hours (with controls)
        - total_active_kwh: total active energy used over 24h
    """
    if peak_irr is None:
        peak_irr = float(p.get("irradiance", 500.0))

    # Get sunrise/sunset if not provided
    if sunrise is None or sunset is None:
        sr, ss = _get_sunrise_sunset_hours(p)
        if sr is not None and ss is not None:
            sunrise, sunset = sr, ss
        else:
            sunrise, sunset = 6.0, 18.0

    # Get min/max outdoor temp if not provided
    if min_temp is None or max_temp is None:
        avg_t = float(p.get("outdoor_temp", 25.0))
        min_temp = avg_t - 15.0
        max_temp = avg_t + 15.0

    dt = 1.0  # 1 hour per step
    avg_temp = (min_temp + max_temp) / 2.0
    amp_temp = (max_temp - min_temp) / 2.0

    # Start indoor temp at the average
    t_in_passive = avg_temp
    t_in_managed = avg_temp

    history = []
    total_solar_kwh = 0.0
    total_heat_loss_kwh = 0.0
    total_active_kwh = 0.0
    
    # Passive stats
    passive_comfort = 0
    passive_sum = 0
    passive_peak = -1e9
    passive_min = 1e9
    
    # Managed stats
    managed_comfort = 0
    managed_sum = 0
    managed_peak = -1e9
    managed_min = 1e9

    for h in range(steps):
        # 1. Outdoor temperature: sinusoidal peak at 3 PM, min at 5 AM
        t_out = avg_temp + amp_temp * math.sin((h - 15) * math.pi / 12.0)

        # 2. Solar irradiance: half‑sine between sunrise and sunset
        if sunrise <= h <= sunset:
            day_len = sunset - sunrise
            frac = (h - sunrise) / day_len
            irr = peak_irr * math.sin(math.pi * frac)
            if irr < 0:
                irr = 0
        else:
            irr = 0.0

        # --- PASSIVE (no controls) ---
        t_in_new_passive, q_solar, q_loss = step_design(p, t_out, irr, t_in_passive, dt)
        
        # --- MANAGED (with controls) ---
        # Build a parameter dict with current conditions
        current_p = dict(p)
        # Override outdoor temp and irradiance for this hour
        current_p["outdoor_temp"] = t_out
        current_p["irradiance"] = irr
        # Run management plan to get optimal heating/cooling
        plan = management_plan(current_p)
        # The managed result includes the active power applied
        managed_res = plan["managed"]
        t_in_new_managed = managed_res["t_after"]
        active_w = plan["active_w"]  # positive = heating, negative = cooling
        
        # For the next hour, we use the managed temperature as the starting point
        # (we run the controls every hour)

        # --- Record data ---
        history.append({
            'hour': h,
            't_out': round(t_out, 2),
            't_in_passive': round(t_in_new_passive, 2),
            't_in_managed': round(t_in_new_managed, 2),
            'solar_gain_w': round(q_solar, 2),
            'heat_loss_w': round(q_loss, 2),
            'active_power_w': round(active_w, 2),
            'heater_power': round(max(0, active_w), 2),
            'cooler_power': round(max(0, -active_w), 2)
        })

        # --- Accumulate totals ---
        total_solar_kwh += q_solar * dt / 1000.0
        total_heat_loss_kwh += q_loss * dt / 1000.0
        total_active_kwh += abs(active_w) * dt / 1000.0

        # Passive stats
        if 25.0 <= t_in_new_passive <= 30.0:
            passive_comfort += 1
        if t_in_new_passive > passive_peak:
            passive_peak = t_in_new_passive
        if t_in_new_passive < passive_min:
            passive_min = t_in_new_passive
        passive_sum += t_in_new_passive

        # Managed stats
        if 25.0 <= t_in_new_managed <= 30.0:
            managed_comfort += 1
        if t_in_new_managed > managed_peak:
            managed_peak = t_in_new_managed
        if t_in_new_managed < managed_min:
            managed_min = t_in_new_managed
        managed_sum += t_in_new_managed

        # Update for next step
        t_in_passive = t_in_new_passive
        t_in_managed = t_in_new_managed

    passive_avg = passive_sum / steps
    managed_avg = managed_sum / steps

    return {
        'history': history,
        'passive': {
            'min_temp': round(passive_min, 2),
            'max_temp': round(passive_peak, 2),
            'avg_temp': round(passive_avg, 2),
            'comfort_hours': passive_comfort,
            'solar_gain_kwh': round(total_solar_kwh, 2),
            'heat_loss_kwh': round(total_heat_loss_kwh, 2),
        },
        'managed': {
            'min_temp': round(managed_min, 2),
            'max_temp': round(managed_peak, 2),
            'avg_temp': round(managed_avg, 2),
            'comfort_hours': managed_comfort,
        },
        'total_active_kwh': round(total_active_kwh, 2),
    }    