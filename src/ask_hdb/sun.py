"""Illustrative solar geometry at Singapore's centre, in local time (+08:00).

Ignores shade from other blocks and clouds. This is a geometry indicator, not measured heat.
Uses NOAA's fractional-year equations (no atmospheric refraction), not a weather forecast.
Reference: https://gml.noaa.gov/grad/solcalc/solareqns.PDF
"""

from calendar import isleap
from datetime import date as Date
from math import acos, atan2, cos, degrees, pi, radians, sin

from ask_hdb.geo.outlines import compass

LATITUDE, LONGITUDE = 1.3521, 103.8198
LIMITS = ("Illustrative geometry indicator, not measured heat. Ignores shade from other blocks "
          "and clouds. Facing is approximate per block, not per unit; times are Singapore time (+08:00). "
          "Direct-sun hours use quarter-hour samples.")


def positions(date):
    """Return 96 quarter-hour azimuth/altitude samples, compass degrees from north."""
    day = Date.fromisoformat(date) if isinstance(date, str) else date
    latitude = radians(LATITUDE)
    samples = []
    for minute in range(0, 1440, 15):
        gamma = 2 * pi / (366 if isleap(day.year) else 365) * (
            day.timetuple().tm_yday - 1 + (minute / 60 - 12) / 24)
        equation = 229.18 * (0.000075 + 0.001868 * cos(gamma) - 0.032077 * sin(gamma)
                            - 0.014615 * cos(2 * gamma) - 0.040849 * sin(2 * gamma))
        declination = (0.006918 - 0.399912 * cos(gamma) + 0.070257 * sin(gamma)
                       - 0.006758 * cos(2 * gamma) + 0.000907 * sin(2 * gamma)
                       - 0.002697 * cos(3 * gamma) + 0.00148 * sin(3 * gamma))
        hour = radians(((minute + equation + 4 * LONGITUDE - 60 * 8) % 1440) / 4 - 180)
        zenith = acos(max(-1, min(1, sin(latitude) * sin(declination)
                                 + cos(latitude) * cos(declination) * cos(hour))))
        azimuth = (degrees(atan2(sin(hour), cos(hour) * sin(latitude)
                                - sin(declination) / cos(declination) * cos(latitude))) + 180) % 360
        samples.append({"time": f"{minute // 60:02d}:{minute % 60:02d}",
                        "azimuth": round(azimuth, 3), "altitude": round(90 - degrees(zenith), 3)})
    return samples


def wall_exposure(sun_az, sun_alt, wall_bearing):
    """Cosine incidence on a vertical wall, in 0..1; caller excludes night."""
    value = max(0.0, min(1.0, cos(radians(sun_alt)) * cos(radians(sun_az - wall_bearing))))
    return value if value > 1e-12 else 0.0  # perpendicular rays have zero exposure


def facade_day(date, bearings):
    """Per facade: sampled direct-sun hours, first peak time and a full day's exposures.

    Ignores shade from other blocks and clouds: geometry indicator, not measured heat.
    """
    samples = positions(date)
    facades = []
    for bearing in bearings:
        values = [wall_exposure(s["azimuth"], s["altitude"], bearing)
                  if s["altitude"] > 0 else 0.0 for s in samples]
        peak = max(values)
        facades.append({"bearing": bearing, "label": compass(bearing),
                        "hours": sum(v > 0 for v in values) / 4,
                        "peak_time": samples[values.index(peak)]["time"] if peak else None,
                        "exposure": [round(v, 6) for v in values]})
    return facades
