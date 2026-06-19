from calc.db.standards_xml import load_facings
from calc.db.xml_table_browser import render_xml_table_browser


df = load_facings()

render_xml_table_browser(
    title="Facings",
    caption="ASME B16.5 and ASME B16.47 facing data loaded from Facings.xml, including rows derived from Flanges.xml.",
    df=df,
    key="facings_xml",
    filter_columns=["Standard family", "Table", "Facing type", "Series", "Class", "NPS", "DN"],
    primary_columns=[
        "Standard family",
        "Table",
        "Facing type",
        "Series",
        "NPS",
        "DN",
        "Class",
        "OD",
        "ID",
        "height",
        "depth",
        "RingNumber",
        "P",
        "K",
        "gasketOD",
        "gasketID",
    ],
)
