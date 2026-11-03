"""SIH26051 - Thermal capacity and time constant."""


def component_capacity(volume, density, specific_heat):
    return volume * density * specific_heat   # J/K


def thermal_capacity(components):
    """components: list of (volume, density, specific_heat)."""
    return sum(component_capacity(*c) for c in components)


def time_constant_hours(capacity_j_k, heat_loss_coeff_w_k):
    """Tau = C / H  (seconds -> hours)."""
    if heat_loss_coeff_w_k <= 0:
        raise ValueError("heat loss coefficient must be > 0")
    return capacity_j_k / (heat_loss_coeff_w_k * 3600.0)