"""ASME Materials Database browser."""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from calc.db.materials import (
    allowable_AD2000,
    allowable_BS5500,
    allowable_CODAP,
    allowable_EN13445,
    get_S_div1,
    get_S_div2,
    get_all_materials,
    get_ultimate_at_T,
    get_yield_at_T,
)
try:
    from calc.db.materials import MaterialSearch
except ImportError:
    MaterialSearch = None

# ─────────────────────────────────────────────────────────────────────────────
_DB       = Path(__file__).resolve().parents[2] / "database" / "asme_materials.db"
_PASSWORD = "asme2026"   # ← change this to your preferred password

# ── Password gate ──────────────────────────────────────────────────────────────
if not st.session_state.get("_mat_unlocked", False):
    st.title("📦 ASME Materials Database")
    pwd = st.text_input("🔒 Password", type="password", placeholder="Enter password…")
    if pwd:
        if pwd == _PASSWORD:
            st.session_state["_mat_unlocked"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()

# Temperature breakpoints used in each table family
_TF = [
    40, 65, 100, 125, 150, 175, 200, 225, 250, 275, 300, 325, 350,
    375, 400, 425, 450, 475, 500, 525, 550, 575, 600, 625, 650, 675,
    700, 725, 750, 775, 800, 825, 850, 875, 900,
]  # °F — Yield / Ultimate / Allowable stress tables

_TC_PHYS = [
    20, 50, 75, 100, 125, 150, 175, 200, 225, 250, 275, 300, 325, 350,
    375, 400, 425, 450, 475, 500, 525, 550, 575, 600, 625, 650, 675,
    700, 725, 750, 775, 800, 825, 850, 875, 900,
]  # °C — Thermal expansion / conductivity / diffusivity / specific heat

_TC_E = [
    -200, -125, -75, 25, 100, 150, 200, 250, 300, 350, 400, 450, 500,
    550, 600, 650, 700, 750, 800, 850, 900,
]  # °C — Elastic modulus table


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(_DB))
    c.row_factory = sqlite3.Row
    c.text_factory = lambda b: b.decode("utf-8", errors="replace")
    return c


def _f2c(tf: float) -> float:
    return (tf - 32.0) * 5.0 / 9.0


def _xy(row: dict, temps: list[int], to_celsius: bool = False) -> tuple[list, list]:
    """Extract (x=temperature, y=value) pairs from a wide row, dropping NULLs."""
    xs, ys = [], []
    for t in temps:
        v = row.get(f"T_{t}")
        if v is not None:
            xs.append(round(_f2c(t) if to_celsius else float(t), 1))
            ys.append(float(v))
    return xs, ys


def _interp_series(xs: list[float], ys: list[float], x: float) -> float | None:
    if not xs or not ys:
        return None
    pairs = sorted(zip(xs, ys), key=lambda item: item[0])
    if x < pairs[0][0] or x > pairs[-1][0]:
        return None
    if x == pairs[0][0]:
        return pairs[0][1]
    for (x1, y1), (x2, y2) in zip(pairs, pairs[1:]):
        if x1 <= x <= x2:
            if x2 == x1:
                return y1
            return y1 + (y2 - y1) * (x - x1) / (x2 - x1)
    return None


def _interp_row(row: dict | None, temps: list[int], T_C: float, to_celsius: bool = False) -> float | None:
    if not row:
        return None
    xs, ys = _xy(row, temps, to_celsius=to_celsius)
    return _interp_series(xs, ys, T_C)


def _pick_size_row(rows: list[dict], size_mm: float | None) -> dict | None:
    if not rows:
        return None
    if size_mm is None:
        return rows[0]
    for row in rows:
        lo, hi = row.get("SizeThkMIN"), row.get("SizeThkMAX")
        lo_inc = bool(row.get("SizeThkMIN_Included", 1))
        hi_inc = bool(row.get("SizeThkMAX_Included", 1))
        above_min = lo is None or (size_mm >= lo if lo_inc else size_mm > lo)
        below_max = hi is None or (size_mm <= hi if hi_inc else size_mm < hi)
        if above_min and below_max:
            return row
    return rows[0]


def _thk_label(row: dict) -> str:
    lo, hi = row.get("SizeThkMIN"), row.get("SizeThkMAX")
    if lo is None and hi is None:
        return "All thicknesses"
    lb = "[" if row.get("SizeThkMIN_Included", 1) else "("
    rb = "]" if row.get("SizeThkMAX_Included", 1) else ")"
    ls = f"{lo:.1f}" if lo is not None else "0"
    hs = f"{hi:.1f}" if hi is not None else "∞"
    return f"{lb}{ls} – {hs}{rb} mm"


# ─────────────────────────────────────────────────────────────────────────────
# Cached DB queries
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _load_all() -> pd.DataFrame:
    if MaterialSearch is not None:
        return _materials_to_df(MaterialSearch().search())
    return _materials_to_df(get_all_materials())


@st.cache_data(ttl=3600)
def _search_materials(text: str) -> pd.DataFrame:
    query = text.strip()
    if MaterialSearch is not None:
        return _materials_to_df(MaterialSearch().search(query))
    if not query:
        return _materials_to_df(get_all_materials())

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

    return _materials_to_df(material for material in get_all_materials() if _matches(material))


def _materials_to_df(materials) -> pd.DataFrame:
    rows = [
        {
            "ID": material.get("id"),
            "Specification": material.get("spec"),
            "Grade": material.get("grade"),
            "ClassCondTemper": material.get("cls"),
            "UNS": material.get("alloy"),
            "NominalComposition": material.get("comp"),
            "ProductForm": material.get("pform"),
            "SMYS": material.get("SMYS"),
            "SMTS": material.get("SMTS"),
            "Ar": material.get("Ar"),
            "MaximumAllowableTemperature": material.get("MaximumAllowableTemperature"),
        }
        for material in materials
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "ID",
            "Specification",
            "Grade",
            "ClassCondTemper",
            "UNS",
            "NominalComposition",
            "ProductForm",
            "SMYS",
            "SMTS",
            "Ar",
            "MaximumAllowableTemperature",
        ],
    )


@st.cache_data(ttl=3600)
def _load_detail(mid: int) -> dict:
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM Materials WHERE ID = ?", (mid,))
    row = cur.fetchone()
    cols = [d[0] for d in cur.description]
    conn.close()
    return dict(zip(cols, row)) if row else {}


@st.cache_data(ttl=3600)
def _load_strength(mid: int, table: str) -> list[dict]:
    conn = _conn()
    cur = conn.cursor()
    cur.execute(
        f"SELECT * FROM {table} WHERE MaterialID = ?"
        " ORDER BY COALESCE(SizeThkMIN, -1)",
        (mid,),
    )
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    conn.close()
    return [dict(zip(cols, r)) for r in rows]


@st.cache_data(ttl=3600)
def _load_physical(mid: int) -> dict:
    conn = _conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM MaterialGroupMap WHERE MaterialID = ?", (mid,))
    gmap_row = cur.fetchone()
    gmap = dict(zip([d[0] for d in cur.description], gmap_row)) if gmap_row else {}

    def _grp(table: str, gid_key: str):
        gid = gmap.get(gid_key)
        if not gid:
            return None
        cur.execute(f"SELECT * FROM {table} WHERE ID = ?", (int(gid),))
        r = cur.fetchone()
        return dict(zip([d[0] for d in cur.description], r)) if r else None

    result = {
        "E":      _grp("ElasticModulusTable",     "ElasticModulusGroupID"),
        "alpha":  _grp("ThermalExpansionTable",    "ThermalExpansionGroupID"),
        "lambda": _grp("ThermalConductivityTable", "ThermalConductivityGroupID"),
        "diff":   _grp("ThermalDiffusivityTable",  "ThermalDiffusivityGroupID"),
    }

    cur.execute("SELECT * FROM SpecificHeatTable WHERE MaterialID = ? LIMIT 1", (mid,))
    r = cur.fetchone()
    result["Cp"] = dict(zip([d[0] for d in cur.description], r)) if r else None

    conn.close()
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Chart factory
# ─────────────────────────────────────────────────────────────────────────────

def _base_fig(y_title: str, height: int = 350) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        xaxis_title="Temperature [°C]",
        yaxis_title=y_title,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=15, t=30, b=45),
        height=height,
        plot_bgcolor="rgba(248,250,253,1)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=True, gridcolor="#e0e6ef")
    fig.update_yaxes(showgrid=True, gridcolor="#e0e6ef")
    return fig


def _add_series(fig: go.Figure, row: dict, temps: list[int], to_celsius: bool,
                name: str, color: str, dash: str = "solid") -> None:
    xs, ys = _xy(row, temps, to_celsius)
    if xs:
        fig.add_trace(go.Scatter(
            x=xs, y=ys, name=name, mode="lines+markers",
            line=dict(color=color, width=2, dash=dash),
            marker=dict(size=5),
        ))


def _mini_fig(data: dict | None, temps: list[int], y_title: str,
              name: str, color: str, to_celsius: bool = False) -> go.Figure | None:
    if not data:
        return None
    xs, ys = _xy(data, temps, to_celsius)
    if not xs:
        return None
    fig = _base_fig(y_title, height=280)
    fig.add_trace(go.Scatter(
        x=xs, y=ys, name=name, mode="lines+markers",
        line=dict(color=color, width=2),
        marker=dict(size=5),
    ))
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Helpers for Tab 1 display
# ─────────────────────────────────────────────────────────────────────────────

def _v(d: dict, key: str, fmt: str | None = None) -> str:
    val = d.get(key)
    if val is None or val == "":
        return "—"
    try:
        return format(float(val), fmt) if fmt else str(val)
    except (TypeError, ValueError):
        return str(val)


# ─────────────────────────────────────────────────────────────────────────────
# Page
# ─────────────────────────────────────────────────────────────────────────────

st.title("📦 ASME Materials Database")

all_mats = _load_all()


def _reset_filters() -> None:
    for k in ("mat_search", "mat_pform"):
        st.session_state.pop(k, None)


# ── Pre-compute cascading options from current session values ─────────────────
_cur_search = st.session_state.get("mat_search", "")

# Pool after text search (feeds Product Form options)
try:
    _pool_pform = _search_materials(_cur_search) if _cur_search.strip() else all_mats.copy()
    _search_error = None
except ValueError as exc:
    _pool_pform = _materials_to_df([])
    _search_error = str(exc)

avail_pforms = ["All"] + sorted(_pool_pform["ProductForm"].dropna().unique().tolist())
if st.session_state.get("mat_pform", "All") not in avail_pforms:
    st.session_state["mat_pform"] = "All"

# ── Filters ───────────────────────────────────────────────────────────────────
fc1, fc3, fc4 = st.columns([3, 2, 1])

with fc1:
    search = st.text_input(
        "🔍 Search",
        key="mat_search",
        placeholder="e.g. SA-516, carbon, Grade 70…",
        help="Full-text search across Specification, Grade, Class/Condition/Temper and Nominal Composition.",
    )
with fc3:
    sel_pform = st.selectbox(
        "Product Form",
        avail_pforms,
        key="mat_pform",
        help="Product form (e.g. Plate, Pipe, Forging). List updates to match the current search.",
    )
with fc4:
    st.markdown("<div style='padding-top:1.72rem'>", unsafe_allow_html=True)
    st.button("↺ Reset", on_click=_reset_filters, use_container_width=True,
              help="Clear all filters and show all materials.")
    st.markdown("</div>", unsafe_allow_html=True)

# ── Apply filters to build the displayed dataframe ────────────────────────────
st.caption(
    'Search examples: spec:SA-516 AND grade:70, composition:"Carbon steel", '
    'SMYS>=260, SMTS=485~0.1, MaximumAllowableTemperature>=538'
)

df = _pool_pform.copy()
if _search_error:
    st.error(f"Invalid material search: {_search_error}")
if sel_pform != "All":
    df = df[df["ProductForm"] == sel_pform]
df = df.reset_index(drop=True)

st.caption(f"{len(df):,} / {len(all_mats):,} materials  — select a row to view details")

# ── Split: list (left) + detail panel (right) ─────────────────────────────────
col_list, col_detail = st.columns([5, 7], gap="medium")

with col_list:
    col_map = {
        "ID":                 "ID",
        "Specification":      "Specification",
        "Grade":              "Grade",
        "ClassCondTemper":    "Class/Cond/T",
        "UNS":                "UNS",
        "NominalComposition": "Composition",
        "ProductForm":        "Product Form",
        "SMYS":               "SMYS [MPa]",
        "SMTS":               "SMTS [MPa]",
        "Ar":                 "Ar [%]",
        "MaximumAllowableTemperature": "Max Allow Temp [C]",
    }
    df_disp = df[list(col_map.keys())].rename(columns=col_map)

    evt = st.dataframe(
        df_disp,
        use_container_width=True,
        height=640,
        on_select="rerun",
        selection_mode="single-row",
        key="mat_grid",
        column_config={
            "ID":          st.column_config.NumberColumn("ID",         width="small",  format="%d"),
            "SMYS [MPa]":  st.column_config.NumberColumn("SMYS [MPa]", format="%.1f"),
            "SMTS [MPa]":  st.column_config.NumberColumn("SMTS [MPa]", format="%.1f"),
            "Ar [%]":      st.column_config.NumberColumn("Ar [%]",     format="%.1f"),
            "Max Allow Temp [C]": st.column_config.NumberColumn(
                "Max Allow Temp [C]",
                format="%.0f",
            ),
        },
    )
    sel_rows = evt.selection.rows

with col_detail:
    if not sel_rows:
        st.info("👈  Select a row from the list to view material details.")
    else:
        selected_summary = df.iloc[sel_rows[0]]
        mat_id = int(selected_summary["ID"])
        md = _load_detail(mat_id)

        title_parts = [
            md.get("Specification") or "",
            md.get("TypeGrade") or "",
            md.get("ClassConditionTemper") or "",
        ]
        st.subheader(" · ".join(p for p in title_parts if p), divider="blue")

        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📋 Material Data",
            "📈 Sy & Su vs T",
            "📊 Allowable Stress",
            "🔬 Physical Properties",
            "🧮 Calculated Values",
        ])

        # ── Tab 1 — Material Data ─────────────────────────────────────────────
        with tab1:
            t1l, t1r = st.columns(2)

            with t1l:
                st.markdown("**Identification**")
                st.table(
                    pd.DataFrame(
                        {
                            "Specification":     [_v(md, "Specification")],
                            "Type / Grade":      [_v(md, "TypeGrade")],
                            "Class/Cond/Temper": [_v(md, "ClassConditionTemper")],
                            "Alloy Desig. No":   [_v(md, "AlloyDesignationNumber")],
                            "Nominal Comp.":     [_v(md, "NominalComposition")],
                            "Product Form":      [_v(md, "ProductForm")],
                            "Flange Group":      [_v(md, "FlangeGroup")],
                            "MDMT Curve 1":      [_v(md, "MDMTCurve1")],
                            "MDMT Curve 2":      [_v(md, "MDMTCurve2")],
                        }
                    ).T.rename(columns={0: "Value"})
                )

            with t1r:
                st.markdown("**Mechanical & Physical Properties**")
                st.table(
                    pd.DataFrame(
                        {
                            "SMYS [MPa]":        [_v(md, "SMYS",                    ".1f")],
                            "SMTS [MPa]":        [_v(md, "SMTS",                    ".1f")],
                            "Elong. Long [%]":   [_v(md, "RuptureElongationLong",   ".1f")],
                            "Elong. Transv [%]": [_v(md, "RuptureElongationTransv", ".1f")],
                            "Density [kg/m³]":   [_v(md, "Density",                 ".0f")],
                            "Poisson Factor":    [_v(md, "PoissonFactor",            ".3f")],
                            "Max Allow Temp [°C]": [
                                f"{selected_summary['MaximumAllowableTemperature']:.0f}"
                                if pd.notna(selected_summary.get("MaximumAllowableTemperature"))
                                else "—"
                            ],
                        }
                    ).T.rename(columns={0: "Value"})
                )

            if md.get("Notes"):
                st.markdown("**Notes**")
                st.info(md["Notes"])

        # ── Tab 2 — Sy & Su vs T ─────────────────────────────────────────────
        with tab2:
            sy_rows = _load_strength(mat_id, "YieldStrengthTable")
            su_rows = _load_strength(mat_id, "UltimateStrengthTable")

            if not sy_rows and not su_rows:
                st.warning("No yield / ultimate strength data for this material.")
            else:
                ref_rows = sy_rows if sy_rows else su_rows
                thk_labels = [_thk_label(r) for r in ref_rows]

                if len(thk_labels) > 1:
                    sel = st.selectbox("Thickness / Size Range", thk_labels, key="t2_thk")
                    idx = thk_labels.index(sel)
                else:
                    idx = 0
                    st.caption(f"Thickness range: **{thk_labels[0]}**")

                fig = _base_fig("Stress [MPa]", height=400)
                if idx < len(sy_rows):
                    _add_series(fig, sy_rows[idx], _TF, True, "Sy — Rp0.2", "#1f6aa5")
                if idx < len(su_rows):
                    _add_series(fig, su_rows[idx], _TF, True, "Su — Rm", "#d62728", dash="dash")
                st.plotly_chart(fig, use_container_width=True)

        # ── Tab 3 — Allowable Stress ──────────────────────────────────────────
        with tab3:
            s1 = _load_strength(mat_id, "AllowableStress1Table")
            s2 = _load_strength(mat_id, "AllowableStress2Table")
            s3 = _load_strength(mat_id, "AllowableStress3Table")

            if not s1 and not s2 and not s3:
                st.warning("No allowable stress data found for this material.")
            else:
                def _thk_pick(rows: list, label: str, key: str) -> int:
                    if not rows:
                        return 0
                    lbls = [_thk_label(r) for r in rows]
                    if len(lbls) == 1:
                        st.caption(f"{label}: **{lbls[0]}**")
                        return 0
                    sel = st.selectbox(label, lbls, key=key)
                    return lbls.index(sel)

                t3c1, t3c2, t3c3 = st.columns(3)
                with t3c1:
                    i1 = _thk_pick(s1, "Div 1 — Thk Range", "s1_thk")
                with t3c2:
                    i2 = _thk_pick(s2, "Div 2 — Thk Range", "s2_thk")
                with t3c3:
                    i3 = _thk_pick(s3, "Bolting — Size Range", "s3_thk")

                fig = _base_fig("Allowable Stress  S  [MPa]", height=400)
                if s1 and i1 < len(s1):
                    _add_series(fig, s1[i1], _TF, True, "S1 — Div 1",  "#2ca02c")
                if s2 and i2 < len(s2):
                    _add_series(fig, s2[i2], _TF, True, "S2 — Div 2",  "#ff7f0e")
                if s3 and i3 < len(s3):
                    _add_series(fig, s3[i3], _TF, True, "S3 — Bolting", "#9467bd")
                st.plotly_chart(fig, use_container_width=True)

                def _max_t(rows, idx, field):
                    if rows and idx < len(rows):
                        v = rows[idx].get(field)
                        if v is not None:
                            return f"{_f2c(float(v)):.0f} °C"
                    return "—"

                mc1, mc2, mc3 = st.columns(3)
                with mc1:
                    st.caption(f"Max T (Div 1): {_max_t(s1, i1, 'MaxTemp_VIII1')}")
                with mc2:
                    st.caption(f"Max T (Div 2): {_max_t(s2, i2, 'MaximumTemperature')}")
                with mc3:
                    st.caption(f"Max T (Bolting): {_max_t(s3, i3, 'MaxTemp_VIII1')}")

        # ── Tab 4 — Physical Properties ───────────────────────────────────────
        with tab4:
            props = _load_physical(mat_id)

            has_data = any(props.get(k) is not None for k in props)
            if not has_data:
                st.warning("No physical property data found for this material.")
            else:
                ph1, ph2 = st.columns(2)

                with ph1:
                    fig_e = _mini_fig(
                        props.get("E"), _TC_E,
                        "E  [MPa]", "Elastic Modulus E", "#1f6aa5",
                    )
                    if fig_e:
                        st.plotly_chart(fig_e, use_container_width=True)
                    else:
                        st.caption("E — no data")

                with ph2:
                    fig_a = _mini_fig(
                        props.get("alpha"), _TC_PHYS,
                        "α  [µm/(m·°C)]", "Thermal Expansion α", "#ff7f0e",
                    )
                    if fig_a:
                        st.plotly_chart(fig_a, use_container_width=True)
                    else:
                        st.caption("α — no data")

                ph3, ph4 = st.columns(2)

                with ph3:
                    fig_l = _mini_fig(
                        props.get("lambda"), _TC_PHYS,
                        "λ  [W/(m·°C)]", "Thermal Conductivity λ", "#2ca02c",
                    )
                    if fig_l:
                        st.plotly_chart(fig_l, use_container_width=True)
                    else:
                        st.caption("λ — no data")

                with ph4:
                    fig_d = _mini_fig(
                        props.get("diff"), _TC_PHYS,
                        "a  [mm²/s]", "Thermal Diffusivity a", "#9467bd",
                    )
                    if fig_d:
                        st.plotly_chart(fig_d, use_container_width=True)
                    else:
                        st.caption("a — no data")

                fig_cp = _mini_fig(
                    props.get("Cp"), _TC_PHYS,
                    "Cp  [J/(kg·°C)]", "Specific Heat Cp", "#d62728",
                )
                if fig_cp:
                    fig_cp.update_layout(height=260)
                    st.plotly_chart(fig_cp, use_container_width=True)
                else:
                    st.caption("Cp — no data")

        # ── Tab 5 — Calculated Values ─────────────────────────────────────────
        with tab5:
            cv1, cv2 = st.columns(2)
            with cv1:
                calc_T = st.number_input(
                    "Temperature [°C]",
                    min_value=-200.0,
                    max_value=900.0,
                    value=200.0,
                    step=5.0,
                    format="%.1f",
                    key=f"calc_T_{mat_id}",
                )
            with cv2:
                calc_size = st.number_input(
                    "Size / thickness [mm]",
                    min_value=0.0,
                    value=20.0,
                    step=0.5,
                    format="%.2f",
                    key=f"calc_size_{mat_id}",
                    help="Used to select thickness-dependent strength and allowable-stress rows.",
                )

            sy_val = get_yield_at_T(mat_id, calc_T, thk_mm=calc_size)
            su_val = get_ultimate_at_T(mat_id, calc_T, thk_mm=calc_size)
            s1_val = get_S_div1(mat_id, calc_T, thk_mm=calc_size)
            s2_val = get_S_div2(mat_id, calc_T, thk_mm=calc_size)

            props = _load_physical(mat_id)
            e_val = _interp_row(props.get("E"), _TC_E, calc_T)
            alpha_val = _interp_row(props.get("alpha"), _TC_PHYS, calc_T)
            lambda_val = _interp_row(props.get("lambda"), _TC_PHYS, calc_T)
            diff_val = _interp_row(props.get("diff"), _TC_PHYS, calc_T)
            cp_val = _interp_row(props.get("Cp"), _TC_PHYS, calc_T)

            s3_row = _pick_size_row(_load_strength(mat_id, "AllowableStress3Table"), calc_size)
            s3_val = _interp_row(s3_row, _TF, calc_T, to_celsius=True)

            Rp_T = sy_val if sy_val is not None else md.get("SMYS")
            Rm_20 = md.get("SMTS")
            Ar = md.get("RuptureElongationLong")
            allow_en = allow_ad = allow_bs = allow_cp = None
            if Rp_T is not None and Rm_20 is not None:
                allow_en = allowable_EN13445(Rp_T, Rm_20, Ar)
                allow_ad = allowable_AD2000(Rp_T, Rm_20)
                allow_bs = allowable_BS5500(Rp_T, Rm_20)
                allow_cp = allowable_CODAP(Rp_T, Rm_20, Ar)

            def _fmt_num(value: float | None, fmt: str = ".2f") -> str:
                return format(value, fmt) if value is not None else "—"

            max_allow_temp = selected_summary.get("MaximumAllowableTemperature")
            max_allow_temp = float(max_allow_temp) if pd.notna(max_allow_temp) else None

            calc_rows = [
                ("SMYS", "Room-temperature yield strength", _fmt_num(md.get("SMYS")), "MPa"),
                ("SMTS", "Room-temperature tensile strength", _fmt_num(md.get("SMTS")), "MPa"),
                ("Sy / Rp0.2_T", "Yield strength at temperature", _fmt_num(sy_val), "MPa"),
                ("Su / Rm_T", "Ultimate strength at temperature", _fmt_num(su_val), "MPa"),
                ("S1", "ASME VIII-1 allowable stress", _fmt_num(s1_val), "MPa"),
                ("S2", "ASME VIII-2 allowable stress", _fmt_num(s2_val), "MPa"),
                ("S3", "ASME bolting allowable stress", _fmt_num(s3_val), "MPa"),
                ("EN 13445 f", "Design stress", _fmt_num(allow_en["f"] if allow_en else None), "MPa"),
                ("AD 2000", "Allowable stress", _fmt_num(allow_ad["f"] if allow_ad else None), "MPa"),
                ("BS PD 5500 f", "Design stress", _fmt_num(allow_bs["f"] if allow_bs else None), "MPa"),
                ("CODAP f", "Design stress", _fmt_num(allow_cp["f"] if allow_cp else None), "MPa"),
                ("Elastic modulus E", "Interpolated physical property", _fmt_num(e_val), "MPa"),
                ("Thermal expansion α", "Interpolated physical property", _fmt_num(alpha_val), "µm/(m·°C)"),
                ("Thermal conductivity λ", "Interpolated physical property", _fmt_num(lambda_val), "W/(m·°C)"),
                ("Thermal diffusivity a", "Interpolated physical property", _fmt_num(diff_val), "mm²/s"),
                ("Specific heat Cp", "Interpolated physical property", _fmt_num(cp_val), "J/(kg·°C)"),
                ("Density", "Room-temperature database value", _fmt_num(md.get("Density"), ".0f"), "kg/m³"),
                ("Max allowable temperature", "Maximum listed allowable-stress temperature", _fmt_num(max_allow_temp, ".0f"), "°C"),
            ]

            st.dataframe(
                pd.DataFrame(calc_rows, columns=["Property", "Basis", "Value", "Unit"]),
                hide_index=True,
                use_container_width=True,
            )

            if max_allow_temp is not None and calc_T > max_allow_temp:
                st.warning("The entered temperature is above the maximum listed allowable-stress temperature for this material.")
