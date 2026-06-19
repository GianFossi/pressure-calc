from calc.db.standards_xml import load_gaskets
from calc.db.xml_table_browser import render_xml_table_browser


df = load_gaskets()

render_xml_table_browser(
    title="Gaskets",
    caption="ASME B16.5 and ASME B16.47 gasket data loaded from Gaskets.xml.",
    df=df,
    key="gaskets_xml",
    filter_columns=["Standard family", "Table", "Gasket type", "Series", "Class", "NPS", "DN"],
    primary_columns=[
        "Standard family",
        "Table",
        "Gasket type",
        "Series",
        "NPS",
        "DN",
        "Class",
        "RingID",
        "GasketID",
        "GasketOD",
        "RingOD",
        "Ring number",
    ],
)
