from calc.db.standards_xml import load_flanges
from calc.db.xml_table_browser import render_xml_table_browser


df = load_flanges()

render_xml_table_browser(
    title="Flanges",
    caption="ASME B16.5 and ASME B16.47 flange dimensions loaded from Flanges.xml.",
    df=df,
    key="flanges_xml",
    filter_columns=["Standard family", "Standard", "Type", "Rating", "NPS", "DN"],
    primary_columns=[
        "Standard family",
        "Standard",
        "Type",
        "NPS",
        "DN",
        "Rating",
        "RingOD",
        "RingWT",
        "BoltNum",
        "BoltCircDiam",
        "BoltHoleDiam2",
        "BoltNomSize2",
        "FacingDiamRF",
        "FacingHeightRF",
    ],
)
