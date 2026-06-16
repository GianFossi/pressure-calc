"""
EN 13445-3 — Cylindrical Shell, Internal Pressure
Reference: Section 7.4.2, Equation (7.4-1)
"""


def thickness_internal(P_bar: float, D_i_mm: float, f_MPa: float, z: float = 1.0) -> dict:
    """
    §7.4.2 Eq. (7.4-1) — Minimum required analysis thickness (structural only).

        e = P · Di / (2·f·z − P)

    Equivalent in terms of inside radius Ri = Di/2:
        e = P · Ri / (f·z − 0.5·P)

    Note: EN uses 0.5·P vs ASME's 0.6·P → ASME is slightly more conservative
    (difference vanishes for P << f·z, i.e. thin shells at low pressure ratio).
    """
    P = P_bar * 0.1          # bar → MPa

    denom = 2.0 * f_MPa * z - P
    if denom <= 0:
        return {"error": "2·f·z − P ≤ 0: la pressione supera il limite ammissibile del materiale"}

    e_min = P * D_i_mm / denom

    return {
        "code":     "EN 13445-3",
        "ref":      "§ 7.4.2 Eq. (7.4-1)",
        "P_MPa":    round(P, 4),
        "D_i_mm":   D_i_mm,
        "f_MPa":    f_MPa,
        "z":        z,
        "e_min_mm": round(e_min, 3),
        "t_min_mm": round(e_min, 3),   # alias — consistent key across all code modules
        "governing": "Internal pressure §7.4.2",
        "latex":    r"e = \frac{P \cdot D_i}{2\,f \cdot z - P}",
    }


def ps_max(e_mm: float, D_i_mm: float, f_MPa: float, z: float = 1.0) -> float:
    """
    Maximum Allowable Pressure (PS) from analysis thickness.
    Eq. (7.4-1) rearranged:  P = 2·f·z·e / (Di + e)
    Returns [bar].
    """
    if D_i_mm + e_mm <= 0:
        return 0.0
    return round(2.0 * f_MPa * z * e_mm / (D_i_mm + e_mm) / 0.1, 3)


def check(e_nom_mm: float, corr_mm: float, undertol_mm: float,
          P_bar: float, D_i_mm: float, f_MPa: float, z: float = 1.0) -> dict:
    """
    Verify a nominal (ordered) thickness against EN 13445-3 §7.4.2.

    Available analysis thickness (§6.1.5):
        e_avail = e_nom − δ₁ − c
    where δ₁ = negative mill tolerance [mm absolute], c = total corrosion allowance.
    Must be ≥ e_min from Eq. (7.4-1).
    """
    result = thickness_internal(P_bar, D_i_mm, f_MPa, z)
    if "error" in result:
        return result

    e_avail = e_nom_mm - undertol_mm - corr_mm
    e_min   = result["e_min_mm"]
    margin  = round(e_avail - e_min, 3)

    result.update({
        "e_nom_mm":    e_nom_mm,
        "undertol_mm": undertol_mm,
        "corr_mm":     corr_mm,
        "e_avail_mm":  round(e_avail, 3),
        "margin_mm":   margin,
        "status":      "OK ✅" if margin >= 0 else "INSUFFICIENTE ❌",
        "PS_max_bar":  ps_max(max(e_avail, 0), D_i_mm, f_MPa, z),
    })
    return result
