"""
AD 2000-B0 — Cylindrical Shell, Internal Pressure
Reference: AD 2000 Merkblatt B0, §6 (Berechnung der Wanddicke)

Formula (Di-based, thin-wall):
    s = p · Di / (2 · σ_zul · v − p)

Notation:
    s       = wall thickness [mm]
    p       = design pressure [MPa]
    Di      = inside diameter [mm]
    σ_zul   = allowable stress [MPa]  (computed in calc.db.materials.allowable_AD2000)
    v       = weld joint factor (equivalent to z or E in other codes)

Allowable stress (groups M1–M5, §7.2):
    σ_zul = min(Rp0.2_T / 1.5,  Rm_20°C / 2.4)
"""


def thickness_internal(P_bar: float, D_i_mm: float, S_MPa: float, v: float = 1.0) -> dict:
    """
    Minimum required analysis thickness (structural only).
    Same algebraic form as EN 13445 §7.4.2 — both use 0.5·P coefficient.
    """
    P = P_bar * 0.1         # bar → MPa

    denom = 2.0 * S_MPa * v - P
    if denom <= 0:
        return {"error": "2·σ_zul·v − p ≤ 0: pressure exceeds material capacity"}

    s_min = P * D_i_mm / denom

    return {
        "code":     "AD 2000",
        "ref":      "B0 §6",
        "P_MPa":    round(P, 4),
        "Di_mm":    D_i_mm,
        "S_MPa":    S_MPa,
        "v":        v,
        "t_min_mm": round(s_min, 3),
        "governing": "Pressione interna B0",
        "latex":    r"s = \frac{p \cdot D_i}{2\,\sigma_{zul} \cdot v - p}",
    }


def mawp(s_mm: float, D_i_mm: float, S_MPa: float, v: float = 1.0) -> float:
    """
    Maximum allowable pressure from analysis thickness.
    Rearranged: p = 2·σ_zul·v·s / (Di + s)
    Returns [bar].
    """
    denom = D_i_mm + s_mm
    if denom <= 0:
        return 0.0
    return round(2.0 * S_MPa * v * s_mm / denom / 0.1, 3)
