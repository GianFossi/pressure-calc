"""
ASME VIII Division 2 — Cylindrical Shell, Internal Pressure
Reference: Part 4, Section 4.3.3, Equation (4.3.1)
"""


def thickness_internal(P_bar: float, D_i_mm: float, S_MPa: float, E: float = 1.0) -> dict:
    """
    4.3.3 Eq. (4.3.1) — Minimum required thickness (structural only).

        t = P · Ri / (S · E − 0.5 · P)

    Division 2 uses 0.5·P (vs 0.6·P in Div.1), identical in form to EN 13445.
    The higher allowable stress S (Table 5A) is the key difference from Div.1.
    """
    P  = P_bar * 0.1        # bar → MPa
    Ri = D_i_mm / 2.0       # inside radius [mm]

    denom = S_MPa * E - 0.5 * P
    if denom <= 0:
        return {"error": "S·E − 0.5·P ≤ 0: pressure exceeds material capacity"}

    t_min = P * Ri / denom

    return {
        "code":     "ASME VIII-2",
        "ref":      "Part 4 §4.3.3 Eq. (4.3.1)",
        "P_MPa":    round(P, 4),
        "Ri_mm":    round(Ri, 2),
        "S_MPa":    S_MPa,
        "E":        E,
        "t_min_mm": round(t_min, 3),
        "governing": "Circumferential stress — Eq. (4.3.1)",
        "latex":    r"t = \frac{P \cdot R_i}{S \cdot E - 0.5\,P}",
    }


def mawp(t_mm: float, D_i_mm: float, S_MPa: float, E: float = 1.0) -> float:
    """
    MAWP from analysis thickness.
    Eq. (4.3.1) rearranged: P = S·E·t / (Ri + 0.5·t)
    Returns [bar].
    """
    Ri = D_i_mm / 2.0
    denom = Ri + 0.5 * t_mm
    if denom <= 0:
        return 0.0
    return round(S_MPa * E * t_mm / denom / 0.1, 3)
