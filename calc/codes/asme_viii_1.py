"""
ASME VIII Division 1 — Cylindrical Shell, Internal Pressure
Reference: UG-27(c)
"""


def thickness_internal(P_bar: float, D_i_mm: float, S_MPa: float, E: float = 1.0) -> dict:
    """
    UG-27(c) — Minimum required thickness (structural only, corrosion not included).

    UG-27(c)(1)  Hoop stress (circumferential joints):
        t = P·R / (S·E − 0.6·P)

    UG-27(c)(2)  Longitudinal stress (longitudinal joints):
        t = P·R / (2·S·E + 0.4·P)

    Governing thickness = max of the two.
    """
    P = P_bar * 0.1          # bar → MPa
    R = D_i_mm / 2.0         # inside radius [mm]

    denom_hoop = S_MPa * E - 0.6 * P
    if denom_hoop <= 0:
        return {"error": "S·E − 0.6·P ≤ 0: la pressione supera il limite ammissibile del materiale"}

    t_hoop = P * R / denom_hoop
    t_long = P * R / (2.0 * S_MPa * E + 0.4 * P)
    t_min  = max(t_hoop, t_long)

    return {
        "code":        "ASME VIII-1",
        "ref":         "UG-27(c)",
        "P_MPa":       round(P, 4),
        "R_mm":        round(R, 2),
        "S_MPa":       S_MPa,
        "E":           E,
        "t_hoop_mm":   round(t_hoop, 3),
        "t_long_mm":   round(t_long, 3),
        "t_min_mm":    round(t_min,  3),
        "governing":   "Hoop — UG-27(c)(1)" if t_hoop >= t_long else "Long. — UG-27(c)(2)",
        "latex_hoop":  r"t = \frac{P \cdot R}{S \cdot E - 0.6\,P}",
        "latex_long":  r"t = \frac{P \cdot R}{2\,S \cdot E + 0.4\,P}",
    }


def mawp(t_mm: float, D_i_mm: float, S_MPa: float, E: float = 1.0) -> float:
    """
    Maximum Allowable Working Pressure from analysis thickness.
    UG-27(c)(1) rearranged:  P = S·E·t / (R + 0.6·t)
    Returns [bar].
    """
    R = D_i_mm / 2.0
    if R + 0.6 * t_mm <= 0:
        return 0.0
    return round(S_MPa * E * t_mm / (R + 0.6 * t_mm) / 0.1, 3)


def check(t_nom_mm: float, corr_mm: float, mill_tol_pct: float,
          P_bar: float, D_i_mm: float, S_MPa: float, E: float = 1.0) -> dict:
    """
    Verify a nominal (ordered) thickness against UG-27.

    Available thickness = t_nom × (1 − mill_tol/100) − corr_mm
    Must be ≥ t_min from UG-27(c).

    mill_tol_pct : 12.5% for plate per SA-20, or per material spec for pipe/tube.
    """
    result = thickness_internal(P_bar, D_i_mm, S_MPa, E)
    if "error" in result:
        return result

    t_avail = t_nom_mm * (1.0 - mill_tol_pct / 100.0) - corr_mm
    t_min   = result["t_min_mm"]
    margin  = round(t_avail - t_min, 3)

    result.update({
        "t_nom_mm":      t_nom_mm,
        "mill_tol_pct":  mill_tol_pct,
        "corr_mm":       corr_mm,
        "t_avail_mm":    round(t_avail, 3),
        "margin_mm":     margin,
        "status":        "OK ✅" if margin >= 0 else "INSUFFICIENTE ❌",
        "MAWP_bar":      mawp(max(t_avail, 0), D_i_mm, S_MPa, E),
    })
    return result
