import streamlit as st
import pandas as pd
import math
import os
import xml.etree.ElementTree as ET
from fractions import Fraction

# ─── XML loader ───────────────────────────────────────────────────────────────

@st.cache_data
def load_pipes() -> list[dict]:
    xml_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "database", "Pipes.xml",
    )
    root = ET.parse(xml_path).getroot()
    pipes = []
    for el in root.findall("PIPE"):
        def txt(tag, default=""):
            node = el.find(tag)
            return node.text.strip() if node is not None and node.text else default

        nps_val  = float(txt("NPS", "0"))
        dn_val   = int(txt("DN", "0"))
        sch_raw  = txt("SCH")
        api_raw  = txt("API")
        od_val   = float(txt("OD", "0"))
        wt_val   = float(txt("WT", "0"))
        mass_val = float(txt("MASS", "0"))
        std      = el.get("Standard", "")

        parts = []
        if sch_raw:
            try:
                parts.append(str(int(float(sch_raw))))
            except ValueError:
                parts.append(sch_raw)
        if api_raw:
            parts.append(api_raw)

        pipes.append({
            "nps": nps_val, "dn": dn_val,
            "sch": " / ".join(parts) if parts else "",
            "sch_raw": sch_raw, "api": api_raw,
            "od": od_val, "wt": wt_val,
            "mass_db": mass_val, "standard": std,
        })
    return pipes


# ─── Helpers ──────────────────────────────────────────────────────────────────

def nps_to_str(nps: float) -> str:
    f = Fraction(nps).limit_denominator(8)
    whole = int(f)
    rem = f - whole
    if rem == 0:
        return f'{whole}"'
    elif whole == 0:
        return f'{rem.numerator}/{rem.denominator}"'
    else:
        return f'{whole}-{rem.numerator}/{rem.denominator}"'


def stat(col, label: str, value: str, unit: str = "") -> None:
    unit_html = (
        f'&thinsp;<span style="font-size:0.78rem;font-weight:400;opacity:0.65">{unit}</span>'
        if unit else ""
    )
    col.markdown(
        f"<p style='margin:0 0 2px;font-size:0.72rem;opacity:0.6'>{label}</p>"
        f"<p style='margin:0;font-size:0.97rem;font-weight:600;line-height:1.3'>"
        f"{value}{unit_html}</p>",
        unsafe_allow_html=True,
    )


def compute_section(od: float, wt: float, mass_db: float) -> dict:
    id_       = od - 2.0 * wt
    id_area   = math.pi / 4.0 * id_ ** 2
    sect_area = math.pi / 4.0 * (od ** 2 - id_ ** 2)
    iz        = math.pi / 64.0 * (od ** 4 - id_ ** 4)
    jt        = 2.0 * iz
    wz        = iz / (od / 2.0) if od > 0 else 0.0
    wt_tor    = jt / (od / 2.0) if od > 0 else 0.0
    i_gyr     = math.sqrt(iz / sect_area) if sect_area > 0 else 0.0
    return {
        "id": id_,
        "id_od_ratio": id_ / od if od > 0 else 0,
        "t_d_pct": wt / od * 100 if od > 0 else 0,
        "id_area": id_area, "sect_area": sect_area,
        "iz": iz, "jt": jt, "wz": wz, "wt_torsion": wt_tor,
        "i_gyration": i_gyr,
        "mass_db": mass_db,
        "mass_calc": sect_area * 7850.0 / 1.0e6,
    }


def flow_velocity(id_mm: float, flow_kgh: float, rho: float) -> float:
    if rho <= 0 or flow_kgh <= 0 or id_mm <= 0:
        return 0.0
    area_m2 = math.pi / 4.0 * (id_mm / 1000.0) ** 2
    return (flow_kgh / 3600.0 / rho) / area_m2


def calc_y_factor(material: str, temp_c: float) -> float:
    """ASME B31.3 Table 304.1.1 — y coefficient for pressure design thickness."""
    if material == "Ferritic steel":
        if temp_c <= 482:  return 0.4
        elif temp_c <= 510: return 0.5
        else:               return 0.7
    elif material == "Austenitic steel":
        if temp_c <= 566:  return 0.4
        elif temp_c <= 593: return 0.5
        else:               return 0.7
    elif material == "Cast iron":
        return 0.0
    else:  # Other ductile metals
        return 0.4


def stress_check(od: float, wt: float,
                 p_mpa: float,
                 f_kn: float, vy_kn: float, vz_kn: float,
                 my_knm: float, mz_knm: float, mt_knm: float,
                 s_mpa: float) -> dict:
    id_   = od - 2.0 * wt
    area  = math.pi / 4.0 * (od ** 2 - id_ ** 2)
    iz    = math.pi / 64.0 * (od ** 4 - id_ ** 4)
    jt    = 2.0 * iz
    r     = od / 2.0

    m_res    = math.sqrt((my_knm * 1e6) ** 2 + (mz_knm * 1e6) ** 2)
    ri       = id_ / 2.0
    sigma_h  = p_mpa * ri / wt if wt > 0 else 0.0
    sigma_ap = p_mpa * math.pi / 4.0 * id_ ** 2 / area if area > 0 else 0.0
    sigma_ad = (f_kn * 1e3) / area if area > 0 else 0.0
    sigma_ab = m_res * r / iz if iz > 0 else 0.0
    sigma_a  = sigma_ap + sigma_ad + sigma_ab
    tau_t    = (mt_knm * 1e6) * r / jt if jt > 0 else 0.0
    v_res    = math.sqrt((vy_kn * 1e3) ** 2 + (vz_kn * 1e3) ** 2)
    tau_v    = 2.0 * v_res / area if area > 0 else 0.0
    tau      = math.sqrt(tau_t ** 2 + tau_v ** 2)
    sigma_vm = math.sqrt(sigma_a ** 2 - sigma_a * sigma_h + sigma_h ** 2 + 3.0 * tau ** 2)
    sigma_ut = math.sqrt((sigma_a - sigma_h) ** 2 + 4.0 * tau ** 2)
    util     = sigma_vm / s_mpa if s_mpa > 0 else float("inf")

    return {
        "sigma_h": sigma_h, "sigma_ap": sigma_ap,
        "sigma_ad": sigma_ad, "sigma_ab": sigma_ab, "sigma_a": sigma_a,
        "tau_t": tau_t, "tau_v": tau_v, "tau": tau,
        "sigma_vm": sigma_vm, "sigma_ut": sigma_ut,
        "util": util, "ok": util <= 1.0,
    }


# ─── Filter ───────────────────────────────────────────────────────────────────

NUMERIC_FIELDS = ["NPS (in)", "DN (mm)", "OD (mm)", "WT (mm)", "ID (mm)"]
TEXT_FIELDS    = ["Schedule", "API"]
ALL_FIELDS     = NUMERIC_FIELDS + TEXT_FIELDS
ALL_OPS        = ["=", "≈ ±%", "<", "≤", ">", "≥", "in [a, b]", "contains"]

_EMPTY_CRITERIA = pd.DataFrame({
    "NOT":        pd.Series(dtype=bool),
    "Field":      pd.Series(dtype=str),
    "Operator":   pd.Series(dtype=str),
    "Value":      pd.Series(dtype=str),
    "Tol% / Max": pd.Series(dtype=str),
})

_FIELD_FN: dict = {
    "NPS (in)": lambda p: p["nps"],
    "DN (mm)":  lambda p: float(p["dn"]),
    "OD (mm)":  lambda p: p["od"],
    "WT (mm)":  lambda p: p["wt"],
    "ID (mm)":  lambda p: p["od"] - 2.0 * p["wt"],
    "Schedule": lambda p: p["sch"],
    "API":      lambda p: p["api"],
}


def _check_one(p: dict, row: pd.Series) -> bool:
    field = str(row.get("Field", "") or "")
    op    = str(row.get("Operator", "") or "")
    v1s   = str(row.get("Value", "") or "").strip()
    v2s   = str(row.get("Tol% / Max", "") or "").strip()

    if not v1s or v1s in ("nan", "None") or not field:
        return True

    fn = _FIELD_FN.get(field)
    if fn is None:
        return True
    raw = fn(p)

    if field in NUMERIC_FIELDS:
        try:
            v1   = float(v1s)
            fval = float(raw)
        except (ValueError, TypeError):
            return True

        if op == "=":
            return fval == v1
        if op == "≈ ±%":
            try:
                tol = float(v2s) / 100.0 if v2s not in ("", "nan") else 0.01
            except ValueError:
                tol = 0.01
            return (abs(fval - v1) / abs(v1) <= tol) if v1 != 0 else fval == 0
        if op == "<":  return fval <  v1
        if op == "≤":  return fval <= v1
        if op == ">":  return fval >  v1
        if op == "≥":  return fval >= v1
        if op == "in [a, b]":
            try:
                v2 = float(v2s)
                return v1 <= fval <= v2
            except ValueError:
                return True
        if op == "contains":
            return v1s.lower() in str(raw).lower()
    else:
        sval = str(raw).lower()
        sv1  = v1s.lower()
        if op in ("=", "= (exact)"):   return sval == sv1
        if op in ("contains", "≈ ±%"): return sv1 in sval

    return True


def apply_filter(pipes: list[dict], criteria: pd.DataFrame, combiner: str) -> list[dict]:
    valid = [
        row for _, row in criteria.iterrows()
        if str(row.get("Value", "") or "").strip() not in ("", "nan", "None")
        and str(row.get("Field", "") or "").strip()
    ]
    if not valid:
        return pipes

    def keep(p: dict) -> bool:
        bits = []
        for row in valid:
            hit = _check_one(p, row)
            if bool(row.get("NOT", False)):
                hit = not hit
            bits.append(hit)
        result = bits[0]
        for b in bits[1:]:
            if combiner == "AND":  result = result and b
            elif combiner == "OR": result = result or b
            elif combiner == "XOR": result = bool(result) ^ bool(b)
        return result

    return [p for p in pipes if keep(p)]


# ─── Page ─────────────────────────────────────────────────────────────────────

st.title("Pipe Dimensions")
st.caption("ASME B36.10 — Complete schedule database  |  Click a row in the tree to view properties")

pipes       = load_pipes()
pipes_sorted = sorted(pipes, key=lambda p: (p["nps"], p["wt"]))

col_tree, col_detail = st.columns([2, 3], gap="large")

# ═══════════════════════════════════════════════════════════════════════════════
#  LEFT — Filter panel + Tree
# ═══════════════════════════════════════════════════════════════════════════════

with col_tree:
    st.subheader("ASME B36.10 — Pipe Tree")

    # ── Filter panel ──────────────────────────────────────────────────────────
    with st.expander("Filter criteria", expanded=False):
        combiner = st.radio(
            "Combine criteria",
            ["AND", "OR", "XOR"],
            horizontal=True,
            help=(
                "AND — all criteria must match  |  "
                "OR — at least one must match  |  "
                "XOR — odd number of criteria match (applied left-to-right)"
            ),
        )
        st.caption(
            "Add rows below.  "
            "**NOT** negates a single criterion.  "
            "**Tol% / Max** = tolerance % for ≈, upper bound for *in [a,b]*, unused otherwise."
        )

        criteria = st.data_editor(
            _EMPTY_CRITERIA,
            num_rows="dynamic",
            column_config={
                "NOT": st.column_config.CheckboxColumn(
                    "NOT", default=False, width="small",
                ),
                "Field": st.column_config.SelectboxColumn(
                    "Field", options=ALL_FIELDS, default="OD (mm)", width="medium",
                ),
                "Operator": st.column_config.SelectboxColumn(
                    "Operator", options=ALL_OPS, default="≈ ±%", width="small",
                ),
                "Value": st.column_config.TextColumn(
                    "Value", width="small",
                ),
                "Tol% / Max": st.column_config.TextColumn(
                    "Tol% / Max", default="1.0", width="small",
                ),
            },
            hide_index=True,
            use_container_width=True,
            key="filter_criteria",
        )

    # ── Filtered pipe list ────────────────────────────────────────────────────
    filtered = apply_filter(pipes_sorted, criteria, combiner)
    st.caption(f"{len(filtered)} / {len(pipes)} pipes")

    if not filtered:
        st.warning("No pipes match the filter criteria.")
        selected_pipe = None
    else:
        # Build interleaved rows: NPS group header + leaf rows
        tree_rows  = []   # list of dicts for display DataFrame
        row_styles = []   # parallel list: "group" or "leaf"
        row_to_pipe: dict[int, dict | None] = {}
        prev_nps = None
        idx = 0

        for p in filtered:
            nps_s = nps_to_str(p["nps"])
            if p["nps"] != prev_nps:
                tree_rows.append({
                    "NPS": f"▸ NPS {nps_s}  ·  DN {p['dn']}  ·  OD {p['od']:.2f} mm",
                    "SCH": "", "WT [mm]": "", "ID [mm]": "",
                })
                row_styles.append("group")
                row_to_pipe[idx] = None
                idx += 1
                prev_nps = p["nps"]

            id_mm = p["od"] - 2 * p["wt"]
            tree_rows.append({
                "NPS":      f"  {nps_s}",
                "SCH":      p["sch"] if p["sch"] else "—",
                "WT [mm]":  f"{p['wt']:.2f}",
                "ID [mm]":  f"{id_mm:.3f}",
            })
            row_styles.append("leaf")
            row_to_pipe[idx] = p
            idx += 1

        tree_df = pd.DataFrame(tree_rows)

        def _style_tree(df: pd.DataFrame) -> pd.DataFrame:
            css_group = "background-color:rgba(74,144,217,0.10);font-weight:600;color:#4a90d9"
            css_leaf  = "padding-left:14px"
            out = pd.DataFrame("", index=df.index, columns=df.columns)
            for i, rtype in enumerate(row_styles):
                if rtype == "group":
                    out.iloc[i] = css_group
                else:
                    out.iloc[i, 0] = css_leaf
            return out

        styled_tree = tree_df.style.apply(_style_tree, axis=None)

        sel = st.dataframe(
            styled_tree,
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            height=540,
            key="pipe_tree",
        )

        selected_pipe = None
        sel_rows = sel.selection.rows
        if sel_rows:
            candidate = row_to_pipe.get(sel_rows[0])
            if candidate is not None:
                selected_pipe = candidate

# ═══════════════════════════════════════════════════════════════════════════════
#  RIGHT — Detail panel
# ═══════════════════════════════════════════════════════════════════════════════

with col_detail:
    if selected_pipe is None:
        st.info("Click a pipe row (not a group header) in the tree on the left.")
        st.stop()

    p   = selected_pipe
    sec = compute_section(p["od"], p["wt"], p["mass_db"])
    nps_str = nps_to_str(p["nps"])
    sch_str = p["sch"] if p["sch"] else "—"

    st.subheader(f"NPS {nps_str}   SCH {sch_str}")
    st.caption(f"DN {p['dn']} mm  |  {p['standard']}  |  Mass (DB) = {p['mass_db']:.2f} kg/m")

    # ── Geometry ──────────────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("**Geometry**")
        g1, g2, g3, g4, g5 = st.columns(5)
        stat(g1, "OD",      f"{p['od']:.2f}",            "mm")
        stat(g2, "WT",      f"{p['wt']:.2f}",            "mm")
        stat(g3, "ID",      f"{sec['id']:.3f}",          "mm")
        stat(g4, "ID / OD", f"{sec['id_od_ratio']:.4f}", "")
        stat(g5, "t / D",   f"{sec['t_d_pct']:.2f}",     "%")

    # ── Full data table ────────────────────────────────────────────────────────
    with st.expander("Full data table"):
        all_rows = [
            ("Standard",                  p["standard"],                ""),
            ("NPS",                       nps_str,                      ""),
            ("NPS (decimal)",             f"{p['nps']:.4f}",            "in"),
            ("DN",                        str(p["dn"]),                  "mm"),
            ("Schedule (SCH)",            sch_str,                      ""),
            ("API designation",           p["api"] or "—",              ""),
            ("OD — Outside Diameter",     f"{p['od']:.2f}",             "mm"),
            ("WT — Wall Thickness",       f"{p['wt']:.2f}",             "mm"),
            ("ID — Inside Diameter",      f"{sec['id']:.4f}",           "mm"),
            ("ID / OD",                   f"{sec['id_od_ratio']:.6f}",  ""),
            ("t / D  (WT/OD × 100)",      f"{sec['t_d_pct']:.4f}",     "%"),
            ("Bore area  A_id",           f"{sec['id_area']:.4f}",      "mm²"),
            ("Metal area  A",             f"{sec['sect_area']:.4f}",    "mm²"),
            ("Second moment  Iz",         f"{sec['iz']:.4f}",           "mm⁴"),
            ("Polar moment  Jt",          f"{sec['jt']:.4f}",           "mm⁴"),
            ("Bending modulus  Wz",       f"{sec['wz']:.4f}",           "mm³"),
            ("Torsion modulus  Wt",       f"{sec['wt_torsion']:.4f}",   "mm³"),
            ("Radius of gyration  i",     f"{sec['i_gyration']:.4f}",   "mm"),
            ("Unit mass (DB)",            f"{sec['mass_db']:.4f}",      "kg/m"),
            ("Unit mass (calc, ρ=7850)",  f"{sec['mass_calc']:.4f}",    "kg/m"),
        ]
        st.dataframe(
            pd.DataFrame(all_rows, columns=["Property", "Value", "Unit"]),
            hide_index=True, use_container_width=True,
        )

    # ── Flow / ρv² ────────────────────────────────────────────────────────────
    with st.expander("Flow — Velocity and ρv²"):
        fc1, fc2 = st.columns(2)
        with fc1:
            flow_kgh = st.number_input("Mass flow  (kg/h)", min_value=0.0,
                                       value=10_000.0, step=1_000.0, format="%.1f")
        with fc2:
            rho = st.number_input("Fluid density  (kg/m³)", min_value=0.001,
                                   value=850.0, step=10.0, format="%.3f")
        v     = flow_velocity(sec["id"], flow_kgh, rho)
        rhov2 = rho * v ** 2
        st.markdown("")
        fv1, fv2, fv3, fv4 = st.columns(4)
        stat(fv1, "Velocity",        f"{v:.4f}",          "m/s")
        stat(fv2, "ρv²",             f"{rhov2:.2f}",      "Pa")
        stat(fv3, "ρv²",             f"{rhov2/1000:.4f}", "kPa")
        stat(fv4, "½ρv²  (dynamic)", f"{rhov2/2000:.4f}", "kPa")

    # ── Stress Check ──────────────────────────────────────────────────────────
    with st.expander("Stress Check — Combined loading  (B31.3 / B31.1)"):

        sc1, sc2 = st.columns(2)

        with sc1:
            st.markdown("**Loads**")
            p_mpa  = st.number_input("P — Internal pressure  (MPa)",     value=1.0,  step=0.5,  format="%.2f")
            f_kn   = st.number_input("F — Axial force  (kN, + tension)", value=0.0,  step=10.0, format="%.2f")
            vy_kn  = st.number_input("Vy — Shear y  (kN)",               value=0.0,  step=5.0,  format="%.2f")
            vz_kn  = st.number_input("Vz — Shear z  (kN)",               value=0.0,  step=5.0,  format="%.2f")
            my_knm = st.number_input("My — Bending moment y  (kN·m)",    value=0.0,  step=1.0,  format="%.2f")
            mz_knm = st.number_input("Mz — Bending moment z  (kN·m)",    value=0.0,  step=1.0,  format="%.2f")
            mt_knm = st.number_input("Mt — Torsional moment  (kN·m)",    value=0.0,  step=1.0,  format="%.2f")

        with sc2:
            st.markdown("**Code factors  (B31.3)**")
            s_mpa  = st.number_input(
                "S — Allowable stress  (MPa)",
                min_value=1.0, value=138.0, step=1.0, format="%.1f",
                help="ASME B31.3 Table A-1",
            )
            e_weld = st.selectbox(
                "E — Longitudinal weld quality factor",
                options=[1.0, 0.85, 0.80],
                format_func=lambda x: {
                    1.0:  "1.00 — Seamless / fully examined",
                    0.85: "0.85 — ERW / partial examination",
                    0.80: "0.80 — EFW",
                }[x],
                help="ASME B31.3 Table A-1B",
            )
            z_factor = st.number_input(
                "Z — Weld strength reduction factor",
                min_value=0.10, max_value=1.0, value=1.0, step=0.05, format="%.2f",
                help=(
                    "ASME B31.3 Table 302.3.5 — creep-range welds.  "
                    "Z = 1.0 for T ≤ 510 °C (most materials)."
                ),
            )

            st.markdown("**Temperature & y factor**")
            mat_type = st.selectbox(
                "Material type  (Table 304.1.1)",
                ["Ferritic steel", "Austenitic steel", "Other ductile metals", "Cast iron"],
            )
            temp_c = st.number_input(
                "Design temperature  (°C)",
                min_value=-50.0, max_value=900.0, value=20.0, step=10.0, format="%.0f",
            )

            y_val = calc_y_factor(mat_type, temp_c)
            s_eff = s_mpa * e_weld * z_factor

            st.markdown("")
            fi1, fi2, fi3 = st.columns(3)
            stat(fi1, "y  (Table 304.1.1)", f"{y_val:.1f}",  "")
            stat(fi2, "S·E·Z",              f"{s_eff:.2f}",  "MPa")

        # ── Pressure design thickness ──────────────────────────────────────────
        denom = 2.0 * (s_eff + p_mpa * y_val)
        t_press = (p_mpa * p["od"] / denom) if denom > 0 else 0.0
        t_ratio = t_press / p["wt"] if p["wt"] > 0 else float("inf")

        with st.container(border=True):
            st.markdown(
                r"**Pressure design thickness — B31.3 Eq. 3a** &nbsp;&nbsp;"
                r"$t_{min} = \dfrac{P \cdot D}{2(S \cdot E \cdot Z\;+\;P \cdot y)}$"
            )
            pt1, pt2, pt3 = st.columns(3)
            stat(pt1, "t_min  (required)", f"{t_press:.3f}", "mm")
            stat(pt2, "WT  (actual)",      f"{p['wt']:.3f}", "mm")
            stat(pt3, "t_min / WT",        f"{t_ratio:.4f}", "")
            st.markdown("")
            if t_ratio <= 1.0:
                st.success(f"Pressure OK — t_min {t_press:.3f} mm ≤ WT {p['wt']:.3f} mm")
            else:
                st.error(f"Pressure FAIL — t_min {t_press:.3f} mm > WT {p['wt']:.3f} mm")

        # ── Combined stress ────────────────────────────────────────────────────
        r = stress_check(
            p["od"], p["wt"],
            p_mpa, f_kn, vy_kn, vz_kn, my_knm, mz_knm, mt_knm,
            s_eff,
        )

        st.divider()
        st.markdown("**Combined stress  (von Mises / Tresca)**")

        r1c1, r1c2, r1c3, r1c4 = st.columns(4)
        stat(r1c1, "σH  (hoop)",    f"{r['sigma_h']:.3f}", "MPa")
        stat(r1c2, "σA  (axial)",   f"{r['sigma_a']:.3f}", "MPa")
        stat(r1c3, "τ  (shear)",    f"{r['tau']:.3f}",     "MPa")
        stat(r1c4, "S·E·Z",         f"{s_eff:.2f}",        "MPa")

        st.markdown("")
        r2c1, r2c2, r2c3, _ = st.columns(4)
        stat(r2c1, "σVM  (von Mises)", f"{r['sigma_vm']:.3f}", "MPa")
        stat(r2c2, "σUT  (Tresca)",    f"{r['sigma_ut']:.3f}", "MPa")
        stat(r2c3, "Utilisation",      f"{r['util']*100:.2f}", "%")

        st.markdown("")
        if r["ok"]:
            st.success(f"PASS — von-Mises utilisation {r['util']*100:.1f} % ≤ 100 %")
        else:
            st.error(f"FAIL — von-Mises utilisation {r['util']*100:.1f} % > 100 %")
