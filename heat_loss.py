"""SIH26051 - Conduction + infiltration heat loss."""

R_IN = 0.13          # internal surface resistance (m2K/W)
INS_K = 0.035        # conductivity of added insulation (W/mK)
U_WINDOW = 3.0       # glazed window U-value (W/m2K)


def outside_resistance(wind_speed=1.0):
    h = 5.8 + 3.94 * max(0.0, float(wind_speed))
    return 1.0 / h


def u_value(conductivity, thickness, wind_speed=1.0, insulation=0.0):
    r = (R_IN + thickness / conductivity + insulation / INS_K
         + outside_resistance(wind_speed))
    return 1.0 / r


def infiltration_coeff(volume, ach):
    """W/K due to air changes: Q = 0.33 * ACH * V * dT."""
    return 0.33 * ach * volume


def overall_heat_loss_coeff(u_wall, wall_area, u_roof, roof_area,
                            window_area, volume, ach):
    return (u_wall * wall_area + u_roof * roof_area
            + U_WINDOW * window_area + infiltration_coeff(volume, ach))


def heat_loss_watts(H, delta_t):
    return H * delta_t