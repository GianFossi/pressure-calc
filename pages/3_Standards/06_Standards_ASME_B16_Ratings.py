from calc.db.standards_xml import load_asme_b16_ratings
from calc.db.xml_table_browser import render_xml_table_browser


df = load_asme_b16_ratings()

render_xml_table_browser(
    title="ASME B16 Ratings",
    caption="Pressure-temperature ratings for ASME B16.5 and ASME B16.47 loaded from ASME_B16_Ratings.xml.",
    df=df,
    key="asme_b16_ratings_xml",
    filter_columns=["Standard family", "Edition", "Class", "Material group", "Material", "Temperature (C)"],
    primary_columns=[
        "Standard family",
        "Edition",
        "Class",
        "Material group",
        "Material",
        "Temperature (C)",
        "Pressure (bar)",
        "Examples",
        "NPS range",
    ],
)
