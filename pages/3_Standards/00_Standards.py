import streamlit as st


st.title("Standards")
st.caption("Piping, tubing and engineering standards reference.")
st.divider()

cards = [
    {
        "title": "Pipe Dimensions",
        "body": "Full ASME B36.10M schedule database. Browse by NPS and schedule, with geometry and checks.",
        "meta": "Standard: ASME B36.10M",
        "page": "pages/3_Standards/01_Standards_Pipes.py",
        "label": "Open Pipe Dimensions",
        "icon": "🔧",
    },
    {
        "title": "Tube Dimensions",
        "body": "TEMA / ASME HEI heat-exchanger and condenser tubes by OD and BWG gauge.",
        "meta": "Gauge system: BWG 0-25",
        "page": "pages/3_Standards/02_Standards_Tubes.py",
        "label": "Open Tube Dimensions",
        "icon": "⭕",
    },
    {
        "title": "Flanges",
        "body": "Browse flange dimensions from Flanges.xml with search, filters, reset and CSV export.",
        "meta": "Standards: ASME B16.5 / B16.47",
        "page": "pages/3_Standards/03_Standards_Flanges.py",
        "label": "Open Flanges",
        "icon": "🔩",
    },
    {
        "title": "Gaskets",
        "body": "Browse ring-joint and spiral-wound gasket data from Gaskets.xml.",
        "meta": "Standards: ASME B16.5 / B16.47",
        "page": "pages/3_Standards/04_Standards_Gaskets.py",
        "label": "Open Gaskets",
        "icon": "🧩",
    },
    {
        "title": "Facings",
        "body": "Browse raised-face, male/female, tongue/groove and RTJ facing data.",
        "meta": "Source: Facings.xml, derived from Flanges.xml where noted",
        "page": "pages/3_Standards/05_Standards_Facings.py",
        "label": "Open Facings",
        "icon": "📐",
    },
    {
        "title": "ASME B16 Ratings",
        "body": "Browse pressure-temperature ratings by standard, class, material group and temperature.",
        "meta": "Standards: ASME B16.5 / B16.47",
        "page": "pages/3_Standards/06_Standards_ASME_B16_Ratings.py",
        "label": "Open Ratings",
        "icon": "📊",
    },
]

for row_start in range(0, len(cards), 3):
    cols = st.columns(3)
    for col, card in zip(cols, cards[row_start : row_start + 3]):
        with col:
            with st.container(border=True):
                st.markdown(f"### {card['icon']} {card['title']}")
                st.markdown(card["body"])
                st.markdown(f"**{card['meta']}**")
                st.page_link(card["page"], label=f"{card['label']} ->", icon=card["icon"])
