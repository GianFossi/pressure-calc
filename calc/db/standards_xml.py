from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[2]
DB_DIR = ROOT_DIR / "database"


def _root(filename: str) -> ET.Element:
    return ET.parse(DB_DIR / filename).getroot()


def _clean(value: str | None) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return str(value).strip()


def _nps_float(value: str | None) -> float:
    text = _clean(value).replace('"', "")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        pass
    if "-" in text:
        whole, frac = text.split("-", 1)
        try:
            num, den = frac.split("/", 1)
            return float(whole) + float(num) / float(den)
        except ValueError:
            return 0.0
    if "/" in text:
        try:
            num, den = text.split("/", 1)
            return float(num) / float(den)
        except ValueError:
            return 0.0
    return 0.0


def _standard_family(value: str | None, nps: str | None = None) -> str:
    text = _clean(value)
    if "16.47" in text:
        return "ASME B16.47"
    if "16.5" in text:
        return "ASME B16.5"
    return "ASME B16.47" if _nps_float(nps) >= 26 else "ASME B16.5"


def _with_attrs(row: dict[str, str], element: ET.Element, prefix: str = "") -> None:
    for key, value in element.attrib.items():
        row[f"{prefix}{key}"] = _clean(value)


def _rows_to_df(rows: list[dict[str, str]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    preferred = [
        "Standard",
        "Standard family",
        "Edition",
        "Type",
        "Table",
        "Facing type",
        "Series",
        "NPS",
        "DN",
        "Rating",
        "Class",
        "Material group",
        "Material",
        "Temperature (C)",
        "Pressure (bar)",
    ]
    cols = [col for col in preferred if col in df.columns]
    cols.extend([col for col in df.columns if col not in cols and not col.startswith("_")])
    hidden = [col for col in df.columns if col.startswith("_")]
    return df[cols + hidden]


def load_flanges() -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for flange in _root("Flanges.xml").findall("Flange"):
        row: dict[str, str] = {}
        _with_attrs(row, flange)
        facing_count = 0
        for child in flange:
            tag = child.tag
            value = _clean(child.text)
            if tag == "FacingDiamRF":
                facing_count += 1
                tag = "FacingDiamRF" if facing_count == 1 else "FacingHeightRF"
            elif tag in row:
                tag = f"{tag}_{sum(1 for key in row if key.startswith(tag)) + 1}"
            row[tag] = value
        row["Standard family"] = _standard_family(row.get("Standard"), row.get("NPS"))
        rows.append(row)
    df = _rows_to_df(rows)
    if not df.empty:
        df["_sort_nps"] = df["NPS"].map(_nps_float)
        df["_sort_rating"] = pd.to_numeric(df["Rating"], errors="coerce").fillna(0)
        df = df.sort_values(["Standard family", "_sort_nps", "_sort_rating", "Type"])
    return df


def load_gaskets() -> pd.DataFrame:
    root = _root("Gaskets.xml")
    rows: list[dict[str, str]] = []

    for ring in root.findall(".//RingJointGaskets/Rings/Ring"):
        row = {"Table": "Ring joint ring dimensions", "Gasket type": "Ring joint"}
        _with_attrs(row, ring)
        rows.append(row)

    for parent in root.findall(".//RingJointGaskets/Assignments"):
        for assignment in list(parent):
            row = {
                "Table": "Ring joint assignments",
                "Gasket type": "Ring joint",
                "Series": assignment.tag,
                "NPS": _clean(assignment.attrib.get("nps")),
                "Class": _clean(assignment.attrib.get("cls")),
                "Ring number": _clean(assignment.text),
            }
            row["Standard family"] = _standard_family("ASME B16.5", row["NPS"])
            rows.append(row)

    for table in root.findall(".//SpiralWoundGaskets"):
        standard = _clean(table.attrib.get("standard"))
        source = _clean(table.attrib.get("source"))
        containers = list(table.findall("Series")) or [table]
        for container in containers:
            series = _clean(container.attrib.get("id"))
            for size in container.findall("Size"):
                for rating in size.findall("Rating"):
                    row = {
                        "Table": source or "Spiral wound gaskets",
                        "Gasket type": "Spiral wound",
                        "Standard family": _standard_family(standard, size.attrib.get("NPS")),
                        "Series": series,
                        "NPS": _clean(size.attrib.get("NPS")),
                        "DN": _clean(size.attrib.get("DN")),
                        "Class": _clean(rating.attrib.get("class")),
                    }
                    _with_attrs(row, size, "Size ")
                    _with_attrs(row, rating)
                    rows.append(row)
    df = _rows_to_df(rows)
    if not df.empty and "NPS" in df:
        df["_sort_nps"] = df["NPS"].map(_nps_float)
        df["_sort_class"] = pd.to_numeric(df.get("Class", ""), errors="coerce").fillna(0)
        df = df.sort_values(["Table", "Standard family", "Series", "_sort_nps", "_sort_class"])
    return df


def load_facings() -> pd.DataFrame:
    root = _root("Facings.xml")
    rows: list[dict[str, str]] = []

    for group in root.findall(".//RaisedFaceDimensions/*"):
        if not group.tag.endswith("Facings"):
            continue
        facing_type = group.tag.replace("Facings", "").replace("Face", " Face")
        for facing in group.findall("Facing"):
            for rating in facing.findall("Rating"):
                row = {
                    "Table": "Facing dimensions",
                    "Facing type": facing_type,
                    "Standard family": _standard_family(
                        facing.attrib.get("standard"), facing.attrib.get("NPS")
                    ),
                    "Series": _clean(facing.attrib.get("series")),
                    "NPS": _clean(facing.attrib.get("NPS")),
                    "DN": _clean(facing.attrib.get("DN")),
                    "Class": _clean(rating.attrib.get("id")),
                }
                _with_attrs(row, facing, "Facing ")
                _with_attrs(row, rating)
                rows.append(row)

    for facing in root.findall(".//RingJointFacings/RingJointFacing"):
        for rating in facing.findall("Rating"):
            row = {
                "Table": "Ring joint facing dimensions",
                "Facing type": "Ring Joint",
                "Standard family": _standard_family(
                    facing.attrib.get("standard"), facing.attrib.get("NPS")
                ),
                "Series": _clean(facing.attrib.get("series")),
                "NPS": _clean(facing.attrib.get("NPS")),
                "DN": _clean(facing.attrib.get("DN")),
                "Class": _clean(rating.attrib.get("id")),
            }
            _with_attrs(row, facing, "Facing ")
            _with_attrs(row, rating)
            rows.append(row)

    for gasket in root.findall(".//RaisedFaceGaskets/Gasket"):
        row = {
            "Table": "Raised face gasket envelope",
            "Facing type": "Raised Face Gasket",
            "Standard family": _standard_family(None, gasket.attrib.get("NPS")),
        }
        _with_attrs(row, gasket)
        rows.append(row)

    df = _rows_to_df(rows)
    if not df.empty and "NPS" in df:
        df["_sort_nps"] = df["NPS"].map(_nps_float)
        df["_sort_class"] = pd.to_numeric(df.get("Class", ""), errors="coerce").fillna(0)
        df = df.sort_values(["Facing type", "Standard family", "Series", "_sort_nps", "_sort_class"])
    return df


def load_asme_b16_ratings() -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    root = _root("ASME_B16_Ratings.xml")
    for standard in root.findall("Standard"):
        for material in standard.findall("MaterialGroup"):
            for cls in material.findall("Class"):
                for pressure in cls.findall(".//P"):
                    rows.append({
                        "Standard": _clean(standard.attrib.get("id")).replace("_", " "),
                        "Standard family": _clean(standard.attrib.get("id")).replace("_", " "),
                        "Edition": _clean(standard.attrib.get("edition")),
                        "Class": _clean(cls.attrib.get("id")),
                        "Material group": _clean(material.attrib.get("id")),
                        "Material": _clean(material.attrib.get("description")),
                        "Examples": _clean(material.attrib.get("examples")),
                        "Temperature (C)": _clean(pressure.attrib.get("temp")),
                        "Pressure (bar)": _clean(pressure.attrib.get("bar")),
                        "NPS range": _clean(standard.attrib.get("NPS_range")),
                    })
    df = _rows_to_df(rows)
    if not df.empty:
        df["_sort_class"] = pd.to_numeric(df["Class"], errors="coerce").fillna(0)
        df["_sort_temp"] = pd.to_numeric(df["Temperature (C)"], errors="coerce").fillna(0)
        df = df.sort_values(["Standard", "Material group", "_sort_class", "_sort_temp"])
    return df


def export_csv(df: pd.DataFrame) -> bytes:
    visible = df[[col for col in df.columns if not col.startswith("_")]]
    return visible.to_csv(index=False).encode("utf-8")
