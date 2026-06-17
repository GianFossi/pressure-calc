"""
ASME materials database access.

Temperature columns in the DB are in °F; stress values are in MPa.
Design temperature input is always in °C and converted internally.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "database" / "asme_materials.db"

# Temperature breakpoints available in stress/property tables [°F]
TEMP_F = [
    40, 65, 100, 125, 150, 175, 200, 225, 250, 275, 300, 325, 350,
    375, 400, 425, 450, 475, 500, 525, 550, 575, 600, 625, 650, 675,
    700, 725, 750, 775, 800, 825, 850, 875, 900,
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH))
    c.text_factory = lambda b: b.decode("utf-8", errors="replace")
    return c


def _col_idx(col_names: list[str], col: str) -> int:
    try:
        return col_names.index(col)
    except ValueError:
        return -1


def _extract_temps(row: tuple, col_names: list[str]) -> dict[float, float]:
    """Build {temp_F: value_MPa} from a DB row, skipping None entries."""
    d: dict[float, float] = {}
    for t in TEMP_F:
        col = f"T_{t}"
        idx = _col_idx(col_names, col)
        if idx >= 0 and row[idx] is not None:
            d[float(t)] = float(row[idx])
    return d


def _interp(data: dict[float, float], T_F: float) -> float | None:
    """
    Linear interpolation at T_F [°F].
    Below the lowest available temperature: returns the lowest value.
    Above the highest: returns None (outside design range — don't extrapolate).
    """
    if not data:
        return None
    ts = sorted(data)
    if T_F <= ts[0]:
        return data[ts[0]]
    if T_F > ts[-1]:
        return None
    for i in range(len(ts) - 1):
        t1, t2 = ts[i], ts[i + 1]
        if t1 <= T_F <= t2:
            v1, v2 = data[t1], data[t2]
            return v1 + (v2 - v1) * (T_F - t1) / (t2 - t1)
    return None


def _first_row(table: str, material_id: int,
               thk_mm: float | None = None) -> tuple[list[str], tuple] | None:
    """
    Return (col_names, row) for the first matching row in a temperature table.
    If thk_mm is provided, filter by the SizeThk range columns.
    """
    conn = _conn()
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    col_names = [c[1] for c in cur.fetchall()]

    has_size = "SizeThkMIN" in col_names

    if has_size and thk_mm is not None:
        cur.execute(f"""
            SELECT * FROM {table}
            WHERE MaterialID = ?
              AND (SizeThkMIN IS NULL
                   OR (SizeThkMIN_Included = 1 AND SizeThkMIN <= ?)
                   OR (SizeThkMIN_Included = 0 AND SizeThkMIN <  ?))
              AND (SizeThkMAX IS NULL
                   OR (SizeThkMAX_Included = 1 AND SizeThkMAX >= ?)
                   OR (SizeThkMAX_Included = 0 AND SizeThkMAX >  ?))
            ORDER BY ID LIMIT 1
        """, (material_id, thk_mm, thk_mm, thk_mm, thk_mm))
    else:
        cur.execute(
            f"SELECT * FROM {table} WHERE MaterialID = ? ORDER BY ID LIMIT 1",
            (material_id,),
        )
    row = cur.fetchone()
    conn.close()
    return (col_names, row) if row else None


# ── Public API ─────────────────────────────────────────────────────────────────

def get_all_materials() -> list[dict]:
    """Return all materials as a list of dicts, sorted by spec / grade / class."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT ID, Specification, TypeGrade, ClassConditionTemper,
               AlloyDesignationNumber, NominalComposition, ProductForm,
               SMTS, SMYS, RuptureElongationLong
        FROM Materials
        ORDER BY Specification, TypeGrade, ClassConditionTemper
    """)
    rows = cur.fetchall()
    conn.close()

    result = []
    for row in rows:
        (mid, spec, grade, cls, alloy, comp, pform, smts, smys, ar) = row
        # When TypeGrade is absent, use UNS/AlloyDesignation as the identifier
        id_part = grade if grade else alloy
        parts = [str(p) for p in [spec, id_part, cls] if p]
        name = " ".join(parts)
        result.append({
            "id":    mid,
            "name":  name,
            "spec":  spec  or "",
            "grade": grade or "",
            "cls":   cls   or "",
            "alloy": alloy or "",
            "comp":  comp  or "",
            "pform": pform or "",
            "SMTS":  smts,
            "SMYS":  smys,
            "Ar":    ar,
        })
    return result


def get_material(material_id: int) -> dict | None:
    """Return static properties for a single material."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT ID, Specification, TypeGrade, ClassConditionTemper,
               AlloyDesignationNumber, NominalComposition, ProductForm,
               SMTS, SMYS, RuptureElongationLong, RuptureElongationTransv, Density
        FROM Materials WHERE ID = ?
    """, (material_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    (mid, spec, grade, cls, alloy, comp, pform,
     smts, smys, ar_l, ar_t, density) = row
    parts = [str(p) for p in [spec, grade, cls] if p]
    return {
        "id":      mid,
        "name":    " ".join(parts),
        "spec":    spec  or "",
        "grade":   grade or "",
        "cls":     cls   or "",
        "alloy":   alloy or "",
        "comp":    comp  or "",
        "pform":   pform or "",
        "SMTS":    smts,
        "SMYS":    smys,
        "Ar":      ar_l,
        "Ar_t":    ar_t,
        "density": density,
    }


def get_yield_at_T(material_id: int, T_C: float,
                   thk_mm: float | None = None) -> float | None:
    """Rp0.2 at T_C [°C] interpolated from YieldStrengthTable [MPa]."""
    res = _first_row("YieldStrengthTable", material_id, thk_mm)
    if not res:
        return None
    col_names, row = res
    return _interp(_extract_temps(row, col_names), T_C * 9 / 5 + 32)


def get_ultimate_at_T(material_id: int, T_C: float,
                      thk_mm: float | None = None) -> float | None:
    """Rm at T_C [°C] interpolated from UltimateStrengthTable [MPa]."""
    res = _first_row("UltimateStrengthTable", material_id, thk_mm)
    if not res:
        return None
    col_names, row = res
    return _interp(_extract_temps(row, col_names), T_C * 9 / 5 + 32)


def get_S_div1(material_id: int, T_C: float,
               thk_mm: float | None = None) -> float | None:
    """ASME VIII-1 allowable stress (Table 1A) at T_C [°C] [MPa]."""
    T_F = T_C * 9 / 5 + 32
    res = _first_row("AllowableStress1Table", material_id, thk_mm)
    if not res:
        return None
    col_names, row = res

    # Respect MaxTemp_VIII1 field when present
    mt_idx = _col_idx(col_names, "MaxTemp_VIII1")
    if mt_idx >= 0 and row[mt_idx] is not None:
        max_T_F = float(row[mt_idx])
        if T_F > max_T_F:
            return None  # beyond rated max temperature for VIII-1

    return _interp(_extract_temps(row, col_names), T_F)


def get_S_div2(material_id: int, T_C: float,
               thk_mm: float | None = None) -> float | None:
    """ASME VIII-2 allowable stress (Table 5A) at T_C [°C] [MPa]."""
    T_F = T_C * 9 / 5 + 32
    res = _first_row("AllowableStress2Table", material_id, thk_mm)
    if not res:
        return None
    col_names, row = res

    mt_idx = _col_idx(col_names, "MaximumTemperature")
    if mt_idx >= 0 and row[mt_idx] is not None:
        max_T_F = float(row[mt_idx])
        if T_F > max_T_F:
            return None

    return _interp(_extract_temps(row, col_names), T_F)


# ── European allowable stress helpers ─────────────────────────────────────────

def allowable_EN13445(Rp02_T: float, Rm_20: float, Ar: float | None) -> dict:
    """
    EN 13445-2 §6.4.3 nominal design stress f [MPa].

    General case (ferritic/alloy steels):
        f = min(Rp0.2_T / 1.5,  Rm_20 / 2.4)

    Austenitic steels (Ar ≥ 30%):
        f = min(Rp0.2_T / 1.5,  Rm_20 / 3.0)
        (the Rp1.0_T / 1.2 criterion is omitted — not in DB)
    """
    austenitic = (Ar is not None) and (Ar >= 30.0)
    sf_u = 3.0 if austenitic else 2.4
    cand_y = Rp02_T / 1.5
    cand_u = Rm_20 / sf_u
    f = min(cand_y, cand_u)
    return {
        "f": f,
        "cand_yield": cand_y,
        "cand_uts":   cand_u,
        "sf_yield":   1.5,
        "sf_uts":     sf_u,
        "governing":  "Rp0.2_T / 1.5" if cand_y <= cand_u else f"Rm_20 / {sf_u}",
        "austenitic": austenitic,
    }


def allowable_AD2000(Rp02_T: float, Rm_20: float) -> dict:
    """
    AD 2000-B0 §7.2 zulässige Spannung σ_zul [MPa].
    Groups M1–M5 (carbon / low-alloy / alloy steels):
        σ_zul = min(Rp0.2_T / 1.5,  Rm_20 / 2.4)
    """
    cand_y = Rp02_T / 1.5
    cand_u = Rm_20  / 2.4
    f = min(cand_y, cand_u)
    return {
        "f": f,
        "cand_yield": cand_y,
        "cand_uts":   cand_u,
        "sf_yield":   1.5,
        "sf_uts":     2.4,
        "governing":  "Rp0.2_T / 1.5" if cand_y <= cand_u else "Rm_20 / 2.4",
    }


def allowable_BS5500(Rp02_T: float, Rm_20: float) -> dict:
    """
    BS PD 5500 Table 4.3-1 nominal design strength f [MPa].
    Category 1, carbon / alloy steels:
        f = min(Rp0.2_T / 1.5,  Rm_20 / 2.5)
    """
    cand_y = Rp02_T / 1.5
    cand_u = Rm_20  / 2.5
    f = min(cand_y, cand_u)
    return {
        "f": f,
        "cand_yield": cand_y,
        "cand_uts":   cand_u,
        "sf_yield":   1.5,
        "sf_uts":     2.5,
        "governing":  "Rp0.2_T / 1.5" if cand_y <= cand_u else "Rm_20 / 2.5",
    }


def allowable_CODAP(Rp02_T: float, Rm_20: float, Ar: float | None) -> dict:
    """
    CODAP 2023 §C2.3.1 contrainte nominale de calcul f [MPa].
    Groups M1–M5:  f = min(Rp0.2_T / 1.5,  Rm_20 / 2.4)
    Group M6 (austenitic SS, Ar ≥ 35%):
              f = min(Rp0.2_T / 1.5,  Rm_20 / 3.0)
    """
    austenitic = (Ar is not None) and (Ar >= 35.0)
    sf_u = 3.0 if austenitic else 2.4
    cand_y = Rp02_T / 1.5
    cand_u = Rm_20 / sf_u
    f = min(cand_y, cand_u)
    return {
        "f": f,
        "cand_yield": cand_y,
        "cand_uts":   cand_u,
        "sf_yield":   1.5,
        "sf_uts":     sf_u,
        "governing":  "Rp0.2_T / 1.5" if cand_y <= cand_u else f"Rm_20 / {sf_u}",
        "austenitic": austenitic,
    }
