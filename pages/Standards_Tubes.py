"""
Heat-exchanger / condenser tube dimensions — BWG series
Standards: TEMA, ASME HEI
OD sizes: ¼" … 2"  ×  Birmingham Wire Gauge (BWG) 0–25
"""

import math
import os
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA
# ═══════════════════════════════════════════════════════════════════════════════

IN_MM = 25.4

# Standard heat-exchanger / condenser tube OD sizes (TEMA / ASME HEI)
TUBE_OD_IN: dict[str, float] = {
    "1/4":   0.250,
    "5/16":  0.3125,
    "3/8":   0.375,
    "1/2":   0.500,
    "5/8":   0.625,
    "3/4":   0.750,
    "7/8":   0.875,
    "1":     1.000,
    "1-1/4": 1.250,
    "1-1/2": 1.500,
    "2":     2.000,
}

ROUGHNESS_PRESETS: dict[str, float] = {
    "Smooth / drawn copper or brass  (0.0015 mm)": 0.0015,
    "Stainless steel — welded  (0.015 mm)":        0.015,
    "Carbon steel — seamless  (0.046 mm)":         0.046,
    "Galvanised steel  (0.15 mm)":                 0.15,
    "Custom":                                       0.046,
}


@st.cache_data
def load_bwg() -> dict[int, float]:
    """Return {BWG gauge → wall thickness mm} from TubesBWGSerie.xml."""
    xml_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "database", "TubesBWGSerie.xml",
    )
    root = ET.parse(xml_path).getroot()
    return {
        int(el.find("VALUE").text.strip()): float(el.find("TSK_SI").text.strip())
        for el in root.findall("BWG")
    }


@st.cache_data
def build_tubes() -> list[dict]:
    """Cross all standard ODs × BWG gauges → valid tube list."""
    bwg = load_bwg()
    tubes: list[dict] = []
    for label, od_in in TUBE_OD_IN.items():
        od_mm = od_in * IN_MM
        for gauge in sorted(bwg):
            wt_mm = bwg[gauge]
            id_mm = od_mm - 2.0 * wt_mm
            if id_mm < 1.0:          # impractical bore
                continue
            if wt_mm / od_mm > 0.35:  # unrealistically heavy wall
                continue
            tubes.append({
                "od_label": label,
                "od_in":    od_in,
                "od_mm":    round(od_mm, 4),
                "gauge":    gauge,
                "wt_mm":    wt_mm,
                "id_mm":    round(id_mm, 4),
                "t_d_pct":  round(wt_mm / od_mm * 100, 3),
            })
    return tubes


# ═══════════════════════════════════════════════════════════════════════════════
#  ENGINEERING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def section_props(od_mm: float, wt_mm: float) -> dict:
    id_mm  = od_mm - 2.0 * wt_mm
    a_bore = math.pi / 4.0 * id_mm ** 2
    a_met  = math.pi / 4.0 * (od_mm ** 2 - id_mm ** 2)
    iz     = math.pi / 64.0 * (od_mm ** 4 - id_mm ** 4)
    jt     = 2.0 * iz
    wz     = iz / (od_mm / 2.0) if od_mm > 0 else 0.0
    mass   = a_met * 7850.0 / 1.0e6   # kg/m, steel ρ = 7850
    return {
        "id_mm": id_mm, "id_od": id_mm / od_mm,
        "t_d":   wt_mm / od_mm * 100,
        "a_bore": a_bore, "a_met": a_met,
        "iz": iz, "jt": jt, "wz": wz, "mass": mass,
    }


def velocity_ms(id_mm: float, flow_kgh: float, rho: float) -> float:
    """Mean tube velocity [m/s] from mass flow per tube."""
    if id_mm <= 0 or flow_kgh <= 0 or rho <= 0:
        return 0.0
    a_m2 = math.pi / 4.0 * (id_mm / 1000.0) ** 2
    return (flow_kgh / 3600.0 / rho) / a_m2


def reynolds_number(v: float, id_mm: float, rho: float, mu_cP: float) -> float:
    mu = mu_cP * 1.0e-3   # mPa·s → Pa·s
    if mu <= 0 or id_mm <= 0 or v <= 0:
        return 0.0
    return rho * v * (id_mm / 1000.0) / mu


def flow_regime(Re: float) -> str:
    if   Re < 2300: return "🟢 Laminar (Re < 2 300)"
    elif Re < 4000: return "🟡 Transition (2 300 ≤ Re < 4 000)"
    else:           return "🔵 Turbulent (Re ≥ 4 000)"


def friction_darcy(Re: float, eps_mm: float, d_mm: float) -> float:
    """
    Darcy friction factor — Churchill (1977).
    Valid for all Re (laminar through fully turbulent) and all ε/D.
    Converges to 64/Re for laminar flow.
    """
    if Re <= 0 or d_mm <= 0:
        return 0.0
    if Re < 1.0:
        return 64.0 / max(Re, 1e-9)
    eps_rel = max(eps_mm, 0.0) / d_mm
    A = (-2.457 * math.log((7.0 / Re) ** 0.9 + 0.27 * eps_rel)) ** 16
    B = (37530.0 / Re) ** 16
    return 8.0 * ((8.0 / Re) ** 12 + (A + B) ** (-1.5)) ** (1.0 / 12.0)


def calc_pressure_drop(
    v: float, rho: float,
    f_D: float, L_m: float, d_mm: float,
    k_in: float, k_out: float,
) -> dict:
    """
    Darcy-Weisbach pressure drop [Pa].

    ΔP_friction = f_D × (L/Di) × ½ρv²
    ΔP_local    = (K_in + K_out) × ½ρv²
    ΔP_total    = ΔP_friction + ΔP_local
    """
    rhov2     = rho * v ** 2
    half_rhov2 = rhov2 / 2.0
    d_m       = d_mm / 1000.0
    dp_f = f_D * (L_m / d_m) * half_rhov2 if d_m > 0 else 0.0
    dp_l = (k_in + k_out) * half_rhov2
    return {
        "rhov2":    rhov2,
        "half_rhov2": half_rhov2,
        "dp_f":     dp_f,
        "dp_l":     dp_l,
        "dp_t":     dp_f + dp_l,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  FILTER ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

FIELDS = ["OD (mm)", "OD (in)", "BWG", "WT (mm)", "ID (mm)", "t/D (%)"]
OPS    = ["=", "≈ ±%", "<", "≤", ">", "≥", "in [a, b]"]

_EMPTY_CRIT = pd.DataFrame({
    "NOT":        pd.Series(dtype=bool),
    "Field":      pd.Series(dtype=str),
    "Operator":   pd.Series(dtype=str),
    "Value":      pd.Series(dtype=str),
    "Tol% / Max": pd.Series(dtype=str),
})

_FIELD_FN: dict = {
    "OD (mm)": lambda t: t["od_mm"],
    "OD (in)": lambda t: t["od_in"],
    "BWG":     lambda t: float(t["gauge"]),
    "WT (mm)": lambda t: t["wt_mm"],
    "ID (mm)": lambda t: t["id_mm"],
    "t/D (%)": lambda t: t["t_d_pct"],
}


def _check_row(t: dict, row: pd.Series) -> bool:
    field = str(row.get("Field", "") or "")
    op    = str(row.get("Operator", "") or "")
    v1s   = str(row.get("Value", "") or "").strip()
    v2s   = str(row.get("Tol% / Max", "") or "").strip()
    if not v1s or v1s in ("nan", "None") or not field:
        return True
    fn = _FIELD_FN.get(field)
    if fn is None:
        return True
    try:
        v1   = float(v1s)
        fval = float(fn(t))
    except (ValueError, TypeError):
        return True
    if op == "=":    return fval == v1
    if op == "≈ ±%":
        try:    tol = float(v2s) / 100.0 if v2s not in ("", "nan") else 0.01
        except: tol = 0.01
        return (abs(fval - v1) / abs(v1) <= tol) if v1 != 0 else fval == 0
    if op == "<":    return fval <  v1
    if op == "≤":    return fval <= v1
    if op == ">":    return fval >  v1
    if op == "≥":    return fval >= v1
    if op == "in [a, b]":
        try:    return v1 <= fval <= float(v2s)
        except: return True
    return True


def apply_filter(tubes: list[dict], crit: pd.DataFrame) -> list[dict]:
    valid = [
        row for _, row in crit.iterrows()
        if str(row.get("Value", "") or "").strip() not in ("", "nan", "None")
        and str(row.get("Field", "") or "").strip()
    ]
    if not valid:
        return tubes

    def keep(t: dict) -> bool:
        bits = [_check_row(t, r) for r in valid]
        for i, row in enumerate(valid):
            if bool(row.get("NOT", False)):
                bits[i] = not bits[i]
        return all(bits)

    return [t for t in tubes if keep(t)]


# ═══════════════════════════════════════════════════════════════════════════════
#  UI HELPER
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE
# ═══════════════════════════════════════════════════════════════════════════════

st.title("Tube Dimensions — BWG Series")
st.caption(
    "TEMA / ASME HEI — Heat-exchanger & condenser tubes  |  "
    "Standard OD ¼\" … 2\"  ×  Birmingham Wire Gauge  BWG 0–25"
)

all_tubes = build_tubes()

col_tree, col_detail = st.columns([2, 3], gap="large")

# ─── LEFT — Filter + Tree ────────────────────────────────────────────────────

with col_tree:
    st.subheader("Tube Tree  (OD × BWG)")

    with st.expander("Filter criteria", expanded=False):
        st.caption(
            "Add rows. **NOT** negates a criterion. "
            "**Tol% / Max** = tolerance % for ≈, upper bound for *in [a,b]*."
        )
        criteria = st.data_editor(
            _EMPTY_CRIT,
            num_rows="dynamic",
            column_config={
                "NOT":        st.column_config.CheckboxColumn("NOT", default=False, width="small"),
                "Field":      st.column_config.SelectboxColumn("Field", options=FIELDS, default="OD (mm)", width="medium"),
                "Operator":   st.column_config.SelectboxColumn("Operator", options=OPS, default="≈ ±%", width="small"),
                "Value":      st.column_config.TextColumn("Value", width="small"),
                "Tol% / Max": st.column_config.TextColumn("Tol% / Max", default="1.0", width="small"),
            },
            hide_index=True,
            use_container_width=True,
            key="tube_filter",
        )

    filtered = apply_filter(all_tubes, criteria)
    st.caption(f"{len(filtered)} / {len(all_tubes)} combinations")

    if not filtered:
        st.warning("No tubes match the filter criteria.")
        selected_tube = None
    else:
        tree_rows:  list[dict]          = []
        row_styles: list[str]           = []
        row_map:    dict[int, dict | None] = {}
        prev_od = None
        idx = 0

        for t in filtered:
            if t["od_label"] != prev_od:
                tree_rows.append({
                    "OD":      f"▸  {t['od_label']}\"   ·   {t['od_mm']:.3f} mm",
                    "BWG":     "", "WT [mm]": "", "ID [mm]": "",
                })
                row_styles.append("group")
                row_map[idx] = None
                idx += 1
                prev_od = t["od_label"]

            tree_rows.append({
                "OD":      f"   {t['od_label']}\"",
                "BWG":     f"BWG {t['gauge']}",
                "WT [mm]": f"{t['wt_mm']:.3f}",
                "ID [mm]": f"{t['id_mm']:.3f}",
            })
            row_styles.append("leaf")
            row_map[idx] = t
            idx += 1

        tree_df = pd.DataFrame(tree_rows)

        def _style_tree(df: pd.DataFrame) -> pd.DataFrame:
            g = "background-color:rgba(74,144,217,0.10);font-weight:600;color:#4a90d9"
            l = "padding-left:14px"
            out = pd.DataFrame("", index=df.index, columns=df.columns)
            for i, rt in enumerate(row_styles):
                out.iloc[i] = g if rt == "group" else ""
                if rt == "leaf":
                    out.iloc[i, 0] = l
            return out

        sel = st.dataframe(
            tree_df.style.apply(_style_tree, axis=None),
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            height=540,
            key="tube_tree",
        )

        selected_tube = None
        if sel.selection.rows:
            cand = row_map.get(sel.selection.rows[0])
            if cand is not None:
                selected_tube = cand

# ─── RIGHT — Detail ──────────────────────────────────────────────────────────

with col_detail:
    if selected_tube is None:
        st.info("Click a tube row (not a group header) in the tree on the left.")
        st.stop()

    t   = selected_tube
    sec = section_props(t["od_mm"], t["wt_mm"])

    st.subheader(f"OD {t['od_label']}\"   ·   BWG {t['gauge']}")
    st.caption(
        f"OD = {t['od_mm']:.3f} mm  |  WT = {t['wt_mm']:.3f} mm  |  "
        f"ID = {sec['id_mm']:.3f} mm  |  t/D = {sec['t_d']:.3f} %"
    )

    # ── Geometry ──────────────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("**Geometry**")
        g1, g2, g3, g4, g5 = st.columns(5)
        stat(g1, "OD",       f"{t['od_mm']:.3f}",   "mm")
        stat(g2, "WT",       f"{t['wt_mm']:.3f}",   "mm")
        stat(g3, "ID",       f"{sec['id_mm']:.3f}", "mm")
        stat(g4, "ID / OD",  f"{sec['id_od']:.4f}", "")
        stat(g5, "t / D",    f"{sec['t_d']:.3f}",   "%")

    # ── Full data ──────────────────────────────────────────────────────────────
    with st.expander("Full data table"):
        st.dataframe(
            pd.DataFrame([
                ("OD — Outside Diameter",      f"{t['od_mm']:.4f}",    "mm"),
                ("OD — imperial",              f"{t['od_label']}\"",   "in"),
                ("BWG gauge",                  str(t["gauge"]),         "—"),
                ("WT — Wall Thickness",        f"{t['wt_mm']:.4f}",    "mm"),
                ("ID — Inside Diameter",       f"{sec['id_mm']:.4f}",  "mm"),
                ("ID / OD",                    f"{sec['id_od']:.6f}",  "—"),
                ("t / D  (WT/OD × 100)",       f"{sec['t_d']:.4f}",   "%"),
                ("Bore area  A_i",             f"{sec['a_bore']:.4f}", "mm²"),
                ("Metal area  A",              f"{sec['a_met']:.4f}",  "mm²"),
                ("Second moment  Iz",          f"{sec['iz']:.4f}",     "mm⁴"),
                ("Polar moment  Jt",           f"{sec['jt']:.4f}",     "mm⁴"),
                ("Section modulus  Wz",        f"{sec['wz']:.4f}",     "mm³"),
                ("Unit mass  (steel ρ=7850)",  f"{sec['mass']:.4f}",   "kg/m"),
            ], columns=["Property", "Value", "Unit"]),
            hide_index=True, use_container_width=True,
        )

    # ── Flow, ρv² and Pressure Drop ───────────────────────────────────────────
    with st.expander("Flow  —  Velocity · ρv² · Pressure Drop", expanded=True):

        # ── Fluid inputs ──────────────────────────────────────────────────────
        with st.container(border=True):
            st.markdown("**Fluid conditions (per tube)**")
            fi1, fi2, fi3 = st.columns(3)
            with fi1:
                flow_kgh = st.number_input(
                    "Mass flow per tube  (kg/h)",
                    min_value=0.0, value=500.0, step=100.0, format="%.1f",
                    key="t_flow",
                )
            with fi2:
                rho = st.number_input(
                    "Density  ρ  (kg/m³)",
                    min_value=0.001, value=850.0, step=10.0, format="%.2f",
                    key="t_rho",
                )
            with fi3:
                mu_cP = st.number_input(
                    "Viscosity  μ  (mPa·s = cP)",
                    min_value=0.001, value=1.0, step=0.1, format="%.3f",
                    key="t_mu",
                    help="Water ≈ 1 cP  |  Light oil ≈ 5–50 cP  |  Heavy oil ≈ 100–1 000 cP",
                )

        # ── Velocity + ρv² ────────────────────────────────────────────────────
        v     = velocity_ms(sec["id_mm"], flow_kgh, rho)
        Re    = reynolds_number(v, sec["id_mm"], rho, mu_cP)
        rhov2 = rho * v ** 2
        half_rhov2 = rhov2 / 2.0

        r1, r2, r3, r4 = st.columns(4)
        stat(r1, "Velocity  v",       f"{v:.4f}",          "m/s")
        stat(r2, "ρv²",               f"{rhov2:.1f}",      "Pa")
        stat(r3, "½ρv²  (dyn. P)",   f"{half_rhov2:.1f}", "Pa")
        stat(r4, "Reynolds  Re",      f"{Re:,.0f}",        "")
        st.caption(f"Flow regime: **{flow_regime(Re)}**")

        # ρv² TEMA note
        if rhov2 > 0:
            if   rhov2 > 7440:  st.warning(f"⚠ ρv² = {rhov2:.0f} Pa — check erosion limits for service.")
            elif rhov2 > 2232:  st.warning(f"⚠ ρv² = {rhov2:.0f} Pa — may exceed TEMA non-corrosive nozzle limit (2 232 Pa).")
            else:               st.success(f"✅ ρv² = {rhov2:.0f} Pa ≤ 2 232 Pa (TEMA non-corrosive limit).")

        st.divider()

        # ── Pressure drop inputs ──────────────────────────────────────────────
        st.markdown("**Pressure Drop — Darcy-Weisbach**")

        pd1, pd2 = st.columns(2)
        with pd1:
            L_m = st.number_input(
                "Tube length  L  (m)",
                min_value=0.01, value=3.0, step=0.5, format="%.2f",
                key="t_L",
            )
            preset_key = st.selectbox(
                "Surface roughness",
                list(ROUGHNESS_PRESETS.keys()),
                index=2,   # Carbon steel default
                key="t_eps_preset",
            )
            if preset_key == "Custom":
                eps_mm = st.number_input(
                    "ε  (mm)", min_value=0.0, value=0.046,
                    step=0.001, format="%.4f", key="t_eps_custom",
                )
            else:
                eps_mm = ROUGHNESS_PRESETS[preset_key]
                st.caption(f"ε = {eps_mm} mm")

        with pd2:
            k_in = st.number_input(
                "K_in  — entrance loss factor",
                min_value=0.0, value=0.5, step=0.05, format="%.2f",
                key="t_kin",
                help="Sharp-edged entrance from header: ≈ 0.5  |  Well-rounded: ≈ 0.04  |  None: 0",
            )
            k_out = st.number_input(
                "K_out  — exit loss factor",
                min_value=0.0, value=1.0, step=0.05, format="%.2f",
                key="t_kout",
                help="Sudden expansion into header: ≈ 1.0",
            )

        # ── Compute ───────────────────────────────────────────────────────────
        f_D = friction_darcy(Re, eps_mm, sec["id_mm"]) if Re > 0 else 0.0
        dp  = calc_pressure_drop(v, rho, f_D, L_m, sec["id_mm"], k_in, k_out)

        d_m   = sec["id_mm"] / 1000.0
        L_D   = L_m / d_m if d_m > 0 else 0.0
        K_tot = f_D * L_D + k_in + k_out

        with st.container(border=True):
            st.markdown(
                r"$\Delta P = \underbrace{\left(f_D \,\dfrac{L}{D_i}\right)}_{\text{friction}}"
                r"+ \underbrace{\left(K_{in} + K_{out}\right)}_{\text{local}}"
                r"\Bigg] \cdot \dfrac{\rho\,v^2}{2}$"
            )
            m1, m2, m3, m4 = st.columns(4)
            stat(m1, "f_D  (Darcy, Churchill)",  f"{f_D:.5f}",   "")
            stat(m2, "ε/D  (relative roughness)", f"{eps_mm / sec['id_mm']:.2e}", "")
            stat(m3, "f_D × L/D  (friction)",     f"{f_D * L_D:.2f}", "")
            stat(m4, "K_tot  (all losses)",       f"{K_tot:.2f}", "")

        st.markdown("")
        dp1, dp2, dp3, dp4, dp5 = st.columns(5)
        stat(dp1, "ΔP friction",  f"{dp['dp_f']:.1f}",           "Pa")
        stat(dp2, "ΔP local",     f"{dp['dp_l']:.1f}",           "Pa")
        stat(dp3, "ΔP total",     f"{dp['dp_t']:.1f}",           "Pa")
        stat(dp4, "ΔP total",     f"{dp['dp_t'] / 1e3:.4f}",     "kPa")
        stat(dp5, "ΔP total",     f"{dp['dp_t'] / 1e5:.6f}",     "bar")

        st.markdown("")
        stat_bar1, stat_bar2 = st.columns(2)
        stat(stat_bar1, "ΔP / length",
             f"{dp['dp_t'] / L_m:.2f}" if L_m > 0 else "—", "Pa/m")
        stat(stat_bar2, "Velocity heads (total)",
             f"{dp['dp_t'] / half_rhov2:.2f}" if half_rhov2 > 0 else "—", "")

        if Re > 0 and f_D > 0:
            regime_plain = flow_regime(Re).split(" ")[1]   # just "Laminar" / "Transition" / "Turbulent"
            st.caption(
                f"Churchill (1977) friction factor — regime: {regime_plain}  |  "
                f"ε/D = {eps_mm/sec['id_mm']:.3e}  |  "
                f"Fully turbulent f_D,∞ = {friction_darcy(1e9, eps_mm, sec['id_mm']):.5f}"
            )

        with st.expander("Reference limits — TEMA ρv²"):
            st.markdown("""
| Service | TEMA ρv² limit |
|---|---|
| Non-corrosive, non-abrasive liquids (shell-side nozzle) | ≤ **2 232 Pa** |
| Corrosive or abrasive liquids | ≤ **744 Pa** |
| Typical tube-side liquid velocity | 0.5 – 3 m/s |
| Typical tube-side gas velocity | 5 – 30 m/s |

> ρv² limits above apply to **shell-side nozzle** impingement (TEMA RGP-T-2.5).
> No universal TEMA limit exists for tube-side ρv²; the velocity range is the usual criterion.
""")
