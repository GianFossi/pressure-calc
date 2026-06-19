"""
ASME materials database access.

Temperature columns in the DB are in °F; stress values are in MPa.
Design temperature input is always in °C and converted internally.
"""

import sqlite3
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DB_PATH = Path(__file__).resolve().parent.parent.parent / "database" / "asme_materials.db"

# Temperature breakpoints available in stress/property tables [°F]
TEMP_F = [
    40, 65, 100, 125, 150, 175, 200, 225, 250, 275, 300, 325, 350,
    375, 400, 425, 450, 475, 500, 525, 550, 575, 600, 625, 650, 675,
    700, 725, 750, 775, 800, 825, 850, 875, 900,
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(DB_PATH))
    c.text_factory = lambda b: b.decode("utf-8", errors="replace")
    return c


def _col_idx(col_names: list[str], col: str) -> int:
    try:
        return col_names.index(col)
    except ValueError:
        return -1


def _extract_temps(row: tuple, col_names: list[str]) -> dict[float, float]:
    """Build {temp_F: value_MPa} from a DB row, skipping None entries."""
    d: dict[float, float] = {}
    for t in TEMP_F:
        col = f"T_{t}"
        idx = _col_idx(col_names, col)
        if idx >= 0 and row[idx] is not None:
            d[float(t)] = float(row[idx])
    return d


def _interp(data: dict[float, float], T_F: float) -> float | None:
    """
    Linear interpolation at T_F [°F].
    Below the lowest available temperature: returns the lowest value.
    Above the highest: returns None (outside design range — don't extrapolate).
    """
    if not data:
        return None
    ts = sorted(data)
    if T_F <= ts[0]:
        return data[ts[0]]
    if T_F > ts[-1]:
        return None
    for i in range(len(ts) - 1):
        t1, t2 = ts[i], ts[i + 1]
        if t1 <= T_F <= t2:
            v1, v2 = data[t1], data[t2]
            return v1 + (v2 - v1) * (T_F - t1) / (t2 - t1)
    return None


def _material_row_to_dict(row: sqlite3.Row | tuple) -> dict:
    """Normalize a Materials row into the compact public material dict."""
    if isinstance(row, sqlite3.Row):
        data = dict(row)
    else:
        (
            mid, spec, grade, cls, alloy, comp, pform,
            smts, smys, ar_l, ar_t, density,
        ) = row
        data = {
            "ID": mid,
            "Specification": spec,
            "TypeGrade": grade,
            "ClassConditionTemper": cls,
            "AlloyDesignationNumber": alloy,
            "NominalComposition": comp,
            "ProductForm": pform,
            "SMTS": smts,
            "SMYS": smys,
            "RuptureElongationLong": ar_l,
            "RuptureElongationTransv": ar_t,
            "Density": density,
            "MaximumAllowableTemperature": None,
        }

    grade = data.get("TypeGrade")
    alloy = data.get("AlloyDesignationNumber")
    id_part = grade if grade else alloy
    parts = [
        str(p)
        for p in [
            data.get("Specification"),
            id_part,
            data.get("ClassConditionTemper"),
        ]
        if p
    ]
    return {
        "id": data.get("ID"),
        "name": " ".join(parts),
        "spec": data.get("Specification") or "",
        "grade": grade or "",
        "cls": data.get("ClassConditionTemper") or "",
        "alloy": alloy or "",
        "comp": data.get("NominalComposition") or "",
        "pform": data.get("ProductForm") or "",
        "SMTS": data.get("SMTS"),
        "SMYS": data.get("SMYS"),
        "Ar": data.get("RuptureElongationLong"),
        "Ar_t": data.get("RuptureElongationTransv"),
        "density": data.get("Density"),
        "MaximumAllowableTemperature": data.get("MaximumAllowableTemperature"),
    }


BooleanOperator = Literal["AND", "OR", "NOT"]
ComparisonOperator = Literal[">=", "<=", "=", "==", ">", "<"]
TextField = Literal[
    "Specification",
    "TypeGrade",
    "AlloyDesignationNumber",
    "ClassConditionTemper",
    "NominalComposition",
]
NumericField = Literal[
    "SMYS",
    "SMTS",
    "RuptureElongationLong",
    "MaximumAllowableTemperature",
]

MAX_ALLOWABLE_TEMPERATURE_EXPR = """
(
    SELECT MAX(MaxTemp)
    FROM (
        SELECT MaximumTemperature AS MaxTemp
        FROM AllowableStress1Table
        WHERE MaterialID = Materials.ID
        UNION ALL
        SELECT MaxTemp_VIII1
        FROM AllowableStress1Table
        WHERE MaterialID = Materials.ID
        UNION ALL
        SELECT MaximumTemperature
        FROM AllowableStress2Table
        WHERE MaterialID = Materials.ID
        UNION ALL
        SELECT MaxTemp_VIII1
        FROM AllowableStress3Table
        WHERE MaterialID = Materials.ID
        UNION ALL
        SELECT MaxTemp_VIII2
        FROM AllowableStress3Table
        WHERE MaterialID = Materials.ID
    )
    WHERE MaxTemp IS NOT NULL
)
"""


@dataclass(frozen=True)
class MaterialCriterion:
    """SQL fragment and parameters for one material search condition."""

    sql: str
    params: tuple[object, ...] = ()

    def __and__(self, other: "MaterialCriterion") -> "MaterialCriterion":
        return combine_material_criteria("AND", self, other)

    def __or__(self, other: "MaterialCriterion") -> "MaterialCriterion":
        return combine_material_criteria("OR", self, other)

    def __invert__(self) -> "MaterialCriterion":
        return combine_material_criteria("NOT", self)


def combine_material_criteria(
    operator: BooleanOperator,
    *criteria: MaterialCriterion,
) -> MaterialCriterion:
    """Combine criteria with AND, OR, or NOT."""
    op = operator.upper()
    if op not in {"AND", "OR", "NOT"}:
        raise ValueError(f"Unsupported boolean operator: {operator}")
    if not criteria:
        raise ValueError("At least one criterion is required.")
    if op == "NOT":
        if len(criteria) != 1:
            raise ValueError("NOT accepts exactly one criterion.")
        return MaterialCriterion(
            f"NOT ({criteria[0].sql})",
            criteria[0].params,
        )

    joined_sql = f" {op} ".join(f"({c.sql})" for c in criteria)
    params: list[object] = []
    for criterion in criteria:
        params.extend(criterion.params)
    return MaterialCriterion(joined_sql, tuple(params))


class MaterialSearchResult(Sequence[dict]):
    """List-like search result with a count property."""

    def __init__(self, materials: Iterable[dict]):
        self._materials = list(materials)

    @property
    def count(self) -> int:
        return len(self._materials)

    def first(self) -> dict | None:
        return self._materials[0] if self._materials else None

    def one(self) -> dict:
        if self.count != 1:
            raise ValueError(f"Expected exactly one material, found {self.count}.")
        return self._materials[0]

    def to_list(self) -> list[dict]:
        return list(self._materials)

    def __iter__(self):
        return iter(self._materials)

    def __len__(self) -> int:
        return len(self._materials)

    def __getitem__(self, index):
        return self._materials[index]


class MaterialSearch:
    """
    Search ASME materials by text, identity fields, composition, and properties.

    Text searches support simple boolean operators:
        "SA-516 AND grade:70"
        "composition:carbon AND SMYS>=260 AND SMTS=485"
        "spec:SA-516 AND NOT grade:55"
    """

    _TEXT_FIELDS = {
        "spec": "Specification",
        "specification": "Specification",
        "grade": "TypeGrade",
        "type": "TypeGrade",
        "typegrade": "TypeGrade",
        "uns": "AlloyDesignationNumber",
        "alloy": "AlloyDesignationNumber",
        "class": "ClassConditionTemper",
        "temper": "ClassConditionTemper",
        "condition": "ClassConditionTemper",
        "composition": "NominalComposition",
        "comp": "NominalComposition",
        "chemical": "NominalComposition",
    }
    _NUMERIC_FIELDS = {
        "smys": "SMYS",
        "sy": "SMYS",
        "smus": "SMTS",
        "smts": "SMTS",
        "su": "SMTS",
        "ar": "RuptureElongationLong",
        "elongation": "RuptureElongationLong",
        "mat": "MaximumAllowableTemperature",
        "maxtemp": "MaximumAllowableTemperature",
        "max_temp": "MaximumAllowableTemperature",
        "maxallowabletemp": "MaximumAllowableTemperature",
        "maximumallowabletemperature": "MaximumAllowableTemperature",
        "maximum_allowable_temperature": "MaximumAllowableTemperature",
    }
    _TOKEN_RE = re.compile(
        r'\w+:"[^"]+"|"[^"]+"|\(|\)|\bAND\b|\bOR\b|\bNOT\b|[^\s()]+',
        re.IGNORECASE,
    )
    _NUMERIC_RE = re.compile(
        r"^(?P<field>smys|sy|smus|smts|su|ar|elongation|mat|maxtemp|max_temp|"
        r"maxallowabletemp|maximumallowabletemperature|maximum_allowable_temperature)\s*"
        r"(?P<op>>=|<=|==|=|>|<)\s*"
        r"(?P<value>-?\d+(?:\.\d+)?)"
        r"(?:(?:\+/-|~|:tol=|:tol)\s*(?P<tol>\d+(?:\.\d+)?))?$",
        re.IGNORECASE,
    )

    def __init__(self, db_path: Path | str = DB_PATH):
        self.db_path = Path(db_path)

    @property
    def count(self) -> int:
        return self.search().count

    @staticmethod
    def identification(
        value: str,
        *,
        field: TextField | None = None,
        exact: bool = False,
    ) -> MaterialCriterion:
        fields = [
            "Specification",
            "TypeGrade",
            "AlloyDesignationNumber",
            "ClassConditionTemper",
        ]
        return MaterialSearch._text_criterion(fields if field is None else [field], value, exact)

    @staticmethod
    def composition(value: str, *, exact: bool = False) -> MaterialCriterion:
        return MaterialSearch._text_criterion(["NominalComposition"], value, exact)

    @staticmethod
    def property(
        field: NumericField,
        operator: ComparisonOperator,
        value: float,
        *,
        tolerance: float | None = None,
    ) -> MaterialCriterion:
        return MaterialSearch._numeric_criterion(field, operator, value, tolerance)

    @staticmethod
    def smys(
        operator: ComparisonOperator,
        value: float,
        *,
        tolerance: float | None = None,
    ) -> MaterialCriterion:
        return MaterialSearch.property("SMYS", operator, value, tolerance=tolerance)

    @staticmethod
    def smus(
        operator: ComparisonOperator,
        value: float,
        *,
        tolerance: float | None = None,
    ) -> MaterialCriterion:
        return MaterialSearch.property("SMTS", operator, value, tolerance=tolerance)

    @staticmethod
    def ar(
        operator: ComparisonOperator,
        value: float,
        *,
        tolerance: float | None = None,
    ) -> MaterialCriterion:
        return MaterialSearch.property("RuptureElongationLong", operator, value, tolerance=tolerance)

    @staticmethod
    def maximum_allowable_temperature(
        operator: ComparisonOperator,
        value: float,
        *,
        tolerance: float | None = None,
    ) -> MaterialCriterion:
        return MaterialSearch.property(
            "MaximumAllowableTemperature",
            operator,
            value,
            tolerance=tolerance,
        )

    def search(
        self,
        text: str | None = None,
        *,
        criteria: MaterialCriterion | Sequence[MaterialCriterion] | None = None,
        operator: Literal["AND", "OR"] = "AND",
        limit: int | None = None,
    ) -> MaterialSearchResult:
        """Return matching materials as a MaterialSearchResult."""
        built: list[MaterialCriterion] = []
        if text:
            built.append(self.parse(text))
        if criteria:
            if isinstance(criteria, MaterialCriterion):
                built.append(criteria)
            else:
                built.extend(criteria)

        where = ""
        params: tuple[object, ...] = ()
        if built:
            combined = built[0] if len(built) == 1 else combine_material_criteria(operator, *built)
            where = f"WHERE {combined.sql}"
            params = combined.params

        limit_sql = "" if limit is None else " LIMIT ?"
        if limit is not None and limit < 0:
            raise ValueError("limit must be greater than or equal to zero.")

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
        cur = conn.cursor()
        query_params = params + (() if limit is None else (limit,))
        cur.execute(
            f"""
            SELECT ID, Specification, TypeGrade, ClassConditionTemper,
                   AlloyDesignationNumber, NominalComposition, ProductForm,
                   SMTS, SMYS, RuptureElongationLong, RuptureElongationTransv,
                   Density,
                   {MAX_ALLOWABLE_TEMPERATURE_EXPR} AS MaximumAllowableTemperature
            FROM Materials
            {where}
            ORDER BY Specification, TypeGrade, ClassConditionTemper, ID
            {limit_sql}
            """,
            query_params,
        )
        rows = cur.fetchall()
        conn.close()
        return MaterialSearchResult(_material_row_to_dict(row) for row in rows)

    def one(
        self,
        text: str | None = None,
        *,
        criteria: MaterialCriterion | Sequence[MaterialCriterion] | None = None,
    ) -> dict:
        return self.search(text, criteria=criteria).one()

    def parse(self, text: str) -> MaterialCriterion:
        text = self._normalize_numeric_expressions(text)
        tokens = [self._clean_token(t) for t in self._TOKEN_RE.findall(text)]
        tokens = [t for t in tokens if t]
        if not tokens:
            raise ValueError("Search text is empty.")

        output: list[MaterialCriterion | str] = []
        ops: list[str] = []
        previous_was_criterion = False
        precedence = {"OR": 1, "AND": 2, "NOT": 3}

        def push_operator(op: str) -> None:
            while (
                ops
                and ops[-1] != "("
                and precedence[ops[-1]] >= precedence[op]
                and op != "NOT"
            ):
                output.append(ops.pop())
            ops.append(op)

        for token in tokens:
            upper = token.upper()
            if upper in {"AND", "OR", "NOT"}:
                push_operator(upper)
                previous_was_criterion = False
            elif token == "(":
                if previous_was_criterion:
                    push_operator("AND")
                ops.append(token)
                previous_was_criterion = False
            elif token == ")":
                while ops and ops[-1] != "(":
                    output.append(ops.pop())
                if not ops:
                    raise ValueError("Unbalanced closing parenthesis in search text.")
                ops.pop()
                previous_was_criterion = True
            else:
                if previous_was_criterion:
                    push_operator("AND")
                output.append(self._criterion_from_token(token))
                previous_was_criterion = True

        while ops:
            op = ops.pop()
            if op == "(":
                raise ValueError("Unbalanced opening parenthesis in search text.")
            output.append(op)

        stack: list[MaterialCriterion] = []
        for item in output:
            if isinstance(item, MaterialCriterion):
                stack.append(item)
            elif item == "NOT":
                if not stack:
                    raise ValueError("NOT requires a following criterion.")
                stack.append(combine_material_criteria("NOT", stack.pop()))
            else:
                if len(stack) < 2:
                    raise ValueError(f"{item} requires two criteria.")
                right = stack.pop()
                left = stack.pop()
                stack.append(combine_material_criteria(item, left, right))
        if len(stack) != 1:
            raise ValueError("Could not parse search text.")
        return stack[0]

    @classmethod
    def _criterion_from_token(cls, token: str) -> MaterialCriterion:
        numeric_match = cls._NUMERIC_RE.match(token)
        if numeric_match:
            field = cls._NUMERIC_FIELDS[numeric_match.group("field").lower()]
            tol = numeric_match.group("tol")
            return cls._numeric_criterion(
                field,
                numeric_match.group("op"),
                float(numeric_match.group("value")),
                float(tol) if tol is not None else None,
            )

        if ":" in token:
            raw_field, value = token.split(":", 1)
            field = cls._TEXT_FIELDS.get(raw_field.lower())
            if field is None:
                raise ValueError(f"Unsupported search field: {raw_field}")
            return cls._text_criterion([field], cls._clean_token(value))

        return cls.identification(token) | cls.composition(token)

    @staticmethod
    def _clean_token(token: str) -> str:
        token = token.strip()
        if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
            return token[1:-1]
        return token

    @staticmethod
    def _normalize_numeric_expressions(text: str) -> str:
        def compact(match: re.Match) -> str:
            field, operator, value, tolerance_marker, tolerance = match.groups()
            expr = f"{field}{operator}{value}"
            if tolerance_marker and tolerance:
                expr += f"{tolerance_marker}{tolerance}"
            return expr

        return re.sub(
            r"\b(smys|sy|smus|smts|su|ar|elongation|mat|maxtemp|max_temp|"
            r"maxallowabletemp|maximumallowabletemperature|maximum_allowable_temperature)\s*"
            r"(>=|<=|==|=|>|<)\s*"
            r"(-?\d+(?:\.\d+)?)"
            r"(?:\s*(\+/-|~|:tol=|:tol)\s*(\d+(?:\.\d+)?))?",
            compact,
            text,
            flags=re.IGNORECASE,
        )

    @staticmethod
    def _text_criterion(
        fields: Sequence[str],
        value: str,
        exact: bool = False,
    ) -> MaterialCriterion:
        if not value:
            raise ValueError("Text criterion value cannot be empty.")
        comparator = "=" if exact else "LIKE"
        needle = value if exact else f"%{value}%"
        sql = " OR ".join(f"COALESCE({field}, '') {comparator} ? COLLATE NOCASE" for field in fields)
        return MaterialCriterion(sql, tuple(needle for _ in fields))

    @staticmethod
    def _numeric_criterion(
        field: str,
        operator: str,
        value: float,
        tolerance: float | None = None,
    ) -> MaterialCriterion:
        if operator not in {">=", "<=", "=", "==", ">", "<"}:
            raise ValueError(f"Unsupported comparison operator: {operator}")
        if tolerance is not None and tolerance < 0:
            raise ValueError("tolerance must be greater than or equal to zero.")
        if field == "MaximumAllowableTemperature":
            return MaterialSearch._derived_numeric_criterion(
                MAX_ALLOWABLE_TEMPERATURE_EXPR,
                operator,
                value,
                tolerance,
            )
        if tolerance is not None:
            low = float(value) - tolerance
            high = float(value) + tolerance
            return MaterialCriterion(f"{field} IS NOT NULL AND {field} BETWEEN ? AND ?", (low, high))
        op = "=" if operator == "==" else operator
        return MaterialCriterion(f"{field} IS NOT NULL AND {field} {op} ?", (float(value),))

    @staticmethod
    def _derived_numeric_criterion(
        expression: str,
        operator: str,
        value: float,
        tolerance: float | None = None,
    ) -> MaterialCriterion:
        if tolerance is not None:
            low = float(value) - tolerance
            high = float(value) + tolerance
            return MaterialCriterion(
                f"{expression} IS NOT NULL AND {expression} BETWEEN ? AND ?",
                (low, high),
            )
        op = "=" if operator == "==" else operator
        return MaterialCriterion(
            f"{expression} IS NOT NULL AND {expression} {op} ?",
            (float(value),),
        )


def _first_row(table: str, material_id: int,
               thk_mm: float | None = None) -> tuple[list[str], tuple] | None:
    """
    Return (col_names, row) for the first matching row in a temperature table.
    If thk_mm is provided, filter by the SizeThk range columns.
    """
    conn = _conn()
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    col_names = [c[1] for c in cur.fetchall()]

    has_size = "SizeThkMIN" in col_names

    if has_size and thk_mm is not None:
        cur.execute(f"""
            SELECT * FROM {table}
            WHERE MaterialID = ?
              AND (SizeThkMIN IS NULL
                   OR (SizeThkMIN_Included = 1 AND SizeThkMIN <= ?)
                   OR (SizeThkMIN_Included = 0 AND SizeThkMIN <  ?))
              AND (SizeThkMAX IS NULL
                   OR (SizeThkMAX_Included = 1 AND SizeThkMAX >= ?)
                   OR (SizeThkMAX_Included = 0 AND SizeThkMAX >  ?))
            ORDER BY ID LIMIT 1
        """, (material_id, thk_mm, thk_mm, thk_mm, thk_mm))
    else:
        cur.execute(
            f"SELECT * FROM {table} WHERE MaterialID = ? ORDER BY ID LIMIT 1",
            (material_id,),
        )
    row = cur.fetchone()
    conn.close()
    return (col_names, row) if row else None


# ── Public API ─────────────────────────────────────────────────────────────────

def get_all_materials() -> list[dict]:
    """Return all materials as a list of dicts, sorted by spec / grade / class."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT ID, Specification, TypeGrade, ClassConditionTemper,
               AlloyDesignationNumber, NominalComposition, ProductForm,
               SMTS, SMYS, RuptureElongationLong,
               {max_temp_expr} AS MaximumAllowableTemperature
        FROM Materials
        ORDER BY Specification, TypeGrade, ClassConditionTemper
    """.format(max_temp_expr=MAX_ALLOWABLE_TEMPERATURE_EXPR))
    rows = cur.fetchall()
    conn.close()

    result = []
    for row in rows:
        (mid, spec, grade, cls, alloy, comp, pform, smts, smys, ar, max_allow_temp) = row
        # When TypeGrade is absent, use UNS/AlloyDesignation as the identifier
        id_part = grade if grade else alloy
        parts = [str(p) for p in [spec, id_part, cls] if p]
        name = " ".join(parts)
        result.append({
            "id":    mid,
            "name":  name,
            "spec":  spec  or "",
            "grade": grade or "",
            "cls":   cls   or "",
            "alloy": alloy or "",
            "comp":  comp  or "",
            "pform": pform or "",
            "SMTS":  smts,
            "SMYS":  smys,
            "Ar":    ar,
            "MaximumAllowableTemperature": max_allow_temp,
        })
    return result


def get_material(material_id: int) -> dict | None:
    """Return static properties for a single material."""
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT ID, Specification, TypeGrade, ClassConditionTemper,
               AlloyDesignationNumber, NominalComposition, ProductForm,
               SMTS, SMYS, RuptureElongationLong, RuptureElongationTransv, Density,
               {max_temp_expr} AS MaximumAllowableTemperature
        FROM Materials WHERE ID = ?
    """.format(max_temp_expr=MAX_ALLOWABLE_TEMPERATURE_EXPR), (material_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    (mid, spec, grade, cls, alloy, comp, pform,
     smts, smys, ar_l, ar_t, density, max_allow_temp) = row
    parts = [str(p) for p in [spec, grade, cls] if p]
    return {
        "id":      mid,
        "name":    " ".join(parts),
        "spec":    spec  or "",
        "grade":   grade or "",
        "cls":     cls   or "",
        "alloy":   alloy or "",
        "comp":    comp  or "",
        "pform":   pform or "",
        "SMTS":    smts,
        "SMYS":    smys,
        "Ar":      ar_l,
        "Ar_t":    ar_t,
        "density": density,
        "MaximumAllowableTemperature": max_allow_temp,
    }


def get_yield_at_T(material_id: int, T_C: float,
                   thk_mm: float | None = None) -> float | None:
    """Rp0.2 at T_C [°C] interpolated from YieldStrengthTable [MPa]."""
    res = _first_row("YieldStrengthTable", material_id, thk_mm)
    if not res:
        return None
    col_names, row = res
    return _interp(_extract_temps(row, col_names), T_C * 9 / 5 + 32)


def get_ultimate_at_T(material_id: int, T_C: float,
                      thk_mm: float | None = None) -> float | None:
    """Rm at T_C [°C] interpolated from UltimateStrengthTable [MPa]."""
    res = _first_row("UltimateStrengthTable", material_id, thk_mm)
    if not res:
        return None
    col_names, row = res
    return _interp(_extract_temps(row, col_names), T_C * 9 / 5 + 32)


def get_S_div1(material_id: int, T_C: float,
               thk_mm: float | None = None) -> float | None:
    """ASME VIII-1 allowable stress (Table 1A) at T_C [°C] [MPa]."""
    T_F = T_C * 9 / 5 + 32
    res = _first_row("AllowableStress1Table", material_id, thk_mm)
    if not res:
        return None
    col_names, row = res

    # Respect MaxTemp_VIII1 field when present
    mt_idx = _col_idx(col_names, "MaxTemp_VIII1")
    if mt_idx >= 0 and row[mt_idx] is not None:
        max_T_F = float(row[mt_idx])
        if T_F > max_T_F:
            return None  # beyond rated max temperature for VIII-1

    return _interp(_extract_temps(row, col_names), T_F)


def get_S_div2(material_id: int, T_C: float,
               thk_mm: float | None = None) -> float | None:
    """ASME VIII-2 allowable stress (Table 5A) at T_C [°C] [MPa]."""
    T_F = T_C * 9 / 5 + 32
    res = _first_row("AllowableStress2Table", material_id, thk_mm)
    if not res:
        return None
    col_names, row = res

    mt_idx = _col_idx(col_names, "MaximumTemperature")
    if mt_idx >= 0 and row[mt_idx] is not None:
        max_T_F = float(row[mt_idx])
        if T_F > max_T_F:
            return None

    return _interp(_extract_temps(row, col_names), T_F)


# ── European allowable stress helpers ─────────────────────────────────────────

def allowable_EN13445(Rp02_T: float, Rm_20: float, Ar: float | None) -> dict:
    """
    EN 13445-2 §6.4.3 nominal design stress f [MPa].

    General case (ferritic/alloy steels):
        f = min(Rp0.2_T / 1.5,  Rm_20 / 2.4)

    Austenitic steels (Ar ≥ 30%):
        f = min(Rp0.2_T / 1.5,  Rm_20 / 3.0)
        (the Rp1.0_T / 1.2 criterion is omitted — not in DB)
    """
    austenitic = (Ar is not None) and (Ar >= 30.0)
    sf_u = 3.0 if austenitic else 2.4
    cand_y = Rp02_T / 1.5
    cand_u = Rm_20 / sf_u
    f = min(cand_y, cand_u)
    return {
        "f": f,
        "cand_yield": cand_y,
        "cand_uts":   cand_u,
        "sf_yield":   1.5,
        "sf_uts":     sf_u,
        "governing":  "Rp0.2_T / 1.5" if cand_y <= cand_u else f"Rm_20 / {sf_u}",
        "austenitic": austenitic,
    }


def allowable_AD2000(Rp02_T: float, Rm_20: float) -> dict:
    """
    AD 2000-B0 §7.2 zulässige Spannung σ_zul [MPa].
    Groups M1–M5 (carbon / low-alloy / alloy steels):
        σ_zul = min(Rp0.2_T / 1.5,  Rm_20 / 2.4)
    """
    cand_y = Rp02_T / 1.5
    cand_u = Rm_20  / 2.4
    f = min(cand_y, cand_u)
    return {
        "f": f,
        "cand_yield": cand_y,
        "cand_uts":   cand_u,
        "sf_yield":   1.5,
        "sf_uts":     2.4,
        "governing":  "Rp0.2_T / 1.5" if cand_y <= cand_u else "Rm_20 / 2.4",
    }


def allowable_BS5500(Rp02_T: float, Rm_20: float) -> dict:
    """
    BS PD 5500 Table 4.3-1 nominal design strength f [MPa].
    Category 1, carbon / alloy steels:
        f = min(Rp0.2_T / 1.5,  Rm_20 / 2.5)
    """
    cand_y = Rp02_T / 1.5
    cand_u = Rm_20  / 2.5
    f = min(cand_y, cand_u)
    return {
        "f": f,
        "cand_yield": cand_y,
        "cand_uts":   cand_u,
        "sf_yield":   1.5,
        "sf_uts":     2.5,
        "governing":  "Rp0.2_T / 1.5" if cand_y <= cand_u else "Rm_20 / 2.5",
    }


def allowable_CODAP(Rp02_T: float, Rm_20: float, Ar: float | None) -> dict:
    """
    CODAP 2023 §C2.3.1 contrainte nominale de calcul f [MPa].
    Groups M1–M5:  f = min(Rp0.2_T / 1.5,  Rm_20 / 2.4)
    Group M6 (austenitic SS, Ar ≥ 35%):
              f = min(Rp0.2_T / 1.5,  Rm_20 / 3.0)
    """
    austenitic = (Ar is not None) and (Ar >= 35.0)
    sf_u = 3.0 if austenitic else 2.4
    cand_y = Rp02_T / 1.5
    cand_u = Rm_20 / sf_u
    f = min(cand_y, cand_u)
    return {
        "f": f,
        "cand_yield": cand_y,
        "cand_uts":   cand_u,
        "sf_yield":   1.5,
        "sf_uts":     sf_u,
        "governing":  "Rp0.2_T / 1.5" if cand_y <= cand_u else f"Rm_20 / {sf_u}",
        "austenitic": austenitic,
    }
