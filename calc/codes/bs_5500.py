"""
BS PD 5500 — Cylindrical Shell, Internal Pressure
Reference: PD 5500:2021, Section 3.5.1.2, Equation (3.5.1.2.1)

Formula (Di-based):
    e = p · Di / (2 · f · z − p)

Notation:
    e   = minimum required thickness [mm]
    p   = design pressure [MPa]
    Di  = inside diameter [mm]
    f   = nominal design strength [MPa]  (from calc.db.materials.allowable_BS5500)
    z   = joint factor (Category 1: 1.0; Category 2: 0.85; Category 3: 0.7)

Nominal design strength (Table 4.3-1, Category 1):
    f = min(Rp0.2_T / 1.5,  Rm_20°C / 2.5)

Note: PD 5500 uses Rm/2.5 (vs EN 13445's Rm/2.4), giving slightly lower allowables.
"""


def thickness_internal(P_bar: float, D_i_mm: float, f_MPa: float, z: float = 1.0) -> dict:
    """
    Minimum required analysis thickness (structural only).
    Same formula form as EN 13445 §7.4.2.
    """
    P = P_bar * 0.1         # bar → MPa

    denom = 2.0 * f_MPa * z - P
    if denom <= 0:
        return {"error": "2·f·z − p ≤ 0: pressure exceeds material capacity"}

    e_min = P * D_i_mm / denom

    return {
        "code":     "BS PD 5500",
        "ref":      "§ 3.5.1.2 Eq. (3.5.1.2.1)",
        "P_MPa":    round(P, 4),
        "Di_mm":    D_i_mm,
        "f_MPa":    f_MPa,
        "z":        z,
        "t_min_mm": round(e_min, 3),
        "governing": "Internal pressure §3.5.1.2",
        "latex":    r"e = \frac{p \cdot D_i}{2\,f \cdot z - p}",
    }


def mawp(e_mm: float, D_i_mm: float, f_MPa: float, z: float = 1.0) -> float:
    """
    Maximum allowable pressure from analysis thickness.
    Rearranged: p = 2·f·z·e / (Di + e)
    Returns [bar].
    """
    denom = D_i_mm + e_mm
    if denom <= 0:
        return 0.0
    return round(2.0 * f_MPa * z * e_mm / denom / 0.1, 3)
