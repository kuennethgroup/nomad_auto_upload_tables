"""
Heuristics for guessing a column-level schema from a pandas DataFrame.

This module is intentionally free of any ``nomad`` import so it can be used
and unit-tested on its own (e.g. from a plain script handed a DataFrame),
and reused unchanged by the NOMAD parser/normalizer that wrap it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd
import pandas.api.types as ptypes

UNIT_PATTERN = re.compile(r'[\(\[]([^()\[\]]+)[\)\]]\s*$')

# Keyword -> ontology category used to guess the semantic meaning of a column
# from its header text. Order matters: first match wins, so more specific
# keywords should come before more generic ones.
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    'sample_id': ['sample id', 'sample_id', 'specimen', 'sample name', 'sample'],
    'composition': ['composition', 'formula', 'stoichiometry', 'at%', 'wt%'],
    'concentration': ['concentration', 'molarity', 'conc.', 'conc'],
    'temperature': ['temperature', 'temp.', 'temp'],
    'pressure': ['pressure'],
    'time': ['duration', 'timestamp', 'date', 'time'],
    'mass': ['mass', 'weight'],
    'length': ['thickness', 'diameter', 'length', 'width', 'height'],
    'voltage': ['voltage', 'potential'],
    'current': ['current'],
    'frequency': ['frequency', 'freq'],
    'energy': ['enthalpy', 'energy'],
    'process_parameter': ['rate', 'speed', 'power', 'flow'],
    'measurement_result': ['result', 'measurement', 'intensity', 'signal', 'value'],
}

CATEGORIES = [*CATEGORY_KEYWORDS.keys(), 'other']

QUANTITY_TYPES = ['string', 'integer', 'float', 'boolean', 'datetime']

KNOWN_KEYWORD_CONFIDENCE = 0.8
DEFAULT_CONFIDENCE = 0.2
MAX_SAMPLE_VALUES = 5


@dataclass
class ColumnGuess:
    header: str
    guessed_name: str
    guessed_type: str
    guessed_unit: str
    category: str
    confidence: float
    n_rows: int
    n_missing: int
    sample_values: str


def read_table(path: str, sheet_name: int | str = 0) -> tuple[pd.DataFrame, str | None]:
    """Read an Excel or CSV file at ``path`` into a DataFrame.

    Returns the DataFrame and the sheet name that was used (``None`` for CSV).
    """
    lower = str(path).lower()
    if lower.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(path, sheet_name=sheet_name)
        used_sheet = sheet_name if isinstance(sheet_name, str) else _first_sheet_name(path)
        return df, used_sheet
    return pd.read_csv(path), None


def _first_sheet_name(path: str) -> str:
    with pd.ExcelFile(path) as xls:
        return xls.sheet_names[0]


def guess_unit(header: str) -> str | None:
    """Pull a pint-parseable unit out of a header like ``'Temperature (K)'``."""
    match = UNIT_PATTERN.search(header)
    if not match:
        return None
    candidate = match.group(1).strip()
    try:
        from pint import UnitRegistry

        UnitRegistry()(candidate)
    except Exception:
        return None
    return candidate


def guess_category(header: str) -> tuple[str, float]:
    lower = header.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in lower for keyword in keywords):
            return category, KNOWN_KEYWORD_CONFIDENCE
    return 'other', DEFAULT_CONFIDENCE


def guess_type(series: pd.Series) -> str:
    if ptypes.is_bool_dtype(series):
        return 'boolean'
    if ptypes.is_integer_dtype(series):
        return 'integer'
    if ptypes.is_float_dtype(series):
        return 'float'
    if ptypes.is_datetime64_any_dtype(series):
        return 'datetime'
    non_null = series.dropna()
    if not non_null.empty and pd.to_datetime(non_null, errors='coerce', format='mixed').notna().all():
        return 'datetime'
    return 'string'


def clean_name(header: str) -> str:
    """Turn a free-text header into a snake_case identifier, unit suffix stripped."""
    without_unit = UNIT_PATTERN.sub('', header).strip()
    name = re.sub(r'[^0-9a-zA-Z]+', '_', without_unit).strip('_').lower()
    return name or 'column'


def guess_columns(
    df: pd.DataFrame, ai_guesses: dict[str, dict] | None = None
) -> list[ColumnGuess]:
    """Build a `ColumnGuess` per column of `df`.

    For columns present in `ai_guesses` (see `ai_guessing.guess_with_ai`), the
    AI-proposed name/type/unit/category/confidence are used instead of the
    local heuristics below.
    """
    columns = []
    for header in df.columns:
        header_str = str(header)
        series = df[header]
        ai_guess = (ai_guesses or {}).get(header_str)
        if ai_guess:
            guessed_name = ai_guess['guessed_name'] or clean_name(header_str)
            guessed_type = ai_guess['guessed_type']
            guessed_unit = ai_guess['guessed_unit']
            category = ai_guess['category']
            confidence = ai_guess['confidence']
        else:
            category, confidence = guess_category(header_str)
            guessed_name = clean_name(header_str)
            guessed_type = guess_type(series)
            guessed_unit = guess_unit(header_str) or ''
        sample = ', '.join(str(v) for v in series.dropna().unique()[:MAX_SAMPLE_VALUES])
        columns.append(
            ColumnGuess(
                header=header_str,
                guessed_name=guessed_name,
                guessed_type=guessed_type,
                guessed_unit=guessed_unit,
                category=category,
                confidence=confidence,
                n_rows=int(series.notna().sum()),
                n_missing=int(series.isna().sum()),
                sample_values=sample,
            )
        )
    return columns


def coerce_value(raw_value, guessed_type: str):
    if pd.isna(raw_value):
        return None
    try:
        if guessed_type == 'integer':
            return int(raw_value)
        if guessed_type == 'float':
            return float(raw_value)
        if guessed_type == 'boolean':
            return bool(raw_value)
        if guessed_type == 'datetime':
            return pd.Timestamp(raw_value).isoformat()
    except (TypeError, ValueError):
        pass
    return str(raw_value)
