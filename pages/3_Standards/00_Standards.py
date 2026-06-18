import streamlit as st

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
        st.page_link("pages/3_Standards/01_Standards_Pipes.py", label="Open Pipe Dimensions →", icon="🔧")

with col2:
    with st.container(border=True):
        st.markdown("### ⭕ Tube Dimensions")
        st.markdown(
            "**TEMA / ASME HEI** heat-exchanger and condenser tubes — "
            "browse by standard OD ¼\"…2\" × BWG gauge and view geometry,"
            "flow velocity, ρv² and full Darcy-Weisbach pressure drop."
        )
        st.markdown("**Gauge system:** BWG 0–25  |  **OD range:** ¼\" – 2\"")
        st.page_link("pages/3_Standards/02_Standards_Tubes.py", label="Open Tube Dimensions →", icon="⭕")

with col3:
    with st.container(border=True):
        st.markdown("### 🔩 Flanges & Fittings")
        st.markdown(
            "ASME B16.5 / B16.47 flange dimensions and pressure-temperature ratings. "
            "*(coming soon)*"
        )
        st.markdown("**Standard:** ASME B16.5 / B16.47")
        st.button("Coming soon", disabled=True, key="flanges")
