import streamlit as st

st.set_page_config(
    page_title="Pressure Vessel Calculator",
    page_icon="🔩",
    layout="wide",
)

pg = st.navigation({
    "": [
        st.Page("pages/Home.py", title="Home", icon="🏠"),
    ],
    "Codici di calcolo": [
        st.Page("pages/01_Virola_Cilindrica.py", title="Virola Cilindrica", icon="🔵"),
    ],
    "Standards": [
        st.Page("pages/Standards.py",       title="Standards",             icon="📋"),
        st.Page("pages/Standards_Pipes.py", title="Pipe Dimensions (B36.10)", icon="🔧"),
    ],
})

pg.run()
