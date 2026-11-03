"""SIH26051 - Scoring engine for thermal design evaluation."""

def score_design(simulation, active_power_w=None):
    """
    Calculate the overall thermal design score (0-100).
    
    Parameters:
        simulation (dict): Must contain 't_after', 't_out', 'cost', and optionally 'heat_loss_kwh', 'solar_energy_kwh'.
        active_power_w (float, optional): Active heating/cooling power in Watts.
                                          Positive = heating needed, Negative = cooling needed.
    """
    # ---------------------------------------------------------
    # Extract simulation data
    # ---------------------------------------------------------
    if active_power_w is None:
        active_power_w = 0.0
    
    # Get key metrics from simulation
    t_after = simulation.get("t_after", 30.0)
    t_out = simulation.get("t_out", 25.0)
    cost = simulation.get("cost", 10000.0)
    
    # Optional metrics (if available)
    heat_loss_kwh = simulation.get("heat_loss_kwh", 0.0)
    solar_energy_kwh = simulation.get("solar_energy_kwh", 0.0)
    
    # ---------------------------------------------------------
    # 1. COMFORT SCORE (70% weight)
    # Target band: 25-30°C
    # ---------------------------------------------------------
    if 25.0 <= t_after <= 30.0:
        comfort_score = 100.0
    else:
        # Lose 10 points for every °C outside the band
        distance = abs(t_after - 27.5)  # Distance from center of band
        comfort_score = max(0.0, 100.0 - distance * 10)
        # Examples: 26°C -> 85, 24°C -> 65, 35°C -> 25, 20°C -> 25
    
    # ---------------------------------------------------------
    # 2. ENERGY EFFICIENCY SCORE (20% weight)
    # Lower active power = better
    # ---------------------------------------------------------
    # 0 kW active power = 100% energy score
    # 10 kW active power = 0% energy score (linear drop)
    active_kw = abs(active_power_w) / 1000.0
    energy_score = max(0.0, 100.0 - active_kw * 10)
    
    # ---------------------------------------------------------
    # 3. COST SCORE (10% weight)
    # Cheaper construction is better
    # ---------------------------------------------------------
    # ₹0 cost = 100% cost score
    # ₹50,000 cost = 0% cost score (linear drop)
    cost_score = max(0.0, 100.0 - (cost / 50000.0) * 100)
    
    # ---------------------------------------------------------
    # 4. FINAL WEIGHTED SCORE
    # ---------------------------------------------------------
    comfort_weight = 0.70
    efficiency_weight = 0.20
    cost_weight = 0.10
    
    total = (comfort_weight * comfort_score + 
             efficiency_weight * energy_score + 
             cost_weight * cost_score)
    
    # ---------------------------------------------------------
    # 5. Return results with breakdown
    # ---------------------------------------------------------
    return {
        "total": round(total, 2),
        "comfort": round(comfort_score, 2),
        "energy": round(energy_score, 2),
        "cost": round(cost_score, 2),
        "weights": {
            "comfort": comfort_weight,
            "efficiency": efficiency_weight,
            "cost": cost_weight
        },
        # Include raw data for debugging/display
        "t_after": t_after,
        "active_kw": active_kw,
        "cost": cost
    }