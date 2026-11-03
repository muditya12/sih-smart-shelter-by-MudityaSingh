"""SIH26051 - Solar heat gain model for a shelter."""

ROOF_FRACTION = 0.5    # fraction of horizontal irradiance seen by roof
WALL_FRACTION = 0.25   # average fraction seen by walls
OPAQUE_INWARD = 0.3    # fraction of absorbed opaque radiation transferred indoors


def solar_gain(irradiance, roof_area, wall_area, window_area,
               roof_absorptivity=0.6, wall_absorptivity=0.5,
               window_shgc=0.6):
    """Total solar heat gain (W) entering the shelter."""
    if irradiance < 0:
        raise ValueError("irradiance must be >= 0")
    q_windows = irradiance * window_area * window_shgc
    q_roof = irradiance * ROOF_FRACTION * roof_absorptivity * OPAQUE_INWARD * roof_area
    q_walls = irradiance * WALL_FRACTION * wall_absorptivity * OPAQUE_INWARD * wall_area
    return q_windows + q_roof + q_walls