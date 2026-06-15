import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

st.set_page_config(page_title="Standards", layout="wide")

st.title("Standards")
st.caption("Piping dimensions and engineering standards reference.")

st.divider()

# ── Sub-page navigation ───────────────────────────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        st.markdown("### Pipe Dimensions")
        st.markdown(
            "Full ASME B36.10M-2015 schedule database — browse by NPS and schedule, "
            "view geometry, section properties and flow calculations."
        )
        st.markdown("**Standard:** ASME B36.10M  |  **Sizes:** NPS 1/8\" – 48\"")
        st.page_link("pages/Standards_Pipes.py", label="Open Pipe Dimensions", icon="🔧")

with col2:
    with st.container(border=True):
        st.markdown("### Flanges & Fittings")
        st.markdown("ASME B16.5 / B16.47 flange dimensions and ratings. *(coming soon)*")
        st.markdown("**Standard:** ASME B16.5 / B16.47")
        st.button("Coming soon", disabled=True, key="flanges")
