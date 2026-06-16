"""
CODAP 2023 — Virole Cylindrique, Pression Intérieure
Référence : CODAP 2023 Division 1 & 2, Section C2.3

Formule (Di-based) :
    e = p · Di / (2 · f · z − p)

Notations :
    e   = épaisseur minimale de calcul [mm]
    p   = pression de calcul [MPa]
    Di  = diamètre intérieur [mm]
    f   = contrainte nominale de calcul [MPa]  (calc.db.materials.allowable_CODAP)
    z   = coefficient de joint soudé

Contrainte nominale de calcul (§C2.3.1) :
    Groupes M1–M5 (aciers C, faiblement alliés, alliés) :
        f = min(Rp0.2_T / 1.5,  Rm_20°C / 2.4)
    Groupe M6 (aciers austénitiques, Ar ≥ 35 %) :
        f = min(Rp0.2_T / 1.5,  Rm_20°C / 3.0)
"""


def thickness_internal(P_bar: float, D_i_mm: float, f_MPa: float, z: float = 1.0) -> dict:
    """
    Épaisseur minimale de calcul (structurale, hors corrosion).
    Même forme algébrique qu'EN 13445 §7.4.2.
    """
    P = P_bar * 0.1         # bar → MPa

    denom = 2.0 * f_MPa * z - P
    if denom <= 0:
        return {"error": "2·f·z − p ≤ 0: la pression dépasse la capacité du matériau"}

    e_min = P * D_i_mm / denom

    return {
        "code":     "CODAP 2023",
        "ref":      "§ C2.3",
        "P_MPa":    round(P, 4),
        "Di_mm":    D_i_mm,
        "f_MPa":    f_MPa,
        "z":        z,
        "t_min_mm": round(e_min, 3),
        "governing": "Pression intérieure §C2.3",
        "latex":    r"e = \frac{p \cdot D_i}{2\,f \cdot z - p}",
    }


def mawp(e_mm: float, D_i_mm: float, f_MPa: float, z: float = 1.0) -> float:
    """
    Pression maximale admissible depuis l'épaisseur d'analyse.
    Formule inversée : p = 2·f·z·e / (Di + e)
    Retourne [bar].
    """
    denom = D_i_mm + e_mm
    if denom <= 0:
        return 0.0
    return round(2.0 * f_MPa * z * e_mm / denom / 0.1, 3)
