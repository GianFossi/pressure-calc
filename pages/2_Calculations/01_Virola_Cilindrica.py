"""
Cylindrical Shell — Internal Pressure  (all 6 codes)

Codes supported:
  ASME VIII Div.1  (UG-27c)
  ASME VIII Div.2  (Part 4 §4.3.3)
  EN 13445-3       (§7.4.2)
  AD 2000          (B0 §6)
  BS PD 5500       (§3.5.1.2)
  CODAP 2023       (§C2.3)
"""

import sys
import os
import math

import streamlit as st
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from calc.db.materials import (
    get_all_materials, get_material,
    get_yield_at_T, get_ultimate_at_T, get_S_div1, get_S_div2,
    allowable_EN13445, allowable_AD2000, allowable_BS5500, allowable_CODAP,
)
try:
    from calc.db.materials import MaterialSearch
except ImportError:
    MaterialSearch = None
from calc.codes import asme_viii_1, en_13445
from calc.codes import asme_viii_2, ad_2000, bs_5500, codap as codap_mod

# ─── Cached data ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def _all_materials():
    if MaterialSearch is not None:
        return MaterialSearch().search().to_list()
    return get_all_materials()


@st.cache_data(ttl=3600)
def _search_materials(text: str):
    query = text.strip()
    if MaterialSearch is not None:
        return MaterialSearch().search(query).to_list()
    if not query:
        return get_all_materials()

    terms = [
        part.strip().lower()
        for part in query.replace(" AND ", " and ").split(" and ")
        if part.strip()
    ]

    def _matches(material: dict) -> bool:
        haystack = " ".join(
            str(material.get(field, ""))
            for field in ("name", "spec", "grade", "cls", "alloy", "comp", "pform")
        ).lower()
        for term in terms:
            if ":" in term:
                field, value = [part.strip() for part in term.split(":", 1)]
                field_map = {
                    "spec": "spec",
                    "grade": "grade",
                    "class": "cls",
                    "cls": "cls",
                    "uns": "alloy",
                    "alloy": "alloy",
                    "composition": "comp",
                    "comp": "comp",
                    "pform": "pform",
                    "productform": "pform",
                }
                key = field_map.get(field)
                if key is None or value.strip('"') not in str(material.get(key, "")).lower():
                    return False
            elif term not in haystack:
                return False
        return True

    return [material for material in get_all_materials() if _matches(material)]

ALL_MATS = _all_materials()

CODE_LABELS = {
    "d1": "ASME VIII-1",
    "d2": "ASME VIII-2",
    "en": "EN 13445-3",
    "ad": "AD 2000",
    "bs": "BS PD 5500",
    "cp": "CODAP 2023",
}

ASME_STRESS_SOURCE = {
    "d1": "AllowableStress1Table / ASME II-D Table 1A (S1)",
    "d2": "AllowableStress2Table / ASME II-D Table 5A (S2)",
}

# ─── Page title ──────────────────────────────────────────────────────────────
st.title("Cylindrical Shell — Internal Pressure")
st.caption(
    "ASME VIII-1 · ASME VIII-2 · EN 13445-3 · AD 2000 · BS PD 5500 · CODAP 2023 — Code comparison"
)

# ─── INPUT ───────────────────────────────────────────────────────────────────
with st.container(border=True):
    st.subheader("Input Data")

    # ── Geometry & default conditions ─────────────────────────────────────────
    gc1, gc2, gc3 = st.columns(3)

    with gc1:
        st.markdown("**Geometry**")
        D_i = st.number_input("Shell ID (mm)", min_value=10.0, value=1000.0,
                               step=10.0, format="%.1f", key="Di")
        WT  = st.number_input("Nominal Wall Thickness WT (mm)", min_value=0.5,
                               value=20.0, step=0.5, format="%.1f", key="WT")
        D_o = D_i + 2.0 * WT
        st.info(f"Calculated OD = **{D_o:.1f} mm**")

    with gc2:
        st.markdown("**Default Operating Conditions**")
        P_default = st.number_input("Default design pressure P (bar)", min_value=0.1,
                                    value=10.0, step=0.5, format="%.2f", key="P_default")
        T_default = st.number_input("Default design temperature T (°C)", min_value=-50.0,
                                    value=200.0, step=5.0, format="%.1f", key="T_default")
        T_F_default = T_default * 9 / 5 + 32
        st.caption(f"T = {T_default:.1f} °C = {T_F_default:.1f} °F")

    with gc3:
        st.markdown("**Default Joint Efficiency / Coefficient**")
        E_asme_default = st.selectbox(
            "Default E — ASME (joint efficiency)",
            options=[1.0, 0.85, 0.70],
            format_func=lambda x: {
                1.0:  "1.00 — Full RT (Cat. A)",
                0.85: "0.85 — Partial RT",
                0.70: "0.70 — No RT",
            }[x],
            help="UW-12: full RT → 1.0, partial → 0.85, none → 0.70",
        )
        link_z_default = st.checkbox("Use same value for European codes (z = E)", value=True)
        if link_z_default:
            z_eu_default = E_asme_default
            st.info(f"z = {z_eu_default}")
        else:
            z_eu_default = st.selectbox(
                "Default z — European codes (joint coefficient)",
                options=[1.0, 0.85, 0.70],
                format_func=lambda x: {
                    1.0:  "1.00 — Cat. A/B examined",
                    0.85: "0.85 — Cat. C/D",
                    0.70: "0.70 — No examination",
                }[x],
            )

    st.markdown("**Calculation Input by Code**")
    st.caption("Each selected code uses its own pressure, temperature, and weld/joint coefficient.")
    code_inputs = {}
    code_tabs = st.tabs(list(CODE_LABELS.values()))
    for tab, (code_key, code_label) in zip(code_tabs, CODE_LABELS.items()):
        with tab:
            enabled = st.checkbox("Include in calculation", value=True, key=f"{code_key}_enabled")
            ci1, ci2, ci3 = st.columns(3)
            with ci1:
                P_code = st.number_input(
                    "Design pressure P (bar)",
                    min_value=0.1,
                    value=P_default,
                    step=0.5,
                    format="%.2f",
                    key=f"{code_key}_P",
                    disabled=not enabled,
                )
            with ci2:
                T_code = st.number_input(
                    "Design temperature T (°C)",
                    min_value=-50.0,
                    value=T_default,
                    step=5.0,
                    format="%.1f",
                    key=f"{code_key}_T",
                    disabled=not enabled,
                )
                st.caption(f"{T_code * 9 / 5 + 32:.1f} °F")
            with ci3:
                if code_key in ("d1", "d2"):
                    Ez_code = st.selectbox(
                        "E — ASME joint efficiency",
                        options=[1.0, 0.85, 0.70],
                        index=[1.0, 0.85, 0.70].index(E_asme_default),
                        format_func=lambda x: {
                            1.0:  "1.00 — Full RT (Cat. A)",
                            0.85: "0.85 — Partial RT",
                            0.70: "0.70 — No RT",
                        }[x],
                        key=f"{code_key}_Ez",
                        disabled=not enabled,
                    )
                else:
                    Ez_code = st.selectbox(
                        "z — joint coefficient",
                        options=[1.0, 0.85, 0.70],
                        index=[1.0, 0.85, 0.70].index(z_eu_default),
                        format_func=lambda x: {
                            1.0:  "1.00 — Cat. A/B examined",
                            0.85: "0.85 — Cat. C/D",
                            0.70: "0.70 — No examination",
                        }[x],
                        key=f"{code_key}_Ez",
                        disabled=not enabled,
                    )
            code_inputs[code_key] = {
                "enabled": enabled,
                "P": P_code,
                "T": T_code,
                "Ez": Ez_code,
            }

# ─── ALLOWANCES ──────────────────────────────────────────────────────────────
with st.container(border=True):
    st.subheader("Allowances")
    ac1, ac2, ac3 = st.columns(3)

    with ac1:
        c_int = st.number_input(
            "Internal corrosion / erosion c₁ (mm)",
            min_value=0.0, value=3.0, step=0.5, format="%.2f",
            help="Corrosion or erosion allowance on the process side",
        )
        c_ext = st.number_input(
            "External corrosion allowance c₂ (mm)",
            min_value=0.0, value=0.0, step=0.5, format="%.2f",
            help="Corrosion allowance on the external surface",
        )

    with ac2:
        fab_mode = st.radio(
            "Fabrication allowance type",
            options=["% of nominal WT", "Absolute (mm)"],
            horizontal=True,
            help="Mill tolerance + any forming thinning. ASME typically 12.5 % for plate.",
        )
        if fab_mode == "% of nominal WT":
            fab_pct = st.number_input("Mill tolerance / fab. thinning (%)",
                                       min_value=0.0, value=12.5, step=0.5, format="%.2f")
            c_fab = WT * fab_pct / 100.0
        else:
            c_fab = st.number_input("Fabrication / undertolerance (mm)",
                                     min_value=0.0, value=1.5, step=0.1, format="%.2f")
            fab_pct = (c_fab / WT * 100.0) if WT > 0 else 0.0
        st.caption(f"c_fab = **{c_fab:.2f} mm** ({fab_pct:.1f}% of WT)")

    with ac3:
        c_total = c_int + c_ext + c_fab
        t_avail = WT - c_fab - c_int - c_ext
        st.markdown("**Summary**")
        st.dataframe(
            pd.DataFrame(
                [
                    ("c₁ internal",   f"{c_int:.2f} mm"),
                    ("c₂ external",   f"{c_ext:.2f} mm"),
                    ("c_fab",         f"{c_fab:.2f} mm"),
                    ("Total allowance", f"{c_total:.2f} mm"),
                    ("Available thickness", f"{max(t_avail, 0):.2f} mm"),
                ],
                columns=["Item", "Value"],
            ),
            hide_index=True, use_container_width=True,
        )

# ─── MATERIAL SELECTION ───────────────────────────────────────────────────────
with st.container(border=True):
    st.subheader("Material Selection")
    ms1, ms2 = st.columns([1, 2])

    if "mat_search_vc" not in st.session_state:
        st.session_state["mat_search_vc"] = "spec:SA-516 AND grade:70"

    with ms1:
        search = st.text_input(
            "Filter for Material Selection (spec / grade / UNS / composition)",
            key="mat_search_vc",
            placeholder="e.g. SA-516 or N06625 or 1.4404 or 1¼Cr-½Mo-Si",
        )
        st.caption(
            'Examples: spec:SA-516 AND grade:70, composition:"Carbon steel", '
            'SMYS>=260, MaximumAllowableTemperature>=538'
        )

    # Filter material list with the common ASME material search parser.
    search_error = None
    try:
        filtered = _search_materials(search) if search.strip() else ALL_MATS
    except ValueError as exc:
        filtered = []
        search_error = str(exc)

    # Clamp selectbox index to valid range after filtering (prevents stale-index errors)
    n_filtered = len(filtered)
    if n_filtered > 0:
        current_idx = st.session_state.get("mat_select", 0)
        if not isinstance(current_idx, int) or current_idx >= n_filtered:
            st.session_state["mat_select"] = 0

    with ms2:
        if not filtered:
            if search_error:
                st.error(f"Invalid material search: {search_error}")
            else:
                st.warning("No materials match the search criteria.")
            mat_id = None
        else:
            mat_names = [m["name"] for m in filtered]

            if len(filtered) == 1:
                st.success(f"✔ Single match — auto-selected: **{mat_names[0]}**")
                st.session_state["mat_select"] = 0
                mat_id = filtered[0]["id"]
            else:
                mat_idx = st.selectbox(
                    "Select the Material",
                    options=range(len(mat_names)),
                    format_func=lambda i: mat_names[i],
                    key="mat_select",
                )
                mat_id = filtered[mat_idx]["id"]

# ─── MATERIAL PROPERTIES ─────────────────────────────────────────────────────
mat_props = None
SMYS = SMTS = Ar = None
Sy_by_code = {}
Su_by_code = {}
allowable_by_code = {key: None for key in CODE_LABELS}

if mat_id is not None:
    mat_props = get_material(mat_id)

    if mat_props:
        SMYS  = mat_props["SMYS"]
        SMTS  = mat_props["SMTS"]
        Ar    = mat_props["Ar"]

        for code_key, code_input in code_inputs.items():
            T_code = code_input["T"]
            Sy_code = get_yield_at_T(mat_id, T_code, thk_mm=WT)
            Su_code = get_ultimate_at_T(mat_id, T_code, thk_mm=WT)
            Sy_by_code[code_key] = Sy_code
            Su_by_code[code_key] = Su_code

            if code_key == "d1":
                allowable_by_code[code_key] = get_S_div1(mat_id, T_code, thk_mm=WT)
            elif code_key == "d2":
                allowable_by_code[code_key] = get_S_div2(mat_id, T_code, thk_mm=WT)
            else:
                Rp_T = Sy_code if Sy_code is not None else SMYS
                if Rp_T is not None and SMTS is not None:
                    if code_key == "en":
                        allowable_by_code[code_key] = allowable_EN13445(Rp_T, SMTS, Ar)
                    elif code_key == "ad":
                        allowable_by_code[code_key] = allowable_AD2000(Rp_T, SMTS)
                    elif code_key == "bs":
                        allowable_by_code[code_key] = allowable_BS5500(Rp_T, SMTS)
                    elif code_key == "cp":
                        allowable_by_code[code_key] = allowable_CODAP(Rp_T, SMTS, Ar)

with st.expander("Material Properties", expanded=(mat_props is not None)):
    if mat_props is None:
        st.info("Select a material to view its properties.")
    else:
        mp1, mp2, mp3 = st.columns(3)

        with mp1:
            st.markdown("**Identification**")
            id_rows = [
                ("Specification",    mat_props["spec"]),
                ("Type / Grade",     mat_props["grade"] or "—"),
                ("Class / Cond.",    mat_props["cls"]   or "—"),
                ("Alloy Desig.",     mat_props["alloy"] or "—"),
                ("Composition",      mat_props["comp"]  or "—"),
                ("Product Form",     mat_props["pform"] or "—"),
            ]
            st.dataframe(pd.DataFrame(id_rows, columns=["Field", "Value"]),
                         hide_index=True, use_container_width=True)

        with mp2:
            st.markdown("**Room-temperature (20 °C) properties**")
            SMYS = mat_props["SMYS"]
            SMTS = mat_props["SMTS"]
            Ar   = mat_props["Ar"]
            den  = mat_props["density"]
            rt_rows = [
                ("SMYS  Rp0.2 (MPa)",    f"{SMYS:.1f}" if SMYS else "—"),
                ("SMTS  Rm   (MPa)",     f"{SMTS:.1f}" if SMTS else "—"),
                ("Ar  elongation (%)",   f"{Ar:.1f}"   if Ar   else "—"),
                ("Density (kg/m³)",      f"{den:.0f}"  if den  else "—"),
            ]
            st.dataframe(pd.DataFrame(rt_rows, columns=["Property", "Value"]),
                         hide_index=True, use_container_width=True)
            if Ar is not None and Ar < 14.0:
                st.warning(f"⚠ Ar = {Ar:.1f}% < 14% — verify code requirements for low-ductility materials.")

        with mp3:
            st.markdown("**At design temperature by code**")
            at_rows = []
            for code_key, code_label in CODE_LABELS.items():
                if not code_inputs[code_key]["enabled"]:
                    continue
                allow = allowable_by_code.get(code_key)
                if isinstance(allow, dict):
                    allow_value = allow["f"]
                else:
                    allow_value = allow
                at_rows.append({
                    "Code": code_label,
                    "T (°C)": f"{code_inputs[code_key]['T']:.1f}",
                    "Sy/Rp0.2_T (MPa)": f"{Sy_by_code.get(code_key):.1f}" if Sy_by_code.get(code_key) is not None else "—",
                    "Su/Rm_T (MPa)": f"{Su_by_code.get(code_key):.1f}" if Su_by_code.get(code_key) is not None else "—",
                    "S/f (MPa)": f"{allow_value:.1f}" if allow_value is not None else "Not listed",
                })
            st.dataframe(pd.DataFrame(at_rows), hide_index=True, use_container_width=True)
            if any(Sy_by_code.get(k) is None for k, v in code_inputs.items() if v["enabled"]):
                st.warning("Rp0.2 at temperature not found for one or more codes — using SMYS for European allowables where needed.")

# ─── ALLOWABLE STRESSES BY CODE ──────────────────────────────────────────────
with st.expander("Allowable Stress by Code", expanded=True):
    if mat_props is None:
        st.info("Select a material first.")
    else:
        def _fmt(v):
            return f"{v:.2f}" if v is not None else "—"

        def _gov(d):
            return d["governing"] if d else "—"

        sf_rows = []

        for code_key, code_label in CODE_LABELS.items():
            if not code_inputs[code_key]["enabled"]:
                continue

            allow = allowable_by_code.get(code_key)
            if code_key == "d1":
                sf_rows.append({
                    "Code":          code_label,
                    "T (°C)":        f"{code_inputs[code_key]['T']:.1f}",
                    "S / f  (MPa)":  _fmt(allow),
                    "Criterion 1":   "Table lookup",
                    "Criterion 2":   "Not recalculated from SMYS/SMTS",
                    "Governing":     ASME_STRESS_SOURCE[code_key],
                    "SF (UTS)":      "per table",
                    "SF (Yield)":    "per table",
                })
            elif code_key == "d2":
                sf_rows.append({
                    "Code":          code_label,
                    "T (°C)":        f"{code_inputs[code_key]['T']:.1f}",
                    "S / f  (MPa)":  _fmt(allow),
                    "Criterion 1":   "Table lookup",
                    "Criterion 2":   "Not recalculated from SMYS/SMTS",
                    "Governing":     ASME_STRESS_SOURCE[code_key],
                    "SF (UTS)":      "per table",
                    "SF (Yield)":    "per table",
                })
            else:
                sf_rows.append({
                    "Code":          code_label,
                    "T (°C)":        f"{code_inputs[code_key]['T']:.1f}",
                    "S / f  (MPa)":  _fmt(allow["f"] if allow else None),
                    "Criterion 1":   _fmt(allow["cand_yield"] if allow else None) + " (Rp0.2_T/1.5)",
                    "Criterion 2":   _fmt(allow["cand_uts"] if allow else None) + f" (Rm/{allow['sf_uts'] if allow else '—'})",
                    "Governing":     _gov(allow),
                    "SF (UTS)":      str(allow["sf_uts"]) if allow else "—",
                    "SF (Yield)":    "1.5",
                })

        st.dataframe(
            pd.DataFrame(sf_rows).set_index("Code"),
            use_container_width=True,
        )

        if allowable_by_code.get("d1") is None and allowable_by_code.get("d2") is None:
            st.warning("This material is not listed in ASME II-D stress tables. "
                       "Enter allowable stress manually if needed.")

# ─── CALCULATION ENGINE ───────────────────────────────────────────────────────
def _run_code(code_key: str, P_bar: float, S: float | None, E_z: float) -> dict | None:
    """Run thickness formula for a single code.  Returns result dict or None."""
    if S is None or S <= 0:
        return None
    if code_key == "d1":
        return asme_viii_1.thickness_internal(P_bar, D_i, S, E_z)
    if code_key == "d2":
        return asme_viii_2.thickness_internal(P_bar, D_i, S, E_z)
    if code_key == "en":
        return en_13445.thickness_internal(P_bar, D_i, S, E_z)
    if code_key == "ad":
        return ad_2000.thickness_internal(P_bar, D_i, S, E_z)
    if code_key == "bs":
        return bs_5500.thickness_internal(P_bar, D_i, S, E_z)
    if code_key == "cp":
        return codap_mod.thickness_internal(P_bar, D_i, S, E_z)
    return None


def _mawp(code_key: str, t_struct: float, S: float, E_z: float) -> float:
    ta = max(t_avail, 0.0)
    if code_key == "d1":
        return asme_viii_1.mawp(ta, D_i, S, E_z)
    if code_key == "d2":
        return asme_viii_2.mawp(ta, D_i, S, E_z)
    if code_key == "en":
        return en_13445.ps_max(ta, D_i, S, E_z)
    if code_key == "ad":
        return ad_2000.mawp(ta, D_i, S, E_z)
    if code_key == "bs":
        return bs_5500.mawp(ta, D_i, S, E_z)
    if code_key == "cp":
        return codap_mod.mawp(ta, D_i, S, E_z)
    return 0.0


CODE_REFS = {
    "d1": ("UG-27(c)(1)", r"t = \dfrac{P \cdot R}{S \cdot E - 0.6\,P}"),
    "d2": ("Part 4 §4.3.3", r"t = \dfrac{P \cdot R_i}{S \cdot E - 0.5\,P}"),
    "en": ("§7.4.2", r"e = \dfrac{P \cdot D_i}{2\,f \cdot z - P}"),
    "ad": ("B0 §6", r"s = \dfrac{p \cdot D_i}{2\,\sigma_{zul} \cdot v - p}"),
    "bs": ("§3.5.1.2", r"e = \dfrac{p \cdot D_i}{2\,f \cdot z - p}"),
    "cp": ("§C2.3", r"e = \dfrac{p \cdot D_i}{2\,f \cdot z - p}"),
}

CODE_DEFS = []
for code_key, code_label in CODE_LABELS.items():
    allow = allowable_by_code.get(code_key)
    S_value = allow["f"] if isinstance(allow, dict) else allow
    ref, latex = CODE_REFS[code_key]
    code_input = code_inputs[code_key]
    CODE_DEFS.append((
        code_key,
        code_label,
        code_input["enabled"],
        code_input["P"],
        code_input["T"],
        S_value,
        code_input["Ez"],
        ref,
        latex,
    ))

results = {}
for key, label, enabled, P_code, T_code, S, Ez, ref, ltx in CODE_DEFS:
    r = _run_code(key, P_code, S, Ez) if enabled else None
    results[key] = {
        "label": label,
        "enabled": enabled,
        "P": P_code,
        "T": T_code,
        "S": S,
        "Ez": Ez,
        "ref": ref,
        "latex": ltx,
        "res": r,
    }

# ─── RESULTS ─────────────────────────────────────────────────────────────────
st.divider()
st.subheader("Results — Minimum Required Thickness")

if mat_props is None:
    st.info("Select a material and fill in the inputs above to see results.")
else:
    enabled_results = [(key, info) for key, info in results.items() if info["enabled"]]
    if not enabled_results:
        st.info("Enable at least one code to see results.")
        st.stop()

    # ── Summary table ──────────────────────────────────────────────────────────
    summary_rows = []
    for key, info in enabled_results:
        r   = info["res"]
        S   = info["S"]
        Ez  = info["Ez"]
        if r is None or "error" in r:
            summary_rows.append({
                "Code":               info["label"],
                "P (bar)":            f"{info['P']:.2f}",
                "T (°C)":             f"{info['T']:.1f}",
                "E / z":              f"{Ez:.2f}",
                "S / f  (MPa)":       f"{S:.2f}" if S else "N/A",
                "t_struct (mm)":      "N/A",
                "t_total (mm)":       "N/A",
                "t_avail (mm)":       f"{max(t_avail,0):.2f}",
                "MAWP (bar)":         "N/A",
                "Status":             "⚠ N/A" if r is None else f"❌ {r.get('error','Error')}",
            })
        else:
            t_st = r["t_min_mm"]
            t_to = round(t_st + c_total, 2)
            mwp  = _mawp(key, t_st, S, Ez) if S else 0.0
            ok   = t_avail >= t_st
            summary_rows.append({
                "Code":               info["label"],
                "P (bar)":            f"{info['P']:.2f}",
                "T (°C)":             f"{info['T']:.1f}",
                "E / z":              f"{Ez:.2f}",
                "S / f  (MPa)":       f"{S:.2f}",
                "t_struct (mm)":      f"{t_st:.2f}",
                "t_total (mm)":       f"{t_to:.2f}",
                "t_avail (mm)":       f"{max(t_avail,0):.2f}",
                "MAWP (bar)":         f"{mwp:.2f}",
                "Status":             "✅ OK" if ok else "❌ WT Insufficient",
            })

    st.dataframe(
        pd.DataFrame(summary_rows).set_index("Code"),
        use_container_width=True,
    )

    # Highlight most / least conservative
    valid_t = [
        (info["label"], info["res"]["t_min_mm"])
        for _, info in enabled_results
        if info["res"] and "t_min_mm" in info["res"]
    ]
    if len(valid_t) >= 2:
        max_lbl, max_t = max(valid_t, key=lambda x: x[1])
        min_lbl, min_t = min(valid_t, key=lambda x: x[1])
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Most conservative", f"{max_t:.2f} mm", delta=f"({max_lbl})", delta_color="off")
        mc2.metric("Least conservative", f"{min_t:.2f} mm", delta=f"({min_lbl})", delta_color="off")
        mc3.metric("Ordered WT", f"{WT:.1f} mm", delta=f"Available: {max(t_avail,0):.2f} mm", delta_color="off")

    # ── Per-code detail tabs ───────────────────────────────────────────────────
    st.divider()
    st.subheader("Per-code Details")

    tab_labels = [info["label"] for _, info in enabled_results]
    tabs = st.tabs(tab_labels)

    for tab, (key, info) in zip(tabs, enabled_results):
        with tab:
            r  = info["res"]
            S  = info["S"]
            Ez = info["Ez"]

            st.caption(f"Reference: **{info['ref']}**")
            st.latex(info["latex"])

            if S is None:
                st.warning(
                    "Allowable stress is not available for this material / code combination. "
                    "No calculation performed."
                )
                continue

            if r is None or "error" in r:
                st.error(r.get("error", "Unknown error") if r else "No result")
                continue

            t_st = r["t_min_mm"]
            t_to = round(t_st + c_total, 2)
            mwp  = _mawp(key, t_st, S, Ez)

            col_a, col_b = st.columns(2)

            with col_a:
                st.markdown("**Calculation**")
                P_bar = info["P"]
                P_mpa = P_bar * 0.1
                rows = [
                    ("Design pressure P",   f"{P_mpa:.4f} MPa  ({P_bar:.2f} bar)"),
                    ("Design temperature T", f"{info['T']:.1f} °C"),
                    ("Allowable stress S/f", f"{S:.2f} MPa"),
                    ("Joint eff. E / z",     f"{Ez:.2f}"),
                ]
                if key in ASME_STRESS_SOURCE:
                    rows.append(("Allowable stress source", ASME_STRESS_SOURCE[key]))
                if key == "d1":
                    rows += [
                        ("Inside radius R",      f"{D_i/2:.2f} mm"),
                        ("t_hoop (c)(1)",         f"{r.get('t_hoop_mm', '—')} mm"),
                        ("t_long (c)(2)",         f"{r.get('t_long_mm', '—')} mm"),
                    ]
                else:
                    rows.append(("Inside diameter Di",  f"{D_i:.1f} mm"))

                rows += [
                    ("Structural thickness t_struct", f"**{t_st:.2f} mm**"),
                    ("+ Internal allowance c₁",      f"{c_int:.2f} mm"),
                    ("+ External allowance c₂",      f"{c_ext:.2f} mm"),
                    ("+ Fabrication allowance c_fab", f"{c_fab:.2f} mm"),
                    ("= Total required (to order)",   f"**{t_to:.2f} mm**"),
                ]
                st.dataframe(
                    pd.DataFrame(rows, columns=["Parameter", "Value"]),
                    hide_index=True, use_container_width=True,
                )

            with col_b:
                st.markdown("**Verification vs. ordered WT**")
                ok = t_avail >= t_st
                verif_rows = [
                    ("Ordered WT",            f"{WT:.2f} mm"),
                    ("– Fab. allowance c_fab", f"{c_fab:.2f} mm"),
                    ("– Internal allow. c₁",  f"{c_int:.2f} mm"),
                    ("– External allow. c₂",  f"{c_ext:.2f} mm"),
                    ("= Available thickness",  f"{max(t_avail,0):.2f} mm"),
                    ("Required structural t",  f"{t_st:.2f} mm"),
                    ("Margin (avail – req.)",  f"{(t_avail - t_st):+.3f} mm"),
                    ("MAWP",                   f"{mwp:.2f} bar"),
                ]
                st.dataframe(
                    pd.DataFrame(verif_rows, columns=["Item", "Value"]),
                    hide_index=True, use_container_width=True,
                )
                if ok:
                    st.success(f"✅ Ordered WT = {WT:.1f} mm  →  **ADEQUATE**")
                else:
                    need = math.ceil((t_st + c_total) * 2) / 2
                    st.error(
                        f"❌ Ordered WT = {WT:.1f} mm is **INSUFFICIENT**  "
                        f"(minimum to order ≈ {need:.1f} mm)"
                    )

    # ── Code-comparison technical notes ───────────────────────────────────────
    with st.expander("Technical Notes — Formula derivation & code comparison"):
        st.markdown(r"""
### Membrane equilibrium — thin-wall cylinder

All six codes derive from the same equilibrium of a slit cylinder:

$$
\sigma_\theta = \frac{P \cdot R}{t}
$$

Setting $\sigma_\theta = S$ (allowable) and solving for $t$ yields the thin-wall formula.
Both ASME codes and the European codes add a correction factor for the compressive
stress component in the longitudinal direction, which shifts the denominator slightly.

### Formula comparison

| Code | Structural formula | P coefficient |
|---|---|---|
| ASME VIII-1 | $t = \dfrac{P \cdot R}{S \cdot E - 0.6\,P}$ | 0.6 |
| ASME VIII-2 | $t = \dfrac{P \cdot R_i}{S \cdot E - 0.5\,P}$ | 0.5 |
| EN 13445-3 | $e = \dfrac{P \cdot D_i}{2\,f \cdot z - P}$ | 0.5 |
| AD 2000 | $s = \dfrac{p \cdot D_i}{2\,\sigma_{zul} \cdot v - p}$ | 0.5 |
| BS PD 5500 | $e = \dfrac{p \cdot D_i}{2\,f \cdot z - p}$ | 0.5 |
| CODAP 2023 | $e = \dfrac{p \cdot D_i}{2\,f \cdot z - p}$ | 0.5 |

ASME VIII-1 uses **0.6·P** (slightly more conservative).
All other codes use **0.5·P** — but vary in their allowable stress definition.

### Allowable stress — key differences

For ASME VIII-1 and VIII-2 this app does **not** recalculate allowable stress from
SMYS/SMTS. It reads the listed ASME allowable stress directly from the embedded
database:

| Code | App source for S |
|---|---|
| ASME VIII-1 | `AllowableStress1Table` / ASME II-D Table 1A (`S1`) |
| ASME VIII-2 | `AllowableStress2Table` / ASME II-D Table 5A (`S2`) |

The following factors are code background for comparison of design philosophy:

| Code | UTS safety factor | Yield safety factor |
|---|---|---|
| ASME VIII-1 | Rm / **3.5** | Sy / 1.5 |
| ASME VIII-2 | Rm / **2.4** | Sy / 1.5 |
| EN 13445-3  | Rm / **2.4** (3.0 for austenitics) | Rp0.2_T / 1.5 |
| AD 2000      | Rm / **2.4** | Rp0.2_T / 1.5 |
| BS PD 5500  | Rm / **2.5** | Rp0.2_T / 1.5 |
| CODAP 2023  | Rm / **2.4** (3.0 for group M6) | Rp0.2_T / 1.5 |

ASME VIII-1 and VIII-2 may reflect additional table rules and limits in the listed
ASME II-D values. European code values shown above are calculated by the app from
the available material properties.

### Allowances

$$
t_{\text{order}} = t_{\text{struct}} + c_1 + c_2 + c_{\text{fab}}
$$

Verification: $t_{\text{available}} = WT - c_{\text{fab}} - c_1 - c_2 \geq t_{\text{struct}}$

where $c_{\text{fab}}$ covers mill undertolerance and any forming thinning.
        """)
