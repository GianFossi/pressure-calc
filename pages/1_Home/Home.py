import streamlit as st

st.title("🔩 Pressure Vessel Calculator")
st.markdown(
    "Calculation tool for **pressure components** with multi-code comparison.  \n"    
)
st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Design Codes")
    st.markdown("""
| Code | Status |
|---|---|
| ASME VIII Div. 1 (UG-27) | ✅ Active |
| ASME VIII Div. 2 (§4.3.3) | ✅ Active |
| EN 13445-3 (§7.4.2) | ✅ Active |
| AD 2000 (B0 §6) | ✅ Active |
| BS PD 5500 (§3.5.1.2) | ✅ Active |
| CODAP 2023 (§C2.3) | ✅ Active |
""")

with col2:
    st.subheader("Implemented Components")
    st.markdown("""
| Component | Load | Status |
|---|---|---|
| Cylindrical shell | Internal pressure | ✅ Active — all 6 codes |
| Cylindrical shell | External pressure | 🔜 Phase 2 |
| Cylindrical shell | Wind / seismic loads | 🔜 Phase 2 |
| Conical transition | Internal / external P | 🔜 Phase 3 |
| Heads (ellipsoidal, torispherical, hemispherical) | Internal P | 🔜 Phase 3 |
| Nozzles & reinforcements | Internal P | 🔜 Phase 4 |
| Flanges (bolted heads) | Internal P | 🔜 Phase 5 |
| Tubesheets | Internal P | 🔜 Phase 5 |
| Supports (saddles, legs, skirt) | Static loads | 🔜 Phase 6 |
""")

st.divider()

with st.container(border=True):
    st.subheader("Material Database")
    st.markdown("""
The calculator draws on the embedded **ASME II Part D** material database:

| Table                    | Content                                             |
|---                       |---                                                  |
| Materials                | SMYS, SMTS, Ar, density — all ASME listed materials |
| Table 1A/5A, 1B/5B and 3 | Allowable stresses — ASME VIII-1 and VIII-2         |
| Table Y                  | Yield strength vs. temperature                      |
| Table U                  | Ultimate strength vs. temperature                   |
| Physical/Thermal Tables  | Physical and thermal properties                     |                

European allowable stresses (EN 13445, AD 2000, BS PD 5500, CODAP) are computed
automatically from Rp0.2\_T and Rm\_20°C using code-specific safety factors.
""")

st.divider()
