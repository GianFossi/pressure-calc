import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

st.title("Standards")
st.caption("Piping, tubing and engineering standards reference.")
st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.markdown("### 🔧 Pipe Dimensions")
        st.markdown(
            "Full **ASME B36.10M** schedule database — browse by NPS and schedule, "
            "view geometry, section properties, flow velocity and stress check."
        )
        st.markdown("**Standard:** ASME B36.10M  |  **Sizes:** NPS ⅛\" – 48\"")
        st.page_link("pages/Standards_Pipes.py", label="Open Pipe Dimensions →", icon="🔧")

with col2:
    with st.container(border=True):
        st.markdown("### ⭕ Tube Dimensions")
        st.markdown(
            "**TEMA / ASME HEI** heat-exchanger and condenser tubes — "
            "standard OD ¼\"…2\" × BWG gauge, with velocity, ρv² and "
            "full Darcy-Weisbach pressure drop."
        )
        st.markdown("**Gauge system:** BWG 0–25  |  **OD range:** ¼\" – 2\"")
        st.page_link("pages/Standards_Tubes.py", label="Open Tube Dimensions →", icon="⭕")

with col3:
    with st.container(border=True):
        st.markdown("### 🔩 Flanges & Fittings")
        st.markdown(
            "ASME B16.5 / B16.47 flange dimensions and pressure-temperature ratings. "
            "*(coming soon)*"
        )
        st.markdown("**Standard:** ASME B16.5 / B16.47")
        st.button("Coming soon", disabled=True, key="flanges")
